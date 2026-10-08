"""A server that holds nothing, to ask a platform five things before anything is built.

Jdot HQ (a ChatGPT workspace) wants to read its mail through an OAuth-connected
remote MCP tool, once an hour, with no one at the keyboard. Whether that works
is the platform's behaviour, not ours, and nobody has written it down
(Organum 173 §1, LxM 151 §4):

  1. after one approval in a chat, is a read-only custom tool asked about again?
  2. is it called at all from a scheduled run, unattended?
  3. how long does the platform wait for a tool to answer?
  4. does it wait for a free instance that has gone to sleep?
  5. does it refresh an expired access token with no one there?
  6. how large may a tool's answer be?                        (Organum 174 §2)
  7. does what the tool says reach the model character for character?
  and, if it shows: does the read-only marking change how the caller is asked?

This server answers nothing else. It reaches no drop, no bucket and no ledger;
its tools return the server's clock and how long this instance has been up.

Shape — the same as the window it stands in for (Organum 173 §3): one POST, one
JSON response, no session, no stream. GET on /mcp is 405.

State — none on disk, and none that a restart loses. A free instance sleeps
after fifteen idle minutes and wakes with empty memory; a client that
registered, or was granted a token, before the sleep must still be good after
it. So nothing is remembered. An authorization code, an access token and a
refresh token are each a payload sealed with an HMAC keyed from PROBE_PASSCODE,
and a client is whoever says it is one: what is checked is the redirect URI,
against the platform's own (PROBE_REDIRECT_PREFIXES), and the PKCE verifier.
The price: a code or a refresh token is single-use only within one boot. This
is a probe, and it guards nothing.

The one secret is PROBE_PASSCODE. Whoever approves the connection types it once
on the approval page; the same value keys the seals. Without it, or with fewer
than 16 characters, the server refuses to start.

Every request prints one JSON line to stdout — when, what, how the token fared
and how old it was, how long the instance had been up. No request body, no
token and no passcode goes to the log or into a response. A sleeping instance
loses its memory but not its stdout, so the log is the record.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

SERVER_NAME, SERVER_VERSION = "lxm-mcp-probe", "0.2.0"
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")   # newest first
SCOPE = "probe"
REQUEST_TTL, CODE_TTL = 600, 120
WAIT_MAX = 300
PAD_MAX = 256 * 1024
# The two callbacks OpenAI documents for a connector (Apps SDK, "Authentication").
DEFAULT_REDIRECT_PREFIXES = ("https://chatgpt.com/connector_platform_oauth_redirect,"
                             "https://chatgpt.com/connector/oauth/")

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
_READ_INPUT = {"type": "object",
               "properties": {"pad_bytes": {"type": "integer", "minimum": 0, "maximum": PAD_MAX,
                                            "description": "append this many bytes of filler, to measure how "
                                                           "large an answer may be"}},
               "additionalProperties": False}
TOOLS = [
    {"name": "probe_read", "title": "Probe: read",
     "description": ("Read-only. Returns this probe server's clock, how many tool calls it has answered since it "
                     "woke, how long it has been awake, how old the caller's token is, and a one-time 64-character "
                     "nonce. It touches nothing."),
     "inputSchema": _READ_INPUT,
     "annotations": {"title": "Probe: read", **_READ_ONLY}},
    {"name": "probe_wait", "title": "Probe: wait, then read",
     "description": ("Read-only. Waits the given number of seconds, then answers like probe_read. "
                     "It exists to measure how long the caller waits for a tool."),
     "inputSchema": {"type": "object",
                     "properties": {"seconds": {"type": "integer", "minimum": 0, "maximum": WAIT_MAX,
                                                "description": "how long to wait before answering"}},
                     "required": ["seconds"], "additionalProperties": False},
     "annotations": {"title": "Probe: wait, then read", **_READ_ONLY}},
    # The same tool as probe_read, published without the marking: does the marking change what the caller is asked?
    {"name": "probe_read_unmarked", "title": "Probe: read (unmarked)",
     "description": ("Does exactly what probe_read does and is just as harmless: it reads the server's clock and "
                     "touches nothing. It is published without the read-only marking on purpose."),
     "inputSchema": _READ_INPUT},
]


# ── seals: everything the server would otherwise have to remember ────────────

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def seal(key: bytes, kind: str, payload: dict, ttl: int, now: float) -> str:
    """`payload`, stamped iat/exp, readable by anyone and alterable by no one without the key.
    `kind` is under the signature, so a refresh token is not an access token."""
    body = _b64(json.dumps({**payload, "iat": int(now), "exp": int(now) + ttl},
                           separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return body + "." + _b64(hmac.new(key, f"{kind}.{body}".encode("ascii"), hashlib.sha256).digest())


def unseal(key: bytes, kind: str, token: str, now: float) -> tuple[dict | None, str]:
    """(payload, "ok"), or (None, why) with why one of malformed / bad-signature / expired."""
    try:
        body, sig = token.split(".")
        want = hmac.new(key, f"{kind}.{body}".encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(sig), want):
            return None, "bad-signature"
        payload = json.loads(_unb64(body))
    except (ValueError, UnicodeError, AttributeError):
        return None, "malformed"
    if not isinstance(payload, dict) or not isinstance(payload.get("exp"), int):
        return None, "malformed"
    return (payload, "ok") if now < payload["exp"] else (None, "expired")


class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.passcode = env.get("PROBE_PASSCODE", "")
        if len(self.passcode) < 16:
            raise SystemExit("PROBE_PASSCODE is missing or shorter than 16 characters: refusing to start")
        self.key = hashlib.sha256(b"lxm-mcp-probe seal v1\0" + self.passcode.encode("utf-8")).digest()
        # Render sets RENDER_EXTERNAL_URL; behind its proxy the request's own scheme is http.
        self.public_url = (env.get("PROBE_PUBLIC_URL") or env.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
        self.access_ttl = int(env.get("PROBE_ACCESS_TTL", "600"))
        self.refresh_ttl = int(env.get("PROBE_REFRESH_TTL", str(30 * 86400)))
        self.redirect_prefixes = tuple(p.strip() for p in
                                       env.get("PROBE_REDIRECT_PREFIXES", DEFAULT_REDIRECT_PREFIXES).split(",")
                                       if p.strip())
        for p in self.redirect_prefixes:      # "https://host" alone would also match "https://host.evil.example"
            if len(urlsplit(p).path) < 2:
                raise SystemExit(f"PROBE_REDIRECT_PREFIXES: {p!r} has no path: refusing to start")

    def base(self, request: Request) -> str:
        if self.public_url:
            return self.public_url
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
        return f"{scheme}://{request.headers.get('host', request.url.netloc)}"

    def redirect_ok(self, uri) -> bool:
        return isinstance(uri, str) and any(uri.startswith(p) for p in self.redirect_prefixes)


def _utc(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _form(raw: bytes) -> dict[str, str]:
    """An urlencoded body, last value of each name. (Starlette's own parser wants another package.)"""
    try:
        return {k: v[-1] for k, v in parse_qs(raw.decode("utf-8"), keep_blank_values=True).items()}
    except UnicodeError:
        return {}


def _oauth_error(status: int, error: str, description: str) -> JSONResponse:
    return JSONResponse({"error": error, "error_description": description}, status_code=status,
                        headers={"Cache-Control": "no-store"})


def _rpc_error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>LxM MCP probe</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem}}
input,button{{font:inherit;padding:.5rem;width:100%;box-sizing:border-box;margin-top:.5rem}}
.err{{color:#b00020}}code{{word-break:break-all}}</style></head><body>
<h1>LxM MCP probe</h1>
<p>A test server with two read-only tools. It holds no mail, no keys and no ledger.</p>
<p>Approving lets <code>{client}</code> call those tools, returning to <code>{redirect}</code>.</p>
{error}<form method="post" action="/authorize">
<input type="hidden" name="req" value="{req}">
<label>Passcode<input type="password" name="passcode" autocomplete="off" autofocus required></label>
<button type="submit">Approve</button></form></body></html>"""


def create_app(env=None, clock=time.time, sleep=asyncio.sleep) -> Starlette:
    cfg = Config(env)
    state = {"started": clock(), "calls": 0, "last_call": None, "spent": set()}

    def log(event: str, **kv) -> None:
        now = clock()
        print(json.dumps({"probe": event, "utc": _utc(now), "uptime_s": round(now - state["started"], 1), **kv},
                         ensure_ascii=False), flush=True)

    def once(token: str) -> bool:
        """False if this code or refresh token was already used in this boot."""
        mark = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if mark in state["spent"]:
            return False
        state["spent"].add(mark)
        return True

    # ── discovery ───────────────────────────────────────────────────────────

    async def status(request: Request) -> Response:
        now = clock()
        return JSONResponse({"service": SERVER_NAME, "version": SERVER_VERSION,
                             "started_utc": _utc(state["started"]), "uptime_s": round(now - state["started"], 1),
                             "tool_calls_since_boot": state["calls"],
                             "last_tool_call_utc": _utc(state["last_call"]) if state["last_call"] else None})

    async def protected_resource(request: Request) -> Response:
        base = cfg.base(request)
        return JSONResponse({"resource": f"{base}/mcp", "authorization_servers": [base],
                             "scopes_supported": [SCOPE], "bearer_methods_supported": ["header"],
                             "resource_name": SERVER_NAME})

    async def authorization_server(request: Request) -> Response:
        base = cfg.base(request)
        return JSONResponse({"issuer": base, "authorization_endpoint": f"{base}/authorize",
                             "token_endpoint": f"{base}/token", "registration_endpoint": f"{base}/register",
                             "response_types_supported": ["code"],
                             "grant_types_supported": ["authorization_code", "refresh_token"],
                             "code_challenge_methods_supported": ["S256"],
                             "token_endpoint_auth_methods_supported": ["none"],
                             "scopes_supported": [SCOPE]})

    # ── the authorization server: three endpoints and one page ──────────────

    async def register(request: Request) -> Response:
        try:
            meta = json.loads(await request.body())
        except ValueError:
            meta = None
        uris = meta.get("redirect_uris") if isinstance(meta, dict) else None
        if not isinstance(uris, list) or not uris or not all(cfg.redirect_ok(u) for u in uris):
            log("register", outcome="redirect-refused",
                redirect_uris=[str(u)[:200] for u in uris] if isinstance(uris, list) else None)
            return _oauth_error(400, "invalid_redirect_uri", "redirect_uris must all be the platform's own callbacks")
        client_id = "probe-" + secrets.token_urlsafe(9)
        log("register", outcome="ok", client=client_id, redirect_uris=[u[:200] for u in uris],
            client_name=str(meta.get("client_name"))[:80])
        return JSONResponse({"client_id": client_id, "client_id_issued_at": int(clock()), "redirect_uris": uris,
                             "client_name": meta.get("client_name"), "token_endpoint_auth_method": "none",
                             "grant_types": ["authorization_code", "refresh_token"],
                             "response_types": ["code"], "scope": SCOPE}, status_code=201)

    def page(req: str, client: str, redirect: str, error: str = "", status_code: int = 200) -> Response:
        return HTMLResponse(_PAGE.format(req=html.escape(req, quote=True), client=html.escape(client),
                                         redirect=html.escape(redirect),
                                         error=f'<p class="err">{html.escape(error)}</p>' if error else ""),
                            status_code=status_code, headers={"Cache-Control": "no-store"})

    async def authorize(request: Request) -> Response:
        q = request.query_params
        client, redirect = q.get("client_id", ""), q.get("redirect_uri", "")
        problem = ("redirect_uri is not one of the platform's callbacks" if not cfg.redirect_ok(redirect)
                   else "client_id is missing" if not client
                   else "response_type must be code" if q.get("response_type") != "code"
                   else "code_challenge with S256 is required"
                   if not q.get("code_challenge") or q.get("code_challenge_method") != "S256" else None)
        if problem:                                # never redirect to an address that was not checked
            log("authorize", outcome="refused", why=problem, redirect_uri=redirect[:200])
            return HTMLResponse(f"<p>{html.escape(problem)}</p>", status_code=400)
        req = seal(cfg.key, "authz", {"cid": client, "ru": redirect, "cc": q["code_challenge"],
                                      "st": q.get("state"), "res": q.get("resource")}, REQUEST_TTL, clock())
        log("authorize", outcome="page", client=client[:80], resource=(q.get("resource") or "")[:200])
        return page(req, client, redirect)

    async def approve(request: Request) -> Response:
        form = _form(await request.body())
        asked, why = unseal(cfg.key, "authz", form.get("req", ""), clock())
        if asked is None:
            log("approve", outcome="request-" + why)
            return HTMLResponse("<p>This approval page has expired. Start the connection again.</p>", status_code=400)
        if not hmac.compare_digest(form.get("passcode", "").encode("utf-8"), cfg.passcode.encode("utf-8")):
            await sleep(1)
            log("approve", outcome="passcode-refused", client=asked["cid"][:80])
            return page(form["req"], asked["cid"], asked["ru"], "That is not the passcode.", 403)
        code = seal(cfg.key, "code", {k: asked[k] for k in ("cid", "ru", "cc", "res")}, CODE_TTL, clock())
        back = {"code": code} | ({"state": asked["st"]} if asked.get("st") is not None else {})
        log("approve", outcome="ok", client=asked["cid"][:80])
        return RedirectResponse(asked["ru"] + ("&" if "?" in asked["ru"] else "?") + urlencode(back),
                                status_code=302, headers={"Cache-Control": "no-store"})

    def tokens(grant: dict) -> JSONResponse:
        now = clock()
        return JSONResponse({"access_token": seal(cfg.key, "access", grant, cfg.access_ttl, now),
                             "token_type": "Bearer", "expires_in": cfg.access_ttl,
                             "refresh_token": seal(cfg.key, "refresh", grant, cfg.refresh_ttl, now),
                             "scope": SCOPE}, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})

    async def token(request: Request) -> Response:
        form, now = _form(await request.body()), clock()
        kind = form.get("grant_type")
        if kind == "authorization_code":
            code, why = unseal(cfg.key, "code", form.get("code", ""), now)
            verifier = form.get("code_verifier", "")
            problem = (f"code is {why}" if code is None
                       else "client_id does not match" if form.get("client_id") != code["cid"]
                       else "redirect_uri does not match" if form.get("redirect_uri") != code["ru"]
                       else "code_verifier does not match the challenge"
                       if _b64(hashlib.sha256(verifier.encode("ascii", "replace")).digest()) != code["cc"]
                       else "code was already used" if not once(form["code"]) else None)
            if problem:
                log("token", grant="authorization_code", outcome="refused", why=problem)
                return _oauth_error(400, "invalid_grant", problem)
            resource = form.get("resource") or code.get("res") or f"{cfg.base(request)}/mcp"
            log("token", grant="authorization_code", outcome="ok", client=code["cid"][:80], resource=resource[:200])
            return tokens({"sub": "approver", "cid": code["cid"], "aud": resource, "g0": int(now), "gen": 0})
        if kind == "refresh_token":
            old, why = unseal(cfg.key, "refresh", form.get("refresh_token", ""), now)
            problem = (f"refresh_token is {why}" if old is None
                       else "client_id does not match" if form.get("client_id") not in (None, old["cid"])
                       else "refresh_token was already used" if not once(form["refresh_token"]) else None)
            if problem:
                log("token", grant="refresh_token", outcome="refused", why=problem)
                return _oauth_error(400, "invalid_grant", problem)
            log("token", grant="refresh_token", outcome="ok", client=old["cid"][:80], generation=old["gen"] + 1,
                refresh_age_s=int(now) - old["iat"], grant_age_s=int(now) - old["g0"])
            return tokens({k: old[k] for k in ("sub", "cid", "aud", "g0")} | {"gen": old["gen"] + 1})
        log("token", grant=str(kind)[:40], outcome="refused", why="unsupported grant_type")
        return _oauth_error(400, "unsupported_grant_type", "authorization_code or refresh_token")

    # ── the resource: one POST, one JSON response ───────────────────────────

    def unauthorized(request: Request, why: str) -> Response:
        challenge = f'Bearer resource_metadata="{cfg.base(request)}/.well-known/oauth-protected-resource"'
        if why != "missing":                       # a token was shown and is no good: the client should refresh
            challenge += f', error="invalid_token", error_description="access token is {why}"'
        return JSONResponse({"error": "unauthorized", "error_description": f"access token is {why}"},
                            status_code=401, headers={"WWW-Authenticate": challenge})

    def answer(claims: dict, pad: int = 0, **more) -> tuple[dict, str]:
        """(result, nonce). The nonce goes to the log too: it is how a line there is matched to what
        the model showed, and whether a model copies 64 characters faithfully is itself a question."""
        now, nonce = clock(), secrets.token_hex(32)
        state["calls"] += 1
        state["last_call"] = now
        told = {"nonce": nonce, "server_utc": _utc(now), "tool_calls_since_boot": state["calls"],
                "uptime_s": round(now - state["started"], 1), "token_age_s": int(now) - claims["iat"],
                "grant_age_s": int(now) - claims["g0"], "refresh_generation": claims["gen"], **more}
        if pad:                                    # the end is named before the filler, so a cut answer shows
            end = "#END-" + nonce[:8]
            told |= {"filler_bytes": pad, "filler_ends_with": end,
                     "filler": ("0123456789abcdef" * (pad // 16 + 1))[:max(pad - len(end), 0)] + end}
        return {"content": [{"type": "text", "text": json.dumps(told)}], "isError": False}, nonce

    async def call_tool(request: Request, params: dict, claims: dict) -> tuple[dict, dict] | None:
        """(the tool's result, what to log about it), or None for a call this server does not know how to make."""
        name, args = params.get("name"), params.get("arguments") or {}
        if name in ("probe_read", "probe_read_unmarked") and set(args) <= {"pad_bytes"}:
            pad = args.get("pad_bytes", 0)
            if type(pad) is not int or not 0 <= pad <= PAD_MAX:
                return None
            result, nonce = answer(claims, pad)
            return result, {"nonce": nonce, "pad_bytes": pad}
        if name == "probe_wait" and set(args) == {"seconds"} and type(args["seconds"]) is int \
                and 0 <= args["seconds"] <= WAIT_MAX:
            log("wait", stage="begin", seconds=args["seconds"])
            for waited in range(1, args["seconds"] + 1):
                await sleep(1)
                if await request.is_disconnected():      # the caller gave up: this is the number we are after
                    log("wait", stage="caller-gone", seconds=args["seconds"], gone_after_s=waited)
                    result, nonce = answer(claims, waited_s=waited, caller_gone=True)
                    return result, {"nonce": nonce}
            log("wait", stage="end", seconds=args["seconds"])
            result, nonce = answer(claims, waited_s=args["seconds"])
            return result, {"nonce": nonce}
        return None

    async def handle(request: Request, msg, claims: dict) -> dict | None:
        """One JSON-RPC message in, one out; None for a notification."""
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            return _rpc_error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
        method, mid = msg["method"], msg.get("id")
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        if "id" not in msg:
            return None

        def seen(**kv) -> None:                    # which revision the caller speaks is part of what we are asking
            log("rpc", method=method[:60], header_protocol=request.headers.get("mcp-protocol-version", "")[:20], **kv)

        if method == "initialize":
            asked = params.get("protocolVersion")
            seen(protocol=str(asked)[:20], client=str((params.get("clientInfo") or {}).get("name"))[:60])
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": "A probe. Two read-only tools that report the server's clock and uptime."}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": mid, "result": {}}
        if method == "tools/list":
            seen()
            return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
        if method == "tools/call":
            made = await call_tool(request, params, claims)
            seen(tool=str(params.get("name"))[:40], known=made is not None,
                 token_age_s=int(clock()) - claims["iat"], refresh_generation=claims["gen"],
                 **(made[1] if made else {}))
            if made is None:
                return _rpc_error(mid, -32602, "unknown tool or arguments")
            return {"jsonrpc": "2.0", "id": mid, "result": made[0]}
        seen(known=False)                          # e.g. a newer revision's server/discover, before it falls back
        return _rpc_error(mid, -32601, "Method not found")

    async def mcp(request: Request) -> Response:
        if request.method != "POST":               # no stream to open, no session to end
            return Response(status_code=405, headers={"Allow": "POST"})
        shown = request.headers.get("authorization", "")
        claims, why = (unseal(cfg.key, "access", shown[7:].strip(), clock())
                       if shown[:7].lower() == "bearer " else (None, "missing"))
        if claims is None:
            log("mcp", auth=why, status=401, agent=request.headers.get("user-agent", "")[:60])
            return unauthorized(request, why)
        try:
            msg = json.loads(await request.body())
        except ValueError:
            return JSONResponse(_rpc_error(None, -32700, "Parse error"), status_code=400)
        if isinstance(msg, list):
            replies = [r for m in msg if (r := await handle(request, m, claims)) is not None]
            return JSONResponse(replies) if replies else Response(status_code=202)
        reply = await handle(request, msg, claims)
        return JSONResponse(reply) if reply is not None else Response(status_code=202)

    log("boot", version=SERVER_VERSION, access_ttl_s=cfg.access_ttl, public_url=cfg.public_url or None)
    return Starlette(routes=[
        Route("/", status, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource", protected_resource, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource/mcp", protected_resource, methods=["GET"]),
        Route("/.well-known/oauth-authorization-server", authorization_server, methods=["GET"]),
        Route("/register", register, methods=["POST"]),
        Route("/authorize", authorize, methods=["GET"]),
        Route("/authorize", approve, methods=["POST"]),
        Route("/token", token, methods=["POST"]),
        Route("/mcp", mcp, methods=["GET", "POST", "DELETE"]),
    ])


def app() -> Starlette:
    """`uvicorn --factory mcp_probe.app:app` — built at start so a missing passcode stops the boot."""
    return create_app()
