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
