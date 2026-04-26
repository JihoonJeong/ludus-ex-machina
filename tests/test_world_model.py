"""Smoke tests for lxm/world_model.py — D-067 physis trace export.

Schema-driven export of a match's (state, action, reward) trace.
Skeleton-level coverage: schema lookup, trace shape, meta-first +
per-turn + meta-last line emission. Avalon used as the first
schema-bearing field.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from lxm import world_model


# ── fixtures ───────────────────────────────────────────────────────────────


MATCH_CONFIG_AVALON = {
    "match_id": "smoke_avalon",
    "game": {"name": "avalon"},
    "agents": [
        {"agent_id": "a", "display_name": "Alpha", "adapter": "claude", "model": "opus", "seat": 0},
        {"agent_id": "b", "display_name": "Bravo", "adapter": "rule_bot", "model": "n/a", "seat": 1},
    ],
    "seed": 42,
}

MATCH_LOG_AVALON = [
    {
        "turn": 1,
        "agent_id": "a",
        "envelope": {"move": {"type": "proposal", "team": ["a", "b"]}},
        "validation": {"envelope_valid": True, "payload_valid": True},
        "result": "accepted",
        "post_move_state": {
            "phase": "vote",
            "leader": "a",
            "proposed_team": ["a", "b"],
            "quest_number": 1,
            "consecutive_rejections": 0,
            "players": {"a": {"role": "good"}, "b": {"role": "evil"}},
            "evil_players": ["b"],
            "seat_order": ["a", "b"],
            "quest_sizes": [2],
            "last_events": ["a proposes team [a,b]"],
        },
        "post_move_context": {
            "quests_completed": 0,
            "good_wins": 0,
            "evil_wins": 0,
            "all_proposals": [],
        },
        "timestamp": "2026-04-26T00:00:00Z",
    },
    {
        "turn": 2,
        "agent_id": "b",
        "envelope": {"move": {"type": "vote", "choice": "approve"}},
        "validation": {"envelope_valid": True, "payload_valid": True},
        "result": "accepted",
        "post_move_state": {
            "phase": "quest",
            "leader": "a",
            "proposed_team": ["a", "b"],
            "quest_number": 1,
            "consecutive_rejections": 0,
            "players": {"a": {"role": "good"}, "b": {"role": "evil"}},
            "evil_players": ["b"],
            "seat_order": ["a", "b"],
            "quest_sizes": [2],
            "last_events": ["votes settled: 2-0 approve; quest begins"],
        },
        "post_move_context": {"quests_completed": 0, "good_wins": 0, "evil_wins": 0},
        "timestamp": "2026-04-26T00:00:30Z",
    },
]

MATCH_RESULT_AVALON = {
    "outcome": "good_wins",
    "winner": "good",
    "scores": {"a": 1.0, "b": 0.0},
    "summary": "Good wins 3-2!",
}


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Build a minimal LxM-shaped repo: matches/<id>/{config,log,result}
    plus games/avalon/world_schema.json copied from the real one."""
    # Match folder.
    match_dir = tmp_path / "matches" / "smoke_avalon"
    match_dir.mkdir(parents=True)
    (match_dir / "match_config.json").write_text(json.dumps(MATCH_CONFIG_AVALON))
    (match_dir / "log.json").write_text(json.dumps(MATCH_LOG_AVALON))
    (match_dir / "result.json").write_text(json.dumps(MATCH_RESULT_AVALON))

    # Schema folder — copy the real avalon schema so the test exercises
    # the same shape that production will use.
    schema_src = Path(__file__).parent.parent / "games" / "avalon" / "world_schema.json"
    schema_dst = tmp_path / "games" / "avalon" / "world_schema.json"
    schema_dst.parent.mkdir(parents=True)
    schema_dst.write_text(schema_src.read_text())
    return tmp_path


# ── tests ──────────────────────────────────────────────────────────────────


def test_load_schema_avalon():
    schema = world_model.load_schema("avalon")
    assert schema["field"] == "lxm/avalon"
    assert "ground_truth_keys" in schema["state_space"]
    assert "proposal" in {a["type"] for a in schema["action_set"]}


def test_load_schema_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        world_model.load_schema("nonexistent_game", project_root=tmp_path)


def test_schema_for_match_resolves_game(fake_repo: Path):
    game, schema = world_model.schema_for_match("smoke_avalon", project_root=fake_repo)
    assert game == "avalon"
    assert schema["field"] == "lxm/avalon"


def test_emit_trace_lines_shape():
    schema = world_model.load_schema("avalon")
    lines = list(world_model.emit_trace_lines(
        match_id="smoke_avalon",
        config=MATCH_CONFIG_AVALON,
        log=MATCH_LOG_AVALON,
        result=MATCH_RESULT_AVALON,
        schema=schema,
    ))
    # 1 meta_first + 2 turns + 1 meta_last
    assert len(lines) == 4
    assert lines[0]["kind"] == "meta_first"
    assert lines[0]["match_id"] == "smoke_avalon"
    assert lines[0]["field"] == "lxm/avalon"
    assert len(lines[0]["agents"]) == 2

    assert lines[1]["kind"] == "turn"
    assert lines[1]["turn"] == 1
    assert lines[1]["active_agent_id"] == "a"
    assert lines[1]["action"]["type"] == "proposal"
    # ground-truth-keys projection: schema declares these; result must
    # include `phase`, `quest_number`, etc., even when their values are
    # plain Python types post-serialization.
    assert lines[1]["ground_truth_state"]["phase"] == "vote"
    assert lines[1]["ground_truth_state"]["quest_number"] == 1
    assert lines[1]["context_state"]["quests_completed"] == 0
    # Events surface from post_move_state.last_events:
    assert "a proposes team" in lines[1]["events"][0]

    assert lines[2]["kind"] == "turn"
    assert lines[2]["action"]["type"] == "vote"

    assert lines[3]["kind"] == "meta_last"
    assert lines[3]["outcome"] == "good_wins"
    assert lines[3]["scores"] == {"a": 1.0, "b": 0.0}


def test_export_match_trace_writes_jsonl(fake_repo: Path, tmp_path: Path):
    out_path = world_model.export_match_trace(
        "smoke_avalon",
        project_root=fake_repo,
        output_dir=tmp_path / "out",
    )
    assert out_path.exists()
    text = out_path.read_text()
    lines = [json.loads(l) for l in text.splitlines()]
    assert lines[0]["kind"] == "meta_first"
    assert lines[-1]["kind"] == "meta_last"
    # Roughly 1 meta + 2 turns + 1 meta
    assert len(lines) == 4


def test_export_uses_schema_trace_path_when_no_override(fake_repo: Path):
    out_path = world_model.export_match_trace(
        "smoke_avalon", project_root=fake_repo,
    )
    # schema declares "traces/lxm/avalon/<match_id>/trace.jsonl"
    expected = fake_repo / "traces" / "lxm" / "avalon" / "smoke_avalon" / "trace.jsonl"
    assert out_path == expected
    assert out_path.exists()


def test_emit_handles_empty_log():
    schema = world_model.load_schema("avalon")
    lines = list(world_model.emit_trace_lines(
        match_id="empty",
        config={"match_id": "empty", "game": {"name": "avalon"}, "agents": []},
        log=[],
        result={"outcome": "aborted"},
        schema=schema,
    ))
    # Only meta_first + meta_last
    assert len(lines) == 2
    assert lines[0]["kind"] == "meta_first"
    assert lines[1]["kind"] == "meta_last"
    assert lines[0]["started_at"] is None
    assert lines[1]["ended_at"] is None
