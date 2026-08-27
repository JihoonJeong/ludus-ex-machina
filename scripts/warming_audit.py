#!/usr/bin/env python3
"""Did each collection anchor actually get warmed?

The warm-drop run history answered "success" through three different failures
this week — a job that ran 15-34 min late every time, a job that started two
hours late and hit an anchor that had already passed, and two anchors where no
run fired at all. Every one of those is green in the run list, because the job
succeeded at what it did; what it did was not warming an anchor.

So stop reading run outcomes and read anchor coverage instead. A run covers an
anchor if it was alive at that anchor's warming moment (T-5) — that is the
whole question, and it is answerable from run start/end times without opening
a single log.

The curator's standing decision (2026-08-27) is to stay on the free tier and
move to a paid instance if cold starts keep costing members envelopes. This
script exists so "keep costing" is a number rather than an impression.

Usage:
    python scripts/warming_audit.py [--days 7] [--json]

Needs `gh` (authenticated) for the run history; --runs-file reads a saved
`gh run list --json startedAt,updatedAt,conclusion` dump instead.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

WORKFLOW = "warm-drop.yml"
PERIOD_HOURS = 6      # anchors at 00/06/12/18 UTC
LEAD_SECONDS = 300    # the warming moment the welcome page promises: T-5

# A week where fewer than this share of anchors were warmed is the curator's
# review trigger — named here so the threshold is a published number and not
# a feeling about how the week went.
REVIEW_TRIGGER_COVERAGE = 0.90


def anchors_in(start: datetime, end: datetime) -> list[datetime]:
    """Every collection anchor between two instants, inclusive of neither end
    beyond what fits. Anchors sit on the 6h grid in UTC."""
    step = timedelta(hours=PERIOD_HOURS)
    first_hour = (start.hour // PERIOD_HOURS + 1) * PERIOD_HOURS
    cur = start.replace(minute=0, second=0, microsecond=0, hour=0) + timedelta(hours=first_hour)
    out = []
    while cur <= end:
        if cur >= start:
            out.append(cur)
        cur += step
    return out


def coverage(runs: list[tuple[datetime, datetime]],
             anchors: list[datetime]) -> dict[datetime, int]:
    """anchor -> how many runs were alive at its warming moment (T-5).

    Alive, not merely started: a run that began before T-5 but died before
    reaching it warmed nothing, and a run that started after T-5 arrived to an
    anchor already in progress. Both were real failures this week.
    """
    out: dict[datetime, int] = {}
    for a in anchors:
        moment = a - timedelta(seconds=LEAD_SECONDS)
        out[a] = sum(1 for s, e in runs if s <= moment <= e)
    return out


def _fetch_runs(days: int) -> list[tuple[datetime, datetime]]:
    limit = max(30, days * 26)  # hourly firing plus headroom
    raw = subprocess.run(
        ["gh", "run", "list", "--workflow", WORKFLOW, "--limit", str(limit),
         "--json", "startedAt,updatedAt,conclusion"],
        capture_output=True, text=True, check=True).stdout
    return _parse_runs(json.loads(raw))


def _parse_runs(rows: list[dict]) -> list[tuple[datetime, datetime]]:
    runs = []
    for r in rows:
        s, e = r.get("startedAt"), r.get("updatedAt")
        if not s or not e:
            continue
        runs.append((datetime.fromisoformat(s.replace("Z", "+00:00")),
                     datetime.fromisoformat(e.replace("Z", "+00:00"))))
    return runs


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    p.add_argument("--runs-file", help="saved `gh run list --json ...` output")
    a = p.parse_args()

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=a.days)
    if a.runs_file:
        runs = _parse_runs(json.load(open(a.runs_file)))
    else:
        try:
            runs = _fetch_runs(a.days)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"could not read run history via gh: {e}", file=sys.stderr)
            return 2

    # Only anchors that have fully passed can be judged.
    cov = coverage(runs, [x for x in anchors_in(since, now) if x < now])
    if not cov:
        print("no elapsed anchors in window", file=sys.stderr)
        return 2

    served = sum(1 for n in cov.values() if n)
    rate = served / len(cov)

    if a.json:
        print(json.dumps({
            "window_days": a.days,
            "anchors": len(cov),
            "served": served,
            "coverage": round(rate, 4),
            "trigger": REVIEW_TRIGGER_COVERAGE,
            "review_triggered": rate < REVIEW_TRIGGER_COVERAGE,
            "unserved": [k.strftime("%Y-%m-%dT%H:%MZ") for k, v in sorted(cov.items()) if not v],
        }, indent=1))
        return 0

    print(f"warming coverage, last {a.days}d: {served}/{len(cov)} anchors "
          f"({rate:.0%})")
    for anchor, n in sorted(cov.items()):
        mark = "ok  " if n else "MISS"
        print(f"  {mark} {anchor:%m-%d %H:%M}Z  covered by {n} run(s)")
    if rate < REVIEW_TRIGGER_COVERAGE:
        print(f"\nbelow the {REVIEW_TRIGGER_COVERAGE:.0%} review trigger — the "
              f"paid-instance decision is due back to the curator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
