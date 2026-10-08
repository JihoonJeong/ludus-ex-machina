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


def test_both_tools_are_listed_read_only_and_answer_with_the_clock_and_the_token_age():
    clock = Clock()
    c = _client(clock)
    access = _grant(c)["access_token"]
    tools = _rpc(c, access, "tools/list").json()["result"]["tools"]
    assert [t["name"] for t in tools] == ["probe_read", "probe_wait"]
    assert all(t["annotations"]["readOnlyHint"] is True and t["annotations"]["destructiveHint"] is False
               for t in tools)
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


# ── the two checks the authorization server really makes ────────────────────

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
