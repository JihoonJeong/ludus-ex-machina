"""Smoke tests for scripts/export_static.py reach session scanning.

Exercises the D-062 Phase 2b schema end-to-end: a fixture session
directory is parsed by `bundle_session` and `scan_sessions`, and the
output shape matches what `viewer/static/renderers/reach.js` expects
to consume (meta, turns with prompt+responses, closes).
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import export_static  # noqa: E402


FIXTURE_META = """session_id: reach_2026-04-24_hearth_primo_001
field: Council
participants:
  - creature: Hearth
    machine_alias: win-nautilus-001
    role: discussant
  - creature: Primo
    machine_alias: mac-studio-001
    role: discussant
created_at: 2026-04-24T10:00:00Z
max_turns: 10
status: active
close_reason: ""
"""

FIXTURE_TURN = """turn: 2
next:
  creature: Hearth
  machine_alias: win-nautilus-001
prompt_available: true
"""

FIXTURE_PROMPT = """---
turn: 1
addressee:
  creature: Primo
issued_at: 2026-04-24T10:00:05Z
---
Council convenes. What brings you here?
"""

FIXTURE_RESPONSE = """---
turn: 1
creature: Primo
machine_alias: mac-studio-001
timestamp: 2026-04-24T10:00:14Z
---
A question of continuity.
"""

FIXTURE_CLOSE = """---
by_creature: Primo
by_machine_alias: mac-studio-001
timestamp: 2026-04-24T10:05:00Z
reason: explicit_retract
turn: 3
---
Stepping away for now.
"""


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    root = tmp_path / "sessions"
    session = root / "reach_2026-04-24_hearth_primo_001"
    (session / "prompts").mkdir(parents=True)
    (session / "responses").mkdir(parents=True)
    (session / "meta.yaml").write_text(FIXTURE_META)
    (session / "turn.yaml").write_text(FIXTURE_TURN)
    (session / "prompts" / "001.md").write_text(FIXTURE_PROMPT)
    (session / "responses" / "001_primo_mac-studio-001.md").write_text(FIXTURE_RESPONSE)
    (session / "close_primo_mac-studio-001.md").write_text(FIXTURE_CLOSE)
    return root


def test_parse_frontmatter_md_basic():
    text = "---\ntitle: hello\n---\nbody here\n"
    meta, body = export_static._parse_frontmatter_md(text)
    assert meta == {"title": "hello"}
    assert body.strip() == "body here"


def test_parse_frontmatter_md_missing_returns_empty_meta():
    text = "no frontmatter at all\n"
    meta, body = export_static._parse_frontmatter_md(text)
    assert meta == {}
    assert body == text


def test_scan_sessions_lists_valid_session(session_dir: Path):
    sessions = export_static.scan_sessions(session_dir)
    assert len(sessions) == 1
    s = sessions[0]
    assert s["session_id"] == "reach_2026-04-24_hearth_primo_001"
    assert s["field"] == "Council"
    assert s["status"] == "active"
    assert s["turn_count"] == 1
    creatures = [p["creature"] for p in s["participants"]]
    assert creatures == ["Hearth", "Primo"]


def test_scan_sessions_rejects_malformed_id(tmp_path: Path):
    root = tmp_path / "sessions"
    bad = root / "not_a_reach_session"
    bad.mkdir(parents=True)
    (bad / "meta.yaml").write_text("session_id: nope\n")
    assert export_static.scan_sessions(root) == []


def test_bundle_session_full_structure(session_dir: Path):
    bundle = export_static.bundle_session(
        session_dir / "reach_2026-04-24_hearth_primo_001"
    )
    assert bundle is not None
    assert bundle["session_id"] == "reach_2026-04-24_hearth_primo_001"

    # meta propagated
    assert bundle["meta"]["field"] == "Council"
    assert len(bundle["meta"]["participants"]) == 2

    # turn.yaml captured
    assert bundle["turn_state"]["turn"] == 2
    assert bundle["turn_state"]["next"]["creature"] == "Hearth"

    # One turn with one prompt + one response
    assert len(bundle["turns"]) == 1
    turn = bundle["turns"][0]
    assert turn["turn"] == 1
    assert turn["prompt"] is not None
    assert "Council convenes" in turn["prompt"]["body"]
    assert len(turn["responses"]) == 1
    resp = turn["responses"][0]
    assert resp["frontmatter"]["creature"] == "Primo"
    assert "continuity" in resp["body"]

    # Close marker
    assert len(bundle["closes"]) == 1
    close = bundle["closes"][0]
    assert close["frontmatter"]["reason"] == "explicit_retract"
    assert close["frontmatter"]["by_creature"] == "Primo"


def test_bundle_session_missing_meta_returns_none(tmp_path: Path):
    empty = tmp_path / "reach_2026-04-24_x_y_001"
    empty.mkdir()
    assert export_static.bundle_session(empty) is None


def test_export_session_bundles_writes_json(session_dir: Path, tmp_path: Path):
    out = tmp_path / "out"
    out.mkdir()
    count = export_static.export_session_bundles(session_dir, out)
    assert count == 1
    bundle_path = out / "sessions" / "reach_2026-04-24_hearth_primo_001.json"
    assert bundle_path.exists()
    import json
    data = json.loads(bundle_path.read_text())
    assert data["session_id"] == "reach_2026-04-24_hearth_primo_001"
    assert data["turns"][0]["prompt"]["frontmatter"]["turn"] == 1
