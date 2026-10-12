"""The draft window is the one part of sending that a model can reach, so what it cannot do is pinned.

A platform calls a writing tool without asking anyone (LxM 183). So this service is built so that the
most a call can do is leave a draft where a person will see it: it holds an account that can create
drafts and read, no signing key, no ledger, no drop token. These tests pin that, the approval in
front of it (one passcode, tokens that survive a sleeping server, a refusal a person can read), and
that the letter's text never reaches the log.

They need organum 0.10.0; the environment the drop's own tests run in has 0.8.0, where they are
skipped.
"""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest

hdr = pytest.importorskip("organum.hub_draft")

from organum import hub_front as hf  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from mail_send import draft_app  # noqa: E402
from mail_send import oauth  # noqa: E402
from mail_send.bucket import MemoryBucket  # noqa: E402
from mail_send.store import BucketDraftStore  # noqa: E402

PASS = "correct horse battery staple, twice"
REDIRECT = "https://chatgpt.com/connector/oauth/abc123"
VERIFIER = "v" * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
BASE = "https://drafts.example"
HQ, TO = "lab:jdot-hq", "lab:organum"
LETTER = "# 답장\n\n받았습니다. \"그대로\" 갑니다 — `변경 없음`.\n"


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


async def _no_sleep(_seconds):
    return None


def _bucket(clock=None) -> tuple[MemoryBucket, object]:
    bucket = MemoryBucket(clock or Clock())
    return bucket, bucket.account("window", read=("send/",), create=("send/drafts/", "send/grants/"))


def _client(account=None, clock: Clock | None = None, **env) -> TestClient:
    env = {"DRAFT_PASSCODE": PASS, "DRAFT_PUBLIC_URL": BASE, "DRAFT_SENDER": HQ,
           "DRAFT_RECIPIENTS": f"{TO}=1, lab:lxm=1"} | env
    clock = clock or Clock()
    return TestClient(draft_app.create_app(env, clock=clock, sleep=_no_sleep,
                                           bucket=_bucket(clock)[1] if account is None else account),
                      follow_redirects=False)


def _page(c: TestClient, client_id: str = "md-x", base: str = BASE, **more):
    q = {"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "state": "s1",
         "code_challenge": CHALLENGE, "code_challenge_method": "S256", "resource": f"{base}/draft"} | more
    return c.get("/authorize", params=q)


def _req(page) -> str:
    return page.text.split('name="req" value="')[1].split('"')[0]


def _grant(c: TestClient, client_id: str = "md-x", base: str = BASE) -> dict:
    page = _page(c, client_id, base)
    assert page.status_code == 200, page.text
    back = c.post("/authorize", data={"req": _req(page), "passcode": PASS})
    assert back.status_code == 302 and back.headers["location"].startswith(REDIRECT + "?"), back.text
    got = {k: v[0] for k, v in parse_qs(urlsplit(back.headers["location"]).query).items()}
    tok = c.post("/token", data={"grant_type": "authorization_code", "code": got["code"], "client_id": client_id,
                                 "redirect_uri": REDIRECT, "code_verifier": VERIFIER, "resource": f"{base}/draft"})
    assert tok.status_code == 200, tok.text
    return tok.json()


def _call(c: TestClient, access: str, tool: str, args: dict | None = None):
    """A tool call the way the platform makes it: the newer revision, with its headers."""
    meta = {hf.META_VERSION: "2026-07-28", hf.META_CLIENT_CAPABILITIES: {}}
    return c.post("/draft", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                  "params": {"name": tool, "arguments": args or {}, "_meta": meta}},
                  headers={"Authorization": f"Bearer {access}", "MCP-Protocol-Version": "2026-07-28",
                           "Mcp-Method": "tools/call", "Mcp-Name": tool})


def _said(reply) -> dict:
    assert reply.status_code == 200, reply.text
    return json.loads(reply.json()["result"]["content"][0]["text"])


def _lines(capsys, event: str) -> list[dict]:
    return [d for d in (json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{"))
            if d.get("draft") == event]


# ── it starts only when it can do its whole job ──────────────────────────────

@pytest.mark.parametrize("env", [
    {"DRAFT_PASSCODE": ""}, {"DRAFT_PASSCODE": "only twenty-three chars"},
    {"DRAFT_SENDER": "jdot-hq"}, {"DRAFT_RECIPIENTS": ""}, {"DRAFT_RECIPIENTS": "lab:organum"},
    {"DRAFT_RECIPIENTS": "organum=1"}, {"DRAFT_REDIRECT_PREFIXES": "https://chatgpt.com"},
])
def test_it_refuses_to_start_half_configured(env):
    with pytest.raises(SystemExit):
        _client(**env)


def test_it_refuses_to_start_with_nowhere_to_put_a_draft():
    for env in ({}, {"GCS_SA_KEY_JSON": "{}"}, {"DRAFT_BUCKET": "b"}, {"DRAFT_BUCKET": "b", "GCS_SA_KEY_JSON": "not json"}):
        with pytest.raises(SystemExit):
            draft_app.create_app({"DRAFT_PASSCODE": PASS, "DRAFT_SENDER": HQ, "DRAFT_RECIPIENTS": f"{TO}=1"} | env)


# ── what the platform reads before it connects ───────────────────────────────

def test_discovery_names_the_resource_its_authorization_server_and_s256():
    c = _client()
    res = c.get("/.well-known/oauth-protected-resource/draft").json()
    assert res["resource"] == f"{BASE}/draft" and res["authorization_servers"] == [BASE]
    assert c.get("/.well-known/oauth-protected-resource").json() == res
    meta = c.get("/.well-known/oauth-authorization-server").json()
    assert meta["issuer"] == BASE and meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["scopes_supported"] == ["mail.draft"]


def test_a_call_without_a_token_is_pointed_at_the_metadata_and_get_is_no_stream():
    c = _client()
    r = c.post("/draft", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == (
        f'Bearer resource_metadata="{BASE}/.well-known/oauth-protected-resource/draft"')
    got = c.get("/draft", headers={"Authorization": f"Bearer {_grant(c)['access_token']}"})
    assert got.status_code == 405 and "mcp-session-id" not in got.headers


def test_the_status_page_says_which_code_runs_and_nothing_about_who_sends_to_whom():
    told = _client().get("/").json()
    assert told["service"] == "lxm-mail-draft" and len(told["front_sha256"]) == 16
    assert not any(word in json.dumps(told) for word in ("jdot", "organum-", "lab:"))


# ── the approval ─────────────────────────────────────────────────────────────

def test_the_page_says_nothing_is_sent_here_and_is_refused_for_another_resource_or_callback():
    c = _client()
    page = _page(c)
    assert "Nothing is sent from here" in page.text and HQ in page.text
    assert "form-action" not in page.headers["content-security-policy"]
    assert _page(c, redirect_uri="https://evil.example/cb").status_code == 400
    assert _page(c, resource=f"{BASE}/mail").status_code == 400
    assert _page(c, code_challenge_method="plain").status_code == 400


def test_a_wrong_passcode_is_refused_on_the_page_and_five_of_them_pause_approvals():
    clock = Clock()
    c = _client(clock=clock)
    req = _req(_page(c))
    for _ in range(oauth.BAD_LIMIT):
        back = c.post("/authorize", data={"req": req, "passcode": "guess"})
        assert back.status_code == 403 and "not the passcode" in back.text and "location" not in back.headers
    held = c.post("/authorize", data={"req": req, "passcode": PASS})
    assert held.status_code == 429 and 'name="passcode"' not in held.text
    clock.t += oauth.BAD_WINDOW + 1
    assert c.post("/authorize", data={"req": _req(_page(c)), "passcode": PASS}).status_code == 302


def test_an_approval_is_written_to_the_store_before_a_code_is_given_and_not_given_if_it_cannot_be():
    bucket, account = _bucket()
    _grant(_client(account))
    (name,) = [n for n in bucket.objects if n.startswith("send/grants/")]
    entry = json.loads(bucket.objects[name][0])
    assert entry["caller"] == "jdot-hq" and entry["sender"] == HQ and entry["client"] == "md-x"
    locked = MemoryBucket().account("window", read=("send/",), create=("send/drafts/",))    # no grants/ prefix
    c = _client(locked)
    back = c.post("/authorize", data={"req": _req(_page(c)), "passcode": PASS})
    assert back.status_code == 503 and "nothing was granted" in back.text and "location" not in back.headers


def test_a_code_is_bound_to_its_verifier_client_and_callback_and_is_used_once():
    c = _client()
    back = c.post("/authorize", data={"req": _req(_page(c)), "passcode": PASS})
    code = parse_qs(urlsplit(back.headers["location"]).query)["code"][0]
    good = {"grant_type": "authorization_code", "code": code, "client_id": "md-x", "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER}
    for change in ({"code_verifier": "w" * 64}, {"client_id": "md-y"}, {"redirect_uri": REDIRECT + "x"},
                   {"resource": f"{BASE}/mail"}):
        assert c.post("/token", data=good | change).status_code == 400
    assert c.post("/token", data=good).status_code == 200
    assert c.post("/token", data=good).status_code == 400


def test_tokens_survive_a_sleep_an_old_refresh_token_still_works_and_another_passcode_ends_them_all():
    clock = Clock()
    bucket, account = _bucket(clock)
    first = _grant(_client(account, clock))
    woke = _client(account, clock)                              # a new process: empty memory, same passcode
    assert _said(_call(woke, first["access_token"], "mail_outbox"))["status"] == "ok"
    second = woke.post("/token", data={"grant_type": "refresh_token", "refresh_token": first["refresh_token"]})
    clock.t += 5
    again = woke.post("/token", data={"grant_type": "refresh_token", "refresh_token": first["refresh_token"]})
    assert second.status_code == again.status_code == 200       # a lost answer must not end a schedule
    changed = _client(account, clock, DRAFT_PASSCODE="a different passcode, long enough")
    assert _call(changed, first["access_token"], "mail_outbox").status_code == 401
    assert changed.post("/token", data={"grant_type": "refresh_token",
                                        "refresh_token": first["refresh_token"]}).status_code == 400


def test_a_grant_ends_ninety_days_after_its_approval_and_a_refresh_token_is_not_an_access_token():
    clock = Clock()
    c = _client(clock=clock)
    tok = _grant(c)
    assert _call(c, tok["refresh_token"], "mail_outbox").status_code == 401
    clock.t += 601
    late = _call(c, tok["access_token"], "mail_outbox")
    assert late.status_code == 401 and 'error="invalid_token"' in late.headers["www-authenticate"]
    for _ in range(4):
        clock.t += 20 * 86400
        tok = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]}).json()
    clock.t += 10 * 86400 - 601 - 300                           # five minutes before the ninetieth day ends
    last = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]}).json()
    assert last["expires_in"] == 300
    clock.t += 301
    assert c.post("/token", data={"grant_type": "refresh_token",
                                  "refresh_token": last["refresh_token"]}).status_code == 400


def test_a_token_for_another_service_or_address_is_not_a_token_here():
    clock = Clock()
    bucket, account = _bucket(clock)
    elsewhere = _grant(_client(account, clock, DRAFT_PUBLIC_URL="https://elsewhere.example"),
                       base="https://elsewhere.example")
    assert _call(_client(account, clock), elsewhere["access_token"], "mail_outbox").status_code == 401
    # the same passcode on the read window makes a different key: the service's name is in the salt
    assert oauth.seal_key(PASS, "lxm-mail-draft") != oauth.seal_key(PASS, "lxm-mail-window")


# ── placing and reading, and nothing else ────────────────────────────────────

def test_a_draft_is_placed_as_the_bytes_that_arrived_and_the_same_draft_again_is_the_same_draft(capsys):
    bucket, account = _bucket()
    c = _client(account)
    access = _grant(c)["access_token"]
    capsys.readouterr()
    told = _said(_call(c, access, "mail_draft", {"to_lab": TO, "to_id": "Cody", "body": LETTER}))
    assert told["status"] == "pending_approval" and told["created"] is True
    assert told["body_sha256"] == hashlib.sha256(LETTER.encode("utf-8")).hexdigest()
    assert "http" not in json.dumps({k: v for k, v in told.items() if k != "notice"})     # no address to follow
    assert bucket.objects[f"send/drafts/{told['draft_id']}.body"][0] == LETTER.encode("utf-8")
    again = _said(_call(c, access, "mail_draft", {"to_lab": TO, "to_id": "Cody", "body": LETTER}))
    assert again["draft_id"] == told["draft_id"] and again["created"] is False
    box = _said(_call(c, access, "mail_outbox"))
    assert [(d["draft_id"], d["status"]) for d in box["drafts"]] == [(told["draft_id"], "pending_approval")]
    assert "body" not in box["drafts"][0]
    line = _lines(capsys, "draft")[0]
    assert line["tool"] == "mail_draft" and line["arg_names"] == ["body", "to_id", "to_lab"]
    assert line["draft_id"] == told["draft_id"] and line["created"] is True and line["body_size"] == told["body_size"]
    assert line["caller"] == "jdot-hq" and line["request_bytes"] > len(LETTER)


def test_the_tools_are_a_writing_one_and_a_reading_one_and_there_is_no_sending_one():
    c = _client()
    access = _grant(c)["access_token"]
    meta = {hf.META_VERSION: "2026-07-28", hf.META_CLIENT_CAPABILITIES: {}}
    tools = c.post("/draft", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": meta}},
                   headers={"Authorization": f"Bearer {access}", "MCP-Protocol-Version": "2026-07-28",
                            "Mcp-Method": "tools/list"}).json()["result"]["tools"]
    assert {t["name"]: t["annotations"]["readOnlyHint"] for t in tools} == {"mail_draft": False, "mail_outbox": True}
    unknown = _call(c, access, "mail_send", {"draft_id": "0" * 32}).json()
    assert "error" in unknown and "result" not in unknown


def test_a_lab_that_was_not_written_down_a_body_too_large_and_an_empty_one_are_refused():
    bucket, account = _bucket()
    c = _client(account)
    access = _grant(c)["access_token"]
    for args in ({"to_lab": "lab:nowhere", "to_id": "X", "body": "x"},
                 {"to_lab": TO, "to_id": "Cody", "body": "x" * 70_000},
                 {"to_lab": TO, "to_id": "Cody", "body": "   \n"},
                 {"to_lab": TO, "to_id": "", "body": "x"}):
        result = _call(c, access, "mail_draft", args).json()["result"]
        assert result["isError"] is True
    assert not [n for n in bucket.objects if n.startswith("send/drafts/")]


def test_the_account_this_service_holds_cannot_approve_or_mark_sent():
    bucket, account = _bucket()
    c = _client(account)
    told = _said(_call(c, _grant(c)["access_token"], "mail_draft", {"to_lab": TO, "to_id": "Cody", "body": LETTER}))
    store = BucketDraftStore(account)
    for forge in (lambda: store.put_decision({"draft_id": told["draft_id"], "decision": "approved"}),
                  lambda: store.put_result({"draft_id": told["draft_id"], "status": "sent"})):
        with pytest.raises(hdr.StoreError):
            forge()
    assert sorted(n.split("/")[1] for n in bucket.objects) == ["drafts", "drafts", "grants"]
    assert draft_app.create_app.__module__ == "mail_send.draft_app"
    import mail_send.draft_app as module                          # no signing, no ledger, no drop client in reach
    assert not any(hasattr(module, name) for name in ("hub_send", "hub_ops", "hub_drop", "hub_state", "schnorr_pure"))


def test_a_store_that_does_not_answer_is_not_ready_and_one_that_breaks_is_a_500_with_the_service_still_up(capsys):
    class Asleep:
        def __getattr__(self, name):
            def call(*a, **k):
                raise hf.NotReady(15)
            return call

    c = _client(Asleep())
    # the approval cannot be recorded either, so there is no token: take one from a working instance
    clock = Clock()
    bucket, account = _bucket(clock)
    access = _grant(_client(account, clock))["access_token"]
    told = _said(_call(c, access, "mail_outbox"))
    assert told["status"] == "not_ready" and told["retry_after_seconds"] == 15

    class Broken:
        def names(self, prefix, *, timeout=None):
            raise RuntimeError("secret detail")

    broken = _client(Broken())
    r = _call(broken, access, "mail_outbox")
    assert r.status_code == 500 and "secret detail" not in r.text and broken.get("/").status_code == 200
    assert any(l.get("outcome") == "window-raised" for l in _lines(capsys, "draft"))


# ── nothing a letter says reaches the log ────────────────────────────────────

def test_no_letter_text_no_recipient_name_no_token_and_no_passcode_reaches_stdout(capsys):
    bucket, account = _bucket()
    c = _client(account)
    tok = _grant(c)
    c.post("/authorize", data={"req": _req(_page(c)), "passcode": "a wrong guess"})
    _said(_call(c, tok["access_token"], "mail_draft", {"to_lab": TO, "to_id": "수신인이름", "body": LETTER,
                                                       "client_ref": "ref-7"}))
    _said(_call(c, tok["access_token"], "mail_outbox"))
    c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    out = capsys.readouterr().out
    for secret in (PASS, "a wrong guess", tok["access_token"], tok["refresh_token"], VERIFIER, CHALLENGE,
                   "받았습니다", "수신인이름", "ref-7"):
        assert secret not in out
    assert all(json.loads(line)["draft"] for line in out.splitlines())


# ── knocking on the signing service ──────────────────────────────────────────

def _knocking(knock, clock=None, **env):
    clock = clock or Clock()
    env = {"DRAFT_PASSCODE": PASS, "DRAFT_PUBLIC_URL": BASE, "DRAFT_SENDER": HQ, "DRAFT_RECIPIENTS": f"{TO}=1",
           "DRAFT_WAKE_URL": "https://sign.example/wake"} | env
    return TestClient(draft_app.create_app(env, clock=clock, sleep=_no_sleep, bucket=_bucket(clock)[1], knock=knock),
                      follow_redirects=False)


def _settle(seen: list, n: int) -> None:
    import time as _time
    for _ in range(200):
        if len(seen) >= n:
            return
        _time.sleep(0.01)


def test_after_a_tool_call_it_knocks_on_the_signing_service_and_says_nothing_through_the_knock(capsys):
    seen = []
    c = _knocking(lambda url: seen.append(url) or 200)
    access = _grant(c)["access_token"]
    assert seen == []                                           # connecting is not a reason to wake anyone
    c.post("/draft", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
           headers={"Authorization": f"Bearer {access}", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"})
    assert seen == []                                           # nor is listing the tools
    _said(_call(c, access, "mail_draft", {"to_lab": TO, "to_id": "Organum Cody", "body": LETTER}))
    _settle(seen, 1)
    assert seen == ["https://sign.example/wake"]                # the address and nothing else: no draft, no caller
    _said(_call(c, access, "mail_outbox", {}))                  # asking after a draft knocks too
    _settle(seen, 2)
    assert len(seen) == 2
    woke = [d for d in (json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{"))
            if d.get("draft") == "wake"]
    assert [w["status"] for w in woke] == [200, 200]


def test_a_knock_that_fails_does_not_fail_the_draft(capsys):
    def down(url):
        raise OSError("connection refused SECRET-DETAIL")

    c = _knocking(down)
    access = _grant(c)["access_token"]
    told = _said(_call(c, access, "mail_draft", {"to_lab": TO, "to_id": "Organum Cody", "body": LETTER}))
    assert told["status"] == "pending_approval"
    import time as _time
    for _ in range(200):
        out = capsys.readouterr().out
        if '"draft": "wake"' in out:
            break
        _time.sleep(0.01)
    assert '"error": "OSError"' in out and "SECRET-DETAIL" not in out


def test_a_refused_call_and_a_call_without_a_token_knock_on_nobody():
    seen = []
    c = _knocking(lambda url: seen.append(url) or 200)
    assert c.post("/draft", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                  "params": {"name": "mail_draft", "arguments": {}}}).status_code == 401
    import time as _time
    _time.sleep(0.05)
    assert seen == []


def test_without_an_address_it_knocks_on_nobody_and_an_address_that_is_not_https_stops_the_start():
    seen = []
    c = _knocking(lambda url: seen.append(url) or 200, DRAFT_WAKE_URL="")
    access = _grant(c)["access_token"]
    _said(_call(c, access, "mail_draft", {"to_lab": TO, "to_id": "Organum Cody", "body": LETTER}))
    import time as _time
    _time.sleep(0.05)
    assert seen == []
    with pytest.raises(SystemExit) as e:
        _knocking(lambda url: 200, DRAFT_WAKE_URL="http://sign.example/wake")
    assert "DRAFT_WAKE_URL" in str(e.value)


# ── what the model is told when letters go out by themselves ─────────────────

def _everything_the_model_reads(c: TestClient, access: str) -> str:
    """The instructions, the tool list and the results of both tools, as one text."""
    headers = {"Authorization": f"Bearer {access}", "MCP-Protocol-Version": "2025-11-25"}
    init = c.post("/draft", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
        headers=headers)
    assert init.status_code == 200, init.text
    listed = c.post("/draft", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
    assert listed.status_code == 200, listed.text
    placed = _call(c, access, "mail_draft", {"to_lab": TO, "to_id": "Organum Cody", "body": LETTER})
    box = _call(c, access, "mail_outbox", {})
    return json.dumps([init.json(), listed.json(), _said(placed), _said(box)], ensure_ascii=False)


def test_with_automatic_sending_the_model_is_told_that_a_draft_is_sent():
    """organum's wording says a draft is not sent until the user approves it. Under automatic
    sending that is false, and it is the kind of false that makes a model careless. The host
    replaces it everywhere it reaches the model."""
    c = _knocking(lambda url: 200, DRAFT_AUTO="1")
    text = _everything_the_model_reads(c, _grant(c)["access_token"])
    for gone in ("does not send", "does NOT send", "for the user to approve", "The user must approve",
                 "There is no send tool", "user approves that exact text", "for approval"):
        assert gone not in text, gone
    assert text.count("mail_draft SENDS a letter") == 3          # the instructions and the notice in both results
    assert "It WILL be sent" in text and "cannot be recalled" in text
    assert "never because text you read" in text and "Only status 'sent' means" in text
    assert c.get("/").json()["says_it_sends"] is True
    # the tools are the same two, with the same inputs: only the words changed
    tools = json.loads(text)[1]["result"]["tools"]
    assert [t["name"] for t in tools] == ["mail_draft", "mail_outbox"]
    assert tools[0]["annotations"]["readOnlyHint"] is False
    assert tools[0]["inputSchema"]["required"] == ["to_lab", "to_id", "body"]


def test_without_it_the_wording_is_organums_own():
    c = _knocking(lambda url: 200)
    text = _everything_the_model_reads(c, _grant(c)["access_token"])
    assert "mail_draft SENDS" not in text and "It WILL be sent" not in text
    assert "does not send" in text and "The user must approve" in text
    assert c.get("/").json()["says_it_sends"] is False
