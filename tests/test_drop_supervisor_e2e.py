"""The whole supervisor, start to finish, against a bucket made of files.

scripts/drop_supervisor.py cannot be rehearsed on Render: it needs the real
bucket and the real token list. This runs it as a real subprocess — restore,
`organum-hub serve`, mirror passes, SIGTERM, final pass, a second boot — with
the google client replaced by a stub that keeps objects in a directory and
enforces the one GCS rule the supervisor leans on (if_generation_match=0).
"""

from __future__ import annotations

import base64
import json
import os
import signal
import socket
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HUB = Path(sys.executable).parent / "organum-hub"
TOKEN = "e2e-token-for-this-test-only"

STUB = {
    "google/__init__.py": "",
    "google/cloud/__init__.py": "",
    "google/oauth2/__init__.py": "",
    "google/api_core/__init__.py": "",
    "google/api_core/exceptions.py": "class PreconditionFailed(Exception):\n    pass\n",
    "google/oauth2/service_account.py": textwrap.dedent("""
        class Credentials:
            @classmethod
            def from_service_account_info(cls, info):
                return cls()
    """),
    "google/cloud/storage.py": textwrap.dedent("""
        import os, shutil
        from pathlib import Path
        from google.api_core.exceptions import PreconditionFailed
        STORE = Path(os.environ["FAKE_GCS_DIR"])

        class Blob:
            def __init__(self, bucket, name):
                self.bucket, self.name = bucket, name
            def _path(self):
                return STORE / self.name
            def upload_from_filename(self, path, if_generation_match=None):
                p = self._path()
                if if_generation_match == 0 and p.exists():
                    raise PreconditionFailed(self.name)
                self._put(Path(path).read_bytes())
            def upload_from_string(self, data, content_type=None):
                self._put(data.encode() if isinstance(data, str) else data)
            def _put(self, data):
                # an object appears whole or not at all, as in the real bucket
                p = self._path()
                p.parent.mkdir(parents=True, exist_ok=True)
                tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
                tmp.write_bytes(data)
                os.replace(tmp, p)
            def download_to_filename(self, path):
                shutil.copyfile(self._path(), path)
            def download_as_bytes(self):
                return self._path().read_bytes()

        class Bucket:
            def __init__(self, client, name):
                self.client, self.name = client, name
            def blob(self, name):
                return Blob(self, name)

        class Client:
            def __init__(self, credentials=None):
                pass
            def bucket(self, name):
                return Bucket(self, name)
            def list_blobs(self, bucket, prefix=""):
                return [Blob(bucket, str(p.relative_to(STORE))) for p in sorted(STORE.rglob("*"))
                        if p.is_file() and not p.name.startswith(".")
                        and str(p.relative_to(STORE)).startswith(prefix)]
    """),
}


def _free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _req(port, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                               headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=15) as resp:
        return resp.status, json.loads(resp.read())


class Supervisor:
    def __init__(self, tmp: Path, name: str, **more_env: str):
        self.port = _free_port()
        self.root, self.audit = tmp / f"{name}-root", tmp / f"{name}-audit"
        env = dict(os.environ, GCS_SA_KEY_JSON="{}", FAKE_GCS_DIR=str(tmp / "gcs"), DROP_TOKEN_FILE=str(tmp / "tokens.txt"),
                   DROP_ROOT=str(self.root), DROP_AUDIT_DIR=str(self.audit), DROP_SYNC_INTERVAL="1", PORT=str(self.port),
                   PYTHONPATH=str(tmp / "stub"), PATH=f"{HUB.parent}{os.pathsep}{os.environ.get('PATH', '')}")
        env.pop("DROP_AUDIT", None)
        env.update(more_env)
        self.proc = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "drop_supervisor.py")], env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def wait_up(self, seconds: float = 20.0) -> bool:
        t0 = time.time()
        while time.time() - t0 < seconds and self.proc.poll() is None:
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.3).close(); return True
            except OSError:
                time.sleep(0.1)
        return False

    def stop(self) -> tuple[int, str]:
        self.proc.send_signal(signal.SIGTERM)
        out, _ = self.proc.communicate(timeout=30)
        return self.proc.returncode, out


@pytest.fixture
def world(tmp_path):
    if "--audit-log" not in subprocess.run([str(HUB), "serve", "--help"], capture_output=True, text=True).stdout:
        pytest.skip("installed organum has no --audit-log")
    for rel, src in STUB.items():
        p = tmp_path / "stub" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    (tmp_path / "tokens.txt").write_text(f"# e2e\n{TOKEN}  id=e2e\n")
    seed = tmp_path / "gcs" / "drop-root" / "hub-ops" / "from-old"
    seed.mkdir(parents=True)
    (seed / "001-sig.txt").write_text("ab" * 64 + "\n")
    (seed / "001-envelope.json").write_text('{"old": true}')
    return tmp_path


def _audit_objects(tmp: Path) -> dict[str, list[dict]]:
    out = {}
    for p in sorted((tmp / "gcs" / "drop-audit").rglob("audit-*.jsonl")) if (tmp / "gcs" / "drop-audit").is_dir() else []:
        out[str(p.relative_to(tmp / "gcs"))] = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return out


def test_restore_serve_mirror_stop_and_a_second_boot(world):
    tmp = world
    a = Supervisor(tmp, "a")
    try:
        assert a.wait_up(), a.proc.stdout.read() if a.proc.poll() is not None else "serve never bound"
        st, j = _req(a.port, "GET", "/v0/channels")
        assert st == 200 and j["channels"] == {"hub-ops": ["from-old"]}            # the restore brought the old quad back
        quad = {"n": "001", "envelope_b64": base64.b64encode(b'{"new": 1}').decode(), "sig": "cd" * 64}
        st, j = _req(a.port, "POST", "/v0/hub-ops/from-e2e", quad)
        assert st == 200 and j["stored"] and not j["dedup"]
        time.sleep(2.5)                                                            # one mirror pass
        new = tmp / "gcs" / "drop-root" / "hub-ops" / "from-e2e"
        assert (new / "001-envelope.json").read_bytes() == b'{"new": 1}' and (new / "001-sig.txt").is_file()
        mid = _audit_objects(tmp)
        assert len(mid) == 1 and sum(len(v) for v in mid.values()) == 2            # the two requests so far
        _req(a.port, "GET", "/v0/hub-ops/from-e2e?since=000")                      # ...and one more, just before the stop
    finally:
        rc, log_a = a.stop()
    assert rc == 0, log_a
    assert "audit log on:" in log_a and "final audit mirror done" in log_a
    (key, lines), = _audit_objects(tmp).items()
    assert key.startswith("drop-audit/") and key.count("/") == 2                   # drop-audit/<boot>/audit-YYYYMMDD.jsonl
    assert [(l["method"], l["status"]) for l in lines] == [("GET", 200), ("POST", 200), ("GET", 200)]
    assert all(l["id"] == "e2e" for l in lines) and TOKEN not in json.dumps(lines)
    assert not any("audit" in str(p) for p in a.root.rglob("*"))                   # never inside the transport tree

    b = Supervisor(tmp, "b")
    try:
        assert b.wait_up()
        st, j = _req(b.port, "GET", "/v0/channels")
        assert j["channels"] == {"hub-ops": ["from-e2e", "from-old"]}              # both quads restored on the next boot
        assert not any("audit" in p.name for p in b.root.rglob("*"))               # the audit log is not restored
        time.sleep(2.0)
    finally:
        rc, log_b = b.stop()
    assert rc == 0, log_b
    objs = _audit_objects(tmp)
    assert len(objs) == 2 and key in objs and objs[key] == lines                   # boot A's log untouched; boot B has its own


def _boot_records(tmp: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((tmp / "gcs" / "drop-audit").rglob("boot.json"))]


def test_what_the_old_instance_takes_after_the_new_one_restored_reaches_the_new_one_without_a_restart(world):
    """A redeploy, in small: A keeps taking traffic while B has already read the
    bucket. The quad A accepts then is in the bucket and not on B's disk — until
    B's catch-up reads the listing again."""
    tmp = world
    a = Supervisor(tmp, "a")
    b = None
    try:
        assert a.wait_up()
        b = Supervisor(tmp, "b", DROP_CATCHUP_AT="3,6,9", DROP_CATCHUP_EVERY="0")
        assert b.wait_up()                                                         # B's restore is over: it knows only the old quad
        quad = {"n": "001", "envelope_b64": base64.b64encode(b'{"late": 1}').decode(), "sig": "ef" * 64,
                "body_name": "body.md", "body_b64": base64.b64encode(b"# taken by A after B restored\n").decode()}
        st, j = _req(a.port, "POST", "/v0/hub-ops/from-late", quad)
        assert st == 200 and j["stored"]
        assert _req(b.port, "GET", "/v0/channels")[1]["channels"] == {"hub-ops": ["from-old"]}   # the window: B does not show it
        got, t0 = None, time.time()
        while time.time() - t0 < 20:
            _, page = _req(b.port, "GET", "/v0/hub-ops/from-late?since=000")
            if page["quads"]:
                got = page["quads"][0]; break
            time.sleep(0.3)
        assert got is not None, "B never fetched the quad A took"
        assert {k: got[k] for k in quad} == quad                                   # byte for byte what A was given
        st, j = _req(b.port, "POST", "/v0/hub-ops/from-late", quad)                # the sender's re-push is a dedup, not a second copy
        assert st == 200 and j["dedup"]
    finally:
        rc_a, log_a = a.stop()
        rc_b, log_b = b.stop() if b else (0, "")
    assert rc_a == 0 and rc_b == 0, log_a + log_b
    assert "catch-up: 1 quad(s)" in log_b and "hub-ops/from-late/001" in log_b and "CONFLICT" not in log_a + log_b
    assert not [p.name for p in b.root.rglob(".*")]                                # no temp file left in the transport tree
    recs = {r["boot"]: r for r in _boot_records(tmp)}
    assert len(recs) == 2
    rec_b = next(r for r in recs.values() if any(c.get("fetched") for c in r["catch_ups"]))
    assert [c["fetched"] for c in rec_b["catch_ups"] if c.get("fetched")] == [["hub-ops/from-late/001"]]
    for r in recs.values():
        assert r["restore_started_utc"] <= r["restore_done_utc"] <= r["serve_started_utc"] <= r["closed_utc"]
        assert r["conflicts"] == []
