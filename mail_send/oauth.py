"""The approval in front of an MCP resource: one passcode, tokens that outlive a sleeping server.

The same shape the read window runs today (`mail_window/app.py`), lifted out so the draft window
does not carry a second copy of it. The read window keeps its own until it is moved on purpose.

What it is. A platform connector discovers the resource, registers itself, sends the person to the
approval page, and comes back with a code it trades for tokens (OAuth 2.1 with PKCE). One person
approves by typing a passcode. Whoever holds a token from that approval is the caller `caller`.

State — none that a restart loses. A free instance sleeps after fifteen idle minutes and wakes with
empty memory, so a code, an access token and a refresh token are each a payload sealed with an HMAC
whose key is derived from the passcode. Change the passcode and every token dies at once; that is
the revocation. What follows from keeping nothing:

  - A refresh token is not single-use. The platform refreshes before every tool call and each
    refresh returns a new one (LxM 156); if a response is lost the old token comes back, and cutting
    it off would end an unattended schedule. An old one stays good until it expires.
  - So an approval has an end of its own: `grant_max` after it, refreshing stops.
  - A code is single-use within one boot, and bound to its PKCE verifier across boots.

A wrong passcode is refused where a person can read it, on the page, and after five of them
approvals pause for a quarter of an hour. `on_grant` is called before a code is given; if it raises,
nothing is granted — an approval that cannot be written down is not made.

The page carries no `form-action` rule: a browser holds a form's redirects to it too, and the answer
to the approval is a redirect to the platform's callback (LxM 175 §1).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
from urllib.parse import parse_qs, urlencode, urlsplit

import anyio
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

REQUEST_TTL, CODE_TTL = 600, 120
PASSCODE_MIN = 24
BAD_LIMIT, BAD_WINDOW = 5, 900          # this many wrong passcodes within this many seconds pause approvals
# The two callbacks OpenAI documents for a connector (Apps SDK, "Authentication").
DEFAULT_REDIRECT_PREFIXES = ("https://chatgpt.com/connector_platform_oauth_redirect,"
                             "https://chatgpt.com/connector/oauth/")
PAGE_HEADERS = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"}

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem}}
input,button{{font:inherit;padding:.5rem;width:100%;box-sizing:border-box;margin-top:.5rem}}
.err{{color:#b00020}}code{{word-break:break-all}}</style></head><body>
<h1>{title}</h1>
<p>{what} Approving lets <code>{client}</code> do that, returning to <code>{redirect}</code>.</p>
{error}{form}</body></html>"""
_FORM = """<form method="post" action="/authorize">
<input type="hidden" name="req" value="{req}">
<label>Passcode<input type="password" name="passcode" autocomplete="off" autofocus required></label>
<button type="submit">Approve</button></form>"""


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def seal(key: bytes, kind: str, payload: dict, ttl: int, now: float) -> str:
    """`payload`, stamped iat/exp, readable by anyone and alterable by no one without the key.
    `kind` is under the signature, so a refresh token is not an access token."""
    body = b64(json.dumps({**payload, "iat": int(now), "exp": int(now) + ttl},
                          separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return body + "." + b64(hmac.new(key, f"{kind}.{body}".encode("ascii"), hashlib.sha256).digest())


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


def seal_key(passcode: str, service: str) -> bytes:
    """The HMAC key. A token shows its own signature, so it is something to guess the passcode
    against offline; scrypt makes each guess cost what a login attempt should. The service's name is
    in the salt: the same passcode on two services does not make one's tokens good at the other."""
    return hashlib.scrypt(passcode.encode("utf-8"), salt=f"{service} seal v1".encode("utf-8"),
                          n=2 ** 14, r=8, p=1, dklen=32)


def form(raw: bytes) -> dict[str, str]:
    """An urlencoded body, last value of each name. (Starlette's own parser wants another package.)"""
    try:
        return {k: v[-1] for k, v in parse_qs(raw.decode("utf-8"), keep_blank_values=True).items()}
    except UnicodeError:
        return {}


def _oauth_error(status: int, error: str, description: str) -> JSONResponse:
    return JSONResponse({"error": error, "error_description": description}, status_code=status,
                        headers={"Cache-Control": "no-store"})


class PasscodeOAuth:
    """The authorization server and the token check for one resource at `/<path>`.

    `env` gives the public address (`<prefix>_PUBLIC_URL`, or Render's own) and the lifetimes and
    callbacks that may be overridden; `passcode` is the secret; `caller` is the name a token's holder
    is given. `on_grant(entry) -> record name` runs before a code is issued. `log(event, **names)`
    prints one line."""

    def __init__(self, *, service: str, prefix: str, env, passcode: str, path: str, scope: str, caller: str,
                 title: str, what: str, clock, sleep, log, on_grant=None, client_tag: str = "mcp"):
        if len(passcode) < PASSCODE_MIN:
            raise SystemExit(f"{prefix}_PASSCODE is missing or shorter than {PASSCODE_MIN} characters: "
                             "refusing to start")
        self.passcode, self.key = passcode, seal_key(passcode, service)
        self.path, self.scope, self.caller = path.strip("/"), scope, caller
        self.title, self.what, self.client_tag = title, what, client_tag
        self.clock, self.sleep, self.log, self.on_grant = clock, sleep, log, on_grant
        # Render sets RENDER_EXTERNAL_URL; behind its proxy the request's own scheme is http.
        self.public_url = (env.get(f"{prefix}_PUBLIC_URL") or env.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
        self.access_ttl = int(env.get(f"{prefix}_ACCESS_TTL", "600"))
        self.refresh_ttl = int(env.get(f"{prefix}_REFRESH_TTL", str(30 * 86400)))
        self.grant_max = int(env.get(f"{prefix}_GRANT_MAX", str(90 * 86400)))
        self.redirect_prefixes = tuple(p.strip() for p in
                                       env.get(f"{prefix}_REDIRECT_PREFIXES", DEFAULT_REDIRECT_PREFIXES).split(",")
                                       if p.strip())
        for p in self.redirect_prefixes:      # "https://host" alone would also match "https://host.evil.example"
            if len(urlsplit(p).path) < 2:
                raise SystemExit(f"{prefix}_REDIRECT_PREFIXES: {p!r} has no path: refusing to start")
        self._spent: set[str] = set()
        self._bad: list[float] = []

    # ── addresses ──
    def base(self, request: Request) -> str:
        if self.public_url:
            return self.public_url
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
        return f"{scheme}://{request.headers.get('host', request.url.netloc)}"

    def resource(self, request: Request) -> str:
        return f"{self.base(request)}/{self.path}"

    def _redirect_ok(self, uri) -> bool:
        return isinstance(uri, str) and any(uri.startswith(p) for p in self.redirect_prefixes)

    def _once(self, token: str) -> bool:
        """False if this code was already used in this boot."""
        mark = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if mark in self._spent:
            return False
        self._spent.add(mark)
        return True

    def _paused(self, now: float) -> int:
        """Seconds approvals stay paused after too many wrong passcodes; 0 when they are open."""
        self._bad = [t for t in self._bad if now - t < BAD_WINDOW]
        return int(self._bad[0] + BAD_WINDOW - now) + 1 if len(self._bad) >= BAD_LIMIT else 0

    # ── discovery ──
    async def _protected_resource(self, request: Request) -> Response:
        base = self.base(request)
        return JSONResponse({"resource": self.resource(request), "authorization_servers": [base],
                             "scopes_supported": [self.scope], "bearer_methods_supported": ["header"],
                             "resource_name": self.title})

    async def _authorization_server(self, request: Request) -> Response:
        base = self.base(request)
        return JSONResponse({"issuer": base, "authorization_endpoint": f"{base}/authorize",
                             "token_endpoint": f"{base}/token", "registration_endpoint": f"{base}/register",
                             "response_types_supported": ["code"],
                             "grant_types_supported": ["authorization_code", "refresh_token"],
                             "code_challenge_methods_supported": ["S256"],
                             "token_endpoint_auth_methods_supported": ["none"],
                             "scopes_supported": [self.scope]})

    # ── the authorization server: three endpoints and one page ──
    async def _register(self, request: Request) -> Response:
        try:
            meta = json.loads(await request.body())
        except ValueError:
            meta = None
        uris = meta.get("redirect_uris") if isinstance(meta, dict) else None
        if not isinstance(uris, list) or not uris or not all(self._redirect_ok(u) for u in uris):
            self.log("register", outcome="redirect-refused",
                     redirect_uris=[str(u)[:200] for u in uris] if isinstance(uris, list) else None)
            return _oauth_error(400, "invalid_redirect_uri", "redirect_uris must all be the platform's own callbacks")
        client_id = f"{self.client_tag}-" + secrets.token_urlsafe(9)   # nothing is kept: a client is whoever passes the checks
        self.log("register", outcome="ok", client=client_id, redirect_uris=[u[:200] for u in uris],
                 client_name=str(meta.get("client_name"))[:80])
        return JSONResponse({"client_id": client_id, "client_id_issued_at": int(self.clock()), "redirect_uris": uris,
                             "client_name": meta.get("client_name"), "token_endpoint_auth_method": "none",
                             "grant_types": ["authorization_code", "refresh_token"],
                             "response_types": ["code"], "scope": self.scope}, status_code=201)

    def _page(self, client: str, redirect: str, req: str | None, error: str = "", status_code: int = 200) -> Response:
        body = _PAGE.format(title=html.escape(self.title), what=html.escape(self.what),
                            client=html.escape(client), redirect=html.escape(redirect),
                            form=_FORM.format(req=html.escape(req, quote=True)) if req is not None else "",
                            error=f'<p class="err">{html.escape(error)}</p>' if error else "")
        return HTMLResponse(body, status_code=status_code, headers=PAGE_HEADERS)

    async def _authorize(self, request: Request) -> Response:
        q = request.query_params
        client, redirect = q.get("client_id", ""), q.get("redirect_uri", "")
        asked_for = (q.get("resource") or self.resource(request)).rstrip("/")
        problem = ("redirect_uri is not one of the platform's callbacks" if not self._redirect_ok(redirect)
                   else "client_id is missing" if not client
                   else "response_type must be code" if q.get("response_type") != "code"
                   else "code_challenge with S256 is required"
                   if not q.get("code_challenge") or q.get("code_challenge_method") != "S256"
                   else "resource is not this service" if asked_for != self.resource(request) else None)
        if problem:                                # never redirect to an address that was not checked
            self.log("authorize", outcome="refused", why=problem, redirect_uri=redirect[:200])
            return HTMLResponse(f"<p>{html.escape(problem)}</p>", status_code=400, headers=PAGE_HEADERS)
        req = seal(self.key, "authz", {"cid": client, "ru": redirect, "cc": q["code_challenge"],
                                       "st": q.get("state")}, REQUEST_TTL, self.clock())
        self.log("authorize", outcome="page", client=client[:80])
        return self._page(client, redirect, req)

    async def _approve(self, request: Request) -> Response:
        fields, now = form(await request.body()), self.clock()
        asked, why = unseal(self.key, "authz", fields.get("req", ""), now)
        if asked is None:
            self.log("approve", outcome="request-" + why)
            return HTMLResponse("<p>This approval page has expired. Start the connection again.</p>",
                                status_code=400, headers=PAGE_HEADERS)
        wait = self._paused(now)
        if wait:                                   # a right passcode is not looked at either: no answer to guess against
            self.log("approve", outcome="paused", client=asked["cid"][:80], seconds=wait)
            return self._page(asked["cid"], asked["ru"], None,
                              f"Too many wrong passcodes. Approvals are paused for {wait // 60 + 1} minutes.", 429)
        if not hmac.compare_digest(fields.get("passcode", "").encode("utf-8"), self.passcode.encode("utf-8")):
            self._bad.append(now)
            await self.sleep(1)
            self.log("approve", outcome="passcode-refused", client=asked["cid"][:80], recent=len(self._bad))
            return self._page(asked["cid"], asked["ru"], fields["req"],
                              "That is not the passcode. Nothing was granted.", 403)
        where = None
        if self.on_grant is not None:
            try:                                   # a grant is the start of a standing access: it is written down first
                where = await anyio.to_thread.run_sync(self.on_grant, {
                    "caller": self.caller, "client": asked["cid"][:80], "redirect_uri": asked["ru"][:200]})
            except Exception as e:                 # noqa: BLE001 — whatever it was, nothing is granted
                self.log("approve", outcome="not-recorded", client=asked["cid"][:80], error=type(e).__name__)
                return self._page(asked["cid"], asked["ru"], fields["req"],
                                  "The approval could not be recorded, so nothing was granted. "
                                  "Try again in a minute.", 503)
        self._bad.clear()
        code = seal(self.key, "code", {k: asked[k] for k in ("cid", "ru", "cc")}, CODE_TTL, now)
        back = {"code": code} | ({"state": asked["st"]} if asked.get("st") is not None else {})
        self.log("approve", outcome="ok", client=asked["cid"][:80], record=where)
        return RedirectResponse(asked["ru"] + ("&" if "?" in asked["ru"] else "?") + urlencode(back),
                                status_code=302, headers={"Cache-Control": "no-store"})

    def _tokens(self, grant: dict, now: float) -> JSONResponse:
        left = grant["g0"] + self.grant_max - int(now)       # a refresh token does not outlive its grant
        return JSONResponse({"access_token": seal(self.key, "access", grant, min(self.access_ttl, left), now),
                             "token_type": "Bearer", "expires_in": min(self.access_ttl, left),
                             "refresh_token": seal(self.key, "refresh", grant, min(self.refresh_ttl, left), now),
                             "scope": self.scope}, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})

    async def _token(self, request: Request) -> Response:
        fields, now = form(await request.body()), self.clock()
        kind = fields.get("grant_type")
        if kind == "authorization_code":
            code, why = unseal(self.key, "code", fields.get("code", ""), now)
            verifier = fields.get("code_verifier", "")
            problem = (f"code is {why}" if code is None
                       else "client_id does not match" if fields.get("client_id") != code["cid"]
                       else "redirect_uri does not match" if fields.get("redirect_uri") != code["ru"]
                       else "code_verifier does not match the challenge"
                       if b64(hashlib.sha256(verifier.encode("ascii", "replace")).digest()) != code["cc"]
                       else "resource is not this service"
                       if fields.get("resource") and fields["resource"].rstrip("/") != self.resource(request)
                       else "code was already used" if not self._once(fields["code"]) else None)
            if problem:
                self.log("token", grant="authorization_code", outcome="refused", why=problem)
                return _oauth_error(400, "invalid_grant", problem)
            self.log("token", grant="authorization_code", outcome="ok", client=code["cid"][:80])
            return self._tokens({"sub": self.caller, "cid": code["cid"], "aud": self.resource(request),
                                 "g0": int(now), "gen": 0}, now)
        if kind == "refresh_token":
            # No "already used" here, and no separate look at the grant's age: `_tokens` never seals a
            # refresh token past the end of its grant, so one that is still good is inside it.
            old, why = unseal(self.key, "refresh", fields.get("refresh_token", ""), now)
            problem = (f"refresh_token is {why}" if old is None
                       else "client_id does not match" if fields.get("client_id") not in (None, old["cid"])
                       else None)
            if problem:
                self.log("token", grant="refresh_token", outcome="refused", why=problem)
                return _oauth_error(400, "invalid_grant", problem)
            self.log("token", grant="refresh_token", outcome="ok", client=old["cid"][:80], generation=old["gen"] + 1,
                     refresh_age_s=int(now) - old["iat"], grant_age_s=int(now) - old["g0"])
            return self._tokens({k: old[k] for k in ("sub", "cid", "aud", "g0")} | {"gen": old["gen"] + 1}, now)
        self.log("token", grant=str(kind)[:40], outcome="refused", why="unsupported grant_type")
        return _oauth_error(400, "unsupported_grant_type", "authorization_code or refresh_token")

    def routes(self) -> list[Route]:
        return [
            Route("/.well-known/oauth-protected-resource", self._protected_resource, methods=["GET"]),
            Route(f"/.well-known/oauth-protected-resource/{self.path}", self._protected_resource, methods=["GET"]),
            Route("/.well-known/oauth-authorization-server", self._authorization_server, methods=["GET"]),
            Route("/register", self._register, methods=["POST"]),
            Route("/authorize", self._authorize, methods=["GET"]),
            Route("/authorize", self._approve, methods=["POST"]),
            Route("/token", self._token, methods=["POST"]),
        ]

    # ── the resource's side ──
    def bearer(self, request: Request) -> tuple[dict | None, str]:
        shown = request.headers.get("authorization", "")
        if shown[:7].lower() != "bearer ":
            return None, "missing"
        claims, why = unseal(self.key, "access", shown[7:].strip(), self.clock())
        if claims is not None and claims.get("aud") != self.resource(request):
            return None, "for another resource"
        return claims, why

    def unauthorized(self, request: Request, why: str) -> Response:
        challenge = (f'Bearer resource_metadata="{self.base(request)}/.well-known/oauth-protected-resource/'
                     f'{self.path}"')
        if why != "missing":                       # a token was shown and is no good: the client should refresh
            challenge += f', error="invalid_token", error_description="access token is {why}"'
        return JSONResponse({"error": "unauthorized", "error_description": f"access token is {why}"},
                            status_code=401, headers={"WWW-Authenticate": challenge})
