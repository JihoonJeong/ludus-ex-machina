"""The published collection timetable and the warming that serves it must agree.

`docs/federation/welcome.md` tells members when the mailbox is hot;
`.github/workflows/warm-drop.yml` is what makes it hot. Two copies of one fact
with nothing crossing them drift — change one and the other keeps promising the
old hours, which is the failure this federation spent a week naming. Ludex hit
the same shape from the other side the same day: their collection was scheduled
in local time on a machine whose timezone had not followed the founder to
another country, so it fired an hour after the warming window closed, every
day, silently.

The warming has been rewritten twice because GitHub's scheduler kept running it
later than the previous shape assumed: 15-34 min late (v1), then 2h02m and
5h12m late (v2, which cost the 08-27 00:00 anchor its warming entirely and
showed up in Ray's collection as >170s against a cold instance). So v3 stops
betting on a single firing: it fires hourly and every run that finds an anchor
within its horizon sleeps to that anchor's absolute times. What these tests pin
is the property that survives the next rewrite — every published anchor must be
covered, and covered redundantly, by runs that cannot all be late at once.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "warm-drop.yml"
WELCOME = ROOT / "docs" / "federation" / "welcome.md"

# One firing per anchor was enough only while delays were minutes. Two of the
# three runs covering an anchor were late past it on 08-26/27, so the floor is
# what survived that: at least three independent chances per anchor.
MIN_RUNS_PER_ANCHOR = 3


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _shell_const(name: str) -> int:
    """A constant the warming job sets, read from the job body itself so the
    tests measure the shipped numbers rather than a copy of them."""
    m = re.search(rf"^\s*{name}=(\d+)", _workflow(), re.MULTILINE)
    assert m, f"the warming job no longer defines {name}"
    return int(m.group(1))


def _cron_firings() -> list[int]:
    """Minutes-past-midnight (UTC) at which the schedule fires in one day."""
    m = re.search(r"cron:\s*'(\S+)\s+(\S+)\s+\*\s+\*\s+\*'", _workflow())
    assert m, "no schedule found in warm-drop.yml"
    minute_f, hour_f = m.group(1), m.group(2)
    assert minute_f.isdigit(), f"unexpected minute field {minute_f!r}"
    hours = range(24) if hour_f == "*" else [int(h) for h in hour_f.split(",")]
    return [h * 60 + int(minute_f) for h in hours]


def _published_anchor_hours() -> set[int]:
    """Hours the welcome page tells members to expect."""
    text = WELCOME.read_text(encoding="utf-8")
    row = re.search(r"수거 시각 \(UTC\)\s*\|([^|]+)\|", text)
    assert row, "the welcome page no longer publishes a timetable row"
    return {int(h) for h in re.findall(r"(\d{2}):00", row.group(1))}


def _coverage() -> dict[int, list[int]]:
    """anchor hour -> firing times that would serve it, by the job's own rule:
    take the next anchor at or after the firing, serve it if within HORIZON."""
    period_min = _shell_const("PERIOD") // 60
    horizon_min = _shell_const("HORIZON") // 60
    covered: dict[int, list[int]] = {}
    for fired in _cron_firings():
        anchor = -(-fired // period_min) * period_min  # ceil to next anchor
        if anchor - fired <= horizon_min:
            covered.setdefault((anchor // 60) % 24, []).append(fired)
    return covered


def test_every_published_anchor_is_covered_redundantly():
    """The load-bearing property: a member reading the page must find the
    mailbox warm, and no single delayed run may be able to prevent that."""
    published, covered = _published_anchor_hours(), _coverage()
    assert published, "no hours parsed from the welcome page"
    missing = sorted(published - covered.keys())
    assert not missing, (
        f"the page promises {sorted(published)} UTC but nothing warms for "
        f"{missing} — members plan against the page"
    )
    thin = {h: len(covered[h]) for h in published if len(covered[h]) < MIN_RUNS_PER_ANCHOR}
    assert not thin, (
        f"anchors with fewer than {MIN_RUNS_PER_ANCHOR} covering runs: {thin}. "
        f"A single late start already emptied an anchor twice; redundancy is "
        f"the whole reason this fires hourly."
    )


def test_warming_serves_only_the_published_hours():
    """The other direction: warming hours that nobody was promised are either a
    stale copy of an old timetable or wasted instance time on a free tier."""
    published, covered = _published_anchor_hours(), _coverage()
    extra = sorted(covered.keys() - published)
    assert not extra, (
        f"warming serves {extra} UTC, which the welcome page does not publish"
    )


def test_the_job_can_finish_its_longest_wait():
    """A run may sleep the full horizon and then hold to T+10. If the job
    timeout is under that, the last covering run of each anchor is killed
    mid-sleep — silently, since a cancelled job leaves no served line."""
    horizon_min = _shell_const("HORIZON") // 60
    tail_min = _shell_const("TAIL") // 60
    m = re.search(r"timeout-minutes:\s*(\d+)", _workflow())
    assert m, "the warming job no longer sets a timeout"
    timeout = int(m.group(1))
    needed = horizon_min + tail_min
    assert timeout > needed, (
        f"timeout-minutes {timeout} cannot cover a {horizon_min} min wait plus "
        f"{tail_min} min of holding ({needed} min)"
    )


def test_idle_runs_do_not_touch_the_drop():
    """Hourly firing is affordable only because runs with no anchor in reach
    cost nothing. If an idle run ever starts waking the instance, 24 wakes a
    day quietly replaces a ~2h/day budget with a ~6h/day one."""
    body = _workflow()
    idle = body.split("if [ \"$until_anchor\" -gt \"$HORIZON\" ]", 1)
    assert len(idle) == 2, "the idle guard is gone — hourly firing now wakes on every run"
    branch = idle[1].split("fi", 1)[0]
    assert "exit 0" in branch, "the idle branch no longer exits"
    assert "wake" not in branch and "curl" not in branch, \
        "the idle branch contacts the drop, which makes hourly firing expensive"


def test_timetable_is_anchored_in_utc():
    """The hours must be stated in UTC on the page, and the runner must be a UTC
    scheduler. GitHub's cron is UTC by contract; the risk this pins is someone
    later moving the warming to a host that schedules in local time, which is
    exactly how Ludex's collection drifted an hour without anyone noticing."""
    assert "UTC" in WELCOME.read_text(encoding="utf-8"), \
        "the timetable must name its timezone — an unqualified hour drifts with whoever reads it"
    assert "runs-on: ubuntu-latest" in _workflow(), \
        "warming must stay on the UTC-scheduled hosted runner"
