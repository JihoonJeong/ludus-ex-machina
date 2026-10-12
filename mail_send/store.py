"""The draft store organum's sending side asks for, on objects that are only ever created.

organum 0.10.0 leaves the store to whoever hosts it (`docs/hub-mail-send-v0-design.md` §13) and
says what it must be: seven calls, nothing changed or removed once placed, and the narrowing between
the two sides held by the store's own permissions, not by the code that calls it. This is that store
on a bucket.

    <root>/drafts/<id>.body       the bytes the draft window received
    <root>/drafts/<id>.json       the draft record — written after the body, so it is the completion mark
    <root>/decisions/<id>.json    the first decision, with its kind and time as object metadata
    <root>/results/<id>.json      the first result
    <root>/decisions/_switch/…    the signing side's own switches (see `switch`): not drafts' decisions

Who may do what is the bucket's business (three managed folders, two accounts):

    the draft window's account   creates under drafts/, reads all three
    the signing side's account   reads drafts/, creates and reads under decisions/ and results/

So a draft window that is broken into, or whose key leaks, can place drafts and cannot make one look
approved or sent. What it can place past every limit the signing side looks at again (`hub_send`).

Three things this store adds to what the contract asks, all from running it (LxM 186, 187):

  - `placed_at` is the bucket's clock: when the draft record's object was made. A record may claim
    any expiry; seven days are counted from here.
  - `approved()` never looks at drafts. It lists decisions and results, the two prefixes only the
    signing side writes, and a decision's kind is in the listing itself, so drafts piled up by a
    leaked key, or a thousand rejections, cost it nothing.
  - a name that is not a draft id never becomes an object name.
  - an object under a draft's name that is not a record, or a record that names another draft than
    the one it is filed as, does not break a listing. It is passed over: one piece of junk placed
    with a leaked key must not empty the page a person decides on.
"""

from __future__ import annotations

import json
import re
import time

from organum import hub_draft as hdr

_ID_RE = re.compile(r"^[0-9a-f]{32}\Z")
_ROOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}(/[A-Za-z0-9][A-Za-z0-9._-]{0,63})*\Z")


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


class _Unreadable(hdr.StoreError):
    """An object under a record's name that is not a record. A refusal by the bucket is not this."""


class BucketDraftStore:
    """`bucket` is one account's view (`mail_send.bucket`). The draft window and the signing side each
    build this over their own account; the calls an account may not make fail in the bucket."""

    def __init__(self, bucket, root: str = "send"):
        if not _ROOT_RE.match(root):
            raise ValueError("root is a plain object path with no leading or trailing slash")
        self._b, self._root = bucket, root

    # ── names ──
    def _name(self, kind: str, draft_id: str, ext: str = "json") -> str:
        if not (isinstance(draft_id, str) and _ID_RE.match(draft_id)):
            raise LookupError("not a draft id")
        return f"{self._root}/{kind}/{draft_id}.{ext}"

    def _listed(self, kind: str) -> dict:
        """{draft id: Entry} for the records under one prefix. Anything else there is not ours."""
        prefix = f"{self._root}/{kind}/"
        return {e.name[len(prefix):-5]: e for e in self._b.names(prefix)
                if e.name.endswith(".json") and _ID_RE.match(e.name[len(prefix):-5])}

    def _json(self, name: str) -> dict:
        try:
            record = json.loads(self._b.read(name).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise _Unreadable("a stored record is not readable") from None
        if not isinstance(record, dict):
            raise _Unreadable("a stored record is not readable")
        return record

    def _entry(self, draft_id: str, placed: float, *, decided: bool | None = None,
               done: bool | None = None) -> dict:
        """One entry. `decided` and `done` say what a listing already knows, so what is known to be
        absent is not asked for."""
        def maybe(kind, known):
            if known is False:
                return None
            try:
                return self._json(self._name(kind, draft_id))
            except LookupError:
                return None
        return {"draft": self._json(self._name("drafts", draft_id)), "placed_at": _iso(placed),
                "decision": maybe("decisions", decided), "result": maybe("results", done)}

    # ── the seven ──
    def put_draft(self, record: dict, body: bytes):
        did = record["draft_id"]
        try:
            self._b.write_new(self._name("drafts", did, "body"), bytes(body))
        except FileExistsError:
            # The id comes from the body's fingerprint, so this should be the same bytes. Look: a body
            # put there by someone else under this id would otherwise surface only at the approval.
            if self._b.read(self._name("drafts", did, "body")) != bytes(body):
                raise hdr.StoreError("another body is already stored under this draft id") from None
        try:
            self._b.write_new(self._name("drafts", did), _dump(record))
            created = True
        except FileExistsError:
            created = False
        return self.get(did), created

    def get(self, draft_id: str) -> dict:
        name = self._name("drafts", draft_id)
        found = [e for e in self._b.names(name) if e.name == name]
        if not found:
            raise LookupError(draft_id)
        return self._entry(draft_id, found[0].created)

    def list(self, sender: str, limit: int, without: str | None = None) -> list:
        drafts, decided, done = self._listed("drafts"), self._listed("decisions"), self._listed("results")
        out = []
        for did in sorted(drafts, key=lambda d: (-drafts[d].created, d)):       # newest first, by the bucket's clock
            if without == "decision" and (did in decided or did in done):
                continue
            if without == "result" and did in done:
                continue
            try:
                entry = self._entry(did, drafts[did].created, decided=did in decided, done=did in done)
            except _Unreadable:
                continue                            # not a record: whoever put it there, it is not a draft
            if entry["draft"].get("draft_id") != did:
                continue                            # nor is a record that goes by another name than its own
            if entry["draft"].get("sender") == sender:
                out.append(entry)
                if len(out) >= limit:
                    break
        return out

    def body(self, draft_id: str) -> bytes:
        return self._b.read(self._name("drafts", draft_id, "body"))

    def approved(self, sender: str, limit: int) -> list:
        decided, done = self._listed("decisions"), self._listed("results")
        waiting = []
        for did, e in decided.items():
            if did in done:
                continue
            kind, when = e.meta.get("decision"), e.meta.get("decided_at", "")
            if kind is None:                        # a decision this store did not write: read it to know
                record = self._json(e.name)
                kind, when = record.get("decision"), record.get("decided_at") or ""
            if kind == "approved":
                waiting.append((when, e.created, did))
        waiting.sort()
        out = []
        for _, _, did in waiting:
            try:
                entry = self.get(did)
            except LookupError:
                continue                            # a decision with no draft: nothing to send
            if entry["draft"].get("sender") == sender:
                out.append(entry)
                if len(out) >= limit:
                    break
        return out

    def put_decision(self, record: dict) -> dict:
        return self._first("decisions", record, {"decision": record.get("decision"),
                                                 "decided_at": record.get("decided_at"),
                                                 "approver": record.get("approver")})

    def put_result(self, record: dict) -> dict:
        return self._first("results", record, {"status": record.get("status")})

    def _first(self, kind: str, record: dict, meta: dict) -> dict:
        name = self._name(kind, record["draft_id"])
        try:
            self._b.write_new(name, _dump(record), meta)
        except FileExistsError:
            pass                                    # the first one stays, and it is what the caller gets
        return self._json(name)


    # ── beside the seven: what the signing side keeps for itself ──
    def approved_on(self, day: str, approver: str) -> int:
        """How many approvals `approver` wrote on the UTC day `YYYY-MM-DD`. From the listing alone:
        a decision's kind, time and approver are its object's metadata."""
        return sum(1 for e in self._listed("decisions").values()
                   if e.meta.get("decision") == "approved" and e.meta.get("approver") == approver
                   and str(e.meta.get("decided_at") or "").startswith(day))

    def switch(self, name: str) -> str | None:
        """The last value a switch was set to, or None if it never was. A switch is a row of
        created-only records, `<root>/decisions/_switch/<name>-<when>-<value>.json`; the newest
        says where it stands. They sit under decisions/ because that is where the signing side may
        create and read and the draft window may not create: a draft window cannot turn one."""
        prefix = f"{self._root}/decisions/_switch/{name}-"
        found = sorted(m.group(1, 2) for m in (_SWITCH_RE.match(e.name[len(prefix):])
                                               for e in self._b.names(prefix)) if m)
        return found[-1][1] if found else None

    def set_switch(self, name: str, value: str, now: float) -> None:
        if not (_SWITCH_NAME_RE.match(name) and _SWITCH_NAME_RE.match(value)):
            raise ValueError("a switch and its value are short plain names")
        stamp = f"{int(now * 1000):015d}"           # milliseconds, so the names sort as time does
        self._b.write_new(f"{self._root}/decisions/_switch/{name}-{stamp}-{value}.json",
                          _dump({"kind": "switch", "name": name, "value": value, "at": _iso(now)}),
                          {"switch": name, "value": value})


_SWITCH_RE = re.compile(r"^([0-9]{15})-([a-z]{1,16})\.json\Z")
_SWITCH_NAME_RE = re.compile(r"^[a-z]{1,16}\Z")


def _dump(record: dict) -> bytes:
    return json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
