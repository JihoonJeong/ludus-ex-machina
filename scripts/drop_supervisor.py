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

Env:
  GCS_SA_KEY_JSON     service-account key JSON string (required; refuses to
                      start without — the mirror IS the durable state)
  DROP_GCS_BUCKET     bucket name (default "lxm-drop" — must be PRIVATE; the
                      public replay bucket must not hold envelopes)
  DROP_GCS_PREFIX     object prefix inside the bucket (default "drop-root")
  DROP_ROOT           local ephemeral root (default "/tmp/drop-root")
  DROP_TOKEN_FILE     token file (default "/etc/secrets/drop-tokens.txt",
                      a Render Secret File)
  DROP_SYNC_INTERVAL  seconds between mirror passes (default 30)
  DROP_RATE_LIMIT     per-token per-minute budget (default 60)
  PORT                injected by Render (default 8642)
"""

from __future__ import annotations

import json
import logging
import os
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


def gcs_bucket():
    from google.cloud import storage
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GCS_SA_KEY_JSON"]))
    client = storage.Client(credentials=creds)
    return client.bucket(os.getenv("DROP_GCS_BUCKET", "lxm-drop"))


def restore(bucket, root: Path) -> dict[str, int]:
    """Download the mirror into --root; returns {relpath: size} as the seed of
    the mirrored-set."""
    mirrored: dict[str, int] = {}
    for blob in bucket.client.list_blobs(bucket, prefix=PREFIX + "/"):
        rel = blob.name[len(PREFIX) + 1:]
        if not rel or ".." in Path(rel).parts:
            continue
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest))
        mirrored[rel] = dest.stat().st_size
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
    interval = float(os.getenv("DROP_SYNC_INTERVAL", "30"))

    bucket = gcs_bucket()
    mirrored = restore(bucket, root)
    log.info("restored %d files from gs://%s/%s", len(mirrored), bucket.name, PREFIX)

    child = subprocess.Popen(["organum-hub", "serve",
                              "--root", str(root), "--token-file", token_file,
                              "--bind", "0.0.0.0",
                              "--port", os.getenv("PORT", "8642"),
                              "--rate-limit", os.getenv("DROP_RATE_LIMIT", "60")])
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
    if stop.is_set():
        return 0
    log.error("serve exited unexpectedly (rc=%s)", child.returncode)
    return child.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
