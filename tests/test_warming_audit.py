"""The warming audit must call an anchor served only if a run was there for it.

This is the instrument that replaced reading run outcomes, because the run
history said "success" through three distinct failures in one week. If the
audit itself is generous — counting a run that started late, or one that died
before the warming moment — it reproduces the lie it exists to catch, and does
it with more authority.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.warming_audit import LEAD_SECONDS, anchors_in, coverage

UTC = timezone.utc


def _dt(day, hour, minute=0):
    return datetime(2026, 8, day, hour, minute, tzinfo=UTC)


def test_anchors_land_on_the_published_grid():
    got = anchors_in(_dt(20, 1), _dt(21, 7))
    assert got == [_dt(20, 6), _dt(20, 12), _dt(20, 18), _dt(21, 0), _dt(21, 6)]
    assert all(a.hour % 6 == 0 and a.minute == 0 for a in got)


def test_a_run_alive_at_the_warming_moment_covers_the_anchor():
    anchor = _dt(24, 18)
    run = (_dt(24, 17, 20), _dt(24, 18, 10))
    assert coverage([run], [anchor])[anchor] == 1


def test_a_run_that_ended_before_the_warming_moment_covers_nothing():
    """v1's failure: it fired, it succeeded, and it was long gone by T-5."""
    anchor = _dt(24, 18)
    run = (_dt(24, 17, 0), _dt(24, 17, 3))
    assert coverage([run], [anchor])[anchor] == 0


def test_a_run_that_started_after_the_warming_moment_covers_nothing():
    """v2's failure: started two hours late, so it arrived to an anchor that
    had already passed and hit an instance nobody was waiting on."""
    anchor = _dt(26, 18)
    run = (_dt(26, 19, 22), _dt(26, 19, 25))
    assert coverage([run], [anchor])[anchor] == 0


def test_the_warming_moment_is_the_published_lead_not_the_anchor():
    """A run alive at the anchor but not at T-5 is too late: members are told
    the mailbox is hot when they arrive, not that it starts warming then."""
    anchor = _dt(24, 18)
    late = (anchor - timedelta(seconds=LEAD_SECONDS - 60), anchor + timedelta(minutes=10))
    assert coverage([late], [anchor])[anchor] == 0


def test_overlapping_runs_are_counted_separately():
    """v3 buys redundancy by overlapping three runs per anchor. If the audit
    collapsed them the redundancy would be invisible, and losing two of three
    would look identical to losing none."""
    anchor = _dt(27, 18)
    runs = [(_dt(27, h, 20), _dt(27, 18, 10)) for h in (15, 16, 17)]
    assert coverage(runs, [anchor])[anchor] == 3


def test_an_anchor_with_no_runs_at_all_is_a_miss_not_an_absence():
    """The 08-27 06:00 and 12:00 anchors had no run in the list. A dict that
    omitted them would make a total scheduler outage the quietest failure."""
    anchor = _dt(27, 6)
    cov = coverage([], [anchor])
    assert anchor in cov and cov[anchor] == 0
