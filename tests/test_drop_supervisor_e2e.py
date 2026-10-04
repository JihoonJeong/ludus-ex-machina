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
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, p)
            def download_to_filename(self, path):
                shutil.copyfile(self._path(), path)

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
                        if p.is_file() and str(p.relative_to(STORE)).startswith(prefix)]
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
    def __init__(self, tmp: Path, name: str):
        self.port = _free_port()
        self.root, self.audit = tmp / f"{name}-root", tmp / f"{name}-audit"
        env = dict(os.environ, GCS_SA_KEY_JSON="{}", FAKE_GCS_DIR=str(tmp / "gcs"), DROP_TOKEN_FILE=str(tmp / "tokens.txt"),
                   DROP_ROOT=str(self.root), DROP_AUDIT_DIR=str(self.audit), DROP_SYNC_INTERVAL="1", PORT=str(self.port),
                   PYTHONPATH=str(tmp / "stub"), PATH=f"{HUB.parent}{os.pathsep}{os.environ.get('PATH', '')}")
        env.pop("DROP_AUDIT", None)
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
