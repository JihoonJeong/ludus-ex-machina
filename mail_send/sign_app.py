"""The signing service, hosted: the pages where a person approves a letter and where the key comes in.

organum 0.10.0's `hub_send` signs and sends; `mail_send.signer` is what holds the ledger and the
key around it. This file is the web in front: who the person is, what they are shown, and which
buttons there are (`docs/hub-mail-send-v0-design.md` §4, §8).

Nothing here is for a model. There is no MCP endpoint, no token to hand a connector, and no address
a tool is told to pass on. A person comes with a passcode, reads the letter as the bytes that
arrived — not rendered, with invisible characters shown — and presses approve or reject. Approving
writes the decision and returns; the signing and the sending go on behind, and the page says where
they are.

What this service holds: the dedicated signing key (through the vault), the sender's ledger and
outbox (restored at every boot), the drop's token for that one door, and an account on the draft
store that can read drafts and create decisions and results. It is the only place that numbers this
sender's letters.

The session. A passcode of its own gives a cookie for an hour: a sealed payload like the tokens of
the read window, so a server that slept still knows it, and changing the passcode ends every
session. The cookie is `__Host-`, `Secure`, `HttpOnly`, `SameSite=Strict`. Every button carries a
token bound to the session, and a request that names another origin is refused. Five wrong
passcodes pause sign-ins for a quarter of an hour. A sign-in is written to the store before the
cookie is given; one that cannot be written is not made.

The pages carry no script and load nothing: `default-src 'none'`. A page that is waiting on
something reloads itself with a `refresh`. Their referrer policy is `same-origin`, not the
`no-referrer` of the other services' pages: under `no-referrer` a browser names no origin on a
form it posts — it sends `Origin: null` even to the page's own address — and every button here
would be refused as coming from somewhere else. (Found by pressing one in a browser; the test
client sends no `Origin` at all.)

Automatic sending (JJ, 2026-10-12). With SIGN_AUTO=1 a placed draft that may be signed is approved
by the service itself and goes out; the pages then show what went and carry the button that pauses
it. `/wake` is how a sleeping service learns there is something to look at.

One line per request on stdout, names only: the page, the draft's id, the decision, the number a
letter got. Never the letter, the passcode, a cookie, the drop's token or the key.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import html
import itertools
import json
import logging
import os
import re
import secrets
import tempfile
import threading
import time

import anyio
import organum
from organum import hub_draft as hdr
from organum import hub_front as hf
from organum import hub_send as hsd
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from . import recipients_table
from .bucket import GcsBucket
from .oauth import BAD_LIMIT, BAD_WINDOW, PASSCODE_MIN, form, seal, seal_key, unseal
from .signer import Busy, Signer
from .store import BucketDraftStore
from .vault import SecretVault, VaultError

SERVER_NAME, SERVER_VERSION = "lxm-mail-sign", "0.2.1"
SESSION_TTL = 3600
COOKIE = "__Host-sign"
POST_MAX = 65_536                       # a form here is a button, or two small records and their signatures
BACKOFF = (10, 20, 40, 80, 160, 300)    # seconds between turns while something is on its way
AUTO_LOOK = 60                          # with automatic approval on, how often an awake service looks at the store
WAKE_GAP = 5                            # a wake asked for sooner than this after the last one is the same wake
# `same-origin`: our own buttons say where they come from, and nothing is said to anyone else.
PAGE_HEADERS = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"}
_DOOR_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}/from-[a-z0-9][a-z0-9-]{0,63}\Z")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}\Z")
_ID_RE = re.compile(r"^[0-9a-f]{32}\Z")

_STYLE = """:root{color-scheme:light dark}
body{font:16px/1.5 system-ui,sans-serif;max-width:50rem;margin:1.5rem auto;padding:0 1rem}
nav{display:flex;gap:1rem;align-items:center;flex-wrap:wrap;border-bottom:1px solid #8884;padding-bottom:.5rem}
nav form{margin-left:auto}
table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:.3rem .6rem .3rem 0;vertical-align:top}
th{font-weight:600;white-space:nowrap}
code,pre{font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}code{overflow-wrap:anywhere}
pre.letter{white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid #8886;padding:1rem;margin:1rem 0}
button,input[type=password]{font:inherit;padding:.5rem .9rem}textarea{font:13px/1.4 ui-monospace,monospace;width:100%;box-sizing:border-box}
.note{border-left:4px solid #8886;padding:.3rem .8rem;margin:1rem 0}.bad{border-color:#b00020}.good{border-color:#1b7f3b}
.err{color:#b00020}.buttons{display:flex;gap:1rem;flex-wrap:wrap;margin:1.5rem 0}
.approve{font-weight:600}.quiet{opacity:.75}"""


def _utc(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def E(value, limit: int = 300) -> str:
    """Anything from a record or a request, as text on a page."""
    return html.escape(str(value)[:limit], quote=True)


def _to(draft) -> str:
    to = draft.get("to") if isinstance(draft, dict) else None
    to = to if isinstance(to, dict) else {}
    return f"{E(to.get('lab_id', '?'), 80)} / {E(to.get('to_id', '?'), 80)}"


def _config(env) -> dict:
    """What the environment must say before anything is opened. A value that is wrong stops the
    boot with the variable's name, never its content."""
    def need(name: str) -> str:
        if not env.get(name):
            raise SystemExit(f"{name} must be set: refusing to start")
        return env[name]

    passcode = env.get("SIGN_PASSCODE", "")
    if len(passcode) < PASSCODE_MIN:
        raise SystemExit(f"SIGN_PASSCODE is missing or shorter than {PASSCODE_MIN} characters: refusing to start")
    sender, recipients = need("SIGN_SENDER"), recipients_table(need("SIGN_RECIPIENTS"))
    try:
        hdr.SendGrant(sender, recipients)           # the same rule the draft window holds its table to
    except (ValueError, TypeError):
        raise SystemExit("SIGN_SENDER must be lab:<name> and SIGN_RECIPIENTS a list like lab:a=1,lab:b=1 "
                         "(each lab with its recipient epoch): refusing to start") from None
    door = need("SIGN_DOOR")
    if not _DOOR_RE.match(door):
        raise SystemExit("SIGN_DOOR must be <channel>/from-<name>: refusing to start")
    trusted = [k.strip() for k in need("SIGN_TRUSTED_PUBKEYS").split(",") if k.strip()]
    if not trusted or not all(_HEX64_RE.match(k) for k in trusted):
        raise SystemExit("SIGN_TRUSTED_PUBKEYS must be public keys of 64 hex characters, comma-separated: "
                         "refusing to start")

    def key(prefix: str, default: str | None):
        kid = env.get(f"{prefix}_KEY_ID", default or "")
        if not kid:
            return None
        epoch = env.get(f"{prefix}_KEY_EPOCH", "1")
        if not (re.fullmatch(r"[A-Za-z0-9._-]{1,32}", kid) and epoch.isdigit() and int(epoch) >= 1):
            raise SystemExit(f"{prefix}_KEY_ID and {prefix}_KEY_EPOCH must be a key's name and its epoch: "
                             "refusing to start")
        return kid, int(epoch)

    mine, recovery, retire = key("SIGN", "k3"), key("SIGN_RECOVERY", "k1"), key("SIGN_RETIRE", None)
    if len({mine, recovery, retire} - {None}) != 2 + (retire is not None):
        raise SystemExit("the signing key, the recovery key and the key to retire must be three different keys: "
                         "refusing to start")
    drop_url = need("SIGN_DROP_URL")
    if not re.match(r"^(https://|http://(127\.0\.0\.1|localhost)[:/])", drop_url + "/"):
        raise SystemExit("SIGN_DROP_URL must be an https address: refusing to start")
    daily = env.get("SIGN_AUTO_DAILY_MAX", "100")
    if not (daily.isdigit() and 1 <= int(daily) <= 10_000):
        raise SystemExit("SIGN_AUTO_DAILY_MAX must be a number from 1 to 10000: refusing to start")
    return dict(auto=env.get("SIGN_AUTO", "0") == "1", auto_daily_max=int(daily),
                passcode=passcode, sender=sender, recipients=recipients, door=door,
                drop_url=drop_url, token=env.get("SIGN_DROP_TOKEN") or None, trusted_pubkeys=trusted,
                key_id=mine[0], key_epoch=mine[1], recovery=recovery, retire=retire,
                retire_reason=env.get("SIGN_RETIRE_REASON", "rotated out")[:200],
                outbox_name=env.get("SIGN_OUTBOX_NAME", "out-hub-ops"), approver=env.get("SIGN_APPROVER", "JJ")[:60],
                received_only=env.get("SIGN_RECEIVED_ONLY", "0") == "1",
                root=env.get("SIGN_ROOT", "send").strip("/"),
                public_url=(env.get("SIGN_PUBLIC_URL") or env.get("RENDER_EXTERNAL_URL") or "").rstrip("/"))


def create_app(env=None, clock=time.time, sleep=asyncio.sleep, bucket=None, vault=None, home=None,
               background: bool = True, send_opts=None, open_opts=None) -> Starlette:
    """`bucket` is the signing account's view of the draft store and `vault` holds the key; left
    out, they are SIGN_BUCKET and SIGN_SECRET through the account in GCS_SA_KEY_JSON. `home` is an
    empty directory for this boot's ledger. With `background` off nothing runs by itself: a turn
    is taken where it is asked for (tests)."""
    env = os.environ if env is None else env
    cfg = _config(env)
    passcode, sender, root, public_url = cfg.pop("passcode"), cfg["sender"], cfg.pop("root"), cfg.pop("public_url")
    key = seal_key(passcode, SERVER_NAME)
    started = clock()
    boot = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(started)) + "-" + secrets.token_hex(2)
    serial, bad = itertools.count(1), []
    with open(hsd.__file__, "rb") as f:               # which signing code this is, readable from outside
        send_sha = hashlib.sha256(f.read()).hexdigest()

    def log(event: str, **kv) -> None:
        now = clock()
        print(json.dumps({"sign": event, "utc": _utc(now), "uptime_s": round(now - started, 1), **kv},
                         ensure_ascii=False), flush=True)

    if bucket is None or vault is None:
        if not env.get("GCS_SA_KEY_JSON"):
            raise SystemExit("GCS_SA_KEY_JSON must be set: refusing to start")
        try:
            if bucket is None:
                if not env.get("SIGN_BUCKET"):
                    raise SystemExit("SIGN_BUCKET must be set: refusing to start")
                bucket = GcsBucket(env["SIGN_BUCKET"], key_json=env["GCS_SA_KEY_JSON"])
            if vault is None:
                if not env.get("SIGN_SECRET"):
                    raise SystemExit("SIGN_SECRET must be set: refusing to start")
                vault = SecretVault(env["SIGN_SECRET"], key_json=env["GCS_SA_KEY_JSON"])
        except (ValueError, KeyError, TypeError):   # the reason would quote the key; the variables' names are enough
            raise SystemExit("GCS_SA_KEY_JSON is not a service-account key, or SIGN_SECRET is not "
                             "projects/<project>/secrets/<name>: refusing to start") from None

    def record(kind: str, entry: dict) -> str:
        """Write what was done to the store and return its name. Raises if it could not be
        written: then it is not done."""
        now = clock()
        name = (f"{root}/signer-log/{time.strftime('%Y-%m-%d', time.gmtime(now))}/"
                f"{time.strftime('%H%M%SZ', time.gmtime(now))}-{boot}-{next(serial):05d}-{kind}.json")
        bucket.write_new(name, json.dumps({"kind": kind, "service": SERVER_NAME, "version": SERVER_VERSION,
                                           "boot": boot, "at": _utc(now), "sender": sender, **entry},
                                          ensure_ascii=False, sort_keys=True).encode("utf-8"), timeout=10)
        return name

    signer = Signer(store=BucketDraftStore(bucket, root), vault=vault,
                    home=home or env.get("SIGN_HOME") or tempfile.mkdtemp(prefix="lxm-mail-sign-"),
                    clock=clock, log=log, record=record, send_opts=send_opts, open_opts=open_opts, **cfg)

    # ── the work behind the pages ──
    wake, stop = threading.Event(), threading.Event()

    def kick() -> None:
        """Ask for a turn. In the background it is taken by the one thread that touches the
        ledger; without one it is taken here."""
        if background:
            wake.set()
        else:
            signer.step()

    def work() -> None:
        delay, tries = None, 0
        while not stop.is_set():
            asked = wake.wait(timeout=delay)
            if stop.is_set():
                break
            wake.clear()
            tries = 0 if asked else tries
            try:
                more = signer.step()
            except Exception as e:                  # noqa: BLE001 — the thread must outlive whatever a turn met
                log("turn", outcome="raised", error=type(e).__name__)
                more = True
            delay = BACKOFF[min(tries, len(BACKOFF) - 1)] if more else (AUTO_LOOK if signer.auto_enabled else None)
            tries = tries + 1 if more else 0

    # ── who is asking ──
    def base(request: Request) -> str:
        if public_url:
            return public_url
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
        return f"{scheme}://{request.headers.get('host', request.url.netloc)}"

    def session_of(request: Request) -> dict | None:
        payload, _why = unseal(key, "session", request.cookies.get(COOKIE, ""), clock())
        return payload if payload and isinstance(payload.get("sid"), str) else None

    def csrf(session: dict) -> str:
        return seal(key, "csrf", {"sid": session["sid"]}, SESSION_TTL, clock())

    def too_large(request: Request) -> bool:
        length = request.headers.get("content-length", "")
        return not length.isdigit() or int(length) > POST_MAX

    def paused(now: float) -> int:
        bad[:] = [t for t in bad if now - t < BAD_WINDOW]
        return int(bad[0] + BAD_WINDOW - now) + 1 if len(bad) >= BAD_LIMIT else 0

    # ── pages ──
    def page(title: str, body: str, *, session: dict | None = None, status: int = 200, refresh: int | None = None,
             view: dict | None = None) -> Response:
        nav = ""
        if session is not None:
            nav = ('<nav><a href="/outbox">Outbox</a><a href="/key">Key and ledger</a>'
                   f'<form method="post" action="/logout"><input type="hidden" name="csrf" value="{csrf(session)}">'
                   '<button type="submit">Sign out</button></form></nav>')
        meta = f'<meta http-equiv="refresh" content="{int(refresh)}">' if refresh else ""
        doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
               f'<meta name="viewport" content="width=device-width, initial-scale=1">{meta}'
               f'<title>{E(title)}</title><style>{_STYLE}</style></head><body>{nav}<h1>{E(title)}</h1>'
               f'{banner(view) if view else ""}{body}</body></html>')
        return HTMLResponse(doc, status_code=status, headers=PAGE_HEADERS)

    def banner(view: dict) -> str:
        ledger, k = view["ledger"], view["key"]
        if ledger["state"] == "stopped" and ledger["during"] == "config":
            return f'<p class="note"><strong>Not opened.</strong> {E(ledger["detail"], 600)}.</p>'
        if ledger["state"] == "stopped":
            return (f'<p class="note bad"><strong>Stopped.</strong> {E(ledger["detail"], 600)} '
                    '<a href="/key">Look at the ledger</a>. Nothing is signed while it is stopped.</p>')
        if ledger["state"] != "open":
            return ('<p class="note">The ledger is opening: it is restored from the drop, which may be waking. '
                    'Nothing can be approved until it is open. This page reloads by itself.</p>')
        if not k["ready"]:
            return (f'<p class="note bad">Nothing can be approved yet: {E(k["why"])}. '
                    '<a href="/key">Key and ledger</a></p>')
        return ""

    def waiting_on(view: dict) -> bool:
        return view["ledger"]["state"] in ("closed", "opening")

    def said(session, title: str, message: str, status: int, back: str = "/outbox") -> Response:
        return page(title, f'<p class="err">{E(message, 600)}</p><p><a href="{E(back)}">Back</a></p>',
                    session=session, status=status)

    def guarded(handler, *, post: bool):
        """A page or a button behind the session. A button also needs the session's own token,
        and a request that names another origin is not from our pages."""
        async def wrapped(request: Request) -> Response:
            session = session_of(request)
            if session is None:
                if post:
                    log("page", route=request.url.path[:80], status=401)
                    return page("Signed out", '<p>The session has ended. <a href="/login">Sign in</a> and try again.'
                                              '</p>', status=401)
                return RedirectResponse("/login", status_code=303, headers={"Cache-Control": "no-store"})
            fields = {}
            if post:
                origin = request.headers.get("origin")
                if origin is not None and origin != base(request):
                    log("page", route=request.url.path[:80], status=403, why="origin")
                    return said(session, "Refused", "This request did not come from this service's pages.", 403)
                if too_large(request):
                    return said(session, "Refused", "That is more than this form takes.", 413)
                fields = form(await request.body())
                token, _why = unseal(key, "csrf", fields.get("csrf", ""), clock())
                if token is None or token.get("sid") != session["sid"]:
                    log("page", route=request.url.path[:80], status=403, why="csrf")
                    return said(session, "Refused", "This page is from an earlier session. Open it again.", 403)
            try:
                response = await handler(request, session, fields)
            except Busy:
                response = said(session, "In use", "The ledger is in use by a send. Try again in a minute.", 503)
            except hf.NotReady:
                response = said(session, "Not now", "The store did not answer. Try again in a minute.", 503)
            except hdr.StoreError:
                response = said(session, "Refused by the store",
                                "The draft store refused a request. Nothing was changed.", 502)
            except VaultError as e:
                response = said(session, "Refused by the vault", str(e), 502)
            except Exception as e:                  # noqa: BLE001 — a page must answer, and say nothing it met
                log("page", route=request.url.path[:80], outcome="raised", error=type(e).__name__)
                response = said(session, "Something went wrong",
                                "This page could not be made. Nothing was changed by asking for it.", 500)
            log("page", route=request.url.path[:80], method=request.method, status=response.status_code,
                session=session["sid"])
            return response
        return wrapped

    async def status(request: Request) -> Response:
        now = clock()
        return JSONResponse({"service": SERVER_NAME, "version": SERVER_VERSION, "organum": organum.__version__,
                             "send_sha256": send_sha[:16], "sender": sender, "key_id": signer.key_id,
                             "pubkey": signer.pubkey, "ledger": signer.ledger["state"],
                             "auto": signer.auto_enabled,
                             "started_utc": _utc(started), "uptime_s": round(now - started, 1)})

    last_wake = [0.0]

    async def wake_up(request: Request) -> Response:
        """Anyone may ask the service to look at the store: the draft window does, after a draft is
        placed, because a free instance sleeps and nobody is on the page. Asking tells it nothing
        and makes it do nothing it would not do by itself on its next turn."""
        now = clock()
        if now - last_wake[0] >= WAKE_GAP:
            last_wake[0] = now
            if background:
                kick()
            else:
                await anyio.to_thread.run_sync(signer.step)
        return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})

    def login_page(error: str = "", status: int = 200) -> Response:
        err = f'<p class="err">{E(error)}</p>' if error else ""
        return page("LxM mail signing", f"""<p>Letters for <code>{E(sender)}</code> are approved here, by a person,
and signed and sent after that.</p>{err}<form method="post" action="/login">
<label>Passcode <input type="password" name="passcode" autocomplete="off" autofocus required></label>
<button type="submit">Sign in</button></form>""", status=status)

    async def login(request: Request) -> Response:
        if request.method == "GET":
            return login_page()
        now = clock()
        wait = paused(now)
        if wait:                                   # a right passcode is not looked at either
            log("login", outcome="paused", seconds=wait)
            return login_page(f"Too many wrong passcodes. Sign-ins are paused for {wait // 60 + 1} minutes.", 429)
        if too_large(request):
            return login_page("That is more than this form takes.", 413)
        given = form(await request.body()).get("passcode", "")
        if not hmac.compare_digest(given.encode("utf-8"), passcode.encode("utf-8")):
            bad.append(now)
            await sleep(1)
            log("login", outcome="passcode-refused", recent=len(bad))
            return login_page("That is not the passcode.", 403)
        sid = secrets.token_hex(8)
        try:                                       # a sign-in opens the way to a signature: it is written down first
            where = await anyio.to_thread.run_sync(record, "login", {"session": sid})
        except Exception as e:                     # noqa: BLE001 — whatever it was, nobody is signed in
            log("login", outcome="not-recorded", error=type(e).__name__)
            return login_page("The sign-in could not be recorded, so it was not made. Try again in a minute.", 503)
        bad.clear()
        log("login", outcome="ok", session=sid, record=where)
        response = RedirectResponse("/outbox", status_code=303, headers={"Cache-Control": "no-store"})
        response.set_cookie(COOKIE, seal(key, "session", {"sid": sid}, SESSION_TTL, now), max_age=SESSION_TTL,
                            path="/", secure=True, httponly=True, samesite="strict")
        return response

    async def logout(request: Request, session: dict, fields: dict) -> Response:
        response = RedirectResponse("/login", status_code=303, headers={"Cache-Control": "no-store"})
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        return response

    def rows(entries: list, *, with_status: bool) -> str:
        if not entries:
            return '<p class="quiet">None.</p>'
        out = ['<table><tr><th>Placed</th><th>To</th><th>Size</th>' + ("<th>Status</th>" if with_status else "")
               + "<th></th></tr>"]
        for e in entries:
            d = e.get("draft") if isinstance(e.get("draft"), dict) else {}
            did = d.get("draft_id") if isinstance(d.get("draft_id"), str) and _ID_RE.match(d["draft_id"]) else None
            state = E(e.get("status", "?"), 30)
            if e.get("status") == "sent":
                state += f' as {E((e.get("result") or {}).get("n", "?"), 8)}'
            elif e.get("status") == "approved" and e.get("progress"):
                state += f' — {E(e["progress"].get("stage") or "on its way", 40)}'
            link = f'<a href="/draft/{did}">Read</a>' if did else ""
            out.append(f'<tr><td>{E(e.get("placed_at", "?"), 30)}</td><td>{_to(d)}</td>'
                       f'<td>{E(d.get("body_size", "?"), 12)}</td>' + (f"<td>{state}</td>" if with_status else "")
                       + f"<td>{link}</td></tr>")
        return "".join(out) + "</table>"

    async def outbox(request: Request, session: dict, fields: dict) -> Response:
        if background:
            kick()                                 # the page being opened is when a sleeping service carries on
        view = await anyio.to_thread.run_sync(signer.view)
        got: dict = {}

        async def read(name: str, fn, *args) -> None:
            try:
                got[name] = await anyio.to_thread.run_sync(fn, *args)
            except Exception as e:                  # noqa: BLE001 — kept, and raised as itself below
                got[name] = e

        async with anyio.create_task_group() as group:      # three readings of the store, side by side
            group.start_soon(read, "waiting", signer.waiting, 20)
            group.start_soon(read, "going", signer.on_the_way, 20)
            group.start_soon(read, "recent", signer.recent, 15)
            group.start_soon(read, "auto", signer.auto)
        for value in got.values():
            if isinstance(value, Exception):
                raise value                         # as the store raised it, so the page can say which it was
        waiting, going, recent, auto = got["waiting"], got["going"], got["recent"], got["auto"]
        pending = [e for e in waiting if e["status"] == "pending_approval"]
        body = automatic(auto, csrf(session), len(pending)) + (f'<h2>Waiting for a decision ({len(pending)})</h2>{rows(pending, with_status=False)}'
                f'<h2>Approved, on their way ({len(going)})</h2>{rows(going, with_status=True)}'
                f'<h2>Latest</h2>{rows(recent, with_status=True)}')
        if pending:
            body += (f'<details><summary>Reject everything that is waiting</summary>'
                     f'<form method="post" action="/reject-all"><input type="hidden" name="csrf" value="{csrf(session)}">'
                     f'<p><label><input type="checkbox" name="confirm" value="yes" required> '
                     f'Reject every draft that is waiting for a decision</label></p>'
                     f'<button type="submit">Reject all</button></form></details>')
        return page(f"Outbox of {sender}", body, session=session, view=view,
                    refresh=10 if (waiting_on(view) or going) else None)

    def automatic(auto: dict, token: str, waiting: int) -> str:
        """Where automatic sending stands, and the one button that turns it. A draft that waits is
        not held for a person: it goes out by itself once sending resumes or the day's count starts
        again (Orin 064). The page says so before the button is pressed, with how many are waiting."""
        if not auto["enabled"]:
            return ""
        count = f'{E(auto["today"], 6)} of {E(auto["max"], 6)} today'
        some = f'the {waiting} waiting below' if waiting else "whatever is waiting then"

        def button(action: str, label: str) -> str:
            return (f'<form method="post" action="/auto/{action}"><input type="hidden" name="csrf" value="{token}">'
                    f'<button type="submit">{label}</button></form>')
        if auto["paused"]:
            label = f"Resume automatic sending — sends the {waiting} waiting" if waiting else "Resume automatic sending"
            return ('<div class="note bad"><p><strong>Automatic sending is paused.</strong> Nothing goes out by '
                    f'itself now, and you can approve or reject each draft. A waiting draft is not held for good: '
                    f'<strong>resuming sends {some}</strong> without asking again. Reject first what should not go. '
                    f'({count})</p>{button("resume", label)}</div>')
        if not auto["on"]:
            return (f'<div class="note bad"><p><strong>Automatic sending has reached today\'s limit</strong> ({count}). '
                    f'The rest wait, and <strong>go out by themselves when the day turns (00:00 UTC)</strong> unless '
                    f'you reject them or pause first.</p>{button("pause", "Pause automatic sending")}</div>')
        return ('<div class="note good"><p><strong>Automatic sending is on.</strong> A letter that is placed goes out '
                f'without waiting for you. ({count})</p>{button("pause", "Pause automatic sending")}</div>')

    async def auto_switch(request: Request, session: dict, fields: dict) -> Response:
        what = request.path_params["what"]
        if what not in ("pause", "resume"):
            return said(session, "No such page", "There is no such switch.", 404)
        try:
            await anyio.to_thread.run_sync(signer.set_auto, what == "resume")
        except hsd.Refused as e:
            return said(session, "Not changed", str(e), 409)
        if what == "resume":
            if background:
                kick()
            else:
                await anyio.to_thread.run_sync(signer.step)
        return RedirectResponse("/outbox", status_code=303, headers={"Cache-Control": "no-store"})

    def facts(pairs: list) -> str:
        return "<table>" + "".join(f"<tr><th>{E(k)}</th><td>{v}</td></tr>" for k, v in pairs) + "</table>"

    async def draft(request: Request, session: dict, fields: dict) -> Response:
        did = request.path_params["draft_id"]
        if not _ID_RE.match(did):
            return said(session, "No such draft", "There is no draft under that name.", 404)
        try:
            entry = await anyio.to_thread.run_sync(signer.entry, did)
        except LookupError:
            return said(session, "No such draft", "There is no draft under that name.", 404)
        view, state = await anyio.to_thread.run_sync(signer.view), entry["status"]
        try:
            seen = await anyio.to_thread.run_sync(signer.review, did)
        except hsd.Refused as e:
            seen, why_not = None, str(e)
        except LookupError:
            seen, why_not = None, "the draft's text is not in the store"
        token = csrf(session)
        reject = (f'<form method="post" action="/draft/{did}/reject"><input type="hidden" name="csrf" '
                  f'value="{token}"><button type="submit">Reject</button></form>')
        if seen is None:
            body = (f'<p class="note bad">This draft cannot be signed: {E(why_not)}. It can only be rejected.</p>'
                    + facts([("Draft", f"<code>{did}</code>"), ("Status", E(state))])
                    + (f'<div class="buttons">{reject}</div>' if state == "pending_approval" else ""))
            return page("A draft that cannot be signed", body, session=session, view=view)
        to = seen["to"]
        pairs = [("To", f'<strong>{E(to["lab_id"], 80)} / {E(to["to_id"], 80)}</strong> (epoch {E(to["to_epoch"], 6)})'),
                 ("From", E(seen["sender"], 80)),
                 ("Kind of text", E(seen["media_type"], 60)),
                 ("Size", f'{E(seen["body_size"], 12)} bytes'),
                 ("Fingerprint", f'<code>{E(seen["body_sha256"], 64)}</code>'),
                 ("Placed", f'{E(seen["placed_at"], 30)} <span class="quiet">(the store\'s clock)</span>'),
                 ("Draft", f"<code>{did}</code>"),
                 ("Status", E(state))]
        if seen.get("client_ref"):
            pairs.insert(3, ("The sender's own mark", f'<code>{E(seen["client_ref"], 120)}</code>'))
        note = ""
        if seen["revealed"]:
            shown = ", ".join(f'{E(r["codepoint"], 10)} {E(r["name"], 40)}' for r in seen["revealed"][:8])
            note = (f'<p class="note bad">{len(seen["revealed"])} character(s) in this text cannot be seen and are '
                    f'written out below as ⟦U+…⟧: {shown}{"…" if len(seen["revealed"]) > 8 else ""}</p>')
        after = ""
        if state == "pending_approval":
            if signer.auto_enabled:
                note += ('<p class="note">This service sends by itself. If this draft is waiting because sending is '
                         'paused or over today\'s limit, it goes out without asking again once sending resumes or '
                         'the day turns. Reject it to stop it.</p>')
            approve = ('<p class="quiet">Approving is not possible right now.</p>' if not view["key"]["ready"] else
                       f'<form method="post" action="/draft/{did}/approve"><input type="hidden" name="csrf" '
                       f'value="{token}"><input type="hidden" name="body_sha256" value="{E(seen["body_sha256"], 64)}">'
                       f'<button type="submit" class="approve">Approve — sign and send to '
                       f'{E(to["lab_id"], 80)} / {E(to["to_id"], 80)}</button></form>')
            after = f'<div class="buttons">{approve}{reject}</div>'
        elif state == "approved":
            where = entry.get("progress") or {}
            after = (f'<p class="note">Approved. It is being signed and sent'
                     f'{": " + E(where.get("stage"), 40) if where.get("stage") else ""}'
                     f'{" — " + E(where.get("detail"), 300) if where.get("detail") else ""}. '
                     'This page reloads by itself.</p>')
        elif state == "sent":
            r = entry["result"]
            after = (f'<p class="note good"><strong>Sent</strong> as letter {E(r.get("n"), 8)} on '
                     f'<code>{E(r.get("door"), 80)}</code> at {E(r.get("sent_at"), 30)}.</p>')
        elif state == "failed":
            r = entry["result"]
            after = (f'<p class="note bad"><strong>Not sent.</strong> {E(r.get("reason"), 300)} '
                     f'{"No number was used." if r.get("number_used") is False else ""}</p>')
        else:
            after = f'<p class="note">This draft is {E(state)}. Nothing was sent.</p>'
        body = (facts(pairs) + note + "<h2>The letter, as it arrived</h2>"
                + f'<pre class="letter">\n{html.escape(seen["text"], quote=False)}</pre>' + after)
        return page("A draft to read", body, session=session, view=view,
                    refresh=10 if state == "approved" else None)

    async def decide(request: Request, session: dict, fields: dict) -> Response:
        did, what = request.path_params["draft_id"], request.path_params["decision"]
        if not _ID_RE.match(did) or what not in ("approve", "reject"):
            return said(session, "No such page", "There is no such draft, or no such decision.", 404)
        try:
            if what == "approve":
                await anyio.to_thread.run_sync(signer.approve, did, fields.get("body_sha256", ""))
            else:
                await anyio.to_thread.run_sync(signer.reject, did)
        except LookupError:
            return said(session, "No such draft", "There is no draft under that name.", 404)
        except hsd.Refused as e:
            return said(session, "Not decided", str(e), 409, back=f"/draft/{did}")
        if what == "approve":
            if background:
                kick()
            else:
                await anyio.to_thread.run_sync(signer.step)
        return RedirectResponse(f"/draft/{did}", status_code=303, headers={"Cache-Control": "no-store"})

    async def reject_all(request: Request, session: dict, fields: dict) -> Response:
        if fields.get("confirm") != "yes":
            return said(session, "Not done", "Tick the box to reject everything that is waiting.", 400)
        count = await anyio.to_thread.run_sync(signer.reject_all)
        log("decision", decision="rejected-all", count=count)
        return page("Rejected", f'<p>{count} draft(s) were rejected. <a href="/outbox">Back to the outbox</a></p>',
                    session=session)

    async def key_page(request: Request, session: dict, fields: dict) -> Response:
        view = await anyio.to_thread.run_sync(signer.view)
        ledger, k, token = view["ledger"], view["key"], csrf(session)
        report = ledger.get("report") or {}
        state = E(ledger["state"])
        if ledger["state"] == "open":
            state += (f' — {"restored from generation " + E(report.get("generation"), 12) if report.get("restored") else "kept from this boot"}'
                      f', {E(report.get("letters"), 8)} letters in the outbox when it was opened')
        parts = [facts([("Ledger", state), ("Door", f'<code>{E(signer.door, 140)}</code>'),
                        ("Sender", f'<code>{E(sender)}</code>')])]
        if ledger["state"] == "stopped":
            parts.append(f'<p class="note{"" if ledger["during"] == "config" else " bad"}">{E(ledger["detail"], 600)}</p>')
        unpushed = ledger["state"] == "open" and not view["pushed"]
        if unpushed:
            parts.append('<p class="note">Something in the outbox is not on the door yet. It is being put there; '
                         'this page reloads by itself.</p>')
        if ledger["state"] in ("stopped", "open") and ledger["during"] != "config":
            parts.append(f'<form method="post" action="/ledger/reopen"><input type="hidden" name="csrf" value="{token}">'
                         '<button type="submit">Clear the local copy and open again from the drop</button></form>')
        if k["bindings"]:
            parts.append("<h2>Keys the ledger holds for this sender</h2><table><tr><th>Key</th><th>Epoch</th>"
                         "<th>Public key</th><th></th></tr>" + "".join(
                             f'<tr><td>{E(b["key_id"], 32)}</td><td>{E(b["key_epoch"], 6)}</td>'
                             f'<td><code>{E(b["pubkey"], 64)}</code></td>'
                             f'<td>{"active" if b["active"] else "revoked"}</td></tr>' for b in k["bindings"])
                         + "</table>" + (f'<p class="quiet">This ledger takes the sender\'s key records from '
                                         f'{E(signer.recovery[0])} alone.</p>' if k["pinned"] else ""))
        parts.append("<h2>This service's key</h2>")
        mine, old = signer.key_id, signer.retire
        if k["pubkey"] is None:
            parts.append(f'<p>{E(k["why"] or "No key has been made.")}</p>')
            if ledger["state"] == "open" and k["vault"] == "empty":
                parts.append(f'<form method="post" action="/key/make"><input type="hidden" name="csrf" value="{token}">'
                             f'<p>The key is made here and stays here. Only its public half is shown.</p>'
                             f'<button type="submit">Make the key {E(mine)}</button></form>')
        else:
            parts.append(facts([(f"Public key of {mine}", f'<code>{E(k["pubkey"], 64)}</code>'),
                                ("In the ledger", "yes" if k["bound"] else "not yet")]))
            if k["ready"]:
                parts.append('<p class="note good">The key is in place. Approved letters are signed with it.</p>')
            elif k["conflict"]:
                parts.append(f'<p class="note bad">{E(k["why"])}. Nothing is signed.</p>')
            elif ledger["state"] == "open":
                want_rotate = not k["bound"]
                want_revoke = bool(old and k["retire"] and k["retire"]["known"] and not k["retire"]["revoked"])
                steps = ["<h2>Bringing the key in</h2><ol>"]
                links = []
                if want_rotate:
                    links.append(f'<a href="/key/rotate.json">rotate-{E(mine)}.json</a>')
                if want_revoke:
                    links.append(f'<a href="/key/revoke.json">revoke-{E(old[0])}.json</a>')
                steps.append(f'<li>Download the unsigned record(s): {" and ".join(links)}.</li>')
                steps.append(f'<li>On the device that holds {E(signer.recovery[0])}: open each file and see that it '
                             f'says what is meant — in the first, that <code>new_pubkey</code> is the public key '
                             f'above. Then sign each: <code>organum-hub sign --key &lt;the seed file of '
                             f'{E(signer.recovery[0])}&gt; --envelope &lt;the file&gt;</code></li>')
                steps.append("<li>Paste each file as it was downloaded, and what <code>sign</code> printed for it."
                             "</li></ol>")
                fields_html = []
                for which, wanted, label in (("rotate", want_rotate, f"rotate-{mine}.json"),
                                             ("revoke", want_revoke, f"revoke-{old[0]}.json" if old else "")):
                    if wanted:
                        fields_html.append(
                            f'<p><label>{E(label)}<textarea name="{which}_envelope" rows="6"></textarea></label></p>'
                            f'<p><label>What <code>sign</code> printed for it<textarea name="{which}_signature" '
                            f'rows="3"></textarea></label></p>')
                if fields_html:
                    parts.append("".join(steps) + f'<form method="post" action="/key/admit"><input type="hidden" '
                                 f'name="csrf" value="{token}">{"".join(fields_html)}'
                                 '<button type="submit">Take the signed record(s) in</button></form>')
                else:
                    parts.append(f'<p class="note bad">{E(k["why"])}.</p>')
        return page("Key and ledger", "".join(parts), session=session, view=None,
                    refresh=10 if (waiting_on(view) or unpushed) else None)

    async def key_make(request: Request, session: dict, fields: dict) -> Response:
        try:
            await anyio.to_thread.run_sync(signer.make_key)
        except hsd.Refused as e:
            return said(session, "No key was made", str(e), 409, back="/key")
        return RedirectResponse("/key", status_code=303, headers={"Cache-Control": "no-store"})

    async def key_unsigned(request: Request, session: dict, fields: dict) -> Response:
        which = request.path_params["which"]
        try:
            raw = await anyio.to_thread.run_sync(signer.unsigned, which)
        except hsd.Refused as e:
            return said(session, "No such record", str(e), 409, back="/key")
        name = f"rotate-{signer.key_id}.json" if which == "rotate" else f"revoke-{signer.retire[0]}.json"
        return Response(raw, media_type="application/json", headers={
            "Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})

    def signature_of(text: str) -> str:
        """What was pasted: the signature, or everything `organum-hub sign` printed around it."""
        text = text.strip()
        if text.startswith("{"):
            try:
                text = str(json.loads(text).get("sig", ""))
            except (ValueError, AttributeError):
                return ""
        return text

    async def key_admit(request: Request, session: dict, fields: dict) -> Response:
        given = {}
        for which in ("rotate", "revoke"):
            envelope, signature = fields.get(f"{which}_envelope", "").strip(), fields.get(f"{which}_signature", "")
            if envelope or signature.strip():
                given[which] = (envelope, signature_of(signature))
        try:
            out = await anyio.to_thread.run_sync(lambda: signer.admit_lifecycle(**given))
        except hsd.Refused as e:
            return said(session, "Not taken in", f"{e}. Nothing was changed.", 409, back="/key")
        except hsd.SendStopped as e:
            return said(session, "Stopped", str(e), 409, back="/key")
        took = "".join(f'<li>{E(which)}: letter {E(out[which]["n"], 8)}'
                       f'{" (it was already in the ledger)" if out[which]["already"] else ""}</li>'
                       for which in ("rotate", "revoke") if which in out)
        if background:                             # putting them on the door can take minutes: not this request's work
            kick()
        else:
            await anyio.to_thread.run_sync(signer.step)
        pushed = (await anyio.to_thread.run_sync(signer.view))["pushed"]
        where = ("They are on the door." if pushed else
                 "They are being put on the door now. <a href=\"/key\">Key and ledger</a> says when they are there.")
        return page("Taken in", f'<ul>{took}</ul><p>{where}</p><p><a href="/key">Key and ledger</a></p>',
                    session=session)

    async def reopen(request: Request, session: dict, fields: dict) -> Response:
        signer.ask_reopen()
        if background:
            kick()
        else:
            await anyio.to_thread.run_sync(signer.step)
        return RedirectResponse("/key", status_code=303, headers={"Cache-Control": "no-store"})

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        thread = threading.Thread(target=work, name="signer", daemon=True)
        if background:
            thread.start()
            wake.set()                             # the first turn opens the ledger
        try:
            yield
        finally:
            stop.set()
            wake.set()

    log("boot", drop_token=bool(cfg["token"]), auto=cfg["auto"], auto_daily_max=cfg["auto_daily_max"],
        version=SERVER_VERSION, organum=organum.__version__, send_sha256=send_sha[:16], boot=boot,
        sender=sender, recipients=sorted(cfg["recipients"]), door=cfg["door"], key_id=cfg["key_id"],
        recovery=cfg["recovery"][0], retire=cfg["retire"][0] if cfg["retire"] else None,
        trusted=len(cfg["trusted_pubkeys"]), received_only=cfg["received_only"], root=root,
        public_url=public_url or None)
    app = Starlette(lifespan=lifespan, routes=[
        Route("/", status, methods=["GET"]),
        Route("/wake", wake_up, methods=["GET"]),
        Route("/login", login, methods=["GET", "POST"]),
        Route("/logout", guarded(logout, post=True), methods=["POST"]),
        Route("/outbox", guarded(outbox, post=False), methods=["GET"]),
        Route("/draft/{draft_id}", guarded(draft, post=False), methods=["GET"]),
        Route("/draft/{draft_id}/{decision:str}", guarded(decide, post=True), methods=["POST"]),
        Route("/reject-all", guarded(reject_all, post=True), methods=["POST"]),
        Route("/auto/{what}", guarded(auto_switch, post=True), methods=["POST"]),
        Route("/key", guarded(key_page, post=False), methods=["GET"]),
        Route("/key/make", guarded(key_make, post=True), methods=["POST"]),
        Route("/key/admit", guarded(key_admit, post=True), methods=["POST"]),
        Route("/key/{which}.json", guarded(key_unsigned, post=False), methods=["GET"]),
        Route("/ledger/reopen", guarded(reopen, post=True), methods=["POST"]),
    ])
    app.state.signer = signer
    return app


def app() -> Starlette:
    """`uvicorn --factory mail_send.sign_app:app` — built at start, so a missing secret stops the boot."""
    logging.getLogger("uvicorn.access").disabled = True      # our own lines are the record
    return create_app()
