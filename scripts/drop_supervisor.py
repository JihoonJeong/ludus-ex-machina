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

"Already there" is not "the same thing is there". When the bucket refuses an
upload because the name is taken, the pass now compares the bytes. If they
differ, the bucket's object stays (a letter is never replaced), the pass says
so at ERROR, and this instance's bytes are kept under
gs://<bucket>/<conflict-prefix>/<boot>/ so the next restart — which serves
the bucket's version — does not erase the only copy of the other one.

Honest loss window: a hard kill (no SIGTERM) loses envelopes received since the
last mirror pass. The envelope layer detects non-receipt and re-push is
idempotent under dedup, so this is bounded, detectable loss — not disk-grade
durability.

The window a redeploy opens. Render starts the new instance while the old
one still takes the traffic, and moves the traffic only once the new one is
up. The new instance reads the bucket's listing once, at the start of its
restore. Whatever the old instance accepts after that reaches the bucket (its
passes keep running, and SIGTERM gets a final one) but not this instance's
disk: the door does not show it until the next restart. So after serve is up
the supervisor reads the listing again — at DROP_CATCHUP_AT seconds, then
every DROP_CATCHUP_EVERY — and fetches every complete quad the bucket holds
and this disk has no file of. A number with any file here is left alone:
serve may be writing it, and a local quad is never mixed with the bucket's.
Files arrive under a dot name and are linked into place only if the name is
free, the envelope last, so serve never lists a half quad.

Each boot also leaves gs://<bucket>/<audit-prefix>/<boot>/boot.json: when the
restore began and ended, when serve started, what each catch-up fetched, what
conflicted, and when the final pass was done. The boot directory's name
carries the time the restore ENDED; the window opens when it began, so the
record is what an overlap is measured from.

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
  DROP_CONFLICT_PREFIX object prefix for local bytes the bucket already holds
                      differently (default "drop-conflicts"; never restored)
  DROP_CATCHUP_AT     seconds after serve starts at which the bucket listing
                      is read again (default "60,180,420"; "" for none)
  DROP_CATCHUP_EVERY  seconds between later re-reads (default 900; 0 for none)
  DROP_RESTORE_WORKERS parallel downloads during boot restore (default 16)
  PORT                injected by Render (default 8642)
"""

from __future__ import annotations

import json
import logging
import os
import re
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
CONFLICT_PREFIX = os.getenv("DROP_CONFLICT_PREFIX", "drop-conflicts").strip("/")
_QUAD_FILE = re.compile(r"^(\d{3,6})-")


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


def sync_pass(bucket, root: Path, mirrored: dict[str, int],
              boot: str | None = None, conflicts: list[str] | None = None) -> int:
    """Upload files not yet mirrored — non-envelope files before envelopes, and
    abort the pass on the first failure (retried whole next pass), so envelope-
    last ordering holds in the bucket too.

    A name the bucket already holds is compared, not assumed equal. Different
    bytes are reported and, when `boot` is given, kept under the conflict
    prefix; the bucket's object is not touched. Either way the file is then
    counted as dealt with, so one conflict is reported once, not every pass."""
    from google.api_core.exceptions import PreconditionFailed
    pending = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
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
            try:
                same = blob.download_as_bytes() == p.read_bytes()
            except Exception as e:
                log.warning("could not compare %s with the bucket (%s) — pass aborted, retrying next pass", rel, e)
                return uploaded
            if not same:
                kept = _keep_conflict(bucket, boot, rel, p)
                log.error("CONFLICT %s: the bucket holds different bytes under this name. The bucket's "
                          "object is left as it is; the next restart will serve it, not what this "
                          "instance serves now. Local bytes %s", rel, kept)
                if conflicts is not None:
                    conflicts.append(rel)
        except Exception as e:
            log.warning("mirror of %s failed (%s) — pass aborted, retrying next pass", rel, e)
            return uploaded
        mirrored[rel] = p.stat().st_size
        uploaded += 1
    return uploaded


def _keep_conflict(bucket, boot: str | None, rel: str, p: Path) -> str:
    """Put this instance's bytes where a restart cannot erase them; say where."""
    if boot is None:
        return "not kept (no boot name)"
    name = f"{CONFLICT_PREFIX}/{boot}/{rel}"
    try:
        bucket.blob(name).upload_from_filename(str(p))
    except Exception as e:
        return f"NOT kept ({e})"
    return f"kept at {name}"


def catch_up(bucket, root: Path, mirrored: dict[str, int], fetched: list[str] | None = None) -> list[str]:
    """Fetch every complete quad the bucket holds and this disk has no file of.

    Returns the quads fetched, as "<channel>/<door>/<NNN>". A quad is complete
    in the bucket when its envelope is listed (the mirror uploads it last). A
    number with any file here already is left alone, whatever the bucket says.
    Raises on a failed listing or download; nothing half-fetched is left, and
    an envelope is only ever linked after its quad's other files. A caller
    that passes `fetched` still has the quads fetched before the failure.
    """
    fetched = [] if fetched is None else fetched
    listed: dict[tuple[str, str], list[tuple[str, object]]] = {}
    for blob in bucket.client.list_blobs(bucket, prefix=PREFIX + "/"):
        rel = blob.name[len(PREFIX) + 1:]
        if not rel or ".." in Path(rel).parts or "/" not in rel:
            continue
        parent, name = rel.rsplit("/", 1)
        m = _QUAD_FILE.match(name)
        if m:
            listed.setdefault((parent, m.group(1)), []).append((name, blob))
    for (parent, n), files in sorted(listed.items()):
        if not any(name == f"{n}-envelope.json" for name, _ in files):
            continue
        dirp = root / parent
        if dirp.is_dir() and any(dirp.glob(f"{n}-*")):
            continue
        dirp.mkdir(parents=True, exist_ok=True)
        files.sort(key=lambda f: f[0].endswith("-envelope.json"))
        tmps, placed = [], []
        try:
            for name, blob in files:
                tmp = dirp / f".{name}.part-{os.getpid()}"
                tmps.append(tmp)
                blob.download_to_filename(str(tmp))
            for (name, _), tmp in zip(files, tmps):
                try:
                    os.link(tmp, dirp / name)
                except FileExistsError:
                    # serve began writing this number between the look and the
                    # link. Its files win; forget ours so the next pass compares.
                    for rel in placed:
                        mirrored.pop(rel, None)
                    placed = []
                    break
                placed.append(f"{parent}/{name}")
                mirrored[placed[-1]] = tmp.stat().st_size
        finally:
            for tmp in tmps:
                tmp.unlink(missing_ok=True)
        if placed:
            fetched.append(f"{parent}/{n}")
    return fetched


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_boot_record(bucket, boot: str, record: dict) -> None:
    """Overwrite this boot's record. Never worth stopping the drop for."""
    try:
        bucket.blob(f"{AUDIT_PREFIX}/{boot}/boot.json").upload_from_string(
            json.dumps(record, sort_keys=True) + "\n", content_type="application/json")
    except Exception as e:
        log.warning("boot record not written (%s)", e)


def catchup_schedule() -> tuple[list[float], float]:
    """(seconds after serve start for the early re-reads, period of the later ones)."""
    at = sorted(float(x) for x in os.getenv("DROP_CATCHUP_AT", "60,180,420").split(",") if x.strip())
    return at, float(os.getenv("DROP_CATCHUP_EVERY", "900") or 0)


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
    record = {"restore_started_utc": utc_now(), "catch_ups": [], "conflicts": []}
    mirrored = restore(bucket, root)
    record.update(restore_done_utc=utc_now(), restored_files=len(mirrored))
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
    record.update(boot=boot, serve_started_utc=utc_now())
    write_boot_record(bucket, boot, record)
    serve_up = time.monotonic()
    early, every = catchup_schedule()
    next_catchup = early.pop(0) if early else (every or None)

    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())

    try:
        while not stop.is_set() and child.poll() is None:
            deadline = time.monotonic() + interval
            while (not stop.is_set() and child.poll() is None
                   and time.monotonic() < deadline):
                stop.wait(1.0)
            seen = len(record["conflicts"])
            n = sync_pass(bucket, root, mirrored, boot, record["conflicts"])
            if n:
                log.info("mirrored %d new files", n)
            if audit_dir is not None:
                audit_sync_pass(bucket, audit_dir, boot, audit_mirrored)
            due = next_catchup is not None and time.monotonic() - serve_up >= next_catchup
            if due:
                entry = {"utc": utc_now(), "fetched": []}
                try:
                    catch_up(bucket, root, mirrored, entry["fetched"])
                except Exception as e:
                    entry["error"] = str(e)
                    log.warning("catch-up failed (%s) — the next one will try again", e)
                else:
                    log.info("catch-up: %d quad(s) the bucket had and this disk did not%s",
                             len(entry["fetched"]), ": " + " ".join(entry["fetched"]) if entry["fetched"] else "")
                record["catch_ups"].append(entry)
                next_catchup = early.pop(0) if early else (next_catchup + every if every else None)
            if due or len(record["conflicts"]) != seen:
                write_boot_record(bucket, boot, record)
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
        # serve is down, nothing is mid-write — this pass captures everything
        sync_pass(bucket, root, mirrored, boot, record["conflicts"])
        log.info("final mirror done (%d files total)", len(mirrored))
        if audit_dir is not None:
            audit_sync_pass(bucket, audit_dir, boot, audit_mirrored)
            log.info("final audit mirror done (%d file(s))", len(audit_mirrored))
        record["closed_utc"] = utc_now()
        write_boot_record(bucket, boot, record)
    if stop.is_set():
        return 0
    log.error("serve exited unexpectedly (rc=%s)", child.returncode)
    return child.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
