"""The draft window, hosted: a model places drafts here and reads what became of them. Nothing is sent here.

organum 0.10.0's `hub_draft.DraftFront` is the window; this file is the host's part
(`docs/hub-mail-send-v0-design.md` §8): who the caller is, the web app, and where the drafts go.

What this service holds, and what it does not. It holds one account's key to the draft store, an
account that can create drafts and read; it cannot write a decision or a result, so nothing that
happens here can make a draft look approved or sent (`mail_send.store`). It holds no signing key, no
ledger and no drop token. The platform calls a tool marked as writing without asking anyone, in a
chat and in a scheduled run alike (LxM 183), so placing is all a call here can do: a letter is
signed only after a person approves the exact bytes on the signing service's own page.

With DRAFT_WAKE_URL set it knocks on the signing service after a tool call: a free instance sleeps,
and with automatic sending nobody opens its page. The knock carries nothing and decides nothing.

It is a service of its own, not a path on the read window: the read window stays as it is, on the
organum it was accepted with, holding only its own account.

One line per request on stdout, names only: the method, the tool, the argument names, how large the
request was, and for a placed draft its id and whether it was new. Never a body, a recipient's name
the caller chose, a token or the passcode. An approval of a connection is written to the store's
`grants/` prefix before a code is given.
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import logging
import os
import secrets
import threading
import time
import urllib.request

import anyio
import organum
from organum import hub_draft as hdr
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from . import recipients_table
from .bucket import GcsBucket
from .oauth import PasscodeOAuth
from .store import BucketDraftStore

SERVER_NAME, SERVER_VERSION = "lxm-mail-draft", "0.2.0"
SCOPE = "mail.draft"


def _utc(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _knock(url: str) -> int:
    """Ask the signing service to look at the store. A sleeping instance takes a while to answer;
    asking is what wakes it."""
    with urllib.request.urlopen(url, timeout=100) as r:
        return r.status


def create_app(env=None, clock=time.time, sleep=asyncio.sleep, bucket=None, knock=_knock) -> Starlette:
    """`bucket` is the draft window's account on the draft store; left out, it is the bucket
    DRAFT_BUCKET through the account in GCS_SA_KEY_JSON. `knock(url)` wakes the signing service."""
    env = os.environ if env is None else env
    wake_url = env.get("DRAFT_WAKE_URL", "").strip()
    if wake_url and not (wake_url.startswith("https://") or wake_url.startswith("http://127.0.0.1")
                         or wake_url.startswith("http://localhost")):
        raise SystemExit("DRAFT_WAKE_URL must be an https address: refusing to start")
    waking = threading.Lock()
    sender = env.get("DRAFT_SENDER", "")
    try:                                        # the window's own rule for who may send to whom
        grant = hdr.SendGrant(sender, recipients_table(env.get("DRAFT_RECIPIENTS", "")))
    except (ValueError, TypeError):
        raise SystemExit("DRAFT_SENDER must be lab:<name> and DRAFT_RECIPIENTS a list like "
                         "lab:a=1,lab:b=1 (each lab with its recipient epoch): refusing to start") from None
    caller = env.get("DRAFT_CALLER") or sender.removeprefix("lab:")
    modern = env.get("DRAFT_MODERN", "1") != "0"
    root = env.get("DRAFT_ROOT", "send").strip("/")
    started = clock()
    boot = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(started)) + "-" + secrets.token_hex(2)
    state = {"calls": 0, "last_call": None}
    serial = itertools.count(1)
    with open(hdr.__file__, "rb") as f:               # which window code this is, readable from outside
        front_sha = hashlib.sha256(f.read()).hexdigest()

    def log(event: str, **kv) -> None:
        now = clock()
        print(json.dumps({"draft": event, "utc": _utc(now), "uptime_s": round(now - started, 1), **kv},
                         ensure_ascii=False), flush=True)

    def record_grant(entry: dict) -> str:
        """Write an approval of a connection to the store and return its name. Raises if it could
        not be written: then nothing is granted."""
        now = clock()
        name = (f"{root}/grants/{time.strftime('%Y-%m-%d', time.gmtime(now))}/"
                f"{time.strftime('%H%M%SZ', time.gmtime(now))}-{boot}-{next(serial):05d}-grant.json")
        bucket.write_new(name, json.dumps({"kind": "grant", "service": SERVER_NAME, "version": SERVER_VERSION,
                                           "boot": boot, "at": _utc(now), "sender": sender, **entry},
                                          ensure_ascii=False, sort_keys=True).encode("utf-8"), timeout=10)
        return name

    auth = PasscodeOAuth(
        service=SERVER_NAME, prefix="DRAFT", env=env, passcode=env.get("DRAFT_PASSCODE", ""), path="draft",
        scope=SCOPE, caller=caller, clock=clock, sleep=sleep, log=log, on_grant=record_grant, client_tag="md",
        title="LxM mail drafts",
        what=(f"Outgoing drafts for {sender}: placing a draft of a letter and seeing what became of it. "
              "Nothing is sent from here; a draft is signed and sent only after it is approved on the "
              "signing service's own page."))
    if bucket is None:
        if not env.get("GCS_SA_KEY_JSON") or not env.get("DRAFT_BUCKET"):
            raise SystemExit("GCS_SA_KEY_JSON and DRAFT_BUCKET must be set: there is nowhere to put a draft, "
                             "refusing to start")
        try:
            bucket = GcsBucket(env["DRAFT_BUCKET"], key_json=env["GCS_SA_KEY_JSON"])
        except (ValueError, KeyError, TypeError):   # the reason would quote the key; the name of the variable is enough
            raise SystemExit("GCS_SA_KEY_JSON is not a service-account key: refusing to start") from None
    front = hdr.DraftFront(BucketDraftStore(bucket, root), {caller: grant}, modern=modern)

    async def status(request: Request) -> Response:
        now = clock()
        return JSONResponse({"service": SERVER_NAME, "version": SERVER_VERSION, "organum": organum.__version__,
                             "front_sha256": front_sha[:16], "modern": modern,
                             "started_utc": _utc(started), "uptime_s": round(now - started, 1),
                             "tool_calls_since_boot": state["calls"],
                             "last_tool_call_utc": _utc(state["last_call"]) if state["last_call"] else None})

    def wire(request: Request, raw: bytes, out: bytes) -> dict:
        """The names of what arrived, for the log: never a value a caller chose, bar the method and
        tool. For a placed draft, its id and whether it was new — the id comes from the content and
        says nothing of it."""
        try:
            msg = json.loads(raw)
        except ValueError:
            msg = None
        msg = msg if isinstance(msg, dict) else {}
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        h = request.headers
        seen = {"method": str(msg.get("method"))[:60], "notification": "id" not in msg,
                "request_bytes": len(raw), "header_protocol": h.get("mcp-protocol-version", "")[:20],
                "header_mcp_name": "mcp-name" in h}
        if msg.get("method") == "tools/call":
            seen |= {"tool": str(params.get("name"))[:40], "arg_names": sorted(str(k)[:20] for k in args)[:8]}
            if params.get("name") == "mail_draft":
                try:
                    told = json.loads(json.loads(out)["result"]["content"][0]["text"])
                    seen |= {"draft_id": told.get("draft_id"), "created": told.get("created"),
                             "draft_status": told.get("status"), "body_size": told.get("body_size"),
                             "refused": "error" in told}
                except (ValueError, KeyError, IndexError, TypeError):
                    pass
        return seen

    def wake() -> None:
        """Tell the signing service there may be something to look at. This window can do no more
        than that: what is signed is decided there, by its own rules, on what is in the store. One
        knock at a time; a failed one is only logged — the draft is in the store either way."""
        if not wake_url or not waking.acquire(blocking=False):
            return

        def run() -> None:
            began = clock()
            try:
                outcome = {"status": knock(wake_url)}
            except Exception as e:                  # noqa: BLE001 — whatever it was, the draft is placed
                outcome = {"error": type(e).__name__}
            finally:
                waking.release()
            log("wake", ms=int((clock() - began) * 1000), **outcome)
        threading.Thread(target=run, name="wake", daemon=True).start()

    async def draft(request: Request) -> Response:
        claims, why = auth.bearer(request)
        if claims is None:
            log("draft", auth=why, status=401)
            return auth.unauthorized(request, why)
        raw, began = await request.body(), clock()
        try:                                       # a blocking function: it runs in a worker thread
            status_code, headers, out = await anyio.to_thread.run_sync(
                front.handle_http, request.method, dict(request.headers), raw, claims["sub"])
        except Exception as e:                     # noqa: BLE001 — the window must not take the service down
            log("draft", caller=claims["sub"], outcome="window-raised", error=type(e).__name__)
            status_code, headers = 500, {"Content-Type": "application/json"}
            out = json.dumps({"jsonrpc": "2.0", "error": {"code": -32603, "message": "Internal error"}}).encode()
        now, seen = clock(), wire(request, raw, out)
        if seen.get("tool"):
            state["calls"] += 1
            state["last_call"] = now
            if status_code == 200:                 # a draft placed, or its fate asked after: either way, look
                wake()
        log("draft", caller=claims["sub"], status=status_code, ms=int((now - began) * 1000),
            token_age_s=int(now) - claims["iat"], grant_age_s=int(now) - claims["g0"],
            refresh_generation=claims["gen"], **seen)
        return Response(out, status_code=status_code, headers=headers)

    log("boot", version=SERVER_VERSION, organum=organum.__version__, front_sha256=front_sha[:16], boot=boot,
        modern=modern, sender=sender, recipients=sorted(grant.to), root=root,
        access_ttl_s=auth.access_ttl, grant_max_s=auth.grant_max, public_url=auth.public_url or None,
        wakes_the_signer=bool(wake_url))
    return Starlette(routes=[Route("/", status, methods=["GET"]), *auth.routes(),
                             Route("/draft", draft, methods=["GET", "POST", "DELETE"])])


def app() -> Starlette:
    """`uvicorn --factory mail_send.draft_app:app` — built at start, so a missing secret stops the boot."""
    # uvicorn's access log prints the request line, and the approval request carries its state and
    # challenge in the query string. Our own lines are the record.
    logging.getLogger("uvicorn.access").disabled = True
    return create_app()
