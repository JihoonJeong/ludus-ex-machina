"""The signing side holds a key that speaks for a lab, so what it does with it is pinned end to end.

The world these tests stand up is the one the service will meet on its first day, with made-up keys:
a lab whose ledger was kept somewhere else, with a recovery key (k1) and a working key (k2) that
signed its letters and its last state bundle; a drop with that bundle in the lab's slot and the
letters on its door; a draft store on a bucket that can only create; and a signing service that
wakes with an empty disk and an empty vault. organum's own server is the drop, on 127.0.0.1.

What is pinned:

  - nothing is signed, and nothing can be approved, before the ledger is open and the key is in it;
  - the key is made once, and an unanswered vault makes none;
  - a key record is taken only if it is the one the service gives out and the recovery key signed it,
    the new key comes in before the old one goes, and the two land on the door as the next two numbers;
  - after that an approved draft becomes the next letter, signed by the new key, and a disk that
    vanished between the approval and the letter costs nothing;
  - a stop while sending stays stopped until someone opens again.

These tests need organum 0.10.0; the environment the drop's own tests run in has 0.8.0, where they
are skipped.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path

import pytest

hdr = pytest.importorskip("organum.hub_draft")

from organum import hub_drop as hd  # noqa: E402
from organum import hub_envelope as he  # noqa: E402
from organum import hub_front as hf  # noqa: E402
from organum import hub_ops as ho  # noqa: E402
from organum import hub_send as hsd  # noqa: E402
from organum import hub_state as hs  # noqa: E402
from organum import schnorr_pure as sp  # noqa: E402

from mail_send.bucket import MemoryBucket  # noqa: E402
from mail_send.signer import Busy, Signer  # noqa: E402
from mail_send.store import BucketDraftStore  # noqa: E402
from mail_send.vault import MemoryVault, SecretVault, VaultError  # noqa: E402

SEED1, SEED2, SEED9 = (3).to_bytes(32, "big"), (5).to_bytes(32, "big"), (9).to_bytes(32, "big")     # TESTONLY
PUB1, PUB2 = sp.public_key(SEED1).hex(), sp.public_key(SEED2).hex()
LAB, TO, DOOR, TOKEN, OUTBOX = "lab:testonly", "lab:receiver", "hub-ops/from-testonly", "tok-test", "out-hub-ops"
RECIPIENTS = {TO: 1}
T0 = 1_791_504_000.0                        # 2026-10-09T00:00:00Z
FAST = dict(wait=0, mirror_wait=0, sleep=lambda s: None, timeout=5)
FAST_OPEN = dict(wait=0, sleep=lambda s: None, timeout=5)


class Clock:
    def __init__(self, t: float = T0):
        self.t = t

    def __call__(self) -> float:
        self.t += 1
        return self.t


class World:
    """A lab's ledger kept elsewhere, its bundle and letters on a drop, a draft store, and a
    signing service about to wake."""

    def __init__(self, tmp: Path, letters: int = 3, retire=("k2", 1), on_door: int | None = None):
        self.tmp, self.clock = tmp, Clock()
        self.root = tmp / "srv"
        self.root.mkdir()
        (self.root / "tokens.txt").write_text(f"{TOKEN}  id=testonly\n")
        self.srv = hd.make_server(self.root / "drops", self.root / "tokens.txt", bind="127.0.0.1", port=0,
                                  rate_limit_per_minute=0, state_dir=self.root / "state")
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self._elsewhere(letters, letters if on_door is None else on_door)
        self.bucket = MemoryBucket(self.clock)
        self.wstore = BucketDraftStore(self.bucket.account("window", read=("send/",), create=("send/drafts/",)))
        self.sstore = BucketDraftStore(self.bucket.account(
            "signer", read=("send/",), create=("send/decisions/", "send/results/")))
        self.front = hdr.DraftFront(self.wstore, {"jdot": {"sender": LAB, "to": RECIPIENTS}}, now=self.clock)
        self.vault, self.lines, self.records, self.boots = MemoryVault(), [], [], 0
        self.retire = retire
        self.signer = self.boot()

    def _elsewhere(self, letters: int, on_door: int) -> None:
        """Where the lab's ledger lived before: k1 from the start, k2 brought in by k1, letters
        signed by k2, a bundle signed by k2 in the slot, the letters on the door (the first
        `on_door` of them: the rest were signed and bundled and never pushed)."""
        hub, out = self.tmp / "elsewhere" / "hub", self.tmp / "elsewhere" / OUTBOX
        hub.mkdir(parents=True)
        cfg = {"source_domain": f"{LAB}/hub", "machine_id": "m-elsewhere", "claims": {"claims": {}},
               "claims_sha256": he.canonical_sha({"claims": {}}),
               "keys": [{"pubkey": PUB1, "signer_id": LAB, "key_id": "k1", "key_epoch": 1}]}
        (hub / "hub.json").write_text(json.dumps(cfg))
        (hub / "events.jsonl").write_bytes(b"")
        with ho.hub_writer(hub) as (d, c, h):
            env = ho.build_envelope(c, "key.rotated", {"new_key_id": "k2", "new_key_epoch": 1, "new_pubkey": PUB2},
                                    signer=LAB, key_id="k1", epoch=1,
                                    subject={"type": "machine", "id": "machine:m-elsewhere"})
            assert ho.sign_and_admit(d, c, h, env, SEED1)["admitted"]
        for i in range(letters):
            body = f"an old letter, number {i + 1}\n".encode()
            with ho.hub_writer(hub) as (d, c, h):
                env = ho.build_message_envelope(c, signer=LAB, key_id="k2", epoch=1, to_lab=TO, to_id="R",
                                                to_epoch=1, body=body, body_locator=f"file://{i + 1:03d}-body.txt",
                                                media_type="text/plain")
                r = ho.sign_and_admit(d, c, h, env, SEED2)
                assert r["admitted"]
            bp = self.tmp / "elsewhere" / "body.txt"
            bp.write_bytes(body)
            ho.export_quad(hub, out, event_id=r["event_id"], body_path=bp)
        cp = hs.checkpoint(hub, {OUTBOX: out}, {OUTBOX: DOOR}, seed=SEED2, drop_url=self.url, token=TOKEN,
                           received_only=True, wait=0, timeout=5, sleep=lambda s: None)
        assert cp.get("received_only"), cp
        for i in range(on_door):
            hd.push_quad(f"{self.url}/v0/{DOOR}", TOKEN, out / f"{i + 1:03d}", timeout=5, warmup=False)

    def boot(self, **over) -> Signer:
        """A fresh instance: an empty disk, the same vault and store."""
        self.boots += 1
        kw = dict(store=self.sstore, vault=self.vault, home=self.tmp / f"boot{self.boots}", sender=LAB,
                  recipients=RECIPIENTS, door=DOOR, drop_url=self.url, token=TOKEN, trusted_pubkeys=[PUB2],
                  key_id="k3", key_epoch=1, recovery=("k1", 1), retire=self.retire, outbox_name=OUTBOX,
                  received_only=True, clock=self.clock, send_opts=FAST, open_opts=FAST_OPEN,
                  log=lambda event, **kv: self.lines.append((event, kv)),
                  record=lambda kind, entry: self.records.append((kind, entry)))
        self.signer = Signer(**(kw | over))
        return self.signer

    def down(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()

    def door(self) -> list:
        d = self.root / "drops" / DOOR
        return sorted(f.name[:3] for f in d.glob("*-envelope.json")) if d.is_dir() else []

    def on_door(self, n: str) -> dict:
        return json.loads((self.root / "drops" / DOOR / f"{n}-envelope.json").read_bytes())

    def draft(self, body: str, **kw) -> str:
        st, out = self.front.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "mail_draft", "arguments": {"to_lab": TO, "to_id": "R", "body": body, **kw}}}, "jdot")
        told = json.loads(out["result"]["content"][0]["text"])
        assert "draft_id" in told, told
        return told["draft_id"]

    def outbox(self) -> list:
        st, out = self.front.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                     "params": {"name": "mail_outbox", "arguments": {}}}, "jdot")
        return json.loads(out["result"]["content"][0]["text"])["drafts"]

    def signed(self, which: str, seed: bytes = SEED1, signer: Signer | None = None) -> tuple:
        """What the device holding the recovery key hands back: the record and its signature."""
        raw = (signer or self.signer).unsigned(which)
        return raw.decode("utf-8"), sp.sign(hashlib.sha256(raw).digest(), seed).hex()

    def key_in(self) -> Signer:
        """The first day, done: opened, key made, both records taken in and on the door."""
        s = self.signer
        s.open()
        s.make_key()
        s.admit_lifecycle(rotate=self.signed("rotate"), revoke=self.signed("revoke") if self.retire else None)
        assert s.step() is False and s.view()["pushed"]
        return s


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.down()


# ── before the key ───────────────────────────────────────────────────────────

def test_it_wakes_with_nothing_and_opens_from_the_slot(world):
    s = world.signer
    assert s.ledger["state"] == "closed" and not s.hub.exists()
    assert s.open()["state"] == "open"
    report = s.ledger["report"]
    assert (report["restored"], report["letters"], report["not_on_the_door"]) == (True, 3, [])
    assert sorted(f.name[:3] for f in s.out.glob("*-envelope.json")) == ["001", "002", "003"]
    key = s.view()["key"]
    assert key["ready"] is False and key["why"] == "no key has been made"
    assert [(b["key_id"], b["active"]) for b in key["bindings"]] == [("k1", True), ("k2", True)]


def test_nothing_can_be_approved_before_the_key_is_in(world):
    s, did = world.signer, world.draft("too early\n")
    seen = hsd.review(world.sstore, did, signer=LAB, recipients=RECIPIENTS, now=world.clock)
    with pytest.raises(hsd.Refused, match="not open"):
        s.approve(did, seen["body_sha256"])                     # the ledger is not open
    s.open()
    with pytest.raises(hsd.Refused, match="no key has been made"):
        s.approve(did, seen["body_sha256"])
    s.make_key()
    with pytest.raises(hsd.Refused, match="k3 is not in the ledger yet"):
        s.approve(did, seen["body_sha256"])
    assert world.sstore.get(did)["decision"] is None
    assert s.step() is False and world.door() == ["001", "002", "003"]
    s.reject(did)                                               # a rejection needs no key
    assert world.outbox()[0]["status"] == "rejected"


def test_the_key_is_made_once_and_never_shown(world):
    s = world.signer
    with pytest.raises(hsd.Refused, match="not open"):
        s.make_key()                                            # not before the ledger is open
    assert world.vault.calls == [] and world.records == []
    s.open()
    pub = s.make_key()
    assert len(pub) == 64 and s.make_key() == pub
    assert world.vault.calls.count("create") == 1
    assert world.records == [("key", {"event": "make", "key_id": "k3", "key_epoch": 1})]
    seed_hex = world.vault.get().hex()
    assert sp.public_key(world.vault.get()).hex() == pub
    assert seed_hex not in json.dumps([world.lines, world.records, s.view()], default=str)
    again = world.boot()                                        # another boot reads the same key
    again.open()
    assert again.view()["key"]["pubkey"] == pub and world.vault.calls.count("create") == 1


def test_an_unanswered_vault_makes_no_key(world):
    class Silent(MemoryVault):
        def get(self):
            raise hf.NotReady(15)

    s = world.boot(vault=Silent())
    s.open()
    assert s.view()["key"]["why"] == "the vault: unknown"
    with pytest.raises(hsd.Refused, match="did not say it is empty"):
        s.make_key()

    class Broken(MemoryVault):
        def get(self):
            raise VaultError("the vault refused to give the key (HTTP 400)")

    s = world.boot(vault=Broken())
    s.open()
    with pytest.raises(hsd.Refused):
        s.make_key()
    assert "refused" in s.view()["key"]["why"]


def test_a_key_that_cannot_be_recorded_is_not_made(world):
    def no_record(kind, entry):
        raise hdr.StoreError("the store refused this request")

    s = world.boot(record=no_record)
    s.open()
    with pytest.raises(hdr.StoreError):
        s.make_key()
    assert world.vault.get() is None


# ── bringing the key in ──────────────────────────────────────────────────────

def test_the_unsigned_record_is_the_one_the_command_line_builds(world, tmp_path):
    from organum import hub_cli
    s = world.signer
    s.open()
    pub = s.make_key()
    ours = json.loads(s.unsigned("rotate"))
    out = tmp_path / "cli-rotate.json"
    assert hub_cli.main(["rotate-key", "--dir", str(s.hub), "--signer", LAB, "--key-id", "k1", "--epoch", "1",
                         "--new-key-id", "k3", "--new-epoch", "1", "--new-pubkey", pub,
                         "--unsigned-out", str(out)]) == 0
    theirs = json.loads(out.read_bytes())
    assert {**ours, "created_at": None} == {**theirs, "created_at": None}
    ours = json.loads(s.unsigned("revoke"))
    out = tmp_path / "cli-revoke.json"
    assert hub_cli.main(["revoke-key", "--dir", str(s.hub), "--signer", LAB, "--key-id", "k1", "--epoch", "1",
                         "--revoke-key-id", "k2", "--revoke-epoch", "1", "--unsigned-out", str(out)]) == 0
    assert {**ours, "created_at": None} == {**json.loads(out.read_bytes()), "created_at": None}
    assert ours["signer"] == {"id": LAB, "key_id": "k1", "key_epoch": 1}
    assert sorted(f.name for f in s.hub.iterdir() if f.suffix == ".jsonl") == ["events.jsonl"]


def test_both_records_come_in_and_land_as_the_next_two_numbers(world):
    s = world.signer
    s.open()
    pub = s.make_key()
    out = s.admit_lifecycle(rotate=world.signed("rotate"), revoke=world.signed("revoke"))
    assert (out["rotate"]["n"], out["revoke"]["n"]) == ("004", "005")
    assert world.door() == ["001", "002", "003"] and s.view()["pushed"] is False     # taking in does not wait for the door
    assert s.step() is False
    assert world.door() == ["001", "002", "003", "004", "005"] and s.view()["pushed"] is True
    rotated, revoked = world.on_door("004"), world.on_door("005")
    assert (rotated["event_kind"], rotated["signer"]["key_id"], rotated["payload"]["new_pubkey"]) == (
        "key.rotated", "k1", pub)
    assert (revoked["event_kind"], revoked["signer"]["key_id"], revoked["payload"]["key_id"]) == (
        "key.revoked", "k1", "k2")
    key = s.view()["key"]
    assert key["ready"] and key["bound"] and key["pinned"] and key["retire"]["revoked"]
    assert [(b["key_id"], b["active"]) for b in key["bindings"]] == [("k1", True), ("k2", False), ("k3", True)]
    kind, entry = world.records[-1]
    assert kind == "lifecycle" and set(entry) == {"rotate", "revoke"}
    # the bundle that carried them is signed by the new key, and a fresh boot opens from it
    again = world.boot()
    assert again.open()["state"] == "open"
    assert again.ledger["report"]["letters"] == 5 and again.view()["key"]["ready"]
    assert json.loads((again.hub / "hub.json").read_text())["lifecycle_pins"][0]["key_id"] == "k1"


def test_a_record_is_taken_only_if_it_is_ours_and_the_recovery_key_signed_it(world):
    s = world.signer
    s.open()
    s.make_key()
    env, sig = world.signed("rotate")
    def by_k1(change: dict) -> tuple:
        """A record that differs from ours and that the recovery key really signed."""
        other = he.canonical_bytes({**json.loads(env), **change})
        return other.decode("utf-8"), sp.sign(hashlib.sha256(other).digest(), SEED1).hex()

    payload = json.loads(env)["payload"]
    cases = {
        "k1 signed another new key": by_k1({"payload": {**payload, "new_pubkey": sp.public_key(SEED9).hex()}}),
        "k1 signed another key id": by_k1({"payload": {**payload, "new_key_id": "k4"}}),
        "k1 signed a revocation, given as the rotation": by_k1(
            {"event_kind": "key.revoked", "payload": {"key_id": "k2", "key_epoch": 1, "reason": "rotated out"}}),
        "k1 signed it for another machine": by_k1({"subject": {"type": "machine", "id": "machine:somewhere"}}),
        "signed by the working key": world.signed("rotate", seed=SEED2),
        "signed by the service's own key": world.signed("rotate", seed=world.vault.get()),
        "another new key": (json.dumps({**json.loads(env), "payload": {
            **json.loads(env)["payload"], "new_pubkey": sp.public_key(SEED9).hex()}}), sig),
        "another key id": (json.dumps({**json.loads(env), "payload": {
            **json.loads(env)["payload"], "new_key_id": "k4"}}), sig),
        "claims the working key as signer": (json.dumps({**json.loads(env), "signer": {
            "id": LAB, "key_id": "k2", "key_epoch": 1}}), sig),
        "not a record": ("{", sig),
        "not a signature": (env, "zz"),
    }
    for why, given in cases.items():
        with pytest.raises(hsd.Refused):
            s.admit_lifecycle(rotate=given)
        assert s.view()["key"]["bound"] is False, why
    with pytest.raises(hsd.Refused, match="comes in first"):
        s.admit_lifecycle(revoke=world.signed("revoke"))        # the old key does not go first
    with pytest.raises(hsd.Refused, match="no record"):
        s.admit_lifecycle()
    assert world.door() == ["001", "002", "003"] and not any(k == "lifecycle" for k, _ in world.records)


def test_one_bad_record_takes_neither(world):
    s = world.signer
    s.open()
    s.make_key()
    with pytest.raises(hsd.Refused):
        s.admit_lifecycle(rotate=world.signed("rotate"), revoke=world.signed("revoke", seed=SEED2))
    assert s.view()["key"]["bound"] is False and world.door() == ["001", "002", "003"]


def test_the_two_records_may_come_one_at_a_time_and_nothing_is_approved_between(world):
    s = world.signer
    s.open()
    s.make_key()
    out = s.admit_lifecycle(rotate=world.signed("rotate"))
    assert out["rotate"]["n"] == "004"
    assert s.step() is False and world.door()[-1] == "004"      # the new key goes to the door without waiting for the other
    key = s.view()["key"]
    assert key["bound"] and not key["ready"] and key["why"] == "k2 is to be revoked first"
    did = world.draft("between the two\n")
    with pytest.raises(hsd.Refused, match="revoked first"):
        s.approve(did, s.review(did)["body_sha256"])
    again = world.boot()                                        # the disk went away in between
    again.open()
    out = again.admit_lifecycle(revoke=world.signed("revoke", signer=again))
    assert out["revoke"]["n"] == "005" and again.view()["key"]["ready"]
    assert again.step() is False and world.door()[-1] == "005"


def test_taking_the_same_records_twice_changes_nothing(world):
    s = world.signer
    s.open()
    s.make_key()
    rotate, revoke = world.signed("rotate"), world.signed("revoke")
    s.admit_lifecycle(rotate=rotate, revoke=revoke)
    s.step()
    again = s.admit_lifecycle(rotate=rotate)
    assert again["rotate"] == {"event_id": again["rotate"]["event_id"], "already": True, "n": "004"}
    s.step()
    assert world.door() == ["001", "002", "003", "004", "005"]


def test_without_a_key_to_retire_the_new_key_alone_is_enough(tmp_path):
    w = World(tmp_path, retire=None)
    try:
        s = w.signer
        s.open()
        s.make_key()
        with pytest.raises(hsd.Refused, match="no such record"):
            s.unsigned("revoke")
        s.admit_lifecycle(rotate=w.signed("rotate"))
        assert s.step() is False
        assert s.view()["key"]["ready"] and w.door()[-1] == "004"
    finally:
        w.down()


def test_the_pin_keeps_the_new_key_from_making_keys(world):
    """What the pin is for: the service's key signs letters; it cannot bring in a key."""
    s = world.key_in()
    with ho.hub_writer(s.hub) as (d, cfg, hub):
        env = ho.build_envelope(cfg, "key.rotated", {"new_key_id": "k4", "new_key_epoch": 1,
                                                     "new_pubkey": sp.public_key(SEED9).hex()},
                                signer=LAB, key_id="k3", epoch=1,
                                subject={"type": "machine", "id": "machine:" + cfg["machine_id"]})
        r = ho.sign_and_admit(d, cfg, hub, env, world.vault.get())
    assert r["admitted"] is False


# ── letters ──────────────────────────────────────────────────────────────────

def test_an_approved_draft_becomes_the_next_letter_signed_by_the_new_key(world):
    s = world.key_in()
    body = "# 첫 편지\n\n서명 서비스가 보냅니다.\n"
    did = world.draft(body)
    seen = s.review(did)
    assert seen["text"] == body and seen["to"] == {"lab_id": TO, "to_id": "R", "to_epoch": 1}
    s.approve(did, seen["body_sha256"])
    assert world.door()[-1] == "005"                            # approving sends nothing by itself
    assert s.step() is False
    assert world.door()[-1] == "006"
    env = world.on_door("006")
    assert env["signer"] == {"id": LAB, "key_id": "k3", "key_epoch": 1}
    assert env["payload"]["body_locator"] == f"draft:{did}"
    assert (world.root / "drops" / DOOR / "006-body.md").read_bytes() == body.encode()
    told = world.outbox()[0]
    assert (told["status"], told["n"], told["door"]) == ("sent", "006", DOOR)
    sig = (world.root / "drops" / DOOR / "006-sig.txt").read_text().strip()
    raw = (world.root / "drops" / DOOR / "006-envelope.json").read_bytes()
    assert sp.verify(bytes.fromhex(sig), hashlib.sha256(raw).digest(), bytes.fromhex(s.view()["key"]["pubkey"]))


def test_the_disk_may_vanish_between_the_approval_and_the_letter(world):
    s = world.key_in()
    did = world.draft("approved, then the server slept\n")
    s.approve(did, s.review(did)["body_sha256"])
    again = world.boot()                                        # nothing of the first instance is left
    assert again.step() is False                                # opens, then carries the approval on
    assert again.ledger["state"] == "open" and world.door()[-1] == "006"
    assert world.outbox()[0]["status"] == "sent"
    assert again.step() is False and world.door()[-1] == "006"  # and does not send it again


def test_what_was_approved_is_what_is_signed(world):
    s = world.key_in()
    did = world.draft("the text that was read\n")
    with pytest.raises(hsd.Refused, match="not the text that was reviewed"):
        s.approve(did, "0" * 64)
    s.approve(did, s.review(did)["body_sha256"])
    with pytest.raises(hsd.Refused, match="already decided"):
        s.reject(did)                                           # the first decision stays
    s.step()
    assert world.outbox()[0]["status"] == "sent"


def test_a_draft_that_may_not_be_signed_can_only_be_rejected(world):
    s = world.key_in()
    did = world.draft("for someone who is not on the list\n")
    name = f"send/drafts/{did}.json"
    data, created, meta = world.bucket.objects[name]
    record = json.loads(data)
    record["to"]["lab_id"] = "lab:not-allowed"
    world.bucket.objects[name] = (json.dumps(record).encode(), created, meta)     # what a leaked key could place
    with pytest.raises(hsd.Refused):
        s.review(did)
    with pytest.raises(hsd.Refused):
        s.approve(did, record["body_sha256"])
    s.reject(did)
    assert s.entry(did)["status"] == "rejected" and world.door()[-1] == "005"


def test_reject_all_clears_what_is_waiting_and_only_that(world):
    s = world.key_in()
    keep = world.draft("approved before the flood\n")
    s.approve(keep, s.review(keep)["body_sha256"])
    for i in range(7):
        world.draft(f"flood {i}\n")
    assert s.reject_all() == 7
    assert [e["status"] for e in s.waiting()] == []
    assert sorted(e["status"] for e in s.recent()) == ["approved"] + ["rejected"] * 7
    s.step()
    assert s.entry(keep)["status"] == "sent" and world.door()[-1] == "006"


def test_a_stop_while_sending_stays_until_someone_opens_again(world):
    s = world.key_in()
    # another writer on the same door: a letter this outbox does not know
    stranger = world.tmp / "stranger"
    stranger.mkdir()
    for part in ("envelope.json", "sig.txt", "body.txt"):
        shutil.copy(world.tmp / "elsewhere" / OUTBOX / f"001-{part}", stranger / f"006-{part}")
    hd.push_quad(f"{world.url}/v0/{DOOR}", TOKEN, stranger / "006", timeout=5, warmup=False)
    did = world.draft("held back\n")
    s.approve(did, s.review(did)["body_sha256"])
    assert s.step() is False
    assert s.ledger["state"] == "stopped" and s.ledger["during"] == "send"
    assert s.step() is False and s.ledger["state"] == "stopped"           # not retried by itself
    with pytest.raises(hsd.Refused, match="not open"):
        s.approve(world.draft("while stopped\n"), "0" * 64)
    assert s.entry(did)["status"] == "approved" and world.door()[-1] == "006"
    assert s.open(fresh=True)["state"] == "stopped"                        # the door still disagrees
    assert s.ledger["during"] == "open"


def test_opening_is_tried_again_by_itself_but_not_forever(world):
    s = world.signer
    world.down()                                                # the drop is not there
    turns = 0
    while s.step():
        turns += 1
        assert turns < 20
    assert s.ledger["state"] == "stopped" and s.ledger["during"] == "open"
    opened = lambda: sum(1 for event, kv in world.lines if event == "ledger" and kv["state"] == "opening")   # noqa: E731
    assert opened() == 5
    for _ in range(3):                                          # and after that it is left alone
        assert s.step() is False
    assert opened() == 5
    world.srv = hd.make_server(world.root / "drops", world.root / "tokens.txt", bind="127.0.0.1", port=0,
                               rate_limit_per_minute=0, state_dir=world.root / "state")
    threading.Thread(target=world.srv.serve_forever, daemon=True).start()
    s.drop_url = f"http://127.0.0.1:{world.srv.server_address[1]}"
    assert s.open(fresh=True)["state"] == "open"                # asked for, it opens


def test_a_page_is_not_kept_waiting_by_a_send(world):
    s = world.key_in()
    before = s.view()
    held = threading.Event()
    release = threading.Event()

    def hold():
        with s._held(None):
            held.set()
            release.wait(5)

    t = threading.Thread(target=hold)
    t.start()
    held.wait(5)
    try:
        now = s.view()
        assert now["busy"] is True and now["key"]["ready"] == before["key"]["ready"]
        with pytest.raises(Busy):
            s.unsigned("rotate")
        did = world.draft("decided while a send runs\n")
        s.approve(did, s.review(did)["body_sha256"])            # a decision touches the store only
    finally:
        release.set()
        t.join()


def test_nothing_secret_reaches_the_log(world):
    s = world.key_in()
    body = "SECRET-BODY-MARK 본문은 로그에 남지 않는다\n"
    did = world.draft(body)
    s.approve(did, s.review(did)["body_sha256"])
    s.step()
    text = json.dumps([world.lines, world.records], ensure_ascii=False, default=str)
    assert "SECRET-BODY-MARK" not in text and TOKEN not in text
    assert world.vault.get().hex() not in text
    assert did in text and '"n": "006"' in text


# ── the vault ────────────────────────────────────────────────────────────────

class _Answer:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


class _Secrets:
    """Secret Manager as the vault uses it: versions of one secret, numbered from 1."""

    def __init__(self, versions=None, deny=False, disabled=()):
        self.versions, self.deny, self.disabled, self.calls = list(versions or []), deny, set(disabled), []

    def get(self, url, timeout):
        self.calls.append(("get", url))
        assert url == "https://secretmanager.googleapis.com/v1/projects/p/secrets/s/versions/1:access"
        if self.deny:
            return _Answer(403, {"error": {"message": "denied SECRET-DETAIL"}})
        if not self.versions:
            return _Answer(404, {"error": {"status": "NOT_FOUND"}})
        if 1 in self.disabled:
            return _Answer(400, {"error": {"status": "FAILED_PRECONDITION"}})
        return _Answer(200, {"payload": {"data": self.versions[0]}})

    def post(self, url, json, timeout):
        self.calls.append(("post", url))
        assert url == "https://secretmanager.googleapis.com/v1/projects/p/secrets/s:addVersion"
        if self.deny:
            return _Answer(403)
        self.versions.append(json["payload"]["data"])
        return _Answer(200, {"name": f"projects/p/secrets/s/versions/{len(self.versions)}"})


def test_the_vault_reads_version_one_and_adds_only_to_an_empty_secret():
    import base64
    http = _Secrets()
    vault = SecretVault("projects/p/secrets/s", session=http)
    assert vault.get() is None
    assert vault.create(SEED9) == SEED9
    assert base64.b64decode(http.versions[0]) == SEED9.hex().encode()
    assert vault.create(SEED1) == SEED9 and len(http.versions) == 1         # the first one stays
    http.versions.append(base64.b64encode(SEED1.hex().encode()).decode())  # someone adds a second version
    assert vault.get() == SEED9                                             # version 1 is still the key


def test_the_vault_says_no_instead_of_making_do():
    import base64
    with pytest.raises(VaultError) as e:
        SecretVault("projects/p/secrets/s", session=_Secrets(deny=True)).get()
    assert "SECRET-DETAIL" not in str(e.value)
    with pytest.raises(VaultError):
        SecretVault("projects/p/secrets/s", session=_Secrets(deny=True)).create(SEED9)
    one = base64.b64encode(SEED9.hex().encode()).decode()
    with pytest.raises(VaultError):                             # a disabled key is not "no key"
        SecretVault("projects/p/secrets/s", session=_Secrets([one], disabled=[1])).create(SEED1)
    for bad in (base64.b64encode(b"not a seed").decode(), base64.b64encode(b"ab" * 31).decode(), "###"):
        with pytest.raises(VaultError):
            SecretVault("projects/p/secrets/s", session=_Secrets([bad])).get()

    class Down:
        def get(self, url, timeout):
            raise OSError("reset SECRET-DETAIL")

    with pytest.raises(hf.NotReady):
        SecretVault("projects/p/secrets/s", session=Down()).get()

    class Busy503:
        def get(self, url, timeout):
            return _Answer(503)

    with pytest.raises(hf.NotReady):
        SecretVault("projects/p/secrets/s", session=Busy503()).get()
    for name in ("s", "projects/p/secrets/", "projects//secrets/s", "projects/p/secret/s"):
        with pytest.raises(ValueError):
            SecretVault(name, session=_Secrets())


def test_a_ledger_that_holds_another_key_under_our_name_signs_nothing(world):
    """The vault's key and the ledger's k3 must be the same key. If k1 brought in another one under
    that name, this service's key is not the lab's: nothing is pushed, signed or approved."""
    s = world.signer
    s.open()
    s.make_key()
    with ho.hub_writer(s.hub) as (d, cfg, hub):                 # k1 brings in some other key as k3
        env = ho.build_envelope(cfg, "key.rotated", {"new_key_id": "k3", "new_key_epoch": 1,
                                                     "new_pubkey": sp.public_key(SEED9).hex()},
                                signer=LAB, key_id="k1", epoch=1,
                                subject={"type": "machine", "id": "machine:" + cfg["machine_id"]})
        assert ho.sign_and_admit(d, cfg, hub, env, SEED1)["admitted"]
    s.open()                                                    # looks at the ledger again
    key = s.view()["key"]
    assert (key["bound"], key["conflict"], key["ready"]) == (False, True, False)
    assert key["why"] == "the ledger holds another key as k3"
    did = world.draft("not with this key\n")
    with pytest.raises(hsd.Refused, match="another key as k3"):
        s.approve(did, s.review(did)["body_sha256"])
    before = (s.hub / "hub.json").read_bytes(), (s.hub / "events.jsonl").read_bytes()
    with pytest.raises(hsd.Refused, match="another key as k3"):
        s.admit_lifecycle(rotate=world.signed("rotate"))        # our own record, rightly signed: still not taken
    assert before == ((s.hub / "hub.json").read_bytes(), (s.hub / "events.jsonl").read_bytes())
    assert s.ledger["state"] == "open"                          # a known state, not a stop
    assert s.step() is False and world.door() == ["001", "002", "003"]
    assert not any(n.startswith("send/results/") for n in world.bucket.objects)


def test_a_key_revoked_in_the_ledger_signs_no_letter_even_one_already_approved(world):
    s = world.key_in()
    did = world.draft("approved while the key was good\n")
    s.approve(did, s.review(did)["body_sha256"])
    with ho.hub_writer(s.hub) as (d, cfg, hub):                 # the recovery key cuts k3 off
        env = ho.build_envelope(cfg, "key.revoked", {"key_id": "k3", "key_epoch": 1, "reason": "cut off"},
                                signer=LAB, key_id="k1", epoch=1,
                                subject={"type": "machine", "id": "machine:" + cfg["machine_id"]})
        assert ho.sign_and_admit(d, cfg, hub, env, SEED1)["admitted"]
    s.open()
    key = s.view()["key"]
    assert (key["bound"], key["ready"], key["why"]) == (False, False, "k3 was revoked in the ledger")
    assert s.step() is False
    assert s.ledger["state"] == "open"                          # not a stop: there was nothing to try
    assert world.door()[-1] == "005" and s.entry(did)["status"] == "approved"
    with pytest.raises(hsd.Refused, match="revoked"):
        s.approve(world.draft("after the cut\n"), "0" * 64)


def test_nothing_goes_to_the_door_before_the_key_is_in_the_ledger(tmp_path):
    """The restored outbox may hold a letter that never reached the door. It waits too: this
    service puts nothing on the door until its key is the ledger's, and then the old letter goes
    first, in the order of the numbers."""
    w = World(tmp_path, on_door=2)
    try:
        s = w.signer
        assert s.open()["report"]["not_on_the_door"] == ["003"] and s.view()["pushed"] is False
        assert s.step() is False and w.door() == ["001", "002"]         # no key at all
        s.make_key()
        assert s.step() is False and w.door() == ["001", "002"]         # a key the ledger does not hold
        s.admit_lifecycle(rotate=w.signed("rotate"), revoke=w.signed("revoke"))
        assert s.step() is False
        assert w.door() == ["001", "002", "003", "004", "005"] and s.view()["pushed"] is True
    finally:
        w.down()


def test_no_letter_goes_between_the_two_key_records_even_if_one_is_already_approved(world):
    """Approving is refused until the old key is revoked. But a decision may already be in the
    store — written by an instance set up otherwise. It is not acted on until everything is in place."""
    s = world.signer
    s.open()
    s.make_key()
    s.admit_lifecycle(rotate=world.signed("rotate"))
    s.step()
    did = world.draft("approved by some other instance\n")
    seen = hsd.review(world.sstore, did, signer=LAB, recipients=RECIPIENTS, now=world.clock)
    hsd.decide(world.sstore, did, "approved", approver="someone", body_sha256=seen["body_sha256"],
               signer=LAB, recipients=RECIPIENTS, now=world.clock)
    assert s.step() is False
    assert world.door()[-1] == "004" and s.entry(did)["status"] == "approved"
    s.admit_lifecycle(revoke=world.signed("revoke"))
    assert s.step() is False
    assert world.door()[-2:] == ["005", "006"]
    assert (world.on_door("005")["event_kind"], world.on_door("006")["event_kind"]) == ("key.revoked", "message.posted")
    assert s.entry(did)["status"] == "sent"
