"""The published collection timetable and the cron that warms for it must agree.

`docs/federation/welcome.md` tells members when the mailbox is hot;
`.github/workflows/warm-drop.yml` is what actually makes it hot, five minutes
earlier. Two copies of one fact with nothing crossing them — change the cron and
the welcome page keeps promising the old hours, which is the failure this
federation spent a week naming. Ludex hit the same shape from the other side the
same day: their collection was scheduled in local time on a machine whose
timezone had not followed the founder to another country, so it fired an hour
after the warming window closed, every day, silently.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "warm-drop.yml"
WELCOME = ROOT / "docs" / "federation" / "welcome.md"

WARM_LEAD_MINUTES = 5


def _cron_anchor_hours() -> set[int]:
    """Collection hours implied by the warming cron (cron time + the lead)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    m = re.search(r"cron:\s*'(\S+)\s+(\S+)\s+\*\s+\*\s+\*'", text)
    assert m, "no schedule found in warm-drop.yml"
    minute, hours = int(m.group(1)), m.group(2)
    assert minute == 60 - WARM_LEAD_MINUTES, (
        f"cron fires at :{minute:02d}, which is not {WARM_LEAD_MINUTES} minutes "
        f"before the hour the welcome page names"
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


def test_timetable_is_anchored_in_utc():
    """The hours must be stated in UTC on the page, and the runner must be a UTC
    scheduler. GitHub's cron is UTC by contract; the risk this pins is someone
    later moving the warming to a host that schedules in local time, which is
    exactly how Ludex's collection drifted an hour without anyone noticing."""
    assert "UTC" in WELCOME.read_text(encoding="utf-8"), \
        "the timetable must name its timezone — an unqualified hour drifts with whoever reads it"
    assert "runs-on: ubuntu-latest" in WORKFLOW.read_text(encoding="utf-8"), \
        "warming must stay on the UTC-scheduled hosted runner"
