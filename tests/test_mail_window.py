"""The mail window reads real letters under the operator's permission, so what it must not do is pinned.

Three things stand between a caller and a letter, and each has its own way to fail quietly:

  the reader   fetches from the bucket mirror. It must fetch what the window asked for and no more —
               an envelope at a time, a body only when the whole letter is asked for — and must not
               call an unfinished quad a letter.
  the approval one passcode, tokens that survive a sleeping instance, and a refresh token that may
               come back twice. A wrong passcode is refused where a person can read why.
  the record   every read that fetched an envelope is written to the bucket before anything is
               returned. No record, no letter.

These tests need organum 0.9.0 (`hub_front`); the environment the drop's own tests run in has
0.8.0, where they are skipped.
"""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest

hf = pytest.importorskip("organum.hub_front")

from starlette.testclient import TestClient  # noqa: E402

from mail_window import app as window  # noqa: E402
from mail_window.mirror import GcsStore, MemoryStore, MirrorReader  # noqa: E402

PASS = "correct horse battery staple, twice"
REDIRECT = "https://chatgpt.com/connector/oauth/abc123"
VERIFIER = "v" * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
BASE = "https://window.example"
HQ, DOOR, OTHER_DOOR = "lab:jdot-hq", "hub-ops/from-organum", "hub-ops/from-ray"


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


async def _no_sleep(_seconds):
    return None


def _envelope(to: str, body: bytes, sender: str = "lab:organum") -> bytes:
    return json.dumps({"envelope_schema": "organum-hub/envelope/v0.2", "event_kind": "message.posted",
                       "signer": {"id": sender, "key_id": "k1", "key_epoch": 1},
                       "created_at": "2026-10-09T00:00:00Z",
                       "payload": {"target": {"lab_id": to, "to_id": "X", "to_epoch": 1},
                                   "body_sha256": hashlib.sha256(body).hexdigest(),
                                   "body_media_type": "text/markdown"}}).encode("utf-8")


def _store() -> MemoryStore:
    """Two doors. Behind the first: 001 for HQ, 002 for someone else, 003 for HQ, and 004 still
    arriving (signature and body are up, the envelope is not)."""
    s = MemoryStore()
    for n, to, text in (("001", HQ, "first"), ("002", "lab:lxm", "not yours"), ("003", HQ, "third — 한글")):
        body = text.encode("utf-8")
        s.put_letter("drop-root", DOOR, n, _envelope(to, body), "ab" * 64, body)
    s.objects[f"drop-root/{DOOR}/004-sig.txt"] = b"cd" * 64 + b"\n"
    s.objects[f"drop-root/{DOOR}/004-body.md"] = b"half a letter"
    body = b"from ray"
    s.put_letter("drop-root", OTHER_DOOR, "001", _envelope(HQ, body, "lab:ray"), "ef" * 64, body, "body.txt")
    s.objects["drop-root/letters/from-organum/001-envelope.json"] = _envelope(HQ, b"x")     # another channel
    s.objects["drop-state/jdot-hq/00000001.state"] = b"not mail"
    return s


def _client(store: MemoryStore | None = None, clock: Clock | None = None, **env) -> TestClient:
    env = {"MAIL_PASSCODE": PASS, "MAIL_PUBLIC_URL": BASE, "MAIL_RECIPIENT": HQ,
           "MAIL_DOORS": f"{DOOR},{OTHER_DOOR}"} | env
    return TestClient(window.create_app(env, clock=clock or Clock(), sleep=_no_sleep,
                                        store=_store() if store is None else store), follow_redirects=False)


def _page(c: TestClient, client_id: str = "mw-x", **more):
    q = {"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "state": "s1",
         "code_challenge": CHALLENGE, "code_challenge_method": "S256", "resource": f"{BASE}/mail"} | more
    return c.get("/authorize", params=q)


def _req(page) -> str:
    return page.text.split('name="req" value="')[1].split('"')[0]


def _grant(c: TestClient, client_id: str = "mw-x", base: str = BASE) -> dict:
    """Walk the whole flow the platform walks: page, passcode, code, tokens."""
    page = _page(c, client_id, resource=f"{base}/mail")
    assert page.status_code == 200, page.text
    back = c.post("/authorize", data={"req": _req(page), "passcode": PASS})
    assert back.status_code == 302 and back.headers["location"].startswith(REDIRECT + "?"), back.text
    got = {k: v[0] for k, v in parse_qs(urlsplit(back.headers["location"]).query).items()}
    assert got.get("state") == "s1"
    tok = c.post("/token", data={"grant_type": "authorization_code", "code": got["code"], "client_id": client_id,
                                 "redirect_uri": REDIRECT, "code_verifier": VERIFIER, "resource": f"{base}/mail"})
    assert tok.status_code == 200, tok.text
    return tok.json()


def _call(c: TestClient, access: str, tool: str, args: dict | None = None):
    """A tool call the way ChatGPT made it in the pre-test: the newer revision, with its headers."""
    meta = {hf.META_VERSION: "2026-07-28", hf.META_CLIENT_CAPABILITIES: {}}
    return c.post("/mail", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                 "params": {"name": tool, "arguments": args or {}, "_meta": meta}},
                  headers={"Authorization": f"Bearer {access}", "MCP-Protocol-Version": "2026-07-28",
                           "Mcp-Method": "tools/call", "Mcp-Name": tool})


def _said(reply) -> dict:
    assert reply.status_code == 200, reply.text
    return json.loads(reply.json()["result"]["content"][0]["text"])


def _lines(capsys, event: str) -> list[dict]:
    return [d for d in (json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{"))
            if d.get("window") == event]


def _records(store: MemoryStore, kind: str) -> list[dict]:
    return [json.loads(v) for k, v in sorted(store.objects.items())
            if k.startswith("mail-audit/") and k.endswith(f"-{kind}.json")]


# ── the reader: what the mirror holds, and no more than was asked ────────────

def test_a_number_is_a_letter_only_once_its_envelope_is_there():
    r = MirrorReader(_store())
    index = r.index(DOOR)
    assert [e["n"] for e in index["index"]] == ["001", "002", "003"] and index["more"] is False   # 004 has no envelope
    assert index["index"][2] == {"n": "003", "envelope_sha256": None, "body_name": "body.md",
                                 "body_sha256": None, "body_size": len("third — 한글".encode("utf-8"))}
    assert [e["n"] for e in r.index(DOOR, "002")["index"]] == ["003"]
    assert r.index("hub-ops/from-nobody")["index"] == []


def test_numbers_are_compared_as_numbers_when_a_door_grows_a_digit():
    s = MemoryStore()
    for n in ("998", "999", "1000", "1001"):
        s.put_letter("drop-root", DOOR, n, _envelope(HQ, b"b"), "ab" * 64, b"b")
    r = MirrorReader(s)
    assert [e["n"] for e in r.index(DOOR, "998")["index"]] == ["999", "1000", "1001"]
    assert [e["n"] for e in r.index(DOOR, "999")["index"]] == ["1000", "1001"]


def test_listing_a_door_reads_no_object_and_an_envelope_read_reads_one():
    s = _store()
    r = MirrorReader(s)
    r.index(DOOR)
    assert s.reads == [] and s.lists == [f"drop-root/{DOOR}/"]
    r.envelope(DOOR, "002")
    assert s.reads == [f"drop-root/{DOOR}/002-envelope.json"]         # not its body, not its signature


def test_a_whole_letter_is_the_stored_bytes_and_the_signature_without_its_newline():
    s = _store()
    got = MirrorReader(s).letter(OTHER_DOOR, "001")
    assert got == {"envelope": s.objects[f"drop-root/{OTHER_DOOR}/001-envelope.json"], "sig": "ef" * 64,
                   "body": b"from ray", "body_name": "body.txt"}


def test_a_letter_that_is_not_there_is_a_lookup_error_and_a_half_quad_is_not_there():
    r = MirrorReader(_store())
    for n in ("009", "004", "4", "../001"):
        with pytest.raises(LookupError):
            r.letter(DOOR, n)
        with pytest.raises(LookupError):
            r.envelope(DOOR, n)


def test_a_name_that_is_not_a_door_never_reaches_the_store():
    s = _store()
    r = MirrorReader(s)
    for door in ("hub-ops", "hub-ops/from-organum/../from-ray", "../drop-state/from-x", "hub-ops/organum", ""):
        with pytest.raises(hf.ReaderError):
            r.index(door)
    assert s.lists == [] and s.reads == []
    with pytest.raises(ValueError):
        MirrorReader(s, "/drop-root/")


def test_the_reader_passes_on_only_what_is_left_of_the_callers_time():
    seen = []

    class Slow(MemoryStore):
        def names(self, prefix, *, timeout=None):
            seen.append(timeout)
            return super().names(prefix, timeout=timeout)

    s = Slow(_store().objects)
    MirrorReader(s, timeout=10).index(DOOR, timeout=3)
    MirrorReader(s, timeout=10).index(DOOR, timeout=300)
    MirrorReader(s, timeout=10).index(DOOR, timeout=-5)
    assert seen[0] <= 3 and seen[1] == 10 and seen[2] == 0.5


# ── the bucket: errors become the window's three words ───────────────────────

class _Blob:
    def __init__(self, bucket, name):
        self.bucket, self.name = bucket, name
        self.size = len(bucket.objects.get(name, b""))

    def download_as_bytes(self, timeout=None, retry=None):
        self.bucket.calls.append(("get", self.name, timeout))
        if self.bucket.fail:
            raise self.bucket.fail
        if self.name not in self.bucket.objects:
            from google.api_core.exceptions import NotFound
            raise NotFound("gs://secret-bucket/" + self.name)
        return self.bucket.objects[self.name]

    def upload_from_string(self, data, content_type=None, if_generation_match=None, timeout=None, retry=None):
        from google.api_core.exceptions import PreconditionFailed
        self.bucket.calls.append(("put", self.name, if_generation_match))
        if self.bucket.fail:
            raise self.bucket.fail
        if self.name in self.bucket.objects:
            raise PreconditionFailed("exists")
        self.bucket.objects[self.name] = data


class _Bucket:
    def __init__(self, objects):
        self.objects, self.calls, self.fail = dict(objects), [], None

    def blob(self, name):
        return _Blob(self, name)


class _GcsClient:
    """What `GcsStore` uses of google-cloud-storage, and nothing else: a bucket handle that asks
    nothing, a listing, a download, a conditional upload."""

    def __init__(self, objects):
        self.b = _Bucket(objects)

    def bucket(self, name):
        return self.b

    def list_blobs(self, bucket, prefix=None, fields=None, timeout=None, retry=None):
        bucket.calls.append(("list", prefix, fields))
        if bucket.fail:
            raise bucket.fail
        return [_Blob(bucket, k) for k in sorted(bucket.objects) if k.startswith(prefix)]


def test_the_bucket_store_lists_names_and_sizes_and_reads_bytes():
    pytest.importorskip("google.cloud.storage")
    client = _GcsClient(_store().objects)
    r = MirrorReader(GcsStore("lxm-drop", client=client))
    assert [e["n"] for e in r.index(DOOR)["index"]] == ["001", "002", "003"]
    assert r.letter(OTHER_DOOR, "001")["body"] == b"from ray"
    assert client.b.calls[0] == ("list", f"drop-root/{DOOR}/", "items(name,size),nextPageToken")


def test_bucket_errors_are_not_there_not_now_or_not_ever_and_never_the_buckets_own_words():
    pytest.importorskip("google.cloud.storage")
    from google.api_core import exceptions as gexc
    client = _GcsClient(_store().objects)
    store = GcsStore("lxm-drop", client=client)
    with pytest.raises(LookupError) as e:
        store.read("drop-root/hub-ops/from-organum/777-envelope.json")
    assert "secret-bucket" not in str(e.value)
    for fail, kind in ((gexc.ServiceUnavailable("x"), hf.NotReady), (gexc.TooManyRequests("x"), hf.NotReady),
                       (gexc.GatewayTimeout("x"), hf.NotReady), (ConnectionError("x"), None),
                       (gexc.Forbidden("sa@project lacks storage.objects.get"), hf.ReaderError)):
        client.b.fail = fail
        if kind is None:                                # not a bucket answer at all: it is not swallowed
            with pytest.raises(ConnectionError):
                store.names("drop-root/")
            continue
        with pytest.raises(kind) as e:
            store.names("drop-root/")
        assert "sa@project" not in str(e.value)


def test_the_bucket_store_creates_and_never_replaces():
    pytest.importorskip("google.cloud.storage")
    client = _GcsClient({})
    store = GcsStore("lxm-drop", client=client)
    store.write_new("mail-audit/a.json", b"{}")
    assert client.b.calls[-1] == ("put", "mail-audit/a.json", 0)
    with pytest.raises(hf.ReaderError):
        store.write_new("mail-audit/a.json", b"{}")


# ── it starts only when it can do its whole job ──────────────────────────────

@pytest.mark.parametrize("env", [
    {"MAIL_PASSCODE": ""}, {"MAIL_PASSCODE": "only twenty-three chars"},
    {"MAIL_RECIPIENT": "jdot-hq"}, {"MAIL_DOORS": ""}, {"MAIL_DOORS": "hub-ops/*"},
    {"MAIL_REDIRECT_PREFIXES": "https://chatgpt.com"},
])
def test_it_refuses_to_start_half_configured(env):
    with pytest.raises(SystemExit):
        _client(**env)


def test_it_refuses_to_start_without_a_way_to_the_letters():
    with pytest.raises(SystemExit):
        window.create_app({"MAIL_PASSCODE": PASS, "MAIL_RECIPIENT": HQ, "MAIL_DOORS": DOOR})


# ── what the platform reads before it connects ───────────────────────────────

def test_discovery_names_the_resource_its_authorization_server_and_s256():
    c = _client()
    res = c.get("/.well-known/oauth-protected-resource/mail").json()
    assert res["resource"] == f"{BASE}/mail" and res["authorization_servers"] == [BASE]
    assert c.get("/.well-known/oauth-protected-resource").json() == res
    meta = c.get("/.well-known/oauth-authorization-server").json()
    assert meta["issuer"] == BASE and meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["token_endpoint_auth_methods_supported"] == ["none"]


def test_a_call_without_a_token_is_pointed_at_the_metadata_and_get_is_no_stream():
    c = _client()
    r = c.post("/mail", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == (
        f'Bearer resource_metadata="{BASE}/.well-known/oauth-protected-resource/mail"')
    access = _grant(c)["access_token"]
    got = c.get("/mail", headers={"Authorization": f"Bearer {access}"})
    assert got.status_code == 405 and "mcp-session-id" not in got.headers


def test_the_status_page_says_which_window_code_runs_and_nothing_about_the_mailbox():
    told = _client().get("/").json()
    assert told["service"] == "lxm-mail-window" and told["organum"] == "0.9.0" and len(told["front_sha256"]) == 16
    assert not any(word in json.dumps(told) for word in ("jdot", "hub-ops", "lxm-drop"))


# ── the approval ─────────────────────────────────────────────────────────────

def test_registration_takes_only_the_platforms_callbacks():
    c = _client()
    ok = c.post("/register", json={"redirect_uris": [REDIRECT], "client_name": "ChatGPT"})
    assert ok.status_code == 201 and ok.json()["client_id"].startswith("mw-")
    for uris in ([], ["https://evil.example/cb"], [REDIRECT, "https://evil.example/cb"], "nope"):
        assert c.post("/register", json={"redirect_uris": uris}).status_code == 400


def test_the_page_is_refused_for_an_unknown_callback_or_another_resource():
    c = _client()
    assert _page(c, redirect_uri="https://evil.example/cb").status_code == 400
    assert _page(c, code_challenge_method="plain").status_code == 400
    assert _page(c, resource=f"{BASE}/other").status_code == 400
    assert _page(c, resource=f"{BASE}/mail/").status_code == 200
    page = _page(c)
    assert HQ in page.text and "frame-ancestors 'none'" in page.headers["content-security-policy"]


def test_a_wrong_passcode_is_refused_on_the_page_with_the_reason_and_no_code(capsys):
    store = _store()
    c = _client(store)
    back = c.post("/authorize", data={"req": _req(_page(c)), "passcode": "not it"})
    assert back.status_code == 403 and "not the passcode" in back.text and "location" not in back.headers
    assert _records(store, "grant") == []
    assert _lines(capsys, "approve")[-1]["outcome"] == "passcode-refused"


def test_five_wrong_passcodes_pause_approvals_even_for_the_right_one_and_time_reopens_them():
    clock = Clock()
    c = _client(clock=clock)
    req = _req(_page(c))
    for _ in range(window.BAD_LIMIT):
        assert c.post("/authorize", data={"req": req, "passcode": "guess"}).status_code == 403
    held = c.post("/authorize", data={"req": req, "passcode": PASS})
    assert held.status_code == 429 and "paused" in held.text and 'name="passcode"' not in held.text
    clock.t += window.BAD_WINDOW + 1
    assert c.post("/authorize", data={"req": _req(_page(c)), "passcode": PASS}).status_code == 302


def test_an_approval_is_written_to_the_bucket_before_a_code_is_given():
    store = _store()
    _grant(_client(store))
    (entry,) = _records(store, "grant")
    assert entry["caller"] == "jdot-hq" and entry["recipient"] == HQ and entry["client"] == "mw-x"
    assert entry["redirect_uri"] == REDIRECT and entry["window"] == "lxm-mail-window"


def test_an_approval_that_cannot_be_recorded_grants_nothing():
    class Full(MemoryStore):
        def write_new(self, name, data, *, timeout=None):
            raise hf.NotReady(15)

    c = _client(Full(_store().objects))
    back = c.post("/authorize", data={"req": _req(_page(c)), "passcode": PASS})
    assert back.status_code == 503 and "nothing was granted" in back.text and "location" not in back.headers


def test_a_code_is_bound_to_its_verifier_client_and_callback_and_is_used_once():
    c = _client()
    back = c.post("/authorize", data={"req": _req(_page(c)), "passcode": PASS})
    code = parse_qs(urlsplit(back.headers["location"]).query)["code"][0]
    good = {"grant_type": "authorization_code", "code": code, "client_id": "mw-x", "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER}
    for change in ({"code_verifier": "w" * 64}, {"client_id": "mw-y"}, {"redirect_uri": REDIRECT + "x"},
                   {"resource": f"{BASE}/other"}):
        assert c.post("/token", data=good | change).status_code == 400
    assert c.post("/token", data=good).status_code == 200
    assert c.post("/token", data=good).status_code == 400


def test_tokens_issued_before_a_sleep_are_good_after_it():
    clock, store = Clock(), _store()
    tok = _grant(_client(store, clock))
    woke = _client(store, clock)                              # a new process: empty memory, same passcode
    assert _said(_call(woke, tok["access_token"], "mail_list"))["status"] == "ok"
    again = woke.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    assert again.status_code == 200


def test_another_passcode_ends_every_token():
    store = _store()
    tok = _grant(_client(store))
    changed = _client(store, MAIL_PASSCODE="a different passcode, long enough")
    assert _call(changed, tok["access_token"], "mail_list").status_code == 401
    assert changed.post("/token", data={"grant_type": "refresh_token",
                                        "refresh_token": tok["refresh_token"]}).status_code == 400


def test_an_old_refresh_token_still_works_because_a_lost_answer_must_not_end_a_schedule():
    clock = Clock()
    c = _client(clock=clock)
    first = _grant(c)
    second = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": first["refresh_token"]}).json()
    clock.t += 5
    again = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": first["refresh_token"]})
    assert again.status_code == 200 and second["refresh_token"] != first["refresh_token"]
    assert _said(_call(c, again.json()["access_token"], "mail_list"))["status"] == "ok"


def test_an_expired_access_token_is_401_with_a_reason_and_a_refresh_token_is_not_an_access_token():
    clock = Clock()
    c = _client(clock=clock)
    tok = _grant(c)
    assert _call(c, tok["refresh_token"], "mail_list").status_code == 401
    clock.t += 601
    late = _call(c, tok["access_token"], "mail_list")
    assert late.status_code == 401 and 'error="invalid_token"' in late.headers["www-authenticate"]


def test_a_grant_ends_ninety_days_after_its_approval_however_often_it_was_refreshed():
    clock = Clock()
    c = _client(clock=clock)
    tok = _grant(c)
    for _ in range(4):                                        # refreshed every twenty days, as a schedule would
        clock.t += 20 * 86400
        tok = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]}).json()
    assert tok["expires_in"] == 600
    clock.t += 9 * 86400                                      # day 89: the tokens now end with the grant
    tok = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]}).json()
    clock.t += 86400 - 300
    last = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]}).json()
    assert last["expires_in"] == 300
    clock.t += 301
    ended = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    assert ended.status_code == 400 and _call(c, last["access_token"], "mail_list").status_code == 401


def test_a_token_for_another_address_is_not_a_token_for_this_one():
    store, clock = _store(), Clock()
    tok = _grant(_client(store, clock, MAIL_PUBLIC_URL="https://elsewhere.example"), base="https://elsewhere.example")
    assert _call(_client(store, clock), tok["access_token"], "mail_list").status_code == 401


# ── the window, in front of the mirror ───────────────────────────────────────

def test_the_caller_gets_its_own_letters_from_every_door_and_a_cursor_that_ends_them(capsys):
    store = _store()
    c = _client(store)
    access = _grant(c)["access_token"]
    capsys.readouterr()
    first = _said(_call(c, access, "mail_list"))
    assert [(l["door"], l["n"]) for l in first["letters"]] == [(DOOR, "001"), (DOOR, "003"), (OTHER_DOOR, "001")]
    assert first["examined"] == 4 and first["complete"] is True and first["signatures_checked"] is False
    assert first["letters"][1]["body_size"] == len("third — 한글".encode("utf-8"))
    assert not any("-body." in name or "-sig." in name for name in store.reads)      # a list reads envelopes only
    again = _said(_call(c, access, "mail_list", {"cursor": first["cursor"]}))
    assert again["letters"] == [] and again["examined"] == 0 and again["complete"] is True
    line = _lines(capsys, "mail")[-1]
    assert line["arg_names"] == ["cursor"] and line["tool"] == "mail_list" and line["caller"] == "jdot-hq"
    assert line["header_protocol"] == "2026-07-28" and line["status"] == 200


def test_a_letter_that_finishes_arriving_is_seen_by_the_next_call_with_the_same_cursor():
    store = _store()
    c = _client(store)
    access = _grant(c)["access_token"]
    cursor = _said(_call(c, access, "mail_list"))["cursor"]
    store.objects[f"drop-root/{DOOR}/004-envelope.json"] = _envelope(HQ, b"half a letter")    # the envelope lands last
    later = _said(_call(c, access, "mail_list", {"cursor": cursor}))
    assert [(l["door"], l["n"]) for l in later["letters"]] == [(DOOR, "004")]


def test_one_letter_comes_whole_and_another_labs_letter_is_the_same_answer_as_none():
    store = _store()
    c = _client(store)
    access = _grant(c)["access_token"]
    got = _said(_call(c, access, "mail_get", {"door": DOOR, "n": "003"}))
    assert got["body"] == "third — 한글" and got["body_matches_envelope"] is True and got["sig"] == "ab" * 64
    assert got["sender"] == {"claimed": "lab:organum", "verified": False}
    assert got["envelope"].encode("utf-8") == store.objects[f"drop-root/{DOOR}/003-envelope.json"]
    store.reads.clear()
    theirs = _call(c, access, "mail_get", {"door": DOOR, "n": "002"}).json()["result"]
    missing = _call(c, access, "mail_get", {"door": DOOR, "n": "099"}).json()["result"]
    assert theirs == missing and theirs["isError"] is True
    assert f"drop-root/{DOOR}/002-body.md" not in store.reads           # their body never entered this process
    outside = _call(c, access, "mail_get", {"door": "letters/from-organum", "n": "001"}).json()["result"]
    assert outside["isError"] is True and "letters/from-organum" not in "".join(store.lists)


def test_every_read_that_fetched_an_envelope_is_in_the_bucket_before_the_answer(capsys):
    store = _store()
    c = _client(store)
    access = _grant(c)["access_token"]
    capsys.readouterr()
    cursor = _said(_call(c, access, "mail_list"))["cursor"]
    _call(c, access, "mail_get", {"door": DOOR, "n": "002"})
    _call(c, access, "mail_get", {"door": DOOR, "n": "099"})                # nothing fetched: no record
    _said(_call(c, access, "mail_list", {"cursor": cursor}))                # nothing fetched: no record
    listed, refused = _records(store, "read")
    assert listed["tool"] == "mail_list" and listed["caller"] == "jdot-hq" and listed["recipient"] == HQ
    assert listed["fetched"] == listed["examined"] and len(listed["fetched"]) == 4
    assert listed["delivered"] == [[DOOR, "001"], [DOOR, "003"], [OTHER_DOOR, "001"]]
    assert refused["status"] == "refused" and refused["fetched"] == [[DOOR, "002"]] and refused["delivered"] == []
    assert len(_lines(capsys, "mail-audit")) == 2
    assert "first" not in json.dumps([listed, refused]) and "not yours" not in json.dumps([listed, refused])


def test_no_record_no_letter():
    class Full(MemoryStore):
        def write_new(self, name, data, *, timeout=None):
            if name.endswith("-read.json"):
                raise hf.ReaderError("the mail store refused this read")
            super().write_new(name, data, timeout=timeout)

    c = _client(Full(_store().objects))
    access = _grant(c)["access_token"]
    for tool, args in (("mail_list", {}), ("mail_get", {"door": DOOR, "n": "001"})):
        result = _call(c, access, tool, args).json()["result"]
        assert result["isError"] is True and "nothing was returned" in result["content"][0]["text"]
        assert "first" not in json.dumps(result) and "cursor" not in result["content"][0]["text"]


def test_a_bucket_that_does_not_answer_is_not_ready_and_not_an_empty_mailbox():
    class Asleep(MemoryStore):
        def names(self, prefix, *, timeout=None):
            raise hf.NotReady(15)

    c = _client(Asleep(_store().objects))
    told = _said(_call(c, _grant(c)["access_token"], "mail_list"))
    assert told["status"] == "not_ready" and told["complete"] is False and told["retry_after_seconds"] == 15


def test_a_reader_that_breaks_is_a_500_and_the_service_stays_up(capsys):
    class Broken(MemoryStore):
        def names(self, prefix, *, timeout=None):
            raise RuntimeError("secret detail")

    c = _client(Broken(_store().objects))
    access = _grant(c)["access_token"]
    r = _call(c, access, "mail_list")
    assert r.status_code == 500 and "secret detail" not in r.text
    assert c.get("/").status_code == 200
    assert any(l.get("outcome") == "window-raised" and l["error"] == "RuntimeError" for l in _lines(capsys, "mail"))


def test_a_token_whose_caller_lost_its_mailbox_gets_the_second_door():
    store, clock = _store(), Clock()
    tok = _grant(_client(store, clock))
    renamed = _client(store, clock, MAIL_CALLER="someone-else")
    r = _call(renamed, tok["access_token"], "mail_list")
    assert r.status_code == 403 and store.reads == []


def test_the_window_speaks_the_newer_revision_and_can_be_told_not_to():
    c = _client()
    access = _grant(c)["access_token"]
    meta = {hf.META_VERSION: "2026-07-28", hf.META_CLIENT_CAPABILITIES: {}}
    found = c.post("/mail", json={"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": meta}},
                   headers={"Authorization": f"Bearer {access}", "MCP-Protocol-Version": "2026-07-28",
                            "Mcp-Method": "server/discover"})
    assert found.status_code == 200 and "2026-07-28" in found.json()["result"]["supportedVersions"]
    old = _client(MAIL_MODERN="0")
    access = _grant(old)["access_token"]
    fell = old.post("/mail", json={"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": meta}},
                    headers={"Authorization": f"Bearer {access}", "MCP-Protocol-Version": "2026-07-28",
                             "Mcp-Method": "server/discover"})
    assert fell.status_code == 200 and fell.json()["error"]["code"] == -32601
    init = old.post("/mail", json={"jsonrpc": "2.0", "id": 2, "method": "initialize",
                                   "params": {"protocolVersion": "2025-11-25"}},
                    headers={"Authorization": f"Bearer {access}"})
    assert init.json()["result"]["protocolVersion"] == "2025-11-25"


# ── nothing a letter or a caller chose reaches the log or the record ─────────

def test_no_secret_no_cursor_and_no_letter_text_reaches_stdout_or_the_record(capsys):
    store = _store()
    c = _client(store)
    tok = _grant(c)
    c.post("/authorize", data={"req": _req(_page(c)), "passcode": "a wrong guess"})
    listed = _said(_call(c, tok["access_token"], "mail_list"))
    _said(_call(c, tok["access_token"], "mail_list", {"cursor": listed["cursor"]}))
    _said(_call(c, tok["access_token"], "mail_get", {"door": DOOR, "n": "001"}))
    c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    out = capsys.readouterr().out
    kept = out + "".join(v.decode("utf-8") for k, v in store.objects.items() if k.startswith("mail-audit/"))
    for secret in (PASS, "a wrong guess", tok["access_token"], tok["refresh_token"], listed["cursor"], VERIFIER,
                   CHALLENGE, "first", "ab" * 64, listed["letters"][0]["event_id"]):
        assert secret not in kept
    assert all(json.loads(line)["window"] for line in out.splitlines())
