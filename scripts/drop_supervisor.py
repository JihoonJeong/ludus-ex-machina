#!/usr/bin/env python3
"""Hosted organum-hub drop on Render free plan — GCS-mirrored --root supervisor.

The drop server (`organum-hub serve`, unmodified) keeps its only state under
--root. Render's free plan has no persistent disk, so this wrapper substitutes
LxM's existing GCS durable layer (same credential pattern as server/gcs_export.py):

  boot:     restore gs://<bucket>/<prefix>/** -> --root, then start serve
  running:  mirror new files to GCS every DROP_SYNC_INTERVAL seconds
  SIGTERM:  stop serve first, then a final mirror pass (deploys and free-plan
            spin-downs are graceful SIGTERMs, so this covers them)

Mirror discipline inherits serve's write discipline: quad files are immutable
once written and the envelope is the completion marker (written last). Each
mirror pass uploads every non-envelope file before any envelope, and a pass
aborts on the first upload failure, so the bucket can never hold an envelope
whose sig is missing — a restored partial quad (sig without envelope) stays
re-pushable, because serve's 409 dedup only triggers on a non-empty envelope
file. Uploads use if_generation_match=0: an object, once written, is never
overwritten.

Honest loss window: a hard kill (no SIGTERM) loses envelopes received since the
last mirror pass. The envelope layer detects non-receipt and re-push is
idempotent under dedup, so this is bounded, detectable loss — not disk-grade
durability.

Audit log (organum 0.7.0, `serve --audit-log`): one JSON line per authenticated
request — which token id read or wrote which door. Those files GROW all day,
so the quad rule above cannot carry them: "never overwrite" would upload the
first few lines and report every later one as already there. They get their
own rule:

  boot:     a directory unique to this boot, outside --root, handed to serve
  running:  each pass re-uploads an audit file whose size changed, overwriting
            its object under gs://<bucket>/<audit-prefix>/<boot>/ — a path only
            this instance writes
  restore:  never. The audit prefix is not under the root prefix, so the log
            does not lengthen the cold start however long it gets.

Same loss window as the quads: the last DROP_SYNC_INTERVAL seconds on a hard
kill, nothing on SIGTERM. Retention is a lifecycle rule on the audit prefix
(the supervisor deletes nothing). If the installed organum has no --audit-log
(0.6.0), the supervisor says so and runs without it.

Env:
  GCS_SA_KEY_JSON     service-account key JSON string (required; refuses to
                      start without — the mirror IS the durable state)
  DROP_GCS_BUCKET     bucket name (default "lxm-drop" — must be PRIVATE; the
                      public replay bucket must not hold envelopes)
  DROP_GCS_PREFIX     object prefix inside the bucket (default "drop-root")
  DROP_ROOT           local ephemeral root (default "/tmp/drop-root")
  DROP_TOKEN_FILE     token file (default "/etc/secrets/drop-tokens.txt",
                      a Render Secret File)
  DROP_SYNC_INTERVAL  seconds between mirror passes (default 5 — an idle pass
                      is a local stat walk with zero GCS calls, so a short
                      interval narrows the loss window at no idle cost)
  DROP_RATE_LIMIT     per-token per-minute budget (default 60)
  DROP_AUDIT          "0" turns the audit log off (default on when serve
                      supports it)
  DROP_AUDIT_DIR      local parent of the per-boot audit directory (default
                      "/tmp/drop-audit" — must stay outside DROP_ROOT)
  DROP_AUDIT_PREFIX   object prefix for the audit mirror (default "drop-audit")
  DROP_RESTORE_WORKERS parallel downloads during boot restore (default 16)
  PORT                injected by Render (default 8642)
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s drop-supervisor %(levelname)s %(message)s")
log = logging.getLogger("drop_supervisor")

PREFIX = os.getenv("DROP_GCS_PREFIX", "drop-root").strip("/")
AUDIT_PREFIX = os.getenv("DROP_AUDIT_PREFIX", "drop-audit").strip("/")


def gcs_bucket():
    from google.cloud import storage
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GCS_SA_KEY_JSON"]))
    client = storage.Client(credentials=creds)
    return client.bucket(os.getenv("DROP_GCS_BUCKET", "lxm-drop"))


def restore(bucket, root: Path, workers: int | None = None) -> dict[str, int]:
    """Download the mirror into --root; returns {relpath: size} as the seed of
    the mirrored-set.

    Parallel since 2026-09-12. Until then this was one HTTPS round trip per
    object, in sequence, and the mirror had grown to ~1,800 objects: every
    cold start and every deploy paid roughly 0.2 s x objects before serve
    could bind. That loop, not the platform, is where the federation's rising
    "cold-start" numbers came from (102 s in late August, 380 s by
    mid-September, tracking the object count), and on 2026-09-12 a deploy
    failed Render's port scan on it. Objects are immutable and names unique,
    so downloads are independent and N workers divide the wall clock by ~N.
    A failed download raises: a partial restore must never be served.
    """
    if workers is None:
        workers = int(os.getenv("DROP_RESTORE_WORKERS", "16"))
    blobs = []
    for blob in bucket.client.list_blobs(bucket, prefix=PREFIX + "/"):
        rel = blob.name[len(PREFIX) + 1:]
        if not rel or ".." in Path(rel).parts:
            continue
        blobs.append((rel, blob))

    def fetch(item):
        rel, blob = item
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest))
        return rel, dest.stat().st_size

    mirrored: dict[str, int] = {}
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for i, (rel, size) in enumerate(ex.map(fetch, blobs), 1):
            mirrored[rel] = size
            if i % 500 == 0:
                log.info("restore: %d/%d files, %.0fs", i, len(blobs), time.monotonic() - t0)
    return mirrored


def sync_pass(bucket, root: Path, mirrored: dict[str, int]) -> int:
    """Upload files not yet mirrored — non-envelope files before envelopes, and
    abort the pass on the first failure (retried whole next pass), so envelope-
    last ordering holds in the bucket too."""
    from google.api_core.exceptions import PreconditionFailed
    pending = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if mirrored.get(rel) == p.stat().st_size:
            continue
        pending.append((rel, p))
    pending.sort(key=lambda rp: rp[0].endswith("-envelope.json"))
    uploaded = 0
    for rel, p in pending:
        blob = bucket.blob(f"{PREFIX}/{rel}")
        try:
            blob.upload_from_filename(str(p), if_generation_match=0)
        except PreconditionFailed:
            pass  # object already in the bucket (files are immutable)
        except Exception as e:
            log.warning("mirror of %s failed (%s) — pass aborted, retrying next pass", rel, e)
            return uploaded
        mirrored[rel] = p.stat().st_size
        uploaded += 1
    return uploaded


def serve_supports_audit() -> bool:
    """organum-hub serve grew --audit-log in 0.7.0. Asked of the installed
    binary, so this file deploys safely before or after the upgrade."""
    try:
        out = subprocess.run(["organum-hub", "serve", "--help"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "--audit-log" in (out.stdout + out.stderr)


def boot_stamp() -> str:
    """Names this boot's audit directory: UTC start time plus the pid, so two
    instances overlapping during a deploy never share a path."""
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + f"-{os.getpid()}"


def audit_sync_pass(bucket, audit_dir: Path, boot: str, mirrored: dict[str, int]) -> int:
    """Upload every audit file whose size changed since it was last mirrored,
    overwriting its object. The size recorded is the one read BEFORE the
    upload: lines appended while it ran make the next pass upload again."""
    uploaded = 0
    if not audit_dir.is_dir():
        return 0
    for p in sorted(audit_dir.glob("audit-*.jsonl")):
        size = p.stat().st_size
        if mirrored.get(p.name) == size:
            continue
        try:
            bucket.blob(f"{AUDIT_PREFIX}/{boot}/{p.name}").upload_from_filename(str(p))
        except Exception as e:
            log.warning("audit mirror of %s failed (%s) — retrying next pass", p.name, e)
            continue
        mirrored[p.name] = size
        uploaded += 1
    return uploaded


def main() -> int:
    if not os.getenv("GCS_SA_KEY_JSON"):
        log.error("GCS_SA_KEY_JSON unset — refusing to serve on ephemeral disk only")
        return 1
    token_file = os.getenv("DROP_TOKEN_FILE", "/etc/secrets/drop-tokens.txt")
    if not Path(token_file).is_file():
        log.error("token file %s missing — refusing to start an open drop", token_file)
        return 1
    root = Path(os.getenv("DROP_ROOT", "/tmp/drop-root"))
    root.mkdir(parents=True, exist_ok=True)
    interval = float(os.getenv("DROP_SYNC_INTERVAL", "5"))

    bucket = gcs_bucket()
    t0 = time.monotonic()
    mirrored = restore(bucket, root)
    log.info("restored %d files from gs://%s/%s in %.1fs", len(mirrored), bucket.name, PREFIX,
             time.monotonic() - t0)

    cmd = ["organum-hub", "serve",
           "--root", str(root), "--token-file", token_file,
           "--bind", "0.0.0.0",
           "--port", os.getenv("PORT", "8642"),
           "--rate-limit", os.getenv("DROP_RATE_LIMIT", "60")]
    audit_dir, boot, audit_mirrored = None, boot_stamp(), {}
    if os.getenv("DROP_AUDIT", "1") != "0":
        if serve_supports_audit():
            audit_dir = Path(os.getenv("DROP_AUDIT_DIR", "/tmp/drop-audit")) / boot
            if root.resolve() in audit_dir.resolve().parents or audit_dir.resolve() == root.resolve():
                log.error("audit dir %s is inside the transport root %s — refusing", audit_dir, root)
                return 1
            audit_dir.mkdir(parents=True, exist_ok=True)
            cmd += ["--audit-log", str(audit_dir)]
            log.info("audit log on: %s -> gs://%s/%s/%s/", audit_dir, bucket.name, AUDIT_PREFIX, boot)
        else:
            log.warning("installed organum-hub serve has no --audit-log (< 0.7.0) — running WITHOUT an audit log")
    child = subprocess.Popen(cmd)
    log.info("serve up on :%s (pid %d)", os.getenv("PORT", "8642"), child.pid)

    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())

    try:
        while not stop.is_set() and child.poll() is None:
            deadline = time.monotonic() + interval
            while (not stop.is_set() and child.poll() is None
                   and time.monotonic() < deadline):
                stop.wait(1.0)
            n = sync_pass(bucket, root, mirrored)
            if n:
                log.info("mirrored %d new files", n)
            if audit_dir is not None:
                audit_sync_pass(bucket, audit_dir, boot, audit_mirrored)
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
        # serve is down, nothing is mid-write — this pass captures everything
        sync_pass(bucket, root, mirrored)
        log.info("final mirror done (%d files total)", len(mirrored))
        if audit_dir is not None:
            audit_sync_pass(bucket, audit_dir, boot, audit_mirrored)
            log.info("final audit mirror done (%d file(s))", len(audit_mirrored))
    if stop.is_set():
        return 0
    log.error("serve exited unexpectedly (rc=%s)", child.returncode)
    return child.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
