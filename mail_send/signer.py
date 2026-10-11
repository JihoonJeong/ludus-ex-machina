"""The signing side, hosted: what holds the one sender's ledger, outbox and dedicated key, and turns an
approved draft into a letter on the door.

organum 0.10.0's `hub_send` does the signing and the sending (`docs/hub-mail-send-v0-design.md` §5,
§13). This is the host's part of it, without the web: when the ledger is opened, where the key is,
what a person may be shown and may decide, and the one-time steps that bring the key in. The pages
are `mail_send.sign_app`.

What is signed here. Two things and no third: an approved `message.posted`, by `hub_send`, and the
state bundle a checkpoint puts in the drop's slot. A key record (`key.rotated`, `key.revoked`) is
never signed here — it is signed on the device that holds the recovery key, and this side only
checks it and takes it in.

A free instance wakes with an empty disk, so nothing is kept between boots but what the drop and the
draft store hold:

    open()      the ledger and outbox are restored from the drop's state slot and laid against the
                door (`hub_send.open_ledger`). Until that has happened nothing is signed.
    step()      one turn of the work: open if not open, push what is in the outbox and not on the
                door (`hub_send.drain`), then carry on every draft that is approved and has no
                result (`hub_send.resume`).
    stopped     a stop a person must look at (`hub_send.SendStopped`). It is not retried. Opening
                again clears the local copy and starts from the slot — what a restart does.

Opening is tried a few times by itself, because a sleeping drop is the usual reason it fails and
opening signs nothing. Sending is not: a stop while sending stays until someone opens again.

The key. Made here, put in the vault, read back; only its public half is ever shown. It is used once
the ledger holds it under this sender — brought in by a `key.rotated` that the recovery key signed —
and, when a key is named to retire, once that key is revoked. Until then nothing can be approved.
Before a key record is taken in, the ledger is pinned so that it takes this sender's key records
from the recovery key alone.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import secrets
import shutil
import threading
import time
from pathlib import Path

from organum import hub_draft as hdr
from organum import hub_envelope as he
from organum import hub_front as hf
from organum import hub_ops as ho
from organum import hub_send as hsd
from organum import schnorr_pure as sp

from .vault import VaultError

OPEN_TRIES = 5                  # how often opening is tried without being asked
BUSY_WAIT = 0.3                 # how long a page waits for the ledger before saying it is in use
_SIG_BYTES = 64


class Busy(Exception):
    """A send holds the ledger. Ask again shortly."""


class Signer:
    """`store` is the signing account's view of the draft store; `vault` holds the key
    (`mail_send.vault`); `home` is an empty directory of this boot. `recovery` and `retire` are
    (key id, epoch) under `sender`: the key whose signature a key record must carry, and a key to be
    revoked along with bringing the new one in (or None). `record(kind, entry)` writes a line where
    it stays; when it raises, the step it was for does not happen. `send_opts` and `open_opts` go to
    `hub_send` as they are (waits and, in tests, clocks)."""

    def __init__(self, *, store, vault, home, sender: str, recipients: dict, door: str, drop_url: str, token: str,
                 trusted_pubkeys, key_id: str = "k3", key_epoch: int = 1, recovery=("k1", 1), retire=None,
                 retire_reason: str = "rotated out", outbox_name: str = "out-hub-ops", approver: str = "JJ",
                 received_only: bool = False, clock=time.time, log=None, record=None,
                 send_opts: dict | None = None, open_opts: dict | None = None):
        self.store, self.vault = store, vault
        self.hub, self.out = Path(home) / "hub", Path(home) / outbox_name
        self.sender, self.recipients = sender, dict(recipients)
        self.door, self.drop_url, self.token = door, drop_url.rstrip("/"), token
        self.trusted = [k for k in trusted_pubkeys if k]
        self.key_id, self.key_epoch = key_id, int(key_epoch)
        self.recovery = (recovery[0], int(recovery[1]))
        self.retire = (retire[0], int(retire[1])) if retire else None
        self.retire_reason, self.outbox_name, self.approver = retire_reason, outbox_name, approver
        self.received_only, self.clock = received_only, clock
        self.log = log or (lambda event, **kv: None)
        self.record = record
        self.send_opts, self.open_opts = dict(send_opts or {}), dict(open_opts or {})
        self._lock = threading.RLock()
        self._seed, self._pub, self.vault_state = None, None, "unknown"
        self.ledger = {"state": "closed", "detail": None, "during": None, "at": clock(), "report": None}
        self.progress: dict[str, dict] = {}          # draft id -> where an approved draft is on its way
        self._open_tries, self._pushed, self._view, self._reopen = 0, False, None, False

    # ── what the calls into organum are given ──
    def _place(self) -> dict:
        return dict(hub_dir=self.hub, outbox_dir=self.out, door=self.door, drop_url=self.drop_url,
                    token=self.token, outbox_name=self.outbox_name)

    def _who(self) -> dict:
        return dict(signer=self.sender, recipients=self.recipients)

    def _trusted(self) -> list:
        """The keys a state bundle may be signed by: the ones named from outside, and this
        service's own once it has one. A key written inside a bundle is never among them."""
        return list(dict.fromkeys(self.trusted + ([self._pub] if self._pub else [])))

    def _cfg(self) -> dict:
        return dict(**self._place(), **self._who(), seed=self._seed, key_id=self.key_id,
                    key_epoch=self.key_epoch, trusted_pubkeys=self._trusted(),
                    received_only=self.received_only, now=self.clock, **self.send_opts)

    @contextlib.contextmanager
    def _held(self, wait: float | None):
        """The ledger, for one caller at a time. `wait` None waits; a number gives up as `Busy`."""
        if not (self._lock.acquire() if wait is None else self._lock.acquire(timeout=wait)):
            raise Busy()
        try:
            yield
        finally:
            self._lock.release()

    def _set(self, state: str, detail: str | None = None, *, during: str | None = None, report=None) -> None:
        self.ledger = {"state": state, "detail": detail, "during": during, "at": self.clock(), "report": report}
        self._view = None
        self.log("ledger", state=state, during=during, detail=(detail or "")[:300] or None,
                 **({k: report.get(k) for k in ("restored", "generation", "letters", "not_on_the_door")}
                    if report else {}))

    # ── the key ──
    @property
    def pubkey(self) -> str | None:
        """The public half, once a key has been read or made. It costs no call to anything."""
        return self._pub

    def _load_key(self) -> None:
        if self._seed is not None:
            return
        try:
            seed = self.vault.get()
        except hf.NotReady:
            self.vault_state = "unknown"             # not an empty vault: no key is made on this answer
            return
        except VaultError as e:
            self.vault_state = f"refused: {e}"
            return
        if seed is None:
            self.vault_state = "empty"
        else:
            self._seed, self._pub, self.vault_state = seed, sp.public_key(seed).hex(), "held"

    def make_key(self) -> str:
        """Make the key if the vault has none, and return the public key. Never a second key: an
        answer that is not "there is none" makes nothing."""
        with self._held(BUSY_WAIT):
            self._load_key()
            if self._seed is None:
                if self.vault_state != "empty":
                    raise hsd.Refused("the vault did not say it is empty; no key is made")
                if self.record:
                    self.record("key", {"event": "make", "key_id": self.key_id, "key_epoch": self.key_epoch})
                seed = self.vault.create(secrets.token_bytes(32))
                self._seed, self._pub, self.vault_state = seed, sp.public_key(seed).hex(), "held"
                self._view = None
                self.log("key", step="made", key_id=self.key_id, pubkey=self._pub)
            return self._pub

    # ── the ledger ──
    def open(self, fresh: bool = False) -> dict:
        """Open the ledger: restore it from the drop's slot if this place is empty, and lay the
        outbox against the door. `fresh` clears the local copy first — what a restart does."""
        with self._held(None):
            if fresh:
                shutil.rmtree(self.hub, ignore_errors=True)
                shutil.rmtree(self.out, ignore_errors=True)
                self._open_tries, self.progress = 0, {}
            self._set("opening")
            self._load_key()
            self._open_tries += 1
            try:
                report = hsd.open_ledger(**self._place(), trusted_pubkeys=self._trusted(),
                                         received_only=self.received_only, **self.open_opts)
            except hsd.SendStopped as e:
                self._set("stopped", str(e), during="open")
                return self.ledger
            self._pushed = not report.get("not_on_the_door")
            self._set("open", report=report)
            return self.ledger

    def ask_reopen(self) -> None:
        """Have the next turn clear the local copy and open from the slot. Opening can take
        minutes while a drop wakes, so a page asks and does not wait."""
        self._reopen = True

    def step(self) -> bool:
        """One turn. True when something is still on its way and another turn is wanted soon."""
        with self._held(None):
            if self._reopen:
                self._reopen = False
                self.open(fresh=True)
            state = self.ledger
            if state["state"] == "closed" or (state["state"] == "stopped" and state["during"] == "open"
                                              and self._open_tries < OPEN_TRIES):
                state = self.open()
            if state["state"] != "open":
                return state["during"] == "open" and self._open_tries < OPEN_TRIES
            key = self.view()["key"]
            if not key["bound"]:                     # the key that signs a bundle must be the ledger's own
                return False
            try:
                if not self._pushed:                 # signed and not on the door comes first
                    progress = hsd.drain(self.store, **self._cfg())
                    self._pushed = bool(progress["clear"])
                    self._view = None
                    if not self._pushed:
                        self.log("send", stage=progress.get("stage"), waiting=progress.get("waiting"))
                        return True
                if not key["ready"]:                 # a key record may be pushed before the next one comes in;
                    return False                     # a letter is signed only when everything is in place
                done = hsd.resume(self.store, **self._cfg())
            except hsd.SendStopped as e:
                self._set("stopped", str(e), during="send")
                return False
            except hdr.StoreError:
                self._set("stopped", "the draft store refused a request", during="store")
                return False
            except (hf.NotReady, OSError) as e:
                self.log("send", outcome="not-now", error=type(e).__name__)
                return True
            self.progress = {r["draft_id"]: {"stage": r.get("stage"), "detail": r.get("detail"), "at": self.clock()}
                             for r in done if r.get("status") == "approved"}
            for r in done:
                self.log("send", draft_id=r.get("draft_id"), status=r.get("status"), n=r.get("n"),
                         stage=r.get("stage"), number_used=r.get("number_used"))
            return bool(self.progress)

    # ── what a page is told ──
    def view(self) -> dict:
        """The ledger's state and the key's, for a page. While a send holds the ledger this is the
        last view taken, marked `busy`."""
        try:
            with self._held(BUSY_WAIT):
                if self._view is None or self.vault_state == "unknown":     # an unanswered vault is asked again
                    self._view = {"ledger": dict(self.ledger), "key": self._key_state(),
                                  "pushed": self._pushed}
                return dict(self._view, busy=False)
        except Busy:
            last = self._view or {"ledger": dict(self.ledger), "key": self._no_key("the ledger is in use"),
                                  "pushed": self._pushed}
            return dict(last, busy=True)

    def _no_key(self, why: str) -> dict:
        return {"pubkey": self._pub, "vault": self.vault_state, "bound": False, "conflict": False,
                "pinned": False, "recovery": False, "retire": None, "bindings": [], "ready": False, "why": why}

    def _key_state(self) -> dict:
        self._load_key()
        if self.ledger["state"] != "open":
            return self._no_key("the ledger is not open")
        _d, cfg, hub = ho.load_hub(self.hub)
        nxt = hub.log.tree_size + 1
        rows = sorted(hub.keys.bindings_of(self.sender), key=lambda b: (b["valid_from_seq"], b["key_id"]))
        for b in rows:
            b["active"] = b["revoked_at_seq"] is None and b["valid_from_seq"] <= nxt
        at = {(b["key_id"], b["key_epoch"]): b for b in rows}
        mine, rec = at.get((self.key_id, self.key_epoch)), at.get(self.recovery)
        out = self._no_key(None)
        out["bindings"] = [{k: b[k] for k in ("key_id", "key_epoch", "pubkey", "valid_from_seq",
                                               "revoked_at_seq", "active")} for b in rows]
        out["recovery"] = bool(rec and rec["active"])
        same = bool(mine and self._pub and mine["pubkey"] == self._pub)
        out["bound"] = bool(same and mine["active"])
        out["conflict"] = bool(mine and not same)
        out["pinned"] = any((p.get("signer_id"), p.get("key_id"), p.get("key_epoch")) == (self.sender, *self.recovery)
                            for p in cfg.get("lifecycle_pins") or [])
        if self.retire:
            old = at.get(self.retire)
            out["retire"] = {"key_id": self.retire[0], "key_epoch": self.retire[1], "known": old is not None,
                             "revoked": bool(old and old["revoked_at_seq"] is not None)}
        if self._pub is None:
            out["why"] = "no key has been made" if self.vault_state == "empty" else f"the vault: {self.vault_state}"
        elif out["conflict"]:
            out["why"] = f"the ledger holds another key as {self.key_id}"
        elif not out["bound"]:
            out["why"] = (f"{self.key_id} was revoked in the ledger" if mine and mine["revoked_at_seq"] is not None
                          else f"{self.key_id} is not in the ledger yet")
        elif out["retire"] and not out["retire"]["revoked"]:
            out["why"] = (f"{self.retire[0]} is to be revoked first" if out["retire"]["known"]
                          else f"the key to retire, {self.retire[0]}, is not in the ledger")
        else:
            out["ready"] = True
        return out

    # ── drafts: what a person sees and decides. These touch the store, not the ledger ──
    def status(self, entry: dict) -> str:
        try:
            return hdr.status_of(entry, self.clock(), hdr.DRAFT_TTL_SECONDS)
        except (KeyError, TypeError, ValueError):
            return "malformed"

    def waiting(self, limit: int = 20) -> list:
        """Drafts with no decision, newest first, each with its status (waiting, or run out)."""
        return [dict(e, status=self.status(e)) for e in self.store.list(self.sender, limit, without="decision")]

    def on_the_way(self, limit: int = 20) -> list:
        """Approved and without a result, oldest approval first, each with where it last was."""
        return [dict(e, status=self.status(e), progress=self.progress.get(e["draft"]["draft_id"]))
                for e in self.store.approved(self.sender, limit)]

    def recent(self, limit: int = 20) -> list:
        return [dict(e, status=self.status(e), progress=self.progress.get((e.get("draft") or {}).get("draft_id")))
                for e in self.store.list(self.sender, limit)]

    def entry(self, draft_id: str) -> dict:
        e = self.store.get(draft_id)
        return dict(e, status=self.status(e), progress=self.progress.get(draft_id))

    def review(self, draft_id: str) -> dict:
        """What the approval page must show (`hub_send.review`). `Refused` when the draft is not
        one that may be signed: such a draft can only be rejected."""
        return hsd.review(self.store, draft_id, **self._who(), now=self.clock)

    def approve(self, draft_id: str, body_sha256: str) -> dict:
        """Write the approval, bound to the fingerprint the person was shown. Nothing can be
        approved before the key is in place: an approval lasts a day and would run out waiting."""
        view = self.view()
        if not view["key"]["ready"]:
            raise hsd.Refused("nothing can be approved yet: " + (view["key"]["why"] or "the service is not ready"))
        d = hsd.decide(self.store, draft_id, "approved", approver=self.approver, body_sha256=body_sha256,
                       **self._who(), now=self.clock)
        self.log("decision", draft_id=draft_id, decision="approved")
        return d

    def reject(self, draft_id: str) -> dict:
        d = hsd.decide(self.store, draft_id, "rejected", approver=self.approver, **self._who(), now=self.clock)
        self.log("decision", draft_id=draft_id, decision="rejected")
        return d

    def reject_all(self, limit: int = 200) -> int:
        """Reject every draft that is waiting — for a store someone has filled. Returns how many."""
        count, seen = 0, set()
        while count < limit:
            todo = [e["draft"]["draft_id"] for e in self.waiting(50)
                    if e["status"] == "pending_approval" and e["draft"]["draft_id"] not in seen]
            if not todo:
                break
            for did in todo:
                seen.add(did)
                try:
                    self.reject(did)
                    count += 1
                except (hsd.Refused, LookupError):
                    pass
        return count

    # ── bringing the key in: records the recovery key signs somewhere else ──
    def _need(self) -> None:
        if self.ledger["state"] != "open":
            raise hsd.Refused("the ledger is not open")
        if self._pub is None:
            raise hsd.Refused("no key has been made")

    def _lifecycle_env(self, cfg: dict, which: str, created_at: str | None = None) -> dict:
        """The record as `organum-hub rotate-key` / `revoke-key … --unsigned-out` builds it."""
        subject = {"type": "machine", "id": "machine:" + cfg["machine_id"]}
        if which == "rotate":
            kind, payload = "key.rotated", {"new_key_id": self.key_id, "new_key_epoch": self.key_epoch,
                                            "new_pubkey": self._pub}
        elif which == "revoke" and self.retire:
            kind, payload = "key.revoked", {"key_id": self.retire[0], "key_epoch": self.retire[1],
                                            "reason": self.retire_reason}
        else:
            raise hsd.Refused("there is no such record to make")
        return ho.build_envelope(cfg, kind, payload, signer=self.sender, key_id=self.recovery[0],
                                 epoch=self.recovery[1], subject=subject, created_at=created_at)

    def unsigned(self, which: str) -> bytes:
        """The unsigned record to carry to the device that holds the recovery key. The ledger is
        not touched. Each call stamps its own time, so the record comes back with its signature."""
        with self._held(BUSY_WAIT):
            self._need()
            _d, cfg, _hub = ho.load_hub(self.hub)
            return he.canonical_bytes(self._lifecycle_env(cfg, which))

    def admit_lifecycle(self, rotate=None, revoke=None) -> dict:
        """Take in the signed records: `rotate` and `revoke` are each (the record's text, the
        signature in hex) or None. Each must be the record this service gives out, to the letter
        but for its time, and carry the recovery key's signature. Both are checked before either is
        taken. Then: pin, take in, and place in the outbox — the new key first. Putting them on the
        door is the next turn's work (`step`): it can take minutes, and a page does not wait for it."""
        with self._held(BUSY_WAIT):
            self._need()
            _d, cfg, hub = ho.load_hub(self.hub)
            todo = []
            for which, given in (("rotate", rotate), ("revoke", revoke)):
                if given is None:
                    continue
                try:
                    env = json.loads(given[0])
                    sig = bytes.fromhex(given[1].strip())
                except (ValueError, AttributeError):
                    raise hsd.Refused(f"the {which} record or its signature could not be read") from None
                if not isinstance(env, dict) or len(sig) != _SIG_BYTES:
                    raise hsd.Refused(f"the {which} record or its signature could not be read")
                if env != self._lifecycle_env(cfg, which, created_at=env.get("created_at")):
                    raise hsd.Refused(f"the {which} record is not the one this service gives out")
                pub = ho.registry_pubkey_for(hub, env["signer"])
                if pub is None:
                    raise hsd.Refused("the recovery key is not an active key in the ledger")
                raw = he.canonical_bytes(env)
                try:
                    good = sp.verify(sig, hashlib.sha256(raw).digest(), bytes.fromhex(pub))
                except (ValueError, TypeError):
                    good = False
                if not good:
                    raise hsd.Refused(f"the signature on the {which} record is not the recovery key's")
                todo.append((which, raw, sig.hex(), pub))
            if not todo:
                raise hsd.Refused("no record was given")
            key = self._key_state()
            if key["conflict"]:                      # known before anything is touched: not a new stop
                raise hsd.Refused(key["why"])
            if todo[0][0] == "revoke" and not key["bound"]:
                raise hsd.Refused("the new key comes in first")
            if self.record:
                self.record("lifecycle", {w: hashlib.sha256(raw).hexdigest() for w, raw, _s, _p in todo})
            out: dict = {}
            with ho.hub_write_lock(self.hub, name=hsd.SEND_LOCK):
                # From here this ledger takes the sender's key records from the recovery key alone.
                pin = ho.pin_lifecycle(self.hub, signer=self.sender, key_id=self.recovery[0], epoch=self.recovery[1])
                out["pinned_from_seq"] = pin["pinned"]["from_seq"]
                for which, raw, sig, pub in todo:
                    with ho.hub_writer(self.hub) as (d, _cfg, hub):
                        r = ho.admit_and_log(d, hub, raw, sig, pub)
                    if not r["admitted"]:
                        self._set("stopped", f"the ledger did not take the {which} record: {r.get('problems')}",
                                  during="key")
                        raise hsd.SendStopped(self.ledger["detail"])
                    out[which] = {"event_id": r["event_id"], "already": bool(r["duplicate"])}
                with ho.hub_write_lock(self.hub):
                    placed = self._placed()
                    for which, _raw, _sig, _pub in todo:
                        eid = out[which]["event_id"]
                        out[which]["n"] = placed.get(eid) or ho.export_quad(self.hub, self.out, event_id=eid)["nnn"]
            self._view, self._pushed = None, False
            self.log("key", step="taken-in", **{w: out[w]["n"] for w, *_ in todo})
            return out

    def _placed(self) -> dict:
        """Event id -> number, for what is complete in the outbox."""
        found = {}
        if self.out.is_dir():
            for f in self.out.glob("*-envelope.json"):
                if ho.quad_number(f.name) is not None:
                    found[he.event_id_of(f.read_bytes())] = f.name.split("-", 1)[0]
        return found
