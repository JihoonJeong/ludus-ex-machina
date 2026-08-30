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

Two refinements came back from W35 when other houses applied this method, and
they are part of the method now:

  alive vs fired (Ludex, 061 §2): the predicate must match what the job is
  for. A warming job must be ALIVE at the moment (this script); a collection
  job must FIRE within budget after it — Ludex applied "alive at T" to their
  collector, read 15%, and the true number was 78%. Before carrying this
  script's predicate to another job, ask which kind it is.

  unserved is two diseases (Ray, 058 칸2(a)): an anchor nobody covered splits
  into "a run existed and missed it" (scheduler design — fix the job) and "no
  run executed at all" (the scheduler or host was absent — no job change can
  help). The prescriptions differ, so the audit names the cause per miss.
  Ray's third state, host powered off, does not exist for GitHub-hosted
  runners; here an absent run IS the scheduler not executing.

The curator's standing decision (2026-08-27) is to stay on the free tier and
move to a paid instance if cold starts keep costing members envelopes. This
script measures our half of that — whether the warming ran when it said it
would — and not the harm. Ray crossed their collection wall-clocks against our
unserved anchors and found two of the four cost them nothing, because other
traffic had already woken the instance. So coverage is the alarm on this layer;
the members' wall-clocks are the verdict, and they are not measurable here.

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

# Mirror of HORIZON in warm-drop.yml: a run whose start is within this of an
# anchor is that anchor's business — either it should have served it (started
# before T) or it is the late remnant of a slot that was meant to (after T).
# HORIZON < PERIOD/2, so neighbouring anchors' windows never overlap and a
# run start attributes to at most one anchor.
HORIZON_SECONDS = 10200

# Coverage is an alarm on OUR layer, not the curator's trigger. Ray crossed
# their collection wall-clocks against our unserved anchors and found the
# instance had been awake for two of the four — other traffic had already
# woken it — so 50% coverage was not 50% consumer harm. What decides the paid
# instance is whether members pay for cold starts, and that is measured at
# their end, not here. Below this share, say so and go read their reports;
# do not report this number as the answer.
ALARM_COVERAGE = 0.90


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


def unserved_cause(runs: list[tuple[datetime, datetime]], anchor: datetime) -> str:
    """Why nobody covered this anchor: "run_missed" or "no_run".

    Ray's split (058 칸2(a)): a run that existed and missed the moment is a
    scheduler-design problem; a run that never executed is an availability
    problem, and "the log shows the same blank for both" is exactly how their
    reboot hid inside a lateness column. A run belongs to this anchor if it
    started within HORIZON of it — before T it should have served it, after T
    it is the late arrival v2 produced (started 82 min past the anchor).
    """
    horizon = timedelta(seconds=HORIZON_SECONDS)
    if any(abs(s - anchor) <= horizon for s, _e in runs):
        return "run_missed"
    return "no_run"


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
            "alarm_threshold": ALARM_COVERAGE,
            "alarm": rate < ALARM_COVERAGE,
            "unserved": [{"anchor": k.strftime("%Y-%m-%dT%H:%MZ"),
                          "cause": unserved_cause(runs, k)}
                         for k, v in sorted(cov.items()) if not v],
        }, indent=1))
        return 0

    print(f"warming coverage, last {a.days}d: {served}/{len(cov)} anchors "
          f"({rate:.0%})")
    for anchor, n in sorted(cov.items()):
        if n:
            print(f"  ok   {anchor:%m-%d %H:%M}Z  covered by {n} run(s)")
        else:
            why = ("a run was near, none alive at T-5"
                   if unserved_cause(runs, anchor) == "run_missed"
                   else "no run within the horizon — nothing executed")
            print(f"  MISS {anchor:%m-%d %H:%M}Z  {why}")
    if rate < ALARM_COVERAGE:
        print(f"\nbelow the {ALARM_COVERAGE:.0%} alarm line — our warming layer is "
              f"failing. This is not the paid-instance verdict: members' "
              f"wall-clocks decide that, and an unserved anchor costs nothing "
              f"if other traffic had the instance up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
