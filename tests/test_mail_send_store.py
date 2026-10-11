"""The draft store is where a leaked key must not be able to turn a draft into a letter.

organum's sending side trusts the store for one thing it cannot check itself: that a decision or a
result was written by the signing side. Everything else it reads from the store it looks at again.
So what is pinned here is the store's half of that bargain, on a bucket that behaves like the real
one was measured to (LxM 158, 166 §3): an account lists and reads under its prefixes, creates where
it may, and has no call that replaces or deletes.

  - it answers the seven calls exactly as organum's own in-memory store does;
  - the draft window's account cannot write a decision or a result, the signing side's cannot place a
    draft, and nothing once placed changes;
  - `placed_at` is the bucket's clock;
  - `approved()` finds an approved draft whatever is piled on top of it, at a cost that does not grow;
  - a name that is not a draft id never becomes an object name.

These tests need organum 0.10.0; the environment the drop's own tests run in has 0.8.0, where they
are skipped.
"""

from __future__ import annotations

import json
import shutil
import threading

import pytest

hdr = pytest.importorskip("organum.hub_draft")

from organum import hub_drop as hd  # noqa: E402
from organum import hub_envelope as he  # noqa: E402
from organum import hub_front as hf  # noqa: E402
from organum import hub_send as hsd  # noqa: E402
from organum import schnorr_pure as sp  # noqa: E402

from mail_send.bucket import Entry, GcsBucket, MemoryBucket  # noqa: E402
from mail_send.store import BucketDraftStore  # noqa: E402

SIGNER, OTHER, TO = "lab:testonly", "lab:someone-else", "lab:receiver"
T0 = 1_791_504_000.0                        # 2026-10-09T00:00:00Z


class Clock:
    def __init__(self, t: float = T0):
        self.t = t

    def __call__(self) -> float:
        self.t += 1                         # every look is a second later: order is never a tie
        return self.t


def _two_sides(clock=None):
    """The bucket, and the store as each account sees it."""
    bucket = MemoryBucket(clock or Clock())
    window = bucket.account("window", read=("send/",), create=("send/drafts/",))
    signer = bucket.account("signer", read=("send/",), create=("send/decisions/", "send/results/"))
    return bucket, BucketDraftStore(window), BucketDraftStore(signer)


def _record(text: str, ref: str = "", sender: str = SIGNER, now: float = T0, ttl: float = 7 * 86400):
    body = text.encode("utf-8")
    return hdr.draft_record(caller="jdot", sender=sender, to_lab=TO, to_id="R", to_epoch=1,
                            media_type="text/markdown", client_ref=ref, body=body, now=now, ttl=ttl), body


def _decision(did: str, kind: str, at: str) -> dict:
    return {"kind": "decision", "v": 1, "draft_id": did, "decision": kind, "approver": "jj", "decided_at": at}


def _spent(bucket: MemoryBucket, since: int) -> dict:
    calls = bucket.calls[since:]
    return {op: sum(1 for _, o, _ in calls if o == op) for op in ("list", "get", "put")}


# ── the same answers as organum's own store ──────────────────────────────────

def test_it_answers_the_seven_calls_as_organums_memory_store_does():
    ours_clock, theirs_clock = Clock(), Clock()
    _, window, signer = _two_sides(ours_clock)
    theirs = hdr.MemoryStore(clock=theirs_clock)
    seen = []

    def both(call, *args):
        """Run one call on both. The clocks tick per look, so keep them in step and compare everything."""
        mine = getattr(signer if call in ("put_decision", "put_result", "approved", "body") else window, call)(*args)
        ours_clock.t = theirs_clock.t = max(ours_clock.t, theirs_clock.t)
        yours = getattr(theirs, call)(*args)
        ours_clock.t = theirs_clock.t = max(ours_clock.t, theirs_clock.t)
        seen.append(call)
        return mine, yours

    def same(mine, yours):
        def strip(e):                       # the bucket's clock and the memory store's tick differently
            return {k: v for k, v in e.items() if k != "placed_at"} if isinstance(e, dict) else e
        if isinstance(mine, tuple):
            assert (strip(mine[0]), mine[1]) == (strip(yours[0]), yours[1])
        elif isinstance(mine, list):
            assert [strip(e) for e in mine] == [strip(e) for e in yours]
        else:
            assert strip(mine) == strip(yours)

    ids = []
    for i, (text, sender) in enumerate([("one", SIGNER), ("two", SIGNER), ("theirs", OTHER), ("three", SIGNER),
                                        ("four", SIGNER), ("five", SIGNER)]):
        record, body = _record(text + "\n", ref=f"r{i}", sender=sender)
        same(*both("put_draft", record, body))
        ids.append(record["draft_id"])
    record, body = _record("one\n", ref="r0")
    same(*both("put_draft", record, body))                      # the same draft again: the first, created False
    for did in ids:
        same(*both("get", did))
        same(*both("body", did))
    same(*both("put_decision", _decision(ids[1], "approved", "2026-10-09T00:10:00Z")))
    same(*both("put_decision", _decision(ids[3], "rejected", "2026-10-09T00:11:00Z")))
    same(*both("put_decision", _decision(ids[4], "approved", "2026-10-09T00:05:00Z")))     # decided earlier, placed later
    same(*both("put_decision", _decision(ids[1], "rejected", "2026-10-09T00:12:00Z")))     # too late: the first stays
    same(*both("put_result", {"kind": "result", "v": 1, "draft_id": ids[0], "status": "failed", "reason": "x",
                              "number_used": False}))
    same(*both("put_result", {"kind": "result", "v": 1, "draft_id": ids[0], "status": "sent", "n": "001"}))
    for sender in (SIGNER, OTHER, "lab:nobody"):
        for without in (None, "decision", "result"):
            for limit in (1, 3, 50):
                same(*both("list", sender, limit, without))
        for limit in (1, 50):
            same(*both("approved", sender, limit))
    same(*both("put_result", {"kind": "result", "v": 1, "draft_id": ids[4], "status": "sent", "n": "002"}))
    same(*both("approved", SIGNER, 50))
    assert [e["draft"]["draft_id"] for e in signer.approved(SIGNER, 50)] == [ids[1]]
    assert set(seen) == {"put_draft", "get", "list", "body", "approved", "put_decision", "put_result"}


def test_a_missing_draft_is_a_lookup_error_from_every_call_that_reads_one():
    _, window, signer = _two_sides()
    for call in (window.get, signer.body):
        with pytest.raises(LookupError):
            call("0" * 32)


# ── who may write what is the bucket's, and nothing placed ever changes ───────

def test_the_draft_windows_account_cannot_make_a_draft_look_approved_or_sent():
    bucket, window, signer = _two_sides()
    record, body = _record("a letter\n")
    window.put_draft(record, body)
    did = record["draft_id"]
    for forge in (lambda: window.put_decision(_decision(did, "approved", "2026-10-09T00:00:00Z")),
                  lambda: window.put_result({"kind": "result", "draft_id": did, "status": "sent", "n": "001"})):
        with pytest.raises(hdr.StoreError):
            forge()
    assert window.get(did)["decision"] is None and window.get(did)["result"] is None
    assert not [n for n in bucket.objects if "/decisions/" in n or "/results/" in n]


def test_the_signing_sides_account_cannot_place_a_draft():
    bucket, _, signer = _two_sides()
    record, body = _record("not from the window\n")
    with pytest.raises(hdr.StoreError):
        signer.put_draft(record, body)
    assert bucket.objects == {}


def test_what_is_placed_never_changes_and_the_first_decision_and_result_stay():
    bucket, window, signer = _two_sides()
    record, body = _record("a letter\n")
    window.put_draft(record, body)
    did = record["draft_id"]
    first = signer.put_decision(_decision(did, "approved", "2026-10-09T00:00:01Z"))
    again = signer.put_decision(_decision(did, "rejected", "2026-10-09T00:00:02Z"))
    assert again == first and again["decision"] == "approved"
    sent = signer.put_result({"kind": "result", "draft_id": did, "status": "sent", "n": "001"})
    assert signer.put_result({"kind": "result", "draft_id": did, "status": "failed"}) == sent
    before = dict(bucket.objects)
    window.put_draft(record, body)
    changed, _ = _record("a letter\n", ttl=999)                 # the same id, another record: the first stays
    entry, created = window.put_draft(changed, body)
    assert created is False and entry["draft"] == record and bucket.objects == before
    assert not any(hasattr(account, name) for account in (window._b, signer._b)
                   for name in ("delete", "replace", "write", "update"))


def test_a_body_put_under_a_draft_id_by_someone_else_is_noticed_when_the_draft_is_placed():
    bucket, window, _ = _two_sides()
    record, body = _record("the honest text\n")
    bucket.objects[f"send/drafts/{record['draft_id']}.body"] = (b"other bytes", T0, {})
    with pytest.raises(hdr.StoreError):
        window.put_draft(record, body)
    with pytest.raises(LookupError):
        window.get(record["draft_id"])                          # no record was written over the wrong body


# ── the bucket's clock ───────────────────────────────────────────────────────

def test_placed_at_is_when_the_bucket_made_the_object_whatever_the_record_claims():
    clock = Clock()
    _, window, signer = _two_sides(clock)
    record, body = _record("claims a year\n", now=T0 - 50 * 86400, ttl=365 * 86400)
    entry, _ = window.put_draft(record, body)
    assert entry["placed_at"].startswith("2026-10-09T00:00:0") and entry["draft"]["created_at"] < "2026-09"
    assert hdr.status_of(entry, clock.t + 6 * 86400, 7 * 86400) == "pending_approval"
    assert hdr.status_of(entry, clock.t + 8 * 86400, 7 * 86400) == "expired"     # the record says ten months more
    assert signer.get(record["draft_id"])["placed_at"] == entry["placed_at"]


# ── an approved draft is found whatever is piled on it ───────────────────────

def test_approved_finds_the_draft_under_any_pile_and_what_it_asks_the_bucket_does_not_grow():
    bucket, window, signer = _two_sides()
    record, body = _record("approved, not yet sent\n")
    window.put_draft(record, body)
    signer.put_decision(_decision(record["draft_id"], "approved", "2026-10-09T00:00:09Z"))
    mark = len(bucket.calls)
    assert [e["draft"]["draft_id"] for e in signer.approved(SIGNER, 200)] == [record["draft_id"]]
    alone = _spent(bucket, mark)
    for i in range(300):                                        # a leaked window key: drafts past every limit
        junk, junk_body = _record(f"junk {i}\n", ref=f"j{i}")
        window.put_draft(junk, junk_body)
        if i % 2:
            signer.put_decision(_decision(junk["draft_id"], "rejected", "2026-10-09T01:00:00Z"))
    assert record["draft_id"] not in [e["draft"]["draft_id"] for e in signer.list(SIGNER, 200, without="result")]
    mark = len(bucket.calls)
    assert [e["draft"]["draft_id"] for e in signer.approved(SIGNER, 200)] == [record["draft_id"]]
    assert _spent(bucket, mark) == alone and alone["list"] == 3 and alone["put"] == 0
    assert not any(op == "list" and name == "send/drafts/" for who, op, name in bucket.calls[mark:])


def test_approved_is_in_the_order_the_decisions_were_made_and_leaves_out_what_has_a_result():
    _, window, signer = _two_sides()
    ids = []
    for i, when in enumerate(("2026-10-09T03:00:00Z", "2026-10-09T01:00:00Z", "2026-10-09T02:00:00Z")):
        record, body = _record(f"letter {i}\n", ref=str(i))
        window.put_draft(record, body)
        signer.put_decision(_decision(record["draft_id"], "approved", when))
        ids.append(record["draft_id"])
    assert [e["draft"]["draft_id"] for e in signer.approved(SIGNER, 50)] == [ids[1], ids[2], ids[0]]
    assert [e["draft"]["draft_id"] for e in signer.approved(SIGNER, 2)] == [ids[1], ids[2]]
    signer.put_result({"kind": "result", "draft_id": ids[1], "status": "sent", "n": "001"})
    assert [e["draft"]["draft_id"] for e in signer.approved(SIGNER, 50)] == [ids[2], ids[0]]
    assert signer.approved(OTHER, 50) == []


def test_a_decision_written_without_its_kind_in_the_listing_is_read_to_find_out():
    bucket, window, signer = _two_sides()
    record, body = _record("decided by an older writer\n")
    window.put_draft(record, body)
    did = record["draft_id"]
    bucket.objects[f"send/decisions/{did}.json"] = (
        json.dumps(_decision(did, "approved", "2026-10-09T00:00:05Z")).encode(), T0 + 5, {})
    assert [e["draft"]["draft_id"] for e in signer.approved(SIGNER, 50)] == [did]


# ── names ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["", "x", "../../drop-state/jdot-hq", "0" * 31, "0" * 33, "G" * 32,
                                  "0" * 32 + "/x", None, 7])
def test_a_name_that_is_not_a_draft_id_never_becomes_an_object_name(name):
    bucket, window, signer = _two_sides()
    for call in (window.get, signer.body):
        with pytest.raises(LookupError):
            call(name)
    with pytest.raises(LookupError):
        signer.put_decision({"draft_id": name, "decision": "approved"})
    with pytest.raises((LookupError, KeyError)):
        window.put_draft({"draft_id": name}, b"x")
    assert bucket.calls == [] and bucket.objects == {}


def test_other_objects_under_the_prefixes_are_not_drafts():
    bucket, window, signer = _two_sides()
    record, body = _record("the only draft\n")
    window.put_draft(record, body)
    for stray in ("send/drafts/README.txt", "send/drafts/notanid.json", "send/decisions/zz.json",
                  "send/results/" + "0" * 32 + ".json.bak", "send/drafts/" + "f" * 32 + ".body"):
        bucket.objects[stray] = (b"{}", T0, {"decision": "approved"})
    assert [e["draft"]["draft_id"] for e in window.list(SIGNER, 50)] == [record["draft_id"]]
    assert signer.approved(SIGNER, 50) == []
    with pytest.raises(ValueError):
        BucketDraftStore(window._b, "/send/")


def test_a_record_that_is_not_json_is_a_store_error_and_not_a_guess():
    bucket, window, _ = _two_sides()
    record, body = _record("fine\n")
    window.put_draft(record, body)
    name = f"send/drafts/{record['draft_id']}.json"
    for broken in (b"\xff\xfe", b"[1, 2]", b"not json"):
        bucket.objects[name] = (broken, T0, {})
        with pytest.raises(hdr.StoreError):
            window.get(record["draft_id"])


# ── with organum's two sides on top, and a drop on this machine ──────────────

SEED1, SEED3 = (3).to_bytes(32, "big"), (5).to_bytes(32, "big")            # TESTONLY: the public BIP-340 test values
PUB1, PUB3 = sp.public_key(SEED1).hex(), sp.public_key(SEED3).hex()
DOOR, TOKEN = "hub-ops/from-testonly", "tok-test"


class _World:
    def __init__(self, tmp):
        self.t = T0
        self.bucket, self.window, self.signer = _two_sides()
        self.front = hdr.DraftFront(self.window, {"jdot": {"sender": SIGNER, "to": {TO: 1}}}, now=lambda: self.t)
        root = tmp / "srv"
        root.mkdir()
        (root / "tokens.txt").write_text(f"{TOKEN}  id=testonly\n")
        self.srv = hd.make_server(root / "drops", root / "tokens.txt", bind="127.0.0.1", port=0,
                                  rate_limit_per_minute=0, state_dir=root / "state")
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url, self.door_dir = f"http://127.0.0.1:{self.srv.server_address[1]}", root / "drops" / DOOR
        self.hub, self.out = tmp / "signer" / "hub", tmp / "signer" / "out"
        self.hub.mkdir(parents=True)
        self.out.mkdir()
        cfg = {"source_domain": "lab:testonly/hub", "machine_id": "TESTONLY-SIGNER", "claims": {"claims": {}},
               "claims_sha256": he.canonical_sha({"claims": {}}),
               "keys": [{"pubkey": PUB1, "signer_id": SIGNER, "key_id": "k1", "key_epoch": 1},
                        {"pubkey": PUB3, "signer_id": SIGNER, "key_id": "k3", "key_epoch": 1}]}
        (self.hub / "hub.json").write_text(json.dumps(cfg))
        (self.hub / "events.jsonl").write_bytes(b"")

    def place(self):
        return dict(hub_dir=self.hub, outbox_dir=self.out, door=DOOR, drop_url=self.url, token=TOKEN)

    def cfg(self):
        return dict(**self.place(), seed=SEED3, signer=SIGNER, key_id="k3", key_epoch=1, recipients={TO: 1},
                    now=lambda: self.t, wait=0, mirror_wait=0, sleep=lambda s: None, received_only=True, timeout=5)

    def tool(self, name, args):
        _, out = self.front.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                    "params": {"name": name, "arguments": args}}, "jdot")
        return json.loads(out["result"]["content"][0]["text"])

    def approved_draft(self, text):
        did = self.tool("mail_draft", {"to_lab": TO, "to_id": "R", "body": text})["draft_id"]
        shown = hsd.review(self.signer, did, signer=SIGNER, recipients={TO: 1}, now=lambda: self.t)
        hsd.decide(self.signer, did, "approved", approver="jj", body_sha256=shown["body_sha256"],
                   signer=SIGNER, recipients={TO: 1}, now=lambda: self.t)
        return did

    def on_the_door(self):
        return sorted(f.name[:3] for f in self.door_dir.glob("*-envelope.json")) if self.door_dir.is_dir() else []


@pytest.fixture
def world(tmp_path):
    w = _World(tmp_path)
    yield w
    w.srv.shutdown()
    w.srv.server_close()


def test_a_draft_goes_from_the_window_through_an_approval_to_the_door(world):
    did = world.tool("mail_draft", {"to_lab": TO, "to_id": "R", "body": "첫 편지\n\"따옴표\"와 `백틱`.\n"})["draft_id"]
    assert [d["status"] for d in world.tool("mail_outbox", {})["drafts"]] == ["pending_approval"]
    shown = hsd.review(world.signer, did, signer=SIGNER, recipients={TO: 1}, now=lambda: world.t)
    assert shown["text"] == "첫 편지\n\"따옴표\"와 `백틱`.\n"
    hsd.decide(world.signer, did, "approved", approver="jj", body_sha256=shown["body_sha256"],
               signer=SIGNER, recipients={TO: 1}, now=lambda: world.t)
    assert world.tool("mail_outbox", {"draft_id": did})["drafts"][0]["status"] == "approved"
    result = hsd.send_approved(world.signer, did, **world.cfg())
    assert result["status"] == "sent" and result["n"] == "001" and world.on_the_door() == ["001"]
    told = world.tool("mail_outbox", {"draft_id": did})["drafts"][0]
    assert (told["status"], told["door"], told["n"]) == ("sent", DOOR, "001")
    assert (world.door_dir / "001-body.md").read_bytes() == world.signer.body(did)
    assert not any(op == "put" and "/drafts/" not in name for who, op, name in world.bucket.calls if who == "window")


def test_a_server_that_slept_opens_its_ledger_again_and_resumes_under_a_pile_of_drafts(world):
    first = world.approved_draft("goes at once\n")
    assert hsd.send_approved(world.signer, first, **world.cfg())["status"] == "sent"
    waiting = world.approved_draft("approved, then the server slept\n")
    shutil.rmtree(world.hub)
    shutil.rmtree(world.out)                                    # a free instance woke: no disk
    for i in range(210):                                        # and meanwhile the window's key leaked
        record, body = _record(f"junk {i}\n", ref=f"j{i}")
        world.window.put_draft(record, body)
    with pytest.raises(hsd.SendStopped):
        hsd.send_approved(world.signer, waiting, **world.cfg())
    opened = hsd.open_ledger(**world.place(), trusted_pubkeys=[PUB3], received_only=True, timeout=5,
                             sleep=lambda s: None)
    assert opened["restored"] is True and opened["letters"] == 1 and opened["not_on_the_door"] == []
    done = hsd.resume(world.signer, **world.cfg())
    assert [(d["status"], d["n"]) for d in done] == [("sent", "002")] and world.on_the_door() == ["001", "002"]
    assert "already waiting" in world.tool("mail_draft", {"to_lab": TO, "to_id": "R", "body": "honest\n"})["error"]


# ── the real bucket's client: call shapes, and errors in the store's words ───

class _Blob:
    def __init__(self, bucket, name):
        self.bucket, self.name, self.metadata = bucket, name, None
        data, created, meta = bucket.objects.get(name, (b"", None, None))
        self.size, self.time_created = len(data), created
        if name in bucket.objects:
            self.metadata = meta

    def download_as_bytes(self, timeout=None, retry=None):
        from google.api_core.exceptions import NotFound
        self.bucket.calls.append(("get", self.name))
        if self.bucket.fail:
            raise self.bucket.fail
        if self.name not in self.bucket.objects:
            raise NotFound("gs://secret-bucket/" + self.name)
        return self.bucket.objects[self.name][0]

    def upload_from_string(self, data, content_type=None, if_generation_match=None, timeout=None, retry=None):
        import datetime
        from google.api_core.exceptions import PreconditionFailed
        self.bucket.calls.append(("put", self.name, if_generation_match, self.metadata))
        if self.bucket.fail:
            raise self.bucket.fail
        if self.name in self.bucket.objects:
            raise PreconditionFailed("exists")
        self.bucket.objects[self.name] = (data, datetime.datetime.fromtimestamp(T0, datetime.timezone.utc),
                                          self.metadata)


class _Client:
    def __init__(self):
        self.objects, self.calls, self.fail = {}, [], None

    def bucket(self, name):
        return self

    def blob(self, name):
        return _Blob(self, name)

    def list_blobs(self, bucket, prefix=None, fields=None, timeout=None, retry=None):
        self.calls.append(("list", prefix, fields))
        if self.fail:
            raise self.fail
        return [_Blob(self, k) for k in sorted(self.objects) if k.startswith(prefix)]


def test_the_real_bucket_creates_with_metadata_never_replaces_and_lists_time_and_metadata():
    pytest.importorskip("google.cloud.storage")
    client = _Client()
    bucket = GcsBucket("lxm-send", client=client)
    bucket.write_new("send/decisions/a.json", b"{}", {"decision": "approved", "decided_at": "2026-10-09T00:00:00Z",
                                                       "skipped": None})
    assert client.calls[-1] == ("put", "send/decisions/a.json", 0,
                                {"decision": "approved", "decided_at": "2026-10-09T00:00:00Z"})
    with pytest.raises(FileExistsError):
        bucket.write_new("send/decisions/a.json", b"other")
    assert bucket.read("send/decisions/a.json") == b"{}"
    (entry,) = bucket.names("send/decisions/")
    assert entry == Entry("send/decisions/a.json", 2, T0, {"decision": "approved",
                                                            "decided_at": "2026-10-09T00:00:00Z"})
    assert client.calls[-1] == ("list", "send/decisions/", "items(name,size,timeCreated,metadata),nextPageToken")


def test_the_real_buckets_errors_are_not_there_not_now_or_not_ever_and_never_its_own_words():
    pytest.importorskip("google.cloud.storage")
    from google.api_core import exceptions as gexc
    client = _Client()
    bucket = GcsBucket("lxm-send", client=client)
    with pytest.raises(LookupError) as e:
        bucket.read("send/drafts/none.json")
    assert "secret-bucket" not in str(e.value)
    for fail, kind in ((gexc.ServiceUnavailable("x"), hf.NotReady), (gexc.TooManyRequests("x"), hf.NotReady),
                       (gexc.Forbidden("sa@project lacks storage.objects.create"), hdr.StoreError)):
        client.fail = fail
        for call in (lambda: bucket.names("send/"), lambda: bucket.read("send/x"),
                     lambda: bucket.write_new("send/x", b"1")):
            with pytest.raises(kind) as e:
                call()
            assert "sa@project" not in str(e.value)


def test_the_store_runs_on_the_real_buckets_client_too():
    pytest.importorskip("google.cloud.storage")
    client = _Client()
    store = BucketDraftStore(GcsBucket("lxm-send", client=client))
    record, body = _record("through the client\n")
    entry, created = store.put_draft(record, body)
    assert created is True and entry["placed_at"] == "2026-10-09T00:00:00Z"
    store.put_decision(_decision(record["draft_id"], "approved", "2026-10-09T00:00:01Z"))
    assert [e["draft"]["draft_id"] for e in store.approved(SIGNER, 10)] == [record["draft_id"]]


def test_junk_under_a_drafts_name_does_not_break_a_listing():
    """One object that is not a record, placed with the window's key, must not empty the page a
    person decides on. A refusal by the bucket is another matter and is still said."""
    clock = Clock()
    bucket = MemoryBucket(clock)
    window = bucket.account("window", read=("send/",), create=("send/drafts/",))
    store = BucketDraftStore(window)
    record = hdr.draft_record(caller="jdot", sender=SIGNER, to_lab=TO, to_id="R", to_epoch=1,
                              media_type="text/markdown", body=b"a real draft\n", client_ref="", now=clock(),
                              ttl=hdr.DRAFT_TTL_SECONDS)
    store.put_draft(record, b"a real draft\n")
    window.write_new("send/drafts/" + "a" * 32 + ".json", b"\xff not json")
    window.write_new("send/drafts/" + "b" * 32 + ".json", b"[1, 2]")
    window.write_new("send/drafts/" + "c" * 32 + ".json",               # a record filed under another name than its own
                     json.dumps(record | {"draft_id": "d" * 32}).encode())
    window.write_new("send/drafts/" + "e" * 32 + ".json", json.dumps({"sender": SIGNER}).encode())
    assert [e["draft"]["draft_id"] for e in store.list(SIGNER, 10)] == [record["draft_id"]]
    assert [e["draft"]["draft_id"] for e in store.list(SIGNER, 10, without="decision")] == [record["draft_id"]]
    with pytest.raises(hdr.StoreError):
        store.get("a" * 32)                                     # asked for by name, it is said
    blind = BucketDraftStore(bucket.account("nobody"))
    with pytest.raises(hdr.StoreError):
        blind.list(SIGNER, 10)
