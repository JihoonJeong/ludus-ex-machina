#!/usr/bin/env python3
"""Pull live-plane match envelopes from Redis to durable local disk.

The plane stores each hosted match at `lxm:match:{id}` with a 24h SLIDING TTL
(server/match_store.py MATCH_TTL_SECONDS) — completed matches vanish a day
after their last write. That bit us on 2026-07-10: the v3 ablation batch
(23 tidewater envelopes) expired before a backfill request landed, and the
broker's own ~12-match rolling window had already evicted 18/30 raw logs
mid-analysis. Two independent retention cliffs, one lesson: pull research
data to disk while it's alive.

Run it after any live batch worth keeping (idempotent — re-archiving an
existing match overwrites its file):

    python scripts/archive_live_matches.py                 # all live matches
    python scripts/archive_live_matches.py --scenario tidewater_warren

Envelopes land in matches_live/{match_id}.json (git-ignored by default;
export/scoring tools can read them like any local record — the orchestrator
log is at envelope["orchestrator"]["log"], scoreable via
`action_index.score_log`).
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "matches_live"


def _redis():
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))
    sys.path.insert(0, str(ROOT))
    from server.redis_client import UpstashRedis
    return UpstashRedis()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", help="only archive matches of this scenario_id")
    args = ap.parse_args()

    r = _redis()
    ARCHIVE_DIR.mkdir(exist_ok=True)
    keys = r.keys("lxm:match:*")
    saved = skipped = 0
    for k in keys:
        d = r.get_json(k)
        if not d:
            continue
        sid = (d.get("config") or {}).get("scenario_id")
        if args.scenario and sid != args.scenario:
            skipped += 1
            continue
        mid = k.split(":")[-1]
        (ARCHIVE_DIR / f"{mid}.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
        n_log = len((d.get("orchestrator") or {}).get("log") or [])
        print(f"  {mid}  {sid}  {d.get('status')}  {n_log} log turns")
        saved += 1
    print(f"\narchived {saved} envelope(s) → {ARCHIVE_DIR}/ "
          f"({skipped} filtered out, {len(keys)} keys seen)")


if __name__ == "__main__":
    main()
