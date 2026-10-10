"""The probe has to survive its own host, and say nothing it should not.

It runs on a free instance that sleeps after fifteen minutes and wakes with
empty memory, in front of a platform whose behaviour is the thing being
measured. If the probe itself forgot a client or a token across a sleep, an
unattended call that failed would look like the platform's answer and be ours.
These tests pin that: a second instance with the same passcode honours what
the first one issued. They also pin the shape the real window will have (one
POST, one JSON response, GET is 405), the two checks the authorization server
really makes (the platform's redirect URI, the PKCE verifier), and that no
token, passcode or body reaches the log.
"""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from mcp_probe import app as probe

PASS = "correct horse battery staple"
REDIRECT = "https://chatgpt.com/connector/oauth/abc123"
VERIFIER = "v" * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


async def _no_sleep(_seconds):
    return None


def _client(clock: Clock | None = None, **env) -> TestClient:
    env = {"PROBE_PASSCODE": PASS, "PROBE_PUBLIC_URL": "https://probe.example"} | env
    return TestClient(probe.create_app(env, clock=clock or Clock(), sleep=_no_sleep), follow_redirects=False)


def _grant(c: TestClient, client_id: str = "probe-x", state: str | None = "s1") -> dict:
    """Walk the whole flow the platform walks: page, passcode, code, tokens."""
    q = {"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
         "code_challenge": CHALLENGE, "code_challenge_method": "S256", "resource": "https://probe.example/mcp"}
    if state is not None:
        q["state"] = state
    page = c.get("/authorize", params=q)
    assert page.status_code == 200
    req = page.text.split('name="req" value="')[1].split('"')[0]
    back = c.post("/authorize", data={"req": req, "passcode": PASS})
    assert back.status_code == 302 and back.headers["location"].startswith(REDIRECT + "?")
    got = {k: v[0] for k, v in parse_qs(urlsplit(back.headers["location"]).query).items()}
    assert got.get("state") == state
    tok = c.post("/token", data={"grant_type": "authorization_code", "code": got["code"], "client_id": client_id,
                                 "redirect_uri": REDIRECT, "code_verifier": VERIFIER})
    assert tok.status_code == 200, tok.text
    return tok.json()


def _rpc(c: TestClient, access: str, method: str, params: dict | None = None, mid=1):
    body = {"jsonrpc": "2.0", "id": mid, "method": method} | ({"params": params} if params is not None else {})
    return c.post("/mcp", json=body, headers={"Authorization": f"Bearer {access}"})


def _told(reply) -> dict:
    return json.loads(reply.json()["result"]["content"][0]["text"])


# ── it starts only with its one secret ───────────────────────────────────────

@pytest.mark.parametrize("env", [{}, {"PROBE_PASSCODE": "short"}])
def test_it_refuses_to_start_without_a_real_passcode(env):
    with pytest.raises(SystemExit):
        probe.create_app(env)


def test_a_redirect_prefix_without_a_path_stops_the_boot():
    with pytest.raises(SystemExit):                     # "https://chatgpt.com" also matches chatgpt.com.evil.example
        probe.create_app({"PROBE_PASSCODE": PASS, "PROBE_REDIRECT_PREFIXES": "https://chatgpt.com"})


# ── what the platform reads before it connects ───────────────────────────────

def test_discovery_names_the_resource_its_authorization_server_and_s256():
    c = _client()
    res = c.get("/.well-known/oauth-protected-resource").json()
    assert res["resource"] == "https://probe.example/mcp"
    assert res["authorization_servers"] == ["https://probe.example"]
    assert c.get("/.well-known/oauth-protected-resource/mcp").json() == res
    meta = c.get("/.well-known/oauth-authorization-server").json()
    assert meta["issuer"] == "https://probe.example"
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["token_endpoint_auth_methods_supported"] == ["none"]
    assert {meta["authorization_endpoint"], meta["token_endpoint"], meta["registration_endpoint"]} == {
        "https://probe.example/authorize", "https://probe.example/token", "https://probe.example/register"}


def test_without_a_public_url_the_forwarded_scheme_is_believed():
    c = TestClient(probe.create_app({"PROBE_PASSCODE": PASS}))
    res = c.get("/.well-known/oauth-protected-resource",
                headers={"host": "p.onrender.com", "x-forwarded-proto": "https"}).json()
    assert res["resource"] == "https://p.onrender.com/mcp"


def test_a_call_without_a_token_is_pointed_at_the_metadata():
    r = _client().post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == \
        'Bearer resource_metadata="https://probe.example/.well-known/oauth-protected-resource"'


# ── the shape of the window it stands in for ─────────────────────────────────

def test_one_post_gets_one_json_answer_and_there_is_no_stream_to_open():
    c = _client()
    access = _grant(c)["access_token"]
    assert c.get("/mcp", headers={"Authorization": f"Bearer {access}"}).status_code == 405
    assert c.delete("/mcp", headers={"Authorization": f"Bearer {access}"}).status_code == 405
    init = _rpc(c, access, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                          "clientInfo": {"name": "t", "version": "0"}})
    assert init.headers["content-type"].startswith("application/json")
    assert "mcp-session-id" not in init.headers
    assert init.json()["result"]["protocolVersion"] == "2025-06-18"
    assert init.json()["result"]["capabilities"] == {"tools": {"listChanged": False}}
    note = c.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                  headers={"Authorization": f"Bearer {access}"})
    assert note.status_code == 202 and note.content == b""


def test_a_protocol_version_it_does_not_know_is_answered_with_its_newest():
    c = _client()
    init = _rpc(c, _grant(c)["access_token"], "initialize", {"protocolVersion": "2099-01-01"})
    assert init.json()["result"]["protocolVersion"] == probe.PROTOCOL_VERSIONS[0]


def test_the_tools_are_listed_read_only_and_answer_with_the_clock_and_the_token_age():
    clock = Clock()
    c = _client(clock)
    access = _grant(c)["access_token"]
    tools = _rpc(c, access, "tools/list").json()["result"]["tools"]
    assert [t["name"] for t in tools] == ["probe_read", "probe_wait", "probe_read_unmarked", "probe_text",
                                          "probe_receive"]
    assert all(t["annotations"]["readOnlyHint"] is True and t["annotations"]["destructiveHint"] is False
               for t in tools[:2])
    assert "annotations" not in tools[2]              # the same tool without the marking: that is the experiment
    clock.t += 42
    first = _told(_rpc(c, access, "tools/call", {"name": "probe_read", "arguments": {}}))
    assert first["tool_calls_since_boot"] == 1 and first["token_age_s"] == 42 and first["refresh_generation"] == 0
    waited = _told(_rpc(c, access, "tools/call", {"name": "probe_wait", "arguments": {"seconds": 3}}))
    assert waited["tool_calls_since_boot"] == 2 and waited["waited_s"] == 3


@pytest.mark.parametrize("params", [
    {"name": "probe_delete", "arguments": {}},
    {"name": "probe_wait", "arguments": {"seconds": 301}},
    {"name": "probe_wait", "arguments": {"seconds": "3"}},
    {"name": "probe_wait", "arguments": {"seconds": True}},
    {"name": "probe_read", "arguments": {"anything": 1}},
    {"name": "probe_read", "arguments": {"pad_bytes": 256 * 1024 + 1}},
    {"name": "probe_read", "arguments": {"pad_bytes": -1}},
    {"name": "probe_read", "arguments": {"pad_bytes": "1024"}},
    {"name": "probe_read_unmarked", "arguments": {"pad_bytes": True}},
    {"name": "probe_text", "arguments": {}},
    {"name": "probe_text", "arguments": {"bytes": 63}},
    {"name": "probe_text", "arguments": {"bytes": 256 * 1024 + 1}},
    {"name": "probe_text", "arguments": {"bytes": "1000"}},
    {"name": "probe_receive", "arguments": {}},
    {"name": "probe_receive", "arguments": {"text": 7}},
    {"name": "probe_receive", "arguments": {"text": "x", "save": True}},
])
def test_a_call_it_does_not_know_is_an_error_not_a_guess(params):
    c = _client()
    r = _rpc(c, _grant(c)["access_token"], "tools/call", params)
    assert r.json()["error"]["code"] == -32602
    assert c.get("/").json()["tool_calls_since_boot"] == 0


def test_an_unknown_method_and_a_broken_body_are_json_rpc_errors():
    c = _client()
    access = _grant(c)["access_token"]
    assert _rpc(c, access, "resources/list").json()["error"]["code"] == -32601
    bad = c.post("/mcp", content=b"{not json", headers={"Authorization": f"Bearer {access}"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == -32700


# ── Organum 174 §2: how large, and does it arrive as it was sent ─────────────

def test_every_answer_carries_a_fresh_64_hex_nonce_and_the_log_has_the_same_one(capsys):
    c = _client()
    access = _grant(c)["access_token"]
    capsys.readouterr()
    told = [_told(_rpc(c, access, "tools/call", {"name": n, "arguments": a})) for n, a in
            (("probe_read", {}), ("probe_read_unmarked", {}), ("probe_wait", {"seconds": 1}))]
    nonces = [t["nonce"] for t in told]
    assert len(set(nonces)) == 3 and all(len(n) == 64 and set(n) <= set("0123456789abcdef") for n in nonces)
    logged = [json.loads(l) for l in capsys.readouterr().out.splitlines()]
    assert [l["nonce"] for l in logged if l["probe"] == "rpc"] == nonces


@pytest.mark.parametrize("size", [1024, 16 * 1024, 64 * 1024, 256 * 1024])
def test_an_answer_can_be_padded_to_a_size_and_names_its_own_end_before_the_filler(size, capsys):
    c = _client()
    access = _grant(c)["access_token"]
    capsys.readouterr()
    r = _rpc(c, access, "tools/call", {"name": "probe_read", "arguments": {"pad_bytes": size}})
    text = r.json()["result"]["content"][0]["text"]
    told = json.loads(text)
    assert len(told["filler"]) == told["filler_bytes"] == size
    assert told["filler"].endswith(told["filler_ends_with"]) and told["filler_ends_with"] == "#END-" + told["nonce"][:8]
    assert text.index('"filler_ends_with"') < text.index('"filler"')      # a cut answer still says what was cut
    line = [json.loads(l) for l in capsys.readouterr().out.splitlines()][-1]
    assert line["pad_bytes"] == size and "filler" not in line


def test_the_unmarked_tool_answers_exactly_as_the_marked_one_does():
    c = _client()
    access = _grant(c)["access_token"]
    a = _told(_rpc(c, access, "tools/call", {"name": "probe_read", "arguments": {}}))
    b = _told(_rpc(c, access, "tools/call", {"name": "probe_read_unmarked", "arguments": {}}))
    assert set(a) == set(b) and b["tool_calls_since_boot"] == a["tool_calls_since_boot"] + 1


# ── the two checks the authorization server really makes ────────────────────

# ── third round: the arrow turned round — what the model hands the tool ──────

def _tool(c, access, name, args):
    return _told(_rpc(c, access, "tools/call", {"name": name, "arguments": args}))


@pytest.mark.parametrize("size", [64, 65, 1000, 4096, 65536, 262144])
def test_the_reference_text_is_exactly_as_large_as_asked_and_can_be_rebuilt_from_its_name(size):
    c = _client()
    given = _tool(c, _grant(c)["access_token"], "probe_text", {"bytes": size})
    text = given["text"]
    assert len(text.encode("utf-8")) == size == given["bytes"] and text.endswith("\n")
    assert given["sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    kind, seed, n = given["reference"].split("-")
    assert kind == "t1" and int(n) == size and probe.reference_text(seed, size) == text    # nothing was remembered
    assert list(given).index("sha256") < list(given).index("text")          # a cut answer still says what it was


def test_the_reference_text_holds_what_a_careless_copy_changes():
    text = probe.reference_text("0a1b2c3d", 2000)
    for trap in ('"', "`", "「", "」", " — ", "\n\n", "| ", "   - "):
        assert trap in text
    assert probe.reference_text("0a1b2c3d", 2000) != probe.reference_text("0a1b2c3e", 2000)


def test_a_text_handed_back_unchanged_matches_and_a_changed_one_says_where():
    c = _client()
    access = _grant(c)["access_token"]
    given = _tool(c, access, "probe_text", {"bytes": 3000})
    text, ref = given["text"], given["reference"]
    same = _tool(c, access, "probe_receive", {"text": text, "reference": ref})
    assert same["matches_reference"] is True and same["first_difference_at"] is None
    assert same["received_bytes"] == 3000 == same["expected_bytes"] and same["sha256"] == given["sha256"]
    curled = text.replace('"', "\u201c", 1)                                # one straight quote made pretty
    told = _tool(c, access, "probe_receive", {"text": curled, "reference": ref})
    assert told["matches_reference"] is False and told["first_difference_at"] == text.index('"')
    assert told["received_chars"] == len(text) and told["received_bytes"] == 3002
    clipped = _tool(c, access, "probe_receive", {"text": text[:-1], "reference": ref})    # the last newline lost
    assert clipped["matches_reference"] is False and clipped["first_difference_at"] == len(text) - 1
    assert clipped["ends_with_newline"] is False
    longer = _tool(c, access, "probe_receive", {"text": text + "\n", "reference": ref})
    assert longer["matches_reference"] is False and longer["first_difference_at"] == len(text)


def test_a_text_with_no_reference_is_measured_and_not_judged_and_a_made_up_reference_is_not_believed():
    c = _client()
    access = _grant(c)["access_token"]
    plain = _tool(c, access, "probe_receive", {"text": "한글 두 글자"})
    assert plain["received_chars"] == 7 and plain["received_bytes"] == 17
    assert "matches_reference" not in plain and "reference" not in plain
    for made_up in ("t1-zzzzzzzz-100", "t1-0a1b2c3d-9999999", "t2-0a1b2c3d-100", "100"):
        told = _tool(c, access, "probe_receive", {"text": "x", "reference": made_up})
        assert told["reference_known"] is False and "matches_reference" not in told


def test_the_receiving_tool_is_published_as_not_read_only_because_that_is_the_question():
    c = _client()
    tools = {t["name"]: t for t in _rpc(c, _grant(c)["access_token"], "tools/list").json()["result"]["tools"]}
    assert tools["probe_text"]["annotations"]["readOnlyHint"] is True
    assert tools["probe_receive"]["annotations"]["readOnlyHint"] is False
    assert tools["probe_receive"]["annotations"]["destructiveHint"] is False
    assert "maxLength" not in tools["probe_receive"]["inputSchema"]["properties"]["text"]     # the platform's limit, not ours


def test_the_log_says_how_much_arrived_and_whether_it_matched_and_never_what_it_said(capsys):
    c = _client()
    access = _grant(c)["access_token"]
    given = _tool(c, access, "probe_text", {"bytes": 1500})
    capsys.readouterr()
    _tool(c, access, "probe_receive", {"text": given["text"], "reference": given["reference"]})
    out = capsys.readouterr().out
    line = [json.loads(l) for l in out.splitlines() if '"probe": "rpc"' in l][-1]
    assert line["tool"] == "probe_receive" and line["arg_names"] == ["reference", "text"]
    assert line["received_bytes"] == 1500 and line["matches_reference"] is True and line["request_bytes"] > 1500
    assert line["sha256"] == given["sha256"][:16] and line["reference"] == given["reference"]
    assert "시험 편지" not in out and given["text"][40:80] not in out


@pytest.mark.parametrize("uri", ["https://evil.example/cb", "https://chatgpt.com.evil.example/connector/oauth/x",
                                 "http://chatgpt.com/connector/oauth/x"])
def test_a_redirect_that_is_not_the_platforms_is_refused_and_never_followed(uri):
    c = _client()
    reg = c.post("/register", json={"redirect_uris": [REDIRECT, uri]})
    assert reg.status_code == 400 and reg.json()["error"] == "invalid_redirect_uri"
    page = c.get("/authorize", params={"response_type": "code", "client_id": "x", "redirect_uri": uri,
                                       "code_challenge": CHALLENGE, "code_challenge_method": "S256"})
    assert page.status_code == 400 and "location" not in page.headers


def test_registration_accepts_the_platforms_callback_and_asks_for_no_client_secret():
    reg = _client().post("/register", json={"redirect_uris": [REDIRECT], "client_name": "ChatGPT"})
    assert reg.status_code == 201
    assert reg.json()["token_endpoint_auth_method"] == "none" and "client_secret" not in reg.json()


def test_a_challenge_other_than_s256_gets_no_page():
    page = _client().get("/authorize", params={"response_type": "code", "client_id": "x", "redirect_uri": REDIRECT,
                                               "code_challenge": CHALLENGE, "code_challenge_method": "plain"})
    assert page.status_code == 400


def test_the_wrong_passcode_gets_the_page_again_and_no_code():
    c = _client()
    page = c.get("/authorize", params={"response_type": "code", "client_id": "x", "redirect_uri": REDIRECT,
                                       "code_challenge": CHALLENGE, "code_challenge_method": "S256"})
    req = page.text.split('name="req" value="')[1].split('"')[0]
    back = c.post("/authorize", data={"req": req, "passcode": "not it"})
    assert back.status_code == 403 and "location" not in back.headers and "not the passcode" in back.text


@pytest.mark.parametrize("change", [{"code_verifier": "w" * 64}, {"redirect_uri": REDIRECT + "x"},
                                    {"client_id": "someone-else"}])
def test_a_code_is_good_only_for_the_verifier_redirect_and_client_it_was_made_for(change):
    c = _client()
    page = c.get("/authorize", params={"response_type": "code", "client_id": "probe-x", "redirect_uri": REDIRECT,
                                       "code_challenge": CHALLENGE, "code_challenge_method": "S256"})
    req = page.text.split('name="req" value="')[1].split('"')[0]
    code = parse_qs(urlsplit(c.post("/authorize", data={"req": req, "passcode": PASS}).headers["location"]).query)["code"][0]
    form = {"grant_type": "authorization_code", "code": code, "client_id": "probe-x",
            "redirect_uri": REDIRECT, "code_verifier": VERIFIER} | change
    r = c.post("/token", data=form)
    assert r.status_code == 400 and r.json()["error"] == "invalid_grant"


def test_a_code_and_a_refresh_token_are_spent_once_within_a_boot():
    c = _client()
    first = _grant(c)
    again = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": first["refresh_token"]})
    assert again.status_code == 200 and again.json()["refresh_token"] != first["refresh_token"]
    replay = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": first["refresh_token"]})
    assert replay.status_code == 400 and replay.json()["error"] == "invalid_grant"


def test_a_refresh_token_is_not_an_access_token_and_a_forged_one_is_nothing():
    c = _client()
    got = _grant(c)
    assert _rpc(c, got["refresh_token"], "tools/list").status_code == 401
    body, sig = got["access_token"].split(".")
    forged = base64.urlsafe_b64encode(json.dumps({"exp": 9_999_999_999, "iat": 0, "g0": 0, "gen": 0}).encode()).decode()
    r = _rpc(c, forged.rstrip("=") + "." + sig, "tools/list")
    assert r.status_code == 401 and 'error="invalid_token"' in r.headers["www-authenticate"]


# ── the sleep: nothing issued before it may be forgotten after it ────────────

def test_an_expired_access_token_is_refused_and_the_refresh_brings_a_new_one():
    clock = Clock()
    c = _client(clock, PROBE_ACCESS_TTL="600")
    got = _grant(c)
    clock.t += 601
    late = _rpc(c, got["access_token"], "tools/call", {"name": "probe_read", "arguments": {}})
    assert late.status_code == 401 and "access token is expired" in late.headers["www-authenticate"]
    new = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": got["refresh_token"],
                                 "client_id": "probe-x"}).json()
    told = _told(_rpc(c, new["access_token"], "tools/call", {"name": "probe_read", "arguments": {}}))
    assert told["refresh_generation"] == 1 and told["token_age_s"] == 0 and told["grant_age_s"] == 601


def test_a_second_instance_with_the_same_passcode_honours_what_the_first_issued():
    clock = Clock()
    got = _grant(_client(clock))
    clock.t += 3600                                  # an hour on: the instance slept, this one has just woken
    woke = _client(clock)
    assert _rpc(woke, got["access_token"], "tools/list").status_code == 401          # only because it expired
    new = woke.post("/token", data={"grant_type": "refresh_token", "refresh_token": got["refresh_token"]})
    assert new.status_code == 200
    told = _told(_rpc(woke, new.json()["access_token"], "tools/call", {"name": "probe_read", "arguments": {}}))
    assert told["tool_calls_since_boot"] == 1 and told["grant_age_s"] == 3600


def test_an_instance_with_another_passcode_honours_nothing():
    got = _grant(_client())
    other = _client(PROBE_PASSCODE="a different passcode entirely")
    assert _rpc(other, got["access_token"], "tools/list").status_code == 401
    r = other.post("/token", data={"grant_type": "refresh_token", "refresh_token": got["refresh_token"]})
    assert r.status_code == 400


# ── the log is the record, and it holds no secret ───────────────────────────

def test_the_log_has_a_line_for_each_step_and_no_token_passcode_or_code_in_it(capsys):
    clock = Clock()
    c = _client(clock)
    got = _grant(c)
    _rpc(c, got["access_token"], "tools/call", {"name": "probe_wait", "arguments": {"seconds": 2}})
    c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    out = capsys.readouterr().out
    lines = [json.loads(line) for line in out.splitlines()]
    assert [l["probe"] for l in lines] == ["boot", "authorize", "approve", "token", "wait", "wait", "rpc", "mcp"]
    assert lines[-1]["auth"] == "missing" and lines[-2]["tool"] == "probe_wait"
    assert all("utc" in l and "uptime_s" in l for l in lines)
    for secret in (PASS, got["access_token"], got["refresh_token"], VERIFIER,
                   got["access_token"].split(".")[1], got["refresh_token"].split(".")[1]):
        assert secret not in out


# ── second round: organum's mail window behind the same approval ─────────────
# The 0.9.0 candidate's MailFront, fed three made-up letters. These run where the candidate is
# installed (the probe's own build); beside the drop's released organum they skip, bar the last.

def _mail(c: TestClient, access: str, method: str, params: dict | None = None, path: str = "/mail",
          headers: dict | None = None, mid=1):
    body = {"jsonrpc": "2.0", "id": mid, "method": method} | ({"params": params} if params is not None else {})
    return c.post(path, json=body, headers={"Authorization": f"Bearer {access}"} | (headers or {}))


def _said(reply) -> dict:
    return json.loads(reply.json()["result"]["content"][0]["text"])


def test_the_window_lists_only_the_callers_letters_and_reads_one(capsys):
    pytest.importorskip("organum.hub_front")
    c = _client()
    access = _grant(c)["access_token"]
    capsys.readouterr()
    assert _mail(c, access, "initialize", {"protocolVersion": "2025-11-25"}).json()["result"]["protocolVersion"] == "2025-11-25"
    assert [t["name"] for t in _mail(c, access, "tools/list").json()["result"]["tools"]] == ["mail_get", "mail_list"]
    listed = _said(_mail(c, access, "tools/call", {"name": "mail_list", "arguments": {}}))
    assert [l["n"] for l in listed["letters"]] == ["001", "003"] and listed["examined"] == 3 and listed["complete"] is True
    assert listed["letters"][0]["sender"] == {"claimed": "lab:sample-sender", "verified": False}
    door = listed["letters"][0]["door"]
    one = _said(_mail(c, access, "tools/call", {"name": "mail_get", "arguments": {"door": door, "n": "001"}}))
    assert one["status"] == "ok" and one["body_matches_envelope"] is True and "Sample letter one" in one["body"]
    theirs = _mail(c, access, "tools/call", {"name": "mail_get", "arguments": {"door": door, "n": "002"}}).json()
    missing = _mail(c, access, "tools/call", {"name": "mail_get", "arguments": {"door": door, "n": "099"}}).json()
    assert theirs == missing and theirs["result"]["isError"] is True      # someone else's letter is no letter

    out = capsys.readouterr().out
    lines = [json.loads(l) for l in out.splitlines()]
    audits = [l for l in lines if l["probe"] == "mail-audit"]
    assert [(a["tool"], a["status"], len(a["examined"]), len(a["delivered"])) for a in audits] == [
        ("mail_list", "ok", 3, 2), ("mail_get", "ok", 1, 1), ("mail_get", "refused", 1, 0)]
    calls = [l for l in lines if l["probe"] == "mail" and l.get("method") == "tools/call"]
    assert calls[0]["tool"] == "mail_list" and calls[0]["arg_names"] == [] and calls[1]["arg_names"] == ["door", "n"]
    assert "Sample letter" not in out and listed["cursor"] not in out      # what the letters say, and the cursor, stay out


def test_a_scheduled_run_that_brings_its_cursor_is_told_apart_in_the_log(capsys):
    pytest.importorskip("organum.hub_front")
    c = _client()
    access = _grant(c)["access_token"]
    cursor = _said(_mail(c, access, "tools/call", {"name": "mail_list", "arguments": {}}))["cursor"]
    capsys.readouterr()
    again = _said(_mail(c, access, "tools/call", {"name": "mail_list", "arguments": {"cursor": cursor}}))
    assert again["letters"] == [] and again["examined"] == 0 and again["complete"] is True
    line = [json.loads(l) for l in capsys.readouterr().out.splitlines() if '"probe": "mail"' in l][-1]
    assert line["arg_names"] == ["cursor"]


def test_the_window_answers_the_newer_revision_and_the_log_names_what_arrived(capsys):
    hf = pytest.importorskip("organum.hub_front")
    c = _client()
    access = _grant(c)["access_token"]
    capsys.readouterr()
    meta = {hf.META_VERSION: "2026-07-28", hf.META_CLIENT_CAPABILITIES: {}}
    r = _mail(c, access, "server/discover", {"_meta": meta},
              headers={"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover"})
    assert r.status_code == 200 and "2026-07-28" in r.json()["result"]["supportedVersions"]
    bare = _mail(c, access, "tools/list", {"_meta": meta}, headers={"MCP-Protocol-Version": "2026-07-28"})
    assert bare.status_code == 400                    # the stricter headers are checked: this is what round two asks
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if '"probe": "mail"' in l]
    assert lines[0]["header_mcp_method"] == "server/discover" and lines[0]["header_protocol"] == "2026-07-28"
    assert lines[0]["meta_keys"] == sorted(meta) and lines[1]["header_mcp_method"] is None and lines[1]["status"] == 400


def test_the_window_can_be_turned_down_to_the_older_revisions_by_one_variable():
    pytest.importorskip("organum.hub_front")
    c = _client(PROBE_MAIL_MODERN="0")
    access = _grant(c)["access_token"]
    r = _mail(c, access, "server/discover", {}, headers={"MCP-Protocol-Version": "2026-07-28"})
    assert r.status_code == 200 and r.json()["error"]["code"] == -32601       # a two-era client falls back on this
    assert _mail(c, access, "initialize", {"protocolVersion": "2025-11-25"}).status_code == 200


def test_a_caller_without_a_mailbox_gets_403_on_every_call_and_no_token_gets_its_own_metadata():
    pytest.importorskip("organum.hub_front")
    c = _client()
    access = _grant(c)["access_token"]
    for method in ("initialize", "tools/list"):
        assert _mail(c, access, method, {}, path="/mail-nobox").status_code == 403
    r = c.post("/mail", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r.status_code == 401 and r.headers["www-authenticate"] == \
        'Bearer resource_metadata="https://probe.example/.well-known/oauth-protected-resource/mail"'
    assert c.get("/.well-known/oauth-protected-resource/mail").json()["resource"] == "https://probe.example/mail"
    assert c.get("/.well-known/oauth-protected-resource/elsewhere").status_code == 404
    assert c.get("/mail", headers={"Authorization": f"Bearer {access}"}).status_code == 405


def test_a_window_that_raises_is_a_500_and_a_line_not_a_dead_service(monkeypatch, capsys):
    hf = pytest.importorskip("organum.hub_front")

    def boom(self, *a):
        raise LookupError("hub-ops/from-sample-sender/004")
    monkeypatch.setattr(hf.MailFront, "handle_http", boom)
    c = _client()
    access = _grant(c)["access_token"]
    r = _mail(c, access, "tools/list")
    assert r.status_code == 500 and r.json()["error"]["code"] == -32603
    assert '"outcome": "window-raised"' in capsys.readouterr().out
    assert c.get("/").status_code == 200


def test_without_the_candidate_installed_the_window_is_absent_and_the_probe_still_runs(monkeypatch):
    monkeypatch.setattr(probe, "hub_front", None)
    c = _client()
    access = _grant(c)["access_token"]
    assert _mail(c, access, "tools/list").status_code == 404
    assert _rpc(c, access, "tools/list").status_code == 200
