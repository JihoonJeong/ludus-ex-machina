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
