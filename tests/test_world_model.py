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


def test_emit_filters_rejected_and_refusal_entries():
    """C2 — distill-side structural fix. log entries with `result` in
    ('rejected', 'refusal') represent failed validations or no-op
    refusals; they did not change game state and must not flow into
    trace.jsonl. Otherwise the rejected attempt's content (e.g. the
    smoke_013 `[hearth, flint]` proposal that flunked validation) gets
    distilled into bond memory and self-reinforces on later recall.
    `accepted` and `timeout` are kept (real applied moves)."""
    schema = world_model.load_schema("avalon")
    log_with_rejects = [
        # Turn 1: rejected attempt (invalid team) — should NOT appear in trace.
        {
            "turn": 1,
            "agent_id": "a",
            "envelope": {"move": {"type": "proposal", "team": ["a", "ghost"]}},
            "validation": {"envelope_valid": False, "payload_valid": False, "engine_message": "ghost not in match"},
            "result": "rejected",
            "attempt": 1,
            "timestamp": "2026-04-26T00:00:00Z",
        },
        # Turn 1 retry: accepted — this IS what happened.
        MATCH_LOG_AVALON[0],
        # Turn 2: refusal — should NOT appear (no state change applied).
        {
            "turn": 2,
            "agent_id": "b",
            "envelope": {"move": None, "meta": {"parse_path": "refusal"}},
            "validation": {"envelope_valid": False, "payload_valid": False, "engine_message": "refusal"},
            "result": "refusal",
            "attempt": 1,
            "timestamp": "2026-04-26T00:00:15Z",
        },
        # Turn 2 vote: accepted.
        MATCH_LOG_AVALON[1],
    ]
    lines = list(world_model.emit_trace_lines(
        match_id="smoke_filter",
        config=MATCH_CONFIG_AVALON,
        log=log_with_rejects,
        result=MATCH_RESULT_AVALON,
        schema=schema,
    ))
    # 1 meta_first + 2 turns (only the accepted ones) + 1 meta_last
    assert len(lines) == 4
    turns = [l for l in lines if l["kind"] == "turn"]
    assert len(turns) == 2
    # The rejected `["a", "ghost"]` team must not surface anywhere.
    serialized = json.dumps(lines)
    assert "ghost" not in serialized
    # Both accepted moves are present in order.
    assert turns[0]["action"]["type"] == "proposal"
    assert turns[0]["action"]["team"] == ["a", "b"]
    assert turns[1]["action"]["type"] == "vote"


def test_emit_keeps_timeout_entries():
    """`timeout` means an auto-move was applied to game state; it's
    real history, not a failed attempt. Must remain in trace."""
    schema = world_model.load_schema("avalon")
    timeout_entry = {
        "turn": 3,
        "agent_id": "b",
        "envelope": None,
        "validation": {"envelope_valid": False, "payload_valid": False, "engine_message": "timeout auto-move"},
        "result": "timeout",
        "attempt": 2,
        "post_move_state": MATCH_LOG_AVALON[1]["post_move_state"],
        "post_move_context": MATCH_LOG_AVALON[1]["post_move_context"],
        "timestamp": "2026-04-26T00:01:00Z",
    }
    lines = list(world_model.emit_trace_lines(
        match_id="smoke_timeout",
        config=MATCH_CONFIG_AVALON,
        log=MATCH_LOG_AVALON + [timeout_entry],
        result=MATCH_RESULT_AVALON,
        schema=schema,
    ))
    turns = [l for l in lines if l["kind"] == "turn"]
    assert len(turns) == 3  # 2 accepted + 1 timeout
    assert any(t.get("result") == "timeout" for t in turns)


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


# ── state_signature + reward_per_turn (D-067 Phase B v3) ───────────────────


def test_avalon_signature_for_evil_active_agent():
    post_state = {
        "phase": "vote",
        "leader": "a",
        "quest_number": 1,
        "consecutive_rejections": 1,
        "players": {
            "a": {"role": "good"}, "b": {"role": "evil"},
            "c": {"role": "good"}, "d": {"role": "evil"},
            "e": {"role": "good"},
        },
        "evil_players": ["b", "d"],
        "quest_sizes": [2, 3, 2, 3, 3],
    }
    post_ctx = {"good_wins": 0, "evil_wins": 0}
    sig = world_model._avalon_signature(post_state, post_ctx, "b")
    assert sig["phase"] == "vote"
    assert sig["my_role"] == "evil"
    assert sig["quest_round"] == 1
    assert sig["rejection_streak_band"] == "low"  # 1
    assert sig["good_wins"] == 0
    assert sig["evil_wins"] == 0
    assert sig["team_size"] == 2  # quest_sizes[0]
    assert sig["is_leader"] is False  # "b" != "a"
    assert sig["evil_revealed_count"] == 2  # evil sees the full evil roster


def test_avalon_signature_good_player_evil_count_hidden():
    post_state = {
        "phase": "propose",
        "leader": "a",
        "quest_number": 3,
        "consecutive_rejections": 0,
        "players": {
            "a": {"role": "good"}, "b": {"role": "evil"},
            "c": {"role": "good"}, "d": {"role": "evil"},
            "e": {"role": "good"},
        },
        "evil_players": ["b", "d"],
        "quest_sizes": [2, 3, 2, 3, 3],
    }
    post_ctx = {"good_wins": 1, "evil_wins": 1}
    sig = world_model._avalon_signature(post_state, post_ctx, "a")
    assert sig["my_role"] == "good"
    assert sig["evil_revealed_count"] is None  # good doesn't see the roster
    assert sig["is_leader"] is True
    assert sig["team_size"] == 2  # quest 3 -> quest_sizes[2]
    assert sig["rejection_streak_band"] == "none"


def test_rejection_streak_bands():
    assert world_model._band_rejection_streak(0) == "none"
    assert world_model._band_rejection_streak(1) == "low"
    assert world_model._band_rejection_streak(2) == "low"
    assert world_model._band_rejection_streak(3) == "high"
    assert world_model._band_rejection_streak(4) == "high"


def test_avalon_reward_terminal_winner_loser():
    """±1.0 on the final turn for winning/losing factions."""
    post_state = {
        "consecutive_rejections": 0,
        "players": {"a": {"role": "good"}, "b": {"role": "evil"}},
    }
    final_scores = {"a": 1.0, "b": 0.0}
    # Final turn for good winner
    r_a = world_model._avalon_reward_per_turn(
        prev_post_state={}, post_state=post_state,
        prev_post_context={}, post_context={},
        active_agent_id="a", is_final_turn=True,
        final_scores=final_scores,
    )
    assert r_a >= 1.0  # at least the +1.0 terminal
    # Final turn for evil loser
    r_b = world_model._avalon_reward_per_turn(
        prev_post_state={}, post_state=post_state,
        prev_post_context={}, post_context={},
        active_agent_id="b", is_final_turn=True,
        final_scores=final_scores,
    )
    assert r_b <= -1.0


def test_avalon_reward_quest_delta():
    """Quest just resolved good (good_wins increased) → +0.5 for good,
    -0.5 for evil."""
    pre = {"good_wins": 0, "evil_wins": 0}
    post = {"good_wins": 1, "evil_wins": 0}
    state = {
        "consecutive_rejections": 0,
        "players": {"a": {"role": "good"}, "b": {"role": "evil"}},
    }
    r_good = world_model._avalon_reward_per_turn(
        prev_post_state=state, post_state=state,
        prev_post_context=pre, post_context=post,
        active_agent_id="a", is_final_turn=False, final_scores=None,
    )
    r_evil = world_model._avalon_reward_per_turn(
        prev_post_state=state, post_state=state,
        prev_post_context=pre, post_context=post,
        active_agent_id="b", is_final_turn=False, final_scores=None,
    )
    assert r_good == pytest.approx(0.5)
    assert r_evil == pytest.approx(-0.5)


def test_avalon_reward_rejection_penalty():
    pre_state = {
        "consecutive_rejections": 0,
        "players": {"a": {"role": "good"}},
    }
    post_state = {
        "consecutive_rejections": 1,
        "players": {"a": {"role": "good"}},
    }
    r = world_model._avalon_reward_per_turn(
        prev_post_state=pre_state, post_state=post_state,
        prev_post_context={"good_wins": 0, "evil_wins": 0},
        post_context={"good_wins": 0, "evil_wins": 0},
        active_agent_id="a", is_final_turn=False, final_scores=None,
    )
    assert r == pytest.approx(-0.1)


def test_avalon_reward_zero_when_nothing_happened():
    state = {
        "consecutive_rejections": 0,
        "players": {"a": {"role": "good"}},
    }
    ctx = {"good_wins": 0, "evil_wins": 0}
    r = world_model._avalon_reward_per_turn(
        prev_post_state=state, post_state=state,
        prev_post_context=ctx, post_context=ctx,
        active_agent_id="a", is_final_turn=False, final_scores=None,
    )
    assert r == 0.0


def test_emit_includes_signature_and_reward():
    schema = world_model.load_schema("avalon")
    lines = list(world_model.emit_trace_lines(
        match_id="smoke",
        config=MATCH_CONFIG_AVALON,
        log=MATCH_LOG_AVALON,
        result=MATCH_RESULT_AVALON,
        schema=schema,
    ))
    turns = [l for l in lines if l["kind"] == "turn"]
    assert all("state_signature" in l for l in turns)
    assert all("reward_per_turn" in l for l in turns)
    # Last turn should carry the terminal reward (≥ +1.0 for winner)
    last = turns[-1]
    if last["active_agent_id"] == "a":
        assert last["reward_per_turn"] >= 1.0
    elif last["active_agent_id"] == "b":
        assert last["reward_per_turn"] <= -1.0


def test_signature_extractor_dispatch():
    assert world_model.signature_extractor_for("lxm/avalon") is not None
    assert world_model.signature_extractor_for("lxm/nonexistent") is None
    assert world_model.reward_deriver_for("lxm/avalon") is not None


def test_trace_line_to_handle_step_kwargs_drops_extras_renames_reward():
    line = {
        "kind": "turn",
        "turn": 3,
        "active_agent_id": "echo",
        "phase": "vote",
        "ground_truth_state": {"phase": "vote"},
        "context_state": {"good_wins": 1},          # dropped
        "state_signature": {"phase": "vote"},        # dropped
        "reward_per_turn": -0.5,                     # renamed -> reward
        "action": {"type": "vote", "choice": "reject"},
        "validation": {"envelope_valid": True},      # dropped
        "result": "accepted",                        # dropped
        "events": ["echo votes reject"],
        "timestamp": "2026-04-28T...",               # dropped
    }
    kw = world_model.trace_line_to_handle_step_kwargs(line, field="lxm/avalon")
    # Required physis handle_step kwargs only — every key here is in
    # the upstream signature.
    assert set(kw.keys()) <= set(world_model._HANDLE_STEP_KWARGS)
    assert kw["field"] == "lxm/avalon"
    assert kw["turn"] == 3
    assert kw["reward"] == -0.5
    assert kw["phase"] == "vote"
    assert kw["active_agent_id"] == "echo"
    assert kw["action"]["choice"] == "reject"
    assert kw["events"] == ["echo votes reject"]
    # No extras leak through:
    assert "context_state" not in kw
    assert "state_signature" not in kw
    assert "reward_per_turn" not in kw
    assert "validation" not in kw


def test_trace_line_to_handle_step_kwargs_skips_non_turn():
    assert world_model.trace_line_to_handle_step_kwargs(
        {"kind": "meta_first"}, field="lxm/avalon"
    ) is None
    assert world_model.trace_line_to_handle_step_kwargs(
        {"kind": "meta_last"}, field="lxm/avalon"
    ) is None
    assert world_model.trace_line_to_handle_step_kwargs(
        None, field="lxm/avalon"
    ) is None


def test_trace_line_to_handle_step_kwargs_signature_in_lockstep():
    """Every kwarg name we emit must be one PhysisBlock.handle_step
    accepts. This guards against signature drift on the Ludex side —
    if Ray adds/removes a kwarg, this test should be updated alongside
    `_HANDLE_STEP_KWARGS` and the mapping body."""
    line = {"kind": "turn", "turn": 1}
    kw = world_model.trace_line_to_handle_step_kwargs(line, field="lxm/avalon")
    assert all(k in world_model._HANDLE_STEP_KWARGS for k in kw)
