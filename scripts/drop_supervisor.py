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
conflicted, and when the final pass was done. Since organum 0.8.0 the boot's
name is taken when the process starts, before the restore (until then it was
taken after, so older names carry the time the restore ended).

State slot (organum 0.8.0, `serve --state-dir --marks-dir`; design memo v0.12
with Organum, LxM 120-136). An uploader keeps its ledger in the drop as one
bundle per generation, `<state-dir>/<id>/NNNNNNNN.state`, written by serve.
Serve's 200 only means "received". What tells the uploader a generation or a
letter is outside — in the bucket — is a MARK, an empty file this supervisor
writes under --marks-dir after the upload, and serve reads:

  marks:    quads/<channel>/<from-x>/<NNN>   the quad's envelope is in the bucket
            state/<id>/<NNNNNNNN>            that generation file is in the bucket
            settled / settled-by-timeout     this instance has caught up with
                                             every boot before it / gave up waiting

  per boot, in gs://<bucket>/<audit-prefix>/<boot>/ (the bucket's clock decides
  every "before" and "after" — the instances' clocks are never compared):
            born     written once, BEFORE the restore lists the bucket
            alive    rewritten every DROP_ALIVE_EVERY seconds by its own thread,
                     restore included; DROP_ALIVE_STALE without one = stopped
            closed   written once, after the final pass's uploads
            settled  written once, when settled (not when only by timeout)

  settling: walk back over earlier boots to the nearest one that settled (or
            the operator's line, gs://<bucket>/<audit-prefix>/line). Each must
            have closed before this boot was born (then this restore saw it
            all), or be seen closed or stopped and then a catch-up done. A
            live one is waited for, however long. A boot with no `born` but a
            boot.json (the supervisor of 2026-10-05) counts as closed if that
            record says `closed_utc`, at the object's bucket time; otherwise
            it can only be timed out: DROP_SETTLE_TIMEOUT, then a catch-up,
            then settled-by-timeout, which restores refuse by default. Boots
            older still left no record and are not looked at. The line object
            ({"boots_before": "<boot name prefix>"}) is how the operator closes
            off boots whose fate cannot be read; it is written by hand, once.
  mirror:   each pass lists the quads, then the generations, uploads the
            generations, then the quads. A generation that vanished (serve
            keeps only the newest --state-keep) or an upload that failed means
            no quads this pass. Before each generation upload: if a boot born
            after this one is alive, this instance no longer moves generations
            (letters it still moves). Generations are written once, like
            quads; different bytes under a taken name are a CONFLICT — kept
            aside, never marked. Only the newest boot deletes generations
            beyond the newest --state-keep in the bucket, each delete
            conditional on the object it listed.
  re-read:  a catch-up also fetches generations numbered above this disk's
            highest, placed the way serve places them (dot name ending .tmp,
            linked only if the name is free).

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
  DROP_STATE          "0" leaves the state slot off (default on when serve
                      has --state-dir and --marks-dir)
  DROP_STATE_DIR      local state slot directory (default "/tmp/drop-state")
  DROP_MARKS_DIR      local marks directory (default "/tmp/drop-marks"); emptied
                      at every boot — it speaks about this instance only
  DROP_STATE_PREFIX   object prefix for generations (default "drop-state")
  DROP_STATE_KEEP     generations kept per slot, here and in the bucket (default 3)
  DROP_STATE_MAX_BYTES  bundle limit handed to serve (default 1048576)
  DROP_STATE_MAX_JUMP   floor_generation allowance handed to serve (default 10000)
  DROP_ALIVE_EVERY    seconds between `alive` rewrites (default 60)
  DROP_ALIVE_STALE    seconds without one after which a boot counts as stopped
                      (default 300)
  DROP_SETTLE_TIMEOUT seconds after serve starts before a boot that cannot see
                      its predecessors settles by timeout (default 420)
  PORT                injected by Render (default 8642)
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
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
STATE_PREFIX = os.getenv("DROP_STATE_PREFIX", "drop-state").strip("/")
_STATE_FILE = re.compile(r"^(\d{8})\.state\Z")
LINE_OBJECT = f"{AUDIT_PREFIX}/line"


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


def pending_quads(root: Path, mirrored: dict[str, int]) -> list[tuple[str, Path]]:
    """Files under --root not yet mirrored, non-envelope files first."""
    pending = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(root).as_posix()
        if mirrored.get(rel) == p.stat().st_size:
            continue
        pending.append((rel, p))
    pending.sort(key=lambda rp: rp[0].endswith("-envelope.json"))
    return pending


def sync_pass(bucket, root: Path, mirrored: dict[str, int],
              boot: str | None = None, conflicts: list[str] | None = None, *,
              pending: list[tuple[str, Path]] | None = None, marks_dir: Path | None = None) -> int:
    """Upload files not yet mirrored — non-envelope files before envelopes, and
    abort the pass on the first failure (retried whole next pass), so envelope-
    last ordering holds in the bucket too.

    A name the bucket already holds is compared, not assumed equal. Different
    bytes are reported and, when `boot` is given, kept under the conflict
    prefix; the bucket's object is not touched. Either way the file is then
    counted as dealt with, so one conflict is reported once, not every pass.

    `pending` is a listing taken earlier in the pass (the quads are listed
    before the generations). With `marks_dir`, a quad whose envelope is now in
    the bucket — uploaded, or already there with the same bytes — is marked."""
    from google.api_core.exceptions import PreconditionFailed
    if pending is None:
        pending = pending_quads(root, mirrored)
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
                mirrored[rel] = p.stat().st_size
                uploaded += 1
                continue                                   # not ours in the bucket: never marked
        except Exception as e:
            log.warning("mirror of %s failed (%s) — pass aborted, retrying next pass", rel, e)
            return uploaded
        mirrored[rel] = p.stat().st_size
        uploaded += 1
        if marks_dir is not None:
            mark_quad(marks_dir, rel)
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


def catch_up(bucket, root: Path, mirrored: dict[str, int], fetched: list[str] | None = None,
             marks_dir: Path | None = None) -> list[str]:
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
                tmp = dirp / f".{name}.{os.getpid()}.tmp"
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
            if marks_dir is not None:
                mark_quad(marks_dir, f"{parent}/{n}-envelope.json")
    return fetched


# ── marks: empty files serve reads; this instance's word that something is outside ──

def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)


def mark_quad(marks_dir: Path, rel: str) -> None:
    """Mark a quad by the path of its envelope (`<channel>/<from-x>/<NNN>-envelope.json`)."""
    parts = rel.split("/")
    if len(parts) == 3 and parts[2].endswith("-envelope.json") and _QUAD_FILE.match(parts[2]):
        _touch(marks_dir / "quads" / parts[0] / parts[1] / parts[2][: -len("-envelope.json")])


def mark_state(marks_dir: Path, rel: str) -> None:
    """Mark a generation by its path under the state directory (`<id>/NNNNNNNN.state`)."""
    parts = rel.split("/")
    if len(parts) == 2 and _STATE_FILE.match(parts[1]):
        _touch(marks_dir / "state" / parts[0] / parts[1][: -len(".state")])


def reset_marks(marks_dir: Path, mirrored: dict[str, int], mirrored_state: dict[str, int]) -> None:
    """Start the marks over, then mark everything the restore brought back — it came from the bucket.
    A `settled` left from an earlier run on a disk that survives restarts would still read as true."""
    shutil.rmtree(marks_dir, ignore_errors=True)
    marks_dir.mkdir(parents=True, exist_ok=True)
    for rel in mirrored:
        mark_quad(marks_dir, rel)
    for rel in mirrored_state:
        mark_state(marks_dir, rel)


# ── the bucket's own clock: objects written once, and the boot objects ─────────

def put_once(bucket, name: str, data: str):
    """Create an object only if the name is free. Returns the blob, carrying the bucket's
    time_created, or None when the name was already taken."""
    from google.api_core.exceptions import PreconditionFailed
    blob = bucket.blob(name)
    try:
        blob.upload_from_string(data, content_type="application/json", if_generation_match=0)
    except PreconditionFailed:
        return None
    return blob


def put(bucket, name: str, data: str):
    blob = bucket.blob(name)
    blob.upload_from_string(data, content_type="application/json")
    return blob


def boot_object(boot: str, what: str) -> str:
    return f"{AUDIT_PREFIX}/{boot}/{what}"


class Heartbeat(threading.Thread):
    """Rewrites this boot's `alive` every `every` seconds — restore, slow passes and catch-ups
    included, which is why it is a thread of its own (LxM 133 §2). `last` is the bucket's
    time_created of the latest one: this instance's reading of the bucket's clock."""

    def __init__(self, bucket, boot: str, every: float):
        super().__init__(name="alive", daemon=True)
        self.bucket, self.boot, self.every = bucket, boot, every
        self.last = None
        self._halt = threading.Event()

    def beat(self) -> None:
        blob = put(self.bucket, boot_object(self.boot, "alive"), json.dumps({"boot": self.boot, "utc": utc_now()}))
        self.last = blob.time_created

    def run(self) -> None:
        while not self._halt.wait(self.every):
            try:
                self.beat()
            except Exception as e:
                log.warning("alive not rewritten (%s) — next one in %.0fs", e, self.every)

    def stop(self) -> None:
        self._halt.set()


class BootView:
    """What the bucket says about boots, by the bucket's clock: when each was born, last said
    it was alive, closed, settled. Boots without `born` ran a supervisor older than the
    state slot. `line_before` is the operator's cut: boots named before it are not looked at."""

    def __init__(self, bucket, start_offset: str | None = None):
        self.boots: dict[str, dict] = {}
        self.line_before = None
        kw = {"prefix": AUDIT_PREFIX + "/"}
        if start_offset:
            kw["start_offset"] = start_offset
        line_blob = None
        for blob in bucket.client.list_blobs(bucket, **kw):
            if blob.name == LINE_OBJECT:
                line_blob = blob
                continue
            rest = blob.name[len(AUDIT_PREFIX) + 1:]
            if "/" not in rest:
                continue
            boot, what = rest.split("/", 1)
            entry = self.boots.setdefault(boot, {})
            if what in ("born", "alive", "closed", "settled"):
                entry[what] = blob.time_created
            elif what == "boot.json":
                entry["boot_json"] = blob
        if line_blob is not None:
            try:
                self.line_before = json.loads(line_blob.download_as_bytes())["boots_before"]
            except Exception as e:
                log.warning("the line object is unreadable (%s) — not used", e)

    def newer_than(self, me: str, my_born) -> list[str]:
        """Boots born strictly after this one."""
        return [b for b, e in self.boots.items() if b != me and e.get("born") is not None and e["born"] > my_born]

    def live(self, boot: str, now, stale: float) -> bool:
        e = self.boots[boot]
        if e.get("closed") is not None:
            return False
        last = max(t for t in (e.get("alive"), e.get("born")) if t is not None)
        return (now - last).total_seconds() < stale


def predecessor_walk(view: BootView, me: str, my_born) -> list[tuple[str, dict]]:
    """Boots before this one, newest first, back to the nearest one that settled (included)
    or the operator's line. Boots born at the same instant count as before each other —
    for settling, waiting is the safe side (LxM 133 §3). Boots with no `born` (an older
    supervisor) come after, in name order."""
    new, legacy = [], []
    for b, e in view.boots.items():
        if b == me or (view.line_before and b < view.line_before):
            continue
        if e.get("born") is not None:
            if e["born"] <= my_born:
                new.append((e["born"], b, e))
        elif "boot_json" in e and b < me:
            legacy.append((b, e))
    walk = []
    for _t, b, e in sorted(new, key=lambda x: (x[0], x[1]), reverse=True):
        walk.append((b, e))
        if e.get("settled") is not None:
            return walk
    for b, e in sorted(legacy, reverse=True):
        walk.append((b, e))
    return walk


def legacy_closed(entry: dict):
    """An older supervisor's boot.json says closed_utc once its final pass was done; the bucket's
    time on that object is when it was last written — the close (LxM 132 §2)."""
    blob = entry.get("boot_json")
    if blob is None:
        return None
    if "legacy_closed" not in entry:
        try:
            entry["legacy_closed"] = blob.time_created if json.loads(blob.download_as_bytes()).get("closed_utc") else None
        except Exception:
            entry["legacy_closed"] = None
    return entry["legacy_closed"]


def settle_verdict(view: BootView, me: str, my_born, now, *, stale: float, timed_out: bool) -> tuple[str, list]:
    """'ready' (nothing to catch up), 'catch-up' (then settled), 'timeout' (catch up, then
    settled-by-timeout), or 'wait'; with what was found about each boot looked at."""
    notes, alive, unknown, after = [], False, False, False
    for b, e in predecessor_walk(view, me, my_born):
        closed = e.get("closed")
        if closed is None and e.get("born") is None:
            closed = legacy_closed(e)
        if closed is not None:
            if closed < my_born:
                notes.append((b, "closed before this boot was born"))
            else:
                after = True
                notes.append((b, "closed after this boot was born"))
        elif e.get("born") is None:
            unknown = True
            notes.append((b, "older supervisor, no close on record"))
        elif view.live(b, now, stale):
            alive = True
            notes.append((b, "alive"))
        else:
            after = True
            notes.append((b, "stopped (alive not rewritten)"))
    if alive:
        return "wait", notes
    if unknown:
        return ("timeout" if timed_out else "wait"), notes
    return ("catch-up" if after else "ready"), notes


# ── the state slot's generations ───────────────────────────────────────────────

def _state_files(state_dir: Path) -> list[tuple[str, Path]]:
    out = []
    if state_dir.is_dir():
        for f in sorted(state_dir.glob("*/*.state")):
            if _STATE_FILE.match(f.name):
                out.append((f.relative_to(state_dir).as_posix(), f))
    return out


def _local_max(state_dir: Path, slot: str) -> int:
    nums = [int(m.group(1)) for f in (state_dir / slot).glob("*.state") if (m := _STATE_FILE.match(f.name))]
    return max(nums, default=0)


def _bucket_generations(bucket, slot: str | None = None) -> dict[str, list[tuple[int, object]]]:
    prefix = f"{STATE_PREFIX}/" + (f"{slot}/" if slot else "")
    out: dict[str, list[tuple[int, object]]] = {}
    for blob in bucket.client.list_blobs(bucket, prefix=prefix):
        rest = blob.name[len(STATE_PREFIX) + 1:]
        if rest.count("/") != 1:
            continue
        s, name = rest.split("/")
        m = _STATE_FILE.match(name)
        if m and s not in ("", ".", ".."):
            out.setdefault(s, []).append((int(m.group(1)), blob))
    for gens in out.values():
        gens.sort(key=lambda g: g[0])
    return out


def _place(dirp: Path, name: str, blob) -> bool:
    """Put a generation file where serve reads it, the way serve does: a dot name ending in
    .tmp, then a link that fails if the name is taken. False if it was taken."""
    dirp.mkdir(parents=True, exist_ok=True)
    tmp = dirp / f".{name}.{os.getpid()}.tmp"
    try:
        blob.download_to_filename(str(tmp))
        try:
            os.link(tmp, dirp / name)
            return True
        except FileExistsError:
            return False
    finally:
        tmp.unlink(missing_ok=True)


def restore_state(bucket, state_dir: Path, keep: int) -> dict[str, int]:
    """The newest `keep` generations of every slot, before serve starts. Raises on a failed
    download — a partial restore must never be served."""
    mirrored: dict[str, int] = {}
    for slot, gens in _bucket_generations(bucket).items():
        for num, blob in gens[-keep:]:
            name = f"{num:08d}.state"
            if _place(state_dir / slot, name, blob):
                mirrored[f"{slot}/{name}"] = (state_dir / slot / name).stat().st_size
    return mirrored


def catch_up_state(bucket, state_dir: Path, mirrored_state: dict[str, int], marks_dir: Path | None,
                   fetched: list[str] | None = None) -> list[str]:
    """Fetch generations numbered above this disk's highest, slot by slot. Lower ones were
    pruned here, or are another line of the same slot — never this instance's current one."""
    fetched = [] if fetched is None else fetched
    for slot, gens in _bucket_generations(bucket).items():
        top = _local_max(state_dir, slot)
        for num, blob in gens:
            if num <= top:
                continue
            name = f"{num:08d}.state"
            if _place(state_dir / slot, name, blob):
                rel = f"{slot}/{name}"
                mirrored_state[rel] = (state_dir / slot / name).stat().st_size
                if marks_dir is not None:
                    mark_state(marks_dir, rel)
                fetched.append(rel)
    return fetched


def state_pass(bucket, state_dir: Path, mirrored_state: dict[str, int], boot: str,
               conflicts: list[str], *, marks_dir: Path | None, fenced) -> tuple[bool, set[str]]:
    """Upload generation files not yet mirrored. Returns (quads may follow, slots uploaded to).

    `fenced()` is asked before each upload, one generation at a time (LxM 133 §4): a boot
    born after this one and still alive means this instance no longer moves generations.
    A generation that vanished before it was uploaded (serve keeps only the newest) or a
    failed upload means no quads this pass — a quad listed earlier may belong to a
    generation that was not."""
    from google.api_core.exceptions import PreconditionFailed
    pending = []
    for rel, f in _state_files(state_dir):
        try:
            size = f.stat().st_size
        except FileNotFoundError:
            return False, set()
        if mirrored_state.get(rel) != size:
            pending.append((rel, f, size))
    slots: set[str] = set()
    for rel, f, size in pending:
        holder = fenced()
        if holder:
            log.info("boot %s is newer and alive — generations stay here (letters still move)", holder)
            return True, slots
        blob = bucket.blob(f"{STATE_PREFIX}/{rel}")
        blob.metadata = {"boot": boot}
        try:
            blob.upload_from_filename(str(f), if_generation_match=0)
        except FileNotFoundError:
            log.info("generation %s vanished before it was mirrored — no letters this pass", rel)
            return False, slots
        except PreconditionFailed:
            try:
                same = blob.download_as_bytes() == f.read_bytes()
            except FileNotFoundError:
                return False, slots
            except Exception as e:
                log.warning("could not compare %s with the bucket (%s) — pass aborted", rel, e)
                return False, slots
            if not same:
                kept = _keep_conflict(bucket, boot, f"{STATE_PREFIX}/{rel}", f)
                log.error("CONFLICT state %s: the bucket holds another generation under this number. "
                          "It stays; this one is not marked, so its uploader will not go on. Local bytes %s", rel, kept)
                conflicts.append(f"{STATE_PREFIX}/{rel}")
                mirrored_state[rel] = size
                continue
        except Exception as e:
            log.warning("mirror of generation %s failed (%s) — no letters this pass", rel, e)
            return False, slots
        mirrored_state[rel] = size
        if marks_dir is not None:
            mark_state(marks_dir, rel)
        slots.add(rel.split("/")[0])
    return True, slots


def prune_state(bucket, slots, keep: int) -> int:
    """Delete generations beyond the newest `keep` of each slot, each delete conditional on the
    object as listed. Called only by the newest boot. Returns how many went."""
    from google.api_core.exceptions import NotFound, PreconditionFailed
    gone = 0
    for slot in slots:
        gens = _bucket_generations(bucket, slot).get(slot, [])
        for _num, blob in gens[:-keep]:
            try:
                blob.delete(if_generation_match=blob.generation)
                gone += 1
            except (NotFound, PreconditionFailed):
                pass
    return gone


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


def _serve_help() -> str:
    try:
        out = subprocess.run(["organum-hub", "serve", "--help"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout + out.stderr


def serve_supports_audit() -> bool:
    """organum-hub serve grew --audit-log in 0.7.0. Asked of the installed
    binary, so this file deploys safely before or after the upgrade."""
    return "--audit-log" in _serve_help()


def serve_supports_state() -> bool:
    """--state-dir and --marks-dir came in 0.8.0."""
    h = _serve_help()
    return "--state-dir" in h and "--marks-dir" in h


def boot_stamp() -> str:
    """Names this boot: UTC start time plus the pid, so two instances overlapping
    during a deploy never share a path. Taken before the restore."""
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


def write_born(bucket, boot: str, tries: int = 6):
    """`born`, before the restore lists anything. Without it this boot cannot be placed among
    the others, so if it will not go in, the state slot stays off for this boot."""
    for attempt in range(tries):
        try:
            blob = put_once(bucket, boot_object(boot, "born"), json.dumps({"boot": boot, "utc": utc_now()}))
            if blob is not None:
                return blob
            blob = bucket.get_blob(boot_object(boot, "born"))
            if blob is not None:
                return blob
        except Exception as e:
            log.warning("born not written (%s) — try %d of %d", e, attempt + 1, tries)
        time.sleep(min(2 ** attempt, 10))
    return None


def _offset(boot: str, hours: float) -> str | None:
    """A listing start a few hours before this boot's name, so a listing of the boot objects
    stays short however many boots the bucket has seen. The instances' clocks only pick
    where to start reading; every comparison is between bucket times."""
    try:
        t = time.mktime(time.strptime(boot.split("-")[0], "%Y%m%dT%H%M%SZ")) - time.timezone - hours * 3600
    except ValueError:
        return None
    return f"{AUDIT_PREFIX}/" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(t))


def settle_view(bucket, boot: str, my_born) -> BootView:
    """The boots that settling has to look at: the last two days first; the whole record
    (from the operator's line, if one is drawn) only when no stop is found in them."""
    view = BootView(bucket, start_offset=_offset(boot, 48))
    walk = predecessor_walk(view, boot, my_born)
    if walk and walk[-1][1].get("settled") is None:
        start = f"{AUDIT_PREFIX}/{view.line_before}" if view.line_before else None
        view = BootView(bucket, start_offset=start)
    return view


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
    boot = boot_stamp()

    bucket = gcs_bucket()
    record = {"boot": boot, "catch_ups": [], "conflicts": []}

    # ── the state slot: born before anything is listed, then alive on its own thread ──
    state_dir = Path(os.getenv("DROP_STATE_DIR", "/tmp/drop-state"))
    marks_dir = Path(os.getenv("DROP_MARKS_DIR", "/tmp/drop-marks"))
    keep = int(os.getenv("DROP_STATE_KEEP", "3"))
    stale = float(os.getenv("DROP_ALIVE_STALE", "300"))
    settle_timeout = float(os.getenv("DROP_SETTLE_TIMEOUT", "420"))
    state_on = os.getenv("DROP_STATE", "1") != "0" and serve_supports_state()
    if os.getenv("DROP_STATE", "1") != "0" and not state_on:
        log.warning("installed organum-hub serve has no --state-dir/--marks-dir (< 0.8.0) — state slot off")
    heartbeat, my_born = None, None
    if state_on:
        born = write_born(bucket, boot)
        if born is None:
            log.error("born could not be written — the state slot stays off for this boot")
            state_on = False
        else:
            my_born = born.time_created
            record["born"] = str(my_born)
            heartbeat = Heartbeat(bucket, boot, float(os.getenv("DROP_ALIVE_EVERY", "60")))
            try:
                heartbeat.beat()
            except Exception as e:
                log.warning("first alive not written (%s)", e)
            heartbeat.start()

    t0 = time.monotonic()
    record["restore_started_utc"] = utc_now()
    mirrored = restore(bucket, root)
    mirrored_state: dict[str, int] = {}
    if state_on:
        mirrored_state = restore_state(bucket, state_dir, keep)
        reset_marks(marks_dir, mirrored, mirrored_state)
    record.update(restore_done_utc=utc_now(), restored_files=len(mirrored), restored_generations=len(mirrored_state))
    log.info("restored %d files and %d generations from gs://%s in %.1fs", len(mirrored), len(mirrored_state),
             bucket.name, time.monotonic() - t0)

    cmd = ["organum-hub", "serve",
           "--root", str(root), "--token-file", token_file,
           "--bind", "0.0.0.0",
           "--port", os.getenv("PORT", "8642"),
           "--rate-limit", os.getenv("DROP_RATE_LIMIT", "60")]
    audit_dir, audit_mirrored = None, {}
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
    if state_on:
        cmd += ["--state-dir", str(state_dir), "--marks-dir", str(marks_dir), "--state-keep", str(keep),
                "--state-max-bytes", os.getenv("DROP_STATE_MAX_BYTES", "1048576"),
                "--state-max-jump", os.getenv("DROP_STATE_MAX_JUMP", "10000")]
        log.info("state slot on: %s -> gs://%s/%s/, marks in %s", state_dir, bucket.name, STATE_PREFIX, marks_dir)
    child = subprocess.Popen(cmd)
    log.info("serve up on :%s (pid %d)", os.getenv("PORT", "8642"), child.pid)
    record["serve_started_utc"] = utc_now()
    write_boot_record(bucket, boot, record)
    serve_up = time.monotonic()
    early, every = catchup_schedule()
    next_catchup = early.pop(0) if early else (every or None)
    settled, next_settle_look = None, 0.0

    def now_on_bucket():
        return heartbeat.last if heartbeat is not None and heartbeat.last is not None else my_born

    def fenced() -> str | None:
        view = BootView(bucket, start_offset=_offset(boot, 1))
        return next((b for b in sorted(view.newer_than(boot, my_born)) if view.live(b, now_on_bucket(), stale)), None)

    def run_catch_up(entry: dict) -> bool:
        try:
            catch_up(bucket, root, mirrored, entry["fetched"], marks_dir=marks_dir if state_on else None)
            if state_on:
                catch_up_state(bucket, state_dir, mirrored_state, marks_dir, entry.setdefault("fetched_state", []))
        except Exception as e:
            entry["error"] = str(e)
            log.warning("catch-up failed (%s) — the next one will try again", e)
            return False
        got = entry["fetched"] + entry.get("fetched_state", [])
        log.info("catch-up: %d quad(s), %d generation(s) the bucket had and this disk did not%s",
                 len(entry["fetched"]), len(entry.get("fetched_state", [])), ": " + " ".join(got) if got else "")
        return True

    def try_settle():
        view = settle_view(bucket, boot, my_born)
        verdict, notes = settle_verdict(view, boot, my_born, now_on_bucket(), stale=stale,
                                        timed_out=time.monotonic() - serve_up >= settle_timeout)
        if verdict == "wait":
            return settled
        if verdict in ("catch-up", "timeout"):
            entry = {"utc": utc_now(), "fetched": [], "for": "settling"}
            ok = run_catch_up(entry)
            record["catch_ups"].append(entry)
            if not ok:
                return settled
        how = {"verdict": verdict, "utc": utc_now(), "boots": [f"{b}: {why}" for b, why in notes]}
        if verdict == "timeout":
            _touch(marks_dir / "settled-by-timeout")
            record["settled_by_timeout"] = how
            log.warning("settled by timeout only — restores from this instance are refused by default")
            return "timeout"
        _touch(marks_dir / "settled")
        (marks_dir / "settled-by-timeout").unlink(missing_ok=True)
        try:
            put_once(bucket, boot_object(boot, "settled"), json.dumps(how))
        except Exception as e:
            log.warning("settled not written to the bucket (%s) — later boots will look further back", e)
        record["settled"] = how
        log.info("settled (%s): %s", verdict, "; ".join(how["boots"]) or "no boot before this one")
        return "settled"

    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())

    try:
        while not stop.is_set() and child.poll() is None:
            deadline = time.monotonic() + interval
            while (not stop.is_set() and child.poll() is None
                   and time.monotonic() < deadline):
                stop.wait(1.0)
            seen, was = len(record["conflicts"]), settled
            quads = pending_quads(root, mirrored)              # quads first, then the generations
            quads_ok = True
            if state_on:
                quads_ok, slots = state_pass(bucket, state_dir, mirrored_state, boot, record["conflicts"],
                                             marks_dir=marks_dir, fenced=fenced)
                if slots and not BootView(bucket, start_offset=_offset(boot, 1)).newer_than(boot, my_born):
                    gone = prune_state(bucket, slots, keep)
                    if gone:
                        log.info("pruned %d generation(s) beyond the newest %d", gone, keep)
            n = sync_pass(bucket, root, mirrored, boot, record["conflicts"], pending=quads,
                          marks_dir=marks_dir if state_on else None) if quads_ok else 0
            if n:
                log.info("mirrored %d new files", n)
            if audit_dir is not None:
                audit_sync_pass(bucket, audit_dir, boot, audit_mirrored)
            due = next_catchup is not None and time.monotonic() - serve_up >= next_catchup
            if due:
                entry = {"utc": utc_now(), "fetched": []}
                run_catch_up(entry)
                record["catch_ups"].append(entry)
                next_catchup = early.pop(0) if early else (next_catchup + every if every else None)
            if state_on and settled != "settled" and time.monotonic() >= next_settle_look:
                try:
                    settled = try_settle()
                except Exception as e:
                    log.warning("could not decide whether this boot has settled (%s)", e)
                next_settle_look = time.monotonic() + (interval if settled is None else 60)
            if due or len(record["conflicts"]) != seen or settled != was:
                write_boot_record(bucket, boot, record)
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
        # serve is down, nothing is mid-write — this pass captures everything. Generations
        # first; the quads go regardless, since nothing can be written between the listings now.
        if state_on:
            state_pass(bucket, state_dir, mirrored_state, boot, record["conflicts"], marks_dir=None, fenced=fenced)
        sync_pass(bucket, root, mirrored, boot, record["conflicts"])
        log.info("final mirror done (%d files, %d generations)", len(mirrored), len(mirrored_state))
        if audit_dir is not None:
            audit_sync_pass(bucket, audit_dir, boot, audit_mirrored)
            log.info("final audit mirror done (%d file(s))", len(audit_mirrored))
        if heartbeat is not None:
            heartbeat.stop()
        if state_on:
            try:
                put_once(bucket, boot_object(boot, "closed"), json.dumps({"boot": boot, "utc": utc_now()}))
            except Exception as e:
                log.warning("closed not written (%s) — later boots will wait for alive to go stale", e)
        record["closed_utc"] = utc_now()
        write_boot_record(bucket, boot, record)
    if stop.is_set():
        return 0
    log.error("serve exited unexpectedly (rc=%s)", child.returncode)
    return child.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
