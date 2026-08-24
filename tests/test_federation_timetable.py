"""The published collection timetable and the cron that warms for it must agree.

`docs/federation/welcome.md` tells members when the mailbox is hot;
`.github/workflows/warm-drop.yml` is what actually makes it hot. Two copies of
one fact with nothing crossing them — change the cron and the welcome page
keeps promising the old hours, which is the failure this federation spent a
week naming. Ludex hit the same shape from the other side the same day: their
collection was scheduled in local time on a machine whose timezone had not
followed the founder to another country, so it fired an hour after the warming
window closed, every day, silently.

Since 2026-08-24 the warming is anchor-targeted: the schedule fires early only
to get a runner, and the job itself hits at absolute times around the anchor.
That split exists because GitHub's scheduler ran 15–34 minutes late on every
single firing of the previous ':55 T-5' schedule (08-21..08-24), which put the
warming AFTER the anchor it was named for — organum measured the resulting
cold first-door pulls from their side (their seq 034 §4).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "warm-drop.yml"
WELCOME = ROOT / "docs" / "federation" / "welcome.md"

# The schedule only requests a runner; its lead must exceed the worst start
# delay actually observed (34 min, 08-21..08-24) or the job wakes up already
# past the window it exists to hold.
SCHEDULE_LEAD_MINUTES = 40
WORST_OBSERVED_DELAY_MINUTES = 34


def _cron_anchor_hours() -> set[int]:
    """Collection hours implied by the warming cron (cron time + the lead)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    m = re.search(r"cron:\s*'(\S+)\s+(\S+)\s+\*\s+\*\s+\*'", text)
    assert m, "no schedule found in warm-drop.yml"
    minute, hours = int(m.group(1)), m.group(2)
    assert minute == 60 - SCHEDULE_LEAD_MINUTES, (
        f"cron fires at :{minute:02d}, not {SCHEDULE_LEAD_MINUTES} minutes "
        f"before the anchors the welcome page names"
    )
    assert SCHEDULE_LEAD_MINUTES > WORST_OBSERVED_DELAY_MINUTES, (
        "the schedule lead no longer covers the delays GitHub actually showed"
    )
    return {(int(h) + 1) % 24 for h in hours.split(",")}


def _published_anchor_hours() -> set[int]:
    """Hours the welcome page tells members to expect."""
    text = WELCOME.read_text(encoding="utf-8")
    row = re.search(r"수거 시각 \(UTC\)\s*\|([^|]+)\|", text)
    assert row, "the welcome page no longer publishes a timetable row"
    return {int(h) for h in re.findall(r"(\d{2}):00", row.group(1))}


def test_warming_cron_matches_the_published_timetable():
    published, warmed = _published_anchor_hours(), _cron_anchor_hours()
    assert published, "no hours parsed from the welcome page"
    assert published == warmed, (
        f"the page promises {sorted(published)} UTC but the cron warms for "
        f"{sorted(warmed)} — members plan against the page"
    )


def test_job_hits_at_absolute_times_and_the_rounding_matches_the_timetable():
    """The job finds its anchor by rounding to a multiple of the anchor period,
    which is only correct while the published hours stay evenly spaced. Cross
    both halves: the period constant must be in the workflow, and the published
    hours must actually sit on that grid."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "21600" in text, (
        "the job no longer computes the anchor in absolute time — offsets "
        "already failed once (every ':55' run started after its anchor)"
    )
    published = sorted(_published_anchor_hours())
    assert published, "no hours parsed from the welcome page"
    period_hours = 21600 // 3600
    assert all(h % period_hours == 0 for h in published), (
        f"published hours {published} are off the {period_hours}h grid the "
        f"job's rounding assumes — change both together or the warming aims "
        f"at the wrong anchor"
    )


def test_timetable_is_anchored_in_utc():
    """The hours must be stated in UTC on the page, and the runner must be a UTC
    scheduler. GitHub's cron is UTC by contract; the risk this pins is someone
    later moving the warming to a host that schedules in local time, which is
    exactly how Ludex's collection drifted an hour without anyone noticing."""
    assert "UTC" in WELCOME.read_text(encoding="utf-8"), \
        "the timetable must name its timezone — an unqualified hour drifts with whoever reads it"
    assert "runs-on: ubuntu-latest" in WORKFLOW.read_text(encoding="utf-8"), \
        "warming must stay on the UTC-scheduled hosted runner"
