"""The mail window, hosted: an approval, tokens, a log and a record in front of organum's function.

`organum.hub_front.MailFront` (0.9.0) turns one MCP request into one response and lets a caller
read the letters addressed to its lab. It leaves four things to whoever hosts it (organum
`docs/hub-mail-front-v0.md` §2): deciding who the caller is, giving it a way to read the letters,
the web server, and the record of what was read. This file is those four, for one mailbox.

Who the caller is. One person approves a connection by typing a passcode on the approval page
(JJ's decision, 2026-10-09: a passcode, one user). Whoever holds a token from that approval is the
caller `MAIL_CALLER`, whose mailbox is the letters addressed to `MAIL_RECIPIENT` behind the doors
`MAIL_DOORS`. Nobody else has a mailbox here, and the refusal is made where a person can read it:
a wrong passcode gets no code and the page says so. (A caller with a token and no mailbox gets
403 from the window, but the platform shows that as a connector with no tools and no reason —
seen in the pre-test, LxM 163 §5.)

The way to the letters is `mirror.MirrorReader`: the bucket mirror, read with an account narrowed
to the letters' prefix.

State — none that a restart loses. A free instance sleeps after fifteen idle minutes and wakes
with empty memory, so a code, an access token and a refresh token are each a payload sealed with
an HMAC whose key is derived from the passcode. Change the passcode and every token dies at once;
that is the revocation. What follows from keeping nothing:

  - A refresh token is not single-use. The platform refreshes before every tool call and each
    refresh returns a new refresh token (pre-test, LxM 156); if one of those responses is lost
    the old token comes back, and cutting it off would kill an unattended schedule. An old one
    stays good until it expires.
  - So a grant has an end of its own: MAIL_GRANT_MAX after the approval, refreshing stops and
    the connection must be approved again.
  - A code is single-use within one boot, and bound to its PKCE verifier across boots.

The record. The window opens every envelope behind a door to see whom it is for, under the
operator's permission, so each read that fetched an envelope is written to the bucket before
anything is returned: one object per read under MAIL_RECORD_PREFIX, created and never replaced.
If it cannot be written, nothing is returned (the window's own rule, §5a). An approval is
recorded the same way, and refused if it cannot be. A call that fetched nothing — a poll with a
cursor and no new mail, most calls — has no record there; like every request it leaves one JSON
line on stdout, which says who asked and when.

No line and no record carries a value a letter or a caller chose: not a body, not a cursor, not
a token, not the passcode. Names only — which method, which tool, which argument names, which
letters by door and number.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import itertools
import json
import logging
import os
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import anyio
import organum
from organum import hub_front as hf
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from .mirror import GcsStore, MirrorReader

SERVER_NAME, SERVER_VERSION = "lxm-mail-window", "0.1.0"
SCOPE = "mail.read"
REQUEST_TTL, CODE_TTL = 600, 120
PASSCODE_MIN = 24
BAD_LIMIT, BAD_WINDOW = 5, 900          # this many wrong passcodes within this many seconds pause approvals
# The two callbacks OpenAI documents for a connector (Apps SDK, "Authentication").
DEFAULT_REDIRECT_PREFIXES = ("https://chatgpt.com/connector_platform_oauth_redirect,"
                             "https://chatgpt.com/connector/oauth/")
_PAGE_HEADERS = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                 "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                                            "frame-ancestors 'none'"}


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


def seal_key(passcode: str) -> bytes:
    """The HMAC key. A token shows its own signature, so it is something to guess the passcode
    against offline; scrypt makes each guess cost what a login attempt should."""
    return hashlib.scrypt(passcode.encode("utf-8"), salt=b"lxm-mail-window seal v1", n=2 ** 14, r=8, p=1, dklen=32)


class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.passcode = env.get("MAIL_PASSCODE", "")
        if len(self.passcode) < PASSCODE_MIN:
            raise SystemExit(f"MAIL_PASSCODE is missing or shorter than {PASSCODE_MIN} characters: refusing to start")
        self.key = seal_key(self.passcode)
        self.recipient = env.get("MAIL_RECIPIENT", "")
        self.doors = tuple(d.strip() for d in env.get("MAIL_DOORS", "").split(",") if d.strip())
        try:                                    # the window's own rule for a mailbox, asked before anything is served
            hf.Grant(self.recipient, self.doors)
        except (ValueError, TypeError):
            raise SystemExit("MAIL_RECIPIENT must be lab:<name> and MAIL_DOORS a comma-separated list of "
                             "<channel>/from-<lab>: refusing to start") from None
        self.caller = env.get("MAIL_CALLER") or self.recipient.removeprefix("lab:")
        self.modern = env.get("MAIL_MODERN", "1") != "0"
        # Render sets RENDER_EXTERNAL_URL; behind its proxy the request's own scheme is http.
        self.public_url = (env.get("MAIL_PUBLIC_URL") or env.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
        self.access_ttl = int(env.get("MAIL_ACCESS_TTL", "600"))
        self.refresh_ttl = int(env.get("MAIL_REFRESH_TTL", str(30 * 86400)))
        self.grant_max = int(env.get("MAIL_GRANT_MAX", str(90 * 86400)))
        self.bucket = env.get("MAIL_BUCKET", "lxm-drop")
        self.prefix = env.get("MAIL_PREFIX", "drop-root")
        self.record_prefix = env.get("MAIL_RECORD_PREFIX", "mail-audit").strip("/")
        self.redirect_prefixes = tuple(p.strip() for p in
                                       env.get("MAIL_REDIRECT_PREFIXES", DEFAULT_REDIRECT_PREFIXES).split(",")
                                       if p.strip())
        for p in self.redirect_prefixes:      # "https://host" alone would also match "https://host.evil.example"
            if len(urlsplit(p).path) < 2:
                raise SystemExit(f"MAIL_REDIRECT_PREFIXES: {p!r} has no path: refusing to start")

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


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>LxM mail window</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem}}
input,button{{font:inherit;padding:.5rem;width:100%;box-sizing:border-box;margin-top:.5rem}}
.err{{color:#b00020}}code{{word-break:break-all}}</style></head><body>
<h1>LxM mail window</h1>
<p>Read-only. Approving lets <code>{client}</code> list and read the letters addressed to
<code>{recipient}</code>, returning to <code>{redirect}</code>. It cannot send, sign or delete.</p>
{error}{form}</body></html>"""
_FORM = """<form method="post" action="/authorize">
<input type="hidden" name="req" value="{req}">
<label>Passcode<input type="password" name="passcode" autocomplete="off" autofocus required></label>
<button type="submit">Approve</button></form>"""


def create_app(env=None, clock=time.time, sleep=asyncio.sleep, store=None) -> Starlette:
    """`store` is where the letters are read from and the record is written to; left out, it is the
    bucket MAIL_BUCKET through the account in GCS_SA_KEY_JSON."""
    env = os.environ if env is None else env
    cfg = Config(env)
    if store is None:
        if not env.get("GCS_SA_KEY_JSON"):
            raise SystemExit("GCS_SA_KEY_JSON is not set: there is no way to the letters, refusing to start")
        try:
            store = GcsStore(cfg.bucket, key_json=env["GCS_SA_KEY_JSON"])
        except (ValueError, KeyError, TypeError):   # the reason would quote the key; the name of the variable is enough
            raise SystemExit("GCS_SA_KEY_JSON is not a service-account key: refusing to start") from None
    started = clock()
    boot = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(started)) + "-" + secrets.token_hex(2)
    state = {"calls": 0, "last_call": None, "spent": set(), "bad": []}
    serial = itertools.count(1)
    with open(hf.__file__, "rb") as f:                # which window code this is, readable from outside
        front_sha = hashlib.sha256(f.read()).hexdigest()

    def log(event: str, **kv) -> None:
        now = clock()
        print(json.dumps({"window": event, "utc": _utc(now), "uptime_s": round(now - started, 1), **kv},
                         ensure_ascii=False), flush=True)

    def record(kind: str, entry: dict) -> str:
        """Write one entry to the bucket and return its name. Raises if it could not be written:
        whoever calls decides what must not happen without it."""
        now = clock()
        name = (f"{cfg.record_prefix}/{time.strftime('%Y-%m-%d', time.gmtime(now))}/"
                f"{time.strftime('%H%M%SZ', time.gmtime(now))}-{boot}-{next(serial):05d}-{kind}.json")
        data = json.dumps({"kind": kind, "window": SERVER_NAME, "version": SERVER_VERSION, "boot": boot, **entry},
                          ensure_ascii=False, sort_keys=True).encode("utf-8")
        store.write_new(name, data, timeout=10)
        return name

    def audit(entry: dict) -> None:
        """The window calls this before it returns anything it fetched. An exception here means
        the caller gets nothing."""
        log("mail-audit", record=record("read", entry), **entry)

    front = hf.MailFront(MirrorReader(store, cfg.prefix),
                         {cfg.caller: {"recipient": cfg.recipient, "doors": list(cfg.doors)}},
                         modern=cfg.modern, audit=audit)

    def once(token: str) -> bool:
        """False if this code was already used in this boot."""
        mark = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if mark in state["spent"]:
            return False
        state["spent"].add(mark)
        return True

    def paused(now: float) -> int:
        """Seconds approvals stay paused after too many wrong passcodes; 0 when they are open."""
        state["bad"] = [t for t in state["bad"] if now - t < BAD_WINDOW]
        return int(state["bad"][0] + BAD_WINDOW - now) + 1 if len(state["bad"]) >= BAD_LIMIT else 0

    def resource(request: Request) -> str:
        return f"{cfg.base(request)}/mail"

    # ── discovery ───────────────────────────────────────────────────────────

    async def status(request: Request) -> Response:
        now = clock()
        return JSONResponse({"service": SERVER_NAME, "version": SERVER_VERSION, "organum": organum.__version__,
                             "front_sha256": front_sha[:16], "modern": cfg.modern,
                             "started_utc": _utc(started), "uptime_s": round(now - started, 1),
                             "tool_calls_since_boot": state["calls"],
                             "last_tool_call_utc": _utc(state["last_call"]) if state["last_call"] else None})

    async def protected_resource(request: Request) -> Response:
        base = cfg.base(request)
        return JSONResponse({"resource": resource(request), "authorization_servers": [base],
                             "scopes_supported": [SCOPE], "bearer_methods_supported": ["header"],
                             "resource_name": "LxM mail window"})

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
        client_id = "mw-" + secrets.token_urlsafe(9)      # nothing is kept: a client is whoever passes the checks
        log("register", outcome="ok", client=client_id, redirect_uris=[u[:200] for u in uris],
            client_name=str(meta.get("client_name"))[:80])
        return JSONResponse({"client_id": client_id, "client_id_issued_at": int(clock()), "redirect_uris": uris,
                             "client_name": meta.get("client_name"), "token_endpoint_auth_method": "none",
                             "grant_types": ["authorization_code", "refresh_token"],
                             "response_types": ["code"], "scope": SCOPE}, status_code=201)

    def page(client: str, redirect: str, req: str | None, error: str = "", status_code: int = 200) -> Response:
        form = _FORM.format(req=html.escape(req, quote=True)) if req is not None else ""
        return HTMLResponse(_PAGE.format(client=html.escape(client), redirect=html.escape(redirect),
                                         recipient=html.escape(cfg.recipient), form=form,
                                         error=f'<p class="err">{html.escape(error)}</p>' if error else ""),
                            status_code=status_code, headers=_PAGE_HEADERS)

    async def authorize(request: Request) -> Response:
        q = request.query_params
        client, redirect = q.get("client_id", ""), q.get("redirect_uri", "")
        asked_for = (q.get("resource") or resource(request)).rstrip("/")
        problem = ("redirect_uri is not one of the platform's callbacks" if not cfg.redirect_ok(redirect)
                   else "client_id is missing" if not client
                   else "response_type must be code" if q.get("response_type") != "code"
                   else "code_challenge with S256 is required"
                   if not q.get("code_challenge") or q.get("code_challenge_method") != "S256"
                   else "resource is not this mail window" if asked_for != resource(request) else None)
        if problem:                                # never redirect to an address that was not checked
            log("authorize", outcome="refused", why=problem, redirect_uri=redirect[:200])
            return HTMLResponse(f"<p>{html.escape(problem)}</p>", status_code=400, headers=_PAGE_HEADERS)
        req = seal(cfg.key, "authz", {"cid": client, "ru": redirect, "cc": q["code_challenge"],
                                      "st": q.get("state")}, REQUEST_TTL, clock())
        log("authorize", outcome="page", client=client[:80])
        return page(client, redirect, req)

    async def approve(request: Request) -> Response:
        form, now = _form(await request.body()), clock()
        asked, why = unseal(cfg.key, "authz", form.get("req", ""), now)
        if asked is None:
            log("approve", outcome="request-" + why)
            return HTMLResponse("<p>This approval page has expired. Start the connection again.</p>",
                                status_code=400, headers=_PAGE_HEADERS)
        wait = paused(now)
        if wait:                                   # a right passcode is not looked at either: no answer to guess against
            log("approve", outcome="paused", client=asked["cid"][:80], seconds=wait)
            return page(asked["cid"], asked["ru"], None,
                        f"Too many wrong passcodes. Approvals are paused for {wait // 60 + 1} minutes.", 429)
        if not hmac.compare_digest(form.get("passcode", "").encode("utf-8"), cfg.passcode.encode("utf-8")):
            state["bad"].append(now)
            await sleep(1)
            log("approve", outcome="passcode-refused", client=asked["cid"][:80], recent=len(state["bad"]))
            return page(asked["cid"], asked["ru"], form["req"],
                        "That is not the passcode. Nothing was granted.", 403)
        try:                                       # a grant is the start of a standing read: it is written down first
            where = await anyio.to_thread.run_sync(record, "grant", {
                "at": _utc(now), "caller": cfg.caller, "recipient": cfg.recipient, "client": asked["cid"][:80],
                "redirect_uri": asked["ru"][:200]})
        except Exception as e:                     # noqa: BLE001 — whatever it was, nothing is granted
            log("approve", outcome="not-recorded", client=asked["cid"][:80], error=type(e).__name__)
            return page(asked["cid"], asked["ru"], form["req"],
                        "The approval could not be recorded, so nothing was granted. Try again in a minute.", 503)
        state["bad"].clear()
        code = seal(cfg.key, "code", {k: asked[k] for k in ("cid", "ru", "cc")}, CODE_TTL, now)
        back = {"code": code} | ({"state": asked["st"]} if asked.get("st") is not None else {})
        log("approve", outcome="ok", client=asked["cid"][:80], record=where)
        return RedirectResponse(asked["ru"] + ("&" if "?" in asked["ru"] else "?") + urlencode(back),
                                status_code=302, headers={"Cache-Control": "no-store"})

    def tokens(grant: dict, now: float) -> JSONResponse:
        left = grant["g0"] + cfg.grant_max - int(now)       # a refresh token does not outlive its grant
        return JSONResponse({"access_token": seal(cfg.key, "access", grant, min(cfg.access_ttl, left), now),
                             "token_type": "Bearer", "expires_in": min(cfg.access_ttl, left),
                             "refresh_token": seal(cfg.key, "refresh", grant, min(cfg.refresh_ttl, left), now),
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
                       else "resource is not this mail window"
                       if form.get("resource") and form["resource"].rstrip("/") != resource(request)
                       else "code was already used" if not once(form["code"]) else None)
            if problem:
                log("token", grant="authorization_code", outcome="refused", why=problem)
                return _oauth_error(400, "invalid_grant", problem)
            log("token", grant="authorization_code", outcome="ok", client=code["cid"][:80])
            return tokens({"sub": cfg.caller, "cid": code["cid"], "aud": resource(request),
                           "g0": int(now), "gen": 0}, now)
        if kind == "refresh_token":
            old, why = unseal(cfg.key, "refresh", form.get("refresh_token", ""), now)
            # No "already used" here, and no separate look at the grant's age: `tokens` never seals a
            # refresh token past the end of its grant, so one that is still good is inside it.
            problem = (f"refresh_token is {why}" if old is None
                       else "client_id does not match" if form.get("client_id") not in (None, old["cid"])
                       else None)
            if problem:
                log("token", grant="refresh_token", outcome="refused", why=problem)
                return _oauth_error(400, "invalid_grant", problem)
            log("token", grant="refresh_token", outcome="ok", client=old["cid"][:80], generation=old["gen"] + 1,
                refresh_age_s=int(now) - old["iat"], grant_age_s=int(now) - old["g0"])
            return tokens({k: old[k] for k in ("sub", "cid", "aud", "g0")} | {"gen": old["gen"] + 1}, now)
        log("token", grant=str(kind)[:40], outcome="refused", why="unsupported grant_type")
        return _oauth_error(400, "unsupported_grant_type", "authorization_code or refresh_token")

    # ── the resource: one POST, one JSON response ───────────────────────────

    def bearer(request: Request) -> tuple[dict | None, str]:
        shown = request.headers.get("authorization", "")
        if shown[:7].lower() != "bearer ":
            return None, "missing"
        claims, why = unseal(cfg.key, "access", shown[7:].strip(), clock())
        if claims is not None and claims.get("aud") != resource(request):
            return None, "for another resource"
        return claims, why

    def unauthorized(request: Request, why: str) -> Response:
        challenge = f'Bearer resource_metadata="{cfg.base(request)}/.well-known/oauth-protected-resource/mail"'
        if why != "missing":                       # a token was shown and is no good: the client should refresh
            challenge += f', error="invalid_token", error_description="access token is {why}"'
        return JSONResponse({"error": "unauthorized", "error_description": f"access token is {why}"},
                            status_code=401, headers={"WWW-Authenticate": challenge})

    def wire(request: Request, raw: bytes) -> dict:
        """The names of what arrived, for the log: never a value a caller chose, bar the method and tool."""
        try:
            msg = json.loads(raw)
        except ValueError:
            msg = None
        msg = msg if isinstance(msg, dict) else {}
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        h = request.headers
        seen = {"method": str(msg.get("method"))[:60], "notification": "id" not in msg,
                "header_protocol": h.get("mcp-protocol-version", "")[:20],
                "header_mcp_method": h.get("mcp-method", "")[:60] if "mcp-method" in h else None,
                "header_mcp_name": "mcp-name" in h,
                "meta_keys": sorted(str(k)[:60] for k in meta)[:8]}
        if msg.get("method") == "tools/call":
            seen |= {"tool": str(params.get("name"))[:40], "arg_names": sorted(str(k)[:20] for k in args)[:8]}
        return seen

    async def mail(request: Request) -> Response:
        claims, why = bearer(request)
        if claims is None:
            log("mail", auth=why, status=401)
            return unauthorized(request, why)
        raw, began = await request.body(), clock()
        try:                                       # a blocking function: it runs in a worker thread
            status_code, headers, out = await anyio.to_thread.run_sync(
                front.handle_http, request.method, dict(request.headers), raw, claims["sub"])
        except Exception as e:                     # noqa: BLE001 — the window must not take the service down
            log("mail", caller=claims["sub"], outcome="window-raised", error=type(e).__name__)
            status_code, headers = 500, {"Content-Type": "application/json"}
            out = json.dumps({"jsonrpc": "2.0", "error": {"code": -32603, "message": "Internal error"}}).encode()
        now, seen = clock(), wire(request, raw)
        if seen.get("tool"):
            state["calls"] += 1
            state["last_call"] = now
        log("mail", caller=claims["sub"], status=status_code, ms=int((now - began) * 1000),
            token_age_s=int(now) - claims["iat"], grant_age_s=int(now) - claims["g0"],
            refresh_generation=claims["gen"], **seen)
        return Response(out, status_code=status_code, headers=headers)

    log("boot", version=SERVER_VERSION, organum=organum.__version__, front_sha256=front_sha[:16], boot=boot,
        modern=cfg.modern, recipient=cfg.recipient, doors=list(cfg.doors), bucket=cfg.bucket, prefix=cfg.prefix,
        record_prefix=cfg.record_prefix, access_ttl_s=cfg.access_ttl, grant_max_s=cfg.grant_max,
        public_url=cfg.public_url or None)
    return Starlette(routes=[
        Route("/", status, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource", protected_resource, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource/mail", protected_resource, methods=["GET"]),
        Route("/.well-known/oauth-authorization-server", authorization_server, methods=["GET"]),
        Route("/register", register, methods=["POST"]),
        Route("/authorize", authorize, methods=["GET"]),
        Route("/authorize", approve, methods=["POST"]),
        Route("/token", token, methods=["POST"]),
        Route("/mail", mail, methods=["GET", "POST", "DELETE"]),
    ])


def app() -> Starlette:
    """`uvicorn --factory mail_window.app:app` — built at start, so a missing secret stops the boot."""
    # uvicorn's access log prints the request line, and the approval request carries its state and
    # challenge in the query string (seen in the pre-test). Our own lines are the record.
    logging.getLogger("uvicorn.access").disabled = True
    return create_app()
