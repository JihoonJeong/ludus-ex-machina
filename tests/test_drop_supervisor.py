"""The boot restore has to finish before the platform stops waiting for a port,
and it must never hand serve a partial tree.

Restore was sequential — one round trip per object — and the mirror grew past
1,800 objects, so a cold start paid minutes before serve could bind. On
2026-09-12 a deploy failed Render's port scan on exactly that. These tests pin
the properties of the replacement: every object lands with its size recorded,
downloads actually overlap, a traversal name never escapes the root, one
failed download fails the whole restore, and the worker count is honoured.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from scripts import drop_supervisor as ds


class FakeBlob:
    def __init__(self, name: str, data: bytes | None, store: dict):
        self.name, self._data, self._store = name, data, store

    def download_to_filename(self, path: str) -> None:
        st = self._store
        with st["lock"]:
            st["active"] += 1
            st["peak"] = max(st["peak"], st["active"])
        try:
            time.sleep(0.02)
            if self._data is None:
                raise OSError("simulated 5xx from the bucket")
            Path(path).write_bytes(self._data)
        finally:
            with st["lock"]:
                st["active"] -= 1


class FakeClient:
    def __init__(self, blobs): self._blobs = blobs
    def list_blobs(self, bucket, prefix): return [b for b in self._blobs if b.name.startswith(prefix)]


class FakeBucket:
    name = "fake"
    def __init__(self, blobs): self.client = FakeClient(blobs)


def _store() -> dict:
    return {"lock": threading.Lock(), "active": 0, "peak": 0}


def _blobs(n: int, store: dict, bad: set[int] = frozenset()) -> list[FakeBlob]:
    return [FakeBlob(f"{ds.PREFIX}/hub-ops/from-x/{i:03d}-envelope.json",
                     None if i in bad else b"{}" * i, store)
            for i in range(1, n + 1)]


def test_every_object_lands_with_its_size_recorded(tmp_path):
    st = _store()
    mirrored = ds.restore(FakeBucket(_blobs(40, st)), tmp_path, workers=8)
    assert len(mirrored) == 40
    for i in range(1, 41):
        rel = f"hub-ops/from-x/{i:03d}-envelope.json"
        assert (tmp_path / rel).read_bytes() == b"{}" * i
        assert mirrored[rel] == 2 * i


def test_downloads_actually_overlap(tmp_path):
    st = _store()
    ds.restore(FakeBucket(_blobs(40, st)), tmp_path, workers=8)
    assert st["peak"] > 1, "restore ran the downloads one at a time"


def test_one_worker_means_one_at_a_time(tmp_path, monkeypatch):
    monkeypatch.setenv("DROP_RESTORE_WORKERS", "1")
    st = _store()
    ds.restore(FakeBucket(_blobs(12, st)), tmp_path)     # workers from env
    assert st["peak"] == 1


def test_a_traversal_name_never_escapes_the_root(tmp_path):
    st = _store()
    blobs = _blobs(2, st) + [FakeBlob(f"{ds.PREFIX}/../escaped.txt", b"x", st)]
    root = tmp_path / "root"
    mirrored = ds.restore(FakeBucket(blobs), root, workers=4)
    assert len(mirrored) == 2
    assert not (tmp_path / "escaped.txt").exists()


def test_one_failed_download_fails_the_whole_restore(tmp_path):
    st = _store()
    with pytest.raises(OSError):
        ds.restore(FakeBucket(_blobs(30, st, bad={17})), tmp_path, workers=8)


# --- audit log mirror (organum 0.7.0, LxM 118 Q4) --------------------------------------
#
# The quad mirror never overwrites, which is right for quads and wrong for a
# file that grows all day: it would upload the first lines and call every later
# one "already there". These pin the audit rule: a growing file is mirrored in
# full, under a path unique to the boot, and the boot restore never reads it.

class UpBlob:
    def __init__(self, name, bucket): self.name, self.bucket = name, bucket
    def upload_from_filename(self, path, **kw):
        self.bucket.calls.append((self.name, dict(kw)))
        if self.bucket.fail:
            raise OSError("simulated 5xx")
        data = Path(path).read_bytes()
        if self.bucket.grow_during_upload:
            with open(path, "ab") as f:
                f.write(self.bucket.grow_during_upload)
            self.bucket.grow_during_upload = b""
        self.bucket.objects[self.name] = data


class UpBucket:
    name = "fake"
    def __init__(self): self.objects, self.calls, self.fail, self.grow_during_upload = {}, [], False, b""
    def blob(self, name): return UpBlob(name, self)


def test_a_growing_audit_file_is_mirrored_in_full_each_time_it_grows(tmp_path):
    f = tmp_path / "audit-20261004.jsonl"
    f.write_text('{"n": 1}\n')
    b, seen = UpBucket(), {}
    assert ds.audit_sync_pass(b, tmp_path, "boot-1", seen) == 1
    key = f"{ds.AUDIT_PREFIX}/boot-1/audit-20261004.jsonl"
    assert b.objects[key] == b'{"n": 1}\n'
    assert ds.audit_sync_pass(b, tmp_path, "boot-1", seen) == 0          # unchanged: no upload
    with f.open("a") as fh:
        fh.write('{"n": 2}\n')
    assert ds.audit_sync_pass(b, tmp_path, "boot-1", seen) == 1
    assert b.objects[key] == b'{"n": 1}\n{"n": 2}\n'                     # the later line is there
    assert all("if_generation_match" not in kw for _, kw in b.calls)     # overwrites — unlike the quad mirror


def test_lines_appended_during_an_upload_are_caught_by_the_next_pass(tmp_path):
    f = tmp_path / "audit-20261004.jsonl"
    f.write_text('{"n": 1}\n')
    b, seen = UpBucket(), {}
    b.grow_during_upload = b'{"n": 2}\n'
    ds.audit_sync_pass(b, tmp_path, "boot-1", seen)
    assert ds.audit_sync_pass(b, tmp_path, "boot-1", seen) == 1
    assert b.objects[f"{ds.AUDIT_PREFIX}/boot-1/audit-20261004.jsonl"] == b'{"n": 1}\n{"n": 2}\n'


def test_a_failed_audit_upload_is_retried_and_other_files_are_ignored(tmp_path):
    (tmp_path / "audit-20261004.jsonl").write_text("x\n")
    (tmp_path / "not-an-audit-file.txt").write_text("y\n")
    b, seen = UpBucket(), {}
    b.fail = True
    assert ds.audit_sync_pass(b, tmp_path, "boot-1", seen) == 0 and seen == {}
    b.fail = False
    assert ds.audit_sync_pass(b, tmp_path, "boot-1", seen) == 1
    assert list(b.objects) == [f"{ds.AUDIT_PREFIX}/boot-1/audit-20261004.jsonl"]
    assert ds.audit_sync_pass(b, tmp_path / "missing", "boot-1", {}) == 0


def test_the_boot_restore_never_reads_the_audit_prefix(tmp_path):
    st = _store()
    blobs = _blobs(5, st) + [FakeBlob(f"{ds.AUDIT_PREFIX}/20261004T000000Z-7/audit-20261004.jsonl", b"audit\n", st)]
    mirrored = ds.restore(FakeBucket(blobs), tmp_path, workers=2)
    assert len(mirrored) == 5 and not list(tmp_path.rglob("audit-*"))
    assert not ds.AUDIT_PREFIX.startswith(ds.PREFIX + "/") and ds.AUDIT_PREFIX != ds.PREFIX


def test_boot_stamps_differ_between_processes_and_sort_by_time():
    a = ds.boot_stamp()
    assert a.endswith(f"-{ds.os.getpid()}") and len(a.split("-")[0]) == 16 and a[8] == "T"


@pytest.mark.parametrize("help_text,expected", [("  --rate-limit RATE_LIMIT\n  --audit-log AUDIT_LOG\n", True),
                                                 ("  --rate-limit RATE_LIMIT\n", False)])
def test_audit_is_only_asked_of_a_serve_that_has_it(monkeypatch, help_text, expected):
    class R:
        stdout, stderr = help_text, ""
    monkeypatch.setattr(ds.subprocess, "run", lambda *a, **k: R())
    assert ds.serve_supports_audit() is expected
    monkeypatch.setattr(ds.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no such binary")))
    assert ds.serve_supports_audit() is False


def test_real_serve_writes_audit_lines_that_the_mirror_carries(tmp_path):
    """End to end against the installed organum: a request appends an audit
    line; the pass mirrors it; a later request's line is mirrored too."""
    import json, socket, subprocess, sys, urllib.request
    hub = Path(sys.executable).parent / "organum-hub"
    if "--audit-log" not in subprocess.run([str(hub), "serve", "--help"], capture_output=True, text=True).stdout:
        pytest.skip("installed organum has no --audit-log")
    root, audit = tmp_path / "root", tmp_path / "audit" / "boot-9"
    root.mkdir(); audit.mkdir(parents=True)
    (tmp_path / "tokens.txt").write_text("test-token-for-this-test-only  id=probe\n")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen([str(hub), "serve", "--root", str(root), "--token-file", str(tmp_path / "tokens.txt"), "--bind", "127.0.0.1",
                             "--port", str(port), "--audit-log", str(audit)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
            except OSError:
                time.sleep(0.1)
        def hit():
            r = urllib.request.Request(f"http://127.0.0.1:{port}/v0/channels", headers={"Authorization": "Bearer test-token-for-this-test-only"})
            urllib.request.urlopen(r, timeout=10).read()
            time.sleep(0.3)
        b, seen = UpBucket(), {}
        hit()
        assert ds.audit_sync_pass(b, audit, "boot-9", seen) == 1
        hit(); hit()
        assert ds.audit_sync_pass(b, audit, "boot-9", seen) == 1
    finally:
        proc.terminate(); proc.wait(5)
    (key, data), = b.objects.items()
    lines = [json.loads(l) for l in data.decode().splitlines()]
    assert key.startswith(f"{ds.AUDIT_PREFIX}/boot-9/audit-") and len(lines) == 3
    assert all(l["id"] == "probe" and l["status"] == 200 for l in lines) and "test-token" not in data.decode()


# --- "already there" is not "the same thing is there"; the catch-up read (LxM 124 §2 · 127 §2) ---
#
# A redeploy runs two instances at once: the new one reads the bucket's listing
# when its restore begins, and whatever the old one accepts after that reaches
# the bucket but not the new disk. Two things follow. The new instance has to
# read the listing again once it is serving. And a name can come to hold
# different bytes on the disk and in the bucket — which the mirror used to
# read as "already there" and count as done.

class MirrorBlob:
    def __init__(self, name, bucket): self.name, self.bucket = name, bucket
    def upload_from_filename(self, path, if_generation_match=None):
        from google.api_core.exceptions import PreconditionFailed
        if if_generation_match == 0 and self.name in self.bucket.objects:
            raise PreconditionFailed(self.name)
        self.bucket.uploads.append(self.name)
        self.bucket.objects[self.name] = Path(path).read_bytes()
    def upload_from_string(self, data, content_type=None):
        if self.bucket.fail_strings:
            raise OSError("simulated 5xx")
        self.bucket.objects[self.name] = data.encode() if isinstance(data, str) else data
    def download_as_bytes(self):
        return self.bucket.objects[self.name]
    def download_to_filename(self, path):
        if self.name in self.bucket.fail_downloads:
            raise OSError("simulated 5xx from the bucket")
        Path(path).write_bytes(self.bucket.objects[self.name])


class MirrorBucket:
    name = "fake"
    def __init__(self, objects=None):
        self.objects = {f"{ds.PREFIX}/{k}": v for k, v in (objects or {}).items()}
        self.uploads, self.fail_downloads, self.fail_strings, self.client = [], set(), False, self
    def blob(self, name): return MirrorBlob(name, self)
    def list_blobs(self, bucket, prefix): return [MirrorBlob(n, self) for n in sorted(self.objects) if n.startswith(prefix)]
    def held(self, rel): return self.objects[f"{ds.PREFIX}/{rel}"]


DOOR = "hub-ops/from-x"


def _local_quad(root: Path, n: str, env: bytes = b'{"e": 1}', body: bytes | None = b"# title\n") -> None:
    d = root / DOOR
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{n}-sig.txt").write_bytes(b"ab" * 64 + b"\n")
    if body is not None:
        (d / f"{n}-body.md").write_bytes(body)
    (d / f"{n}-envelope.json").write_bytes(env)


def _bucket_quad(n: str, env: bytes = b'{"e": 1}', body: bytes | None = b"# title\n", envelope: bool = True) -> dict:
    q = {f"{DOOR}/{n}-sig.txt": b"ab" * 64 + b"\n"}
    if body is not None:
        q[f"{DOOR}/{n}-body.md"] = body
    if envelope:
        q[f"{DOOR}/{n}-envelope.json"] = env
    return q


def test_a_name_the_bucket_already_holds_with_the_same_bytes_is_counted_and_nothing_is_said(tmp_path, caplog):
    _local_quad(tmp_path, "001")
    b, mirrored, conflicts = MirrorBucket(_bucket_quad("001")), {}, []
    assert ds.sync_pass(b, tmp_path, mirrored, "boot-1", conflicts) == 3
    assert conflicts == [] and b.uploads == [] and "CONFLICT" not in caplog.text
    assert ds.sync_pass(b, tmp_path, mirrored, "boot-1", conflicts) == 0


def test_a_name_the_bucket_holds_with_other_bytes_is_reported_kept_and_never_replaced(tmp_path, caplog):
    _local_quad(tmp_path, "001", env=b'{"e": "the letter this instance serves"}')
    b, mirrored, conflicts = MirrorBucket(_bucket_quad("001", env=b'{"e": "the letter the bucket holds"}')), {}, []
    ds.sync_pass(b, tmp_path, mirrored, "boot-1", conflicts)
    rel = f"{DOOR}/001-envelope.json"
    assert conflicts == [rel]
    assert b.held(rel) == b'{"e": "the letter the bucket holds"}'                       # a letter is never replaced
    assert b.objects[f"{ds.CONFLICT_PREFIX}/boot-1/{rel}"] == b'{"e": "the letter this instance serves"}'
    assert f"CONFLICT {rel}" in caplog.text and f"kept at {ds.CONFLICT_PREFIX}/boot-1/{rel}" in caplog.text
    assert not ds.CONFLICT_PREFIX.startswith(ds.PREFIX + "/") and ds.CONFLICT_PREFIX != ds.PREFIX   # never restored
    caplog.clear()
    assert ds.sync_pass(b, tmp_path, mirrored, "boot-1", conflicts) == 0                # said once, not every pass
    assert conflicts == [rel] and "CONFLICT" not in caplog.text


def test_a_comparison_that_cannot_be_made_aborts_the_pass_and_is_retried(tmp_path):
    _local_quad(tmp_path, "001", env=b"local")
    b, mirrored, conflicts = MirrorBucket(_bucket_quad("001", env=b"bucket")), {}, []
    real = MirrorBlob.download_as_bytes
    try:
        MirrorBlob.download_as_bytes = lambda self: (_ for _ in ()).throw(OSError("simulated 5xx"))
        assert ds.sync_pass(b, tmp_path, mirrored, "boot-1", conflicts) == 0 and mirrored == {} and conflicts == []
    finally:
        MirrorBlob.download_as_bytes = real
    ds.sync_pass(b, tmp_path, mirrored, "boot-1", conflicts)
    assert conflicts == [f"{DOOR}/001-envelope.json"]


def test_a_dot_file_is_never_mirrored(tmp_path):
    _local_quad(tmp_path, "001")
    (tmp_path / DOOR / ".002-envelope.json.part-7").write_bytes(b"half a download")
    b = MirrorBucket()
    assert ds.sync_pass(b, tmp_path, {}) == 3
    assert not any(".002" in name for name in b.objects)


def test_catch_up_fetches_a_quad_the_bucket_has_and_this_disk_does_not(tmp_path):
    _local_quad(tmp_path, "001")
    b = MirrorBucket(_bucket_quad("001") | _bucket_quad("002", env=b'{"e": 2}', body=b"# second\n") | _bucket_quad("003", body=None))
    mirrored = {}
    assert ds.catch_up(b, tmp_path, mirrored) == [f"{DOOR}/002", f"{DOOR}/003"]
    d = tmp_path / DOOR
    assert (d / "002-envelope.json").read_bytes() == b'{"e": 2}' and (d / "002-body.md").read_bytes() == b"# second\n"
    assert (d / "003-envelope.json").is_file() and not list(d.glob("003-body.*"))
    assert not [f.name for f in d.iterdir() if f.name.startswith(".")]                   # no temp file left
    assert set(mirrored) == {f"{DOOR}/002-sig.txt", f"{DOOR}/002-body.md", f"{DOOR}/002-envelope.json",
                             f"{DOOR}/003-sig.txt", f"{DOOR}/003-envelope.json"}
    assert ds.catch_up(b, tmp_path, mirrored) == []                                      # a second read finds nothing new


def test_what_catch_up_fetched_is_not_uploaded_again(tmp_path):
    b, mirrored = MirrorBucket(_bucket_quad("002")), {}
    ds.catch_up(b, tmp_path, mirrored)
    assert ds.sync_pass(b, tmp_path, mirrored) == 0 and b.uploads == []


def test_catch_up_leaves_a_quad_whose_envelope_is_not_in_the_bucket_yet(tmp_path):
    b = MirrorBucket(_bucket_quad("002", envelope=False))                                # the other mirror is mid-pass
    assert ds.catch_up(b, tmp_path, {}) == []
    assert not list(tmp_path.rglob("002-*"))
    b.objects[f"{ds.PREFIX}/{DOOR}/002-envelope.json"] = b'{"e": 1}'                     # ...and its pass finishes
    assert ds.catch_up(b, tmp_path, {}) == [f"{DOOR}/002"]


def test_catch_up_leaves_a_number_that_has_any_file_here(tmp_path):
    d = tmp_path / DOOR
    d.mkdir(parents=True)
    (d / "002-sig.txt").write_bytes(b"cd" * 64 + b"\n")                                  # serve is writing 002, or left it half done
    _local_quad(tmp_path, "003", env=b'{"e": "local"}')
    b = MirrorBucket(_bucket_quad("002") | _bucket_quad("003", env=b'{"e": "bucket"}'))
    mirrored = {}
    assert ds.catch_up(b, tmp_path, mirrored) == [] and mirrored == {}
    assert sorted(f.name for f in d.glob("002-*")) == ["002-sig.txt"]                    # not mixed with the bucket's quad
    assert (d / "003-envelope.json").read_bytes() == b'{"e": "local"}'


def test_a_failed_download_leaves_no_envelope_and_no_temp_file(tmp_path):
    b = MirrorBucket(_bucket_quad("002"))
    b.fail_downloads = {f"{ds.PREFIX}/{DOOR}/002-body.md"}
    mirrored = {}
    with pytest.raises(OSError):
        ds.catch_up(b, tmp_path, mirrored)
    assert mirrored == {} and [f.name for f in (tmp_path / DOOR).iterdir()] == []
    b.fail_downloads = set()
    assert ds.catch_up(b, tmp_path, mirrored) == [f"{DOOR}/002"]                         # the next read completes it


def test_quads_fetched_before_a_failure_are_still_reported(tmp_path):
    b, got = MirrorBucket(_bucket_quad("002") | _bucket_quad("003")), []
    b.fail_downloads = {f"{ds.PREFIX}/{DOOR}/003-sig.txt"}
    with pytest.raises(OSError):
        ds.catch_up(b, tmp_path, {}, got)
    assert got == [f"{DOOR}/002"] and (tmp_path / DOOR / "002-envelope.json").is_file()


def test_catch_up_links_the_envelope_after_the_quads_other_files(tmp_path, monkeypatch):
    order, real = [], ds.os.link
    monkeypatch.setattr(ds.os, "link", lambda src, dst: (order.append(Path(dst).name), real(src, dst))[1])
    ds.catch_up(MirrorBucket(_bucket_quad("002")), tmp_path, {})
    assert order[-1] == "002-envelope.json" and sorted(order[:-1]) == ["002-body.md", "002-sig.txt"]


def test_if_serve_writes_the_number_meanwhile_its_files_win_and_ours_are_forgotten(tmp_path, monkeypatch):
    real = ds.os.link
    def link(src, dst):
        if Path(dst).name == "002-envelope.json":                                        # serve finished 002 just before our last link
            _local_quad(tmp_path, "002", env=b'{"e": "what serve was given"}', body=b"# serve's\n")
        return real(src, dst)
    monkeypatch.setattr(ds.os, "link", link)
    b, mirrored = MirrorBucket(_bucket_quad("002", env=b'{"e": "what the bucket holds"}')), {}
    assert ds.catch_up(b, tmp_path, mirrored) == [] and mirrored == {}
    d = tmp_path / DOOR
    assert (d / "002-envelope.json").read_bytes() == b'{"e": "what serve was given"}' and (d / "002-body.md").read_bytes() == b"# serve's\n"
    conflicts = []
    ds.sync_pass(b, tmp_path, mirrored, "boot-1", conflicts)                             # ...and the next pass sees the difference
    assert f"{DOOR}/002-envelope.json" in conflicts


def test_catch_up_never_writes_outside_the_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    b = MirrorBucket({"../escaped/001-sig.txt": b"x", "../escaped/001-envelope.json": b"x", "001-envelope.json": b"top level"})
    assert ds.catch_up(b, root, {}) == [] and not (tmp_path / "escaped").exists() and list(root.iterdir()) == []


@pytest.mark.parametrize("at,every,expected", [(None, None, ([60.0, 180.0, 420.0], 900.0)), ("3, 1", "0", ([1.0, 3.0], 0.0)),
                                                ("", "", ([], 0.0))])
def test_the_catch_up_schedule_comes_from_the_environment(monkeypatch, at, every, expected):
    for k, v in (("DROP_CATCHUP_AT", at), ("DROP_CATCHUP_EVERY", every)):
        monkeypatch.delenv(k, raising=False) if v is None else monkeypatch.setenv(k, v)
    assert ds.catchup_schedule() == expected


def test_the_boot_record_is_one_object_per_boot_and_a_failed_write_stops_nothing(tmp_path):
    import json
    b = MirrorBucket()
    ds.write_boot_record(b, "boot-1", {"restore_started_utc": "2026-10-05T00:00:00Z", "catch_ups": []})
    ds.write_boot_record(b, "boot-1", {"restore_started_utc": "2026-10-05T00:00:00Z", "catch_ups": [{"fetched": []}]})
    (key, data), = b.objects.items()
    assert key == f"{ds.AUDIT_PREFIX}/boot-1/boot.json" and json.loads(data)["catch_ups"] == [{"fetched": []}]
    b.fail_strings = True
    ds.write_boot_record(b, "boot-1", {})                                                # logs, does not raise
    assert not key.endswith(".jsonl")                                                    # the audit mirror's glob never picks it up


# --- the state slot (organum 0.8.0; LxM 120-136 with Organum) ------------------------
#
# serve's 200 means "received". A mark — an empty file this supervisor writes after the
# upload — is what says "outside". The boot objects (born, alive, closed, settled) are read
# by the bucket's clock only. These pin the rules the design memo closed on.

import json
from datetime import datetime, timedelta, timezone

T0 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)


class ClockBlob:
    def __init__(self, name, bucket):
        self.name, self.bucket, self.metadata = name, bucket, None
        o = bucket.objects.get(name)
        self.generation, self.time_created = (o["gen"], o["t"]) if o else (None, None)

    def _write(self, data, if_generation_match):
        from google.api_core.exceptions import PreconditionFailed
        cur = self.bucket.objects.get(self.name)
        if if_generation_match is not None and if_generation_match != (cur["gen"] if cur else 0):
            raise PreconditionFailed(self.name)
        if self.name in self.bucket.fail_writes:
            raise OSError("simulated 5xx")
        self.bucket.gen += 1
        self.bucket.objects[self.name] = {"data": data, "gen": self.bucket.gen, "t": self.bucket.now(), "meta": self.metadata}
        self.generation, self.time_created = self.bucket.gen, self.bucket.objects[self.name]["t"]

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        self._write(data.encode() if isinstance(data, str) else data, if_generation_match)

    def upload_from_filename(self, path, if_generation_match=None):
        self._write(Path(path).read_bytes(), if_generation_match)

    def download_as_bytes(self):
        return self.bucket.objects[self.name]["data"]

    def download_to_filename(self, path):
        Path(path).write_bytes(self.bucket.objects[self.name]["data"])

    def delete(self, if_generation_match=None):
        from google.api_core.exceptions import NotFound, PreconditionFailed
        cur = self.bucket.objects.get(self.name)
        if cur is None:
            raise NotFound(self.name)
        if if_generation_match is not None and if_generation_match != cur["gen"]:
            raise PreconditionFailed(self.name)
        del self.bucket.objects[self.name]


class ClockBucket:
    """A bucket with its own clock: every write gets the next tick unless the test moves time."""
    name = "fake"

    def __init__(self):
        self.objects, self.gen, self.t, self.fail_writes, self.client = {}, 0, T0, set(), self

    def now(self):
        self.t += timedelta(milliseconds=1)
        return self.t

    def advance(self, seconds):
        self.t += timedelta(seconds=seconds)

    def blob(self, name):
        return ClockBlob(name, self)

    def get_blob(self, name):
        return ClockBlob(name, self) if name in self.objects else None

    def list_blobs(self, bucket, prefix="", start_offset=None):
        return [ClockBlob(n, self) for n in sorted(self.objects)
                if n.startswith(prefix) and (start_offset is None or n >= start_offset)]

    def put(self, name, data=b"{}"):
        ClockBlob(name, self).upload_from_string(data)
        return self.objects[name]["t"]


def _boot(bucket, name, *, alive_after=None, closed=False, settled=False):
    """Make a boot's objects; returns its born time."""
    born = bucket.put(ds.boot_object(name, "born"))
    if alive_after is not None:
        bucket.advance(alive_after)
        bucket.put(ds.boot_object(name, "alive"))
    if settled:
        bucket.put(ds.boot_object(name, "settled"))
    if closed:
        bucket.put(ds.boot_object(name, "closed"))
    return born


def _verdict(bucket, me, my_born, *, timed_out=False, stale=300):
    v = ds.BootView(bucket)
    return ds.settle_verdict(v, me, my_born, bucket.t, stale=stale, timed_out=timed_out)[0]


def test_the_first_boot_with_nothing_before_it_settles_at_once():
    b = ClockBucket()
    born = _boot(b, "20261007T120000Z-1")
    assert _verdict(b, "20261007T120000Z-1", born) == "ready"


def test_a_boot_closed_before_this_one_was_born_needs_no_catch_up():
    b = ClockBucket()
    _boot(b, "20261007T110000Z-1", closed=True, settled=True)
    b.advance(600)
    born = _boot(b, "20261007T120000Z-2")
    assert _verdict(b, "20261007T120000Z-2", born) == "ready"


def test_a_live_predecessor_is_waited_for_however_long_and_its_close_means_one_catch_up():
    b = ClockBucket()
    _boot(b, "20261007T110000Z-1", settled=True)
    b.advance(30)
    born = _boot(b, "20261007T120000Z-2")
    for _ in range(12):                                          # an hour of a predecessor that keeps beating
        b.advance(300)
        b.put(ds.boot_object("20261007T110000Z-1", "alive"))
        assert _verdict(b, "20261007T120000Z-2", born, timed_out=True) == "wait"
    b.put(ds.boot_object("20261007T110000Z-1", "closed"))
    assert _verdict(b, "20261007T120000Z-2", born) == "catch-up"


def test_a_predecessor_that_stopped_rewriting_alive_is_stopped_after_the_stale_time():
    b = ClockBucket()
    _boot(b, "20261007T110000Z-1", alive_after=1, settled=True)
    born = _boot(b, "20261007T120000Z-2")
    b.advance(299)
    assert _verdict(b, "20261007T120000Z-2", born) == "wait"
    b.advance(2)
    assert _verdict(b, "20261007T120000Z-2", born) == "catch-up"


def test_born_counts_as_the_first_alive():
    b = ClockBucket()
    _boot(b, "20261007T110000Z-1")                               # died between born and the first alive
    born = _boot(b, "20261007T120000Z-2")
    assert _verdict(b, "20261007T120000Z-2", born) == "wait"
    b.advance(301)
    assert _verdict(b, "20261007T120000Z-2", born) == "catch-up"


def test_the_walk_stops_at_the_nearest_boot_that_settled():
    b = ClockBucket()
    _boot(b, "20261007T090000Z-1")                               # never closed, never settled: an old hard kill
    b.advance(10)
    _boot(b, "20261007T100000Z-2", closed=True, settled=True)
    b.advance(10)
    born = _boot(b, "20261007T120000Z-3")
    assert _verdict(b, "20261007T120000Z-3", born) == "ready"    # -1 is behind -2, which settled


def test_a_boot_settled_only_by_timeout_is_not_a_stop():
    b = ClockBucket()
    b.put(f"{ds.AUDIT_PREFIX}/20261007T080000Z-9/boot.json", json.dumps({"boot": "x"}).encode())   # an older supervisor, never closed
    _boot(b, "20261007T100000Z-2", closed=True)                  # settled by timeout: no `settled` object
    born = _boot(b, "20261007T120000Z-3")
    assert _verdict(b, "20261007T120000Z-3", born) == "wait"
    assert _verdict(b, "20261007T120000Z-3", born, timed_out=True) == "timeout"


def test_an_older_supervisors_boot_json_with_closed_utc_counts_as_closed_at_its_bucket_time():
    b = ClockBucket()
    b.put(f"{ds.AUDIT_PREFIX}/20261006T080000Z-41/boot.json", json.dumps({"closed_utc": "2026-10-06T09:00:00Z"}).encode())
    b.advance(60)
    born = _boot(b, "20261007T120000Z-3")
    assert _verdict(b, "20261007T120000Z-3", born) == "ready"


def test_the_operators_line_cuts_off_the_boots_before_it():
    import json as _json
    b = ClockBucket()
    b.put(f"{ds.AUDIT_PREFIX}/20261006T080000Z-41/boot.json", _json.dumps({"boot": "unknown fate"}).encode())
    born = _boot(b, "20261007T120000Z-3")
    assert _verdict(b, "20261007T120000Z-3", born, timed_out=True) == "timeout"
    b.put(ds.LINE_OBJECT, _json.dumps({"boots_before": "20261007T000000Z"}).encode())
    assert _verdict(b, "20261007T120000Z-3", born) == "ready"


def test_two_boots_born_at_the_same_instant_wait_for_each_other():
    b = ClockBucket()
    born = b.put(ds.boot_object("20261007T120000Z-1", "born"))
    b.objects[ds.boot_object("20261007T120000Z-2", "born")] = dict(b.objects[ds.boot_object("20261007T120000Z-1", "born")])
    assert _verdict(b, "20261007T120000Z-1", born) == "wait"
    assert _verdict(b, "20261007T120000Z-2", born) == "wait"


def test_fencing_counts_only_boots_born_strictly_later_and_still_alive():
    b = ClockBucket()
    mine = _boot(b, "20261007T120000Z-1")
    v = ds.BootView(b)
    assert v.newer_than("20261007T120000Z-1", mine) == []
    b.objects[ds.boot_object("20261007T120001Z-7", "born")] = dict(b.objects[ds.boot_object("20261007T120000Z-1", "born")])
    assert ds.BootView(b).newer_than("20261007T120000Z-1", mine) == []          # same instant: not newer, both keep moving
    b.advance(5)
    _boot(b, "20261007T130000Z-2")
    v = ds.BootView(b)
    assert v.newer_than("20261007T120000Z-1", mine) == ["20261007T130000Z-2"]
    assert v.live("20261007T130000Z-2", b.t, 300)
    b.advance(301)
    assert not ds.BootView(b).live("20261007T130000Z-2", b.t, 300)


def _gen_file(state_dir, slot, num, payload=b"bundle"):
    d = state_dir / slot
    d.mkdir(parents=True, exist_ok=True)
    head = json.dumps({"generation": num, "sha256": "0" * 64, "prev_generation": num - 1, "prev_sha256": "", "size": len(payload), "sig": "ab" * 64},
                      sort_keys=True, separators=(",", ":")).encode() + b"\n"
    (d / f"{num:08d}.state").write_bytes(head + payload)
    return d / f"{num:08d}.state"


def test_a_generation_goes_up_once_with_the_uploading_boot_and_is_marked_only_then(tmp_path):
    b, st, marks, mirrored, conflicts = ClockBucket(), tmp_path / "state", tmp_path / "marks", {}, []
    _gen_file(st, "jdot-hq", 1)
    ok, slots = ds.state_pass(b, st, mirrored, "boot-1", conflicts, marks_dir=marks, fenced=lambda: None)
    key = f"{ds.STATE_PREFIX}/jdot-hq/00000001.state"
    assert ok and slots == {"jdot-hq"} and key in b.objects and b.objects[key]["meta"] == {"boot": "boot-1"}
    assert (marks / "state" / "jdot-hq" / "00000001").is_file()
    gen_before = b.objects[key]["gen"]
    assert ds.state_pass(b, st, mirrored, "boot-1", conflicts, marks_dir=marks, fenced=lambda: None) == (True, set())
    assert b.objects[key]["gen"] == gen_before                                  # not uploaded twice


def test_another_generation_under_the_same_number_is_a_conflict_kept_aside_and_never_marked(tmp_path):
    b, st, marks, conflicts = ClockBucket(), tmp_path / "state", tmp_path / "marks", []
    key = f"{ds.STATE_PREFIX}/jdot-hq/00000002.state"
    b.put(key, b"the bucket's generation 2")
    _gen_file(st, "jdot-hq", 2, b"this instance's generation 2")
    ok, _ = ds.state_pass(b, st, {}, "boot-1", conflicts, marks_dir=marks, fenced=lambda: None)
    assert ok and conflicts == [key] and b.objects[key]["data"] == b"the bucket's generation 2"
    assert f"{ds.CONFLICT_PREFIX}/boot-1/{key}" in b.objects
    assert not (marks / "state" / "jdot-hq" / "00000002").exists()


def test_a_fenced_instance_moves_no_generation_and_lets_the_letters_go(tmp_path):
    b, st, marks = ClockBucket(), tmp_path / "state", tmp_path / "marks"
    _gen_file(st, "jdot-hq", 3)
    asked = []
    ok, slots = ds.state_pass(b, st, {}, "boot-1", [], marks_dir=marks, fenced=lambda: asked.append(1) or "boot-2")
    assert ok and slots == set() and asked and not any(k.startswith(ds.STATE_PREFIX) for k in b.objects)
    assert not (marks / "state").exists()


def test_the_fence_is_asked_before_every_generation_not_once_a_pass(tmp_path):
    b, st, marks = ClockBucket(), tmp_path / "state", tmp_path / "marks"
    for n in (9, 10, 11):
        _gen_file(st, "jdot-hq", n)
    answers = iter([None, "boot-2", "boot-2"])                  # a newer boot appears after the first upload
    ok, _ = ds.state_pass(b, st, {}, "boot-1", [], marks_dir=marks, fenced=lambda: next(answers))
    went = sorted(k for k in b.objects if k.startswith(ds.STATE_PREFIX))
    assert ok and went == [f"{ds.STATE_PREFIX}/jdot-hq/00000009.state"]


def test_a_failed_generation_upload_means_no_quads_this_pass(tmp_path):
    b, st = ClockBucket(), tmp_path / "state"
    _gen_file(st, "jdot-hq", 1)
    b.fail_writes.add(f"{ds.STATE_PREFIX}/jdot-hq/00000001.state")
    assert ds.state_pass(b, st, {}, "boot-1", [], marks_dir=None, fenced=lambda: None)[0] is False


def test_restore_brings_the_newest_k_and_catch_up_only_higher_numbers(tmp_path):
    b, st, marks = ClockBucket(), tmp_path / "state", tmp_path / "marks"
    for n in (1, 2, 3, 4):
        b.put(f"{ds.STATE_PREFIX}/jdot-hq/{n:08d}.state", f"g{n}".encode())
    mirrored = ds.restore_state(b, st, keep=3)
    assert sorted(mirrored) == ["jdot-hq/00000002.state", "jdot-hq/00000003.state", "jdot-hq/00000004.state"]
    b.put(f"{ds.STATE_PREFIX}/jdot-hq/00000001.state", b"a late low one")        # lower than this disk's top: left
    b.put(f"{ds.STATE_PREFIX}/jdot-hq/00000009.state", b"g9")
    assert ds.catch_up_state(b, st, mirrored, marks) == ["jdot-hq/00000009.state"]
    assert (st / "jdot-hq" / "00000009.state").read_bytes() == b"g9" and (marks / "state" / "jdot-hq" / "00000009").is_file()
    assert not (st / "jdot-hq" / "00000001.state").exists()
    assert not [p.name for p in (st / "jdot-hq").iterdir() if p.name.startswith(".")]


def test_a_placed_generation_never_replaces_a_file_already_there(tmp_path):
    b, st = ClockBucket(), tmp_path / "state"
    b.put(f"{ds.STATE_PREFIX}/jdot-hq/00000005.state", b"from the bucket")
    (st / "jdot-hq").mkdir(parents=True)
    (st / "jdot-hq" / "00000005.state").write_bytes(b"written by serve")
    assert ds._place(st / "jdot-hq", "00000005.state", b.blob(f"{ds.STATE_PREFIX}/jdot-hq/00000005.state")) is False
    assert (st / "jdot-hq" / "00000005.state").read_bytes() == b"written by serve"


def test_prune_keeps_the_newest_k_and_deletes_only_what_it_listed():
    b = ClockBucket()
    for n in (1, 2, 3, 4, 5):
        b.put(f"{ds.STATE_PREFIX}/jdot-hq/{n:08d}.state", f"g{n}".encode())
    assert ds.prune_state(b, {"jdot-hq"}, keep=3) == 2
    assert sorted(k.rsplit("/", 1)[1] for k in b.objects) == ["00000003.state", "00000004.state", "00000005.state"]


def test_marks_start_over_at_boot_and_cover_what_the_restore_brought(tmp_path):
    marks = tmp_path / "marks"
    marks.mkdir()
    (marks / "settled").touch()                                   # left by an earlier run on a disk that survived
    ds.reset_marks(marks, {"hub-ops/from-x/001-sig.txt": 1, "hub-ops/from-x/001-envelope.json": 2},
                   {"jdot-hq/00000004.state": 9})
    assert sorted(str(p.relative_to(marks)) for p in marks.rglob("*") if p.is_file()) == [
        "quads/hub-ops/from-x/001", "state/jdot-hq/00000004"]
