"""Tests for lxm/state.py"""

from lxm.state import LxMState


MATCH_CONFIG = {
    "protocol_version": "lxm-v0.2",
    "match_id": "match_001",
    "time_model": {
        "type": "turn_based",
        "turn_order": "sequential",
    },
    "agents": [
        {"agent_id": "claude-alpha", "display_name": "Alpha", "seat": 0},
        {"agent_id": "claude-beta", "display_name": "Beta", "seat": 1},
    ],
    "history": {"recent_moves_count": 3},
}

DUMMY_GAME = {"current": {}, "context": {}}


class TestInitialState:
    def test_initial_turn_zero(self):
        state = LxMState(MATCH_CONFIG)
        assert state.turn == 0
        assert state.phase == "READY"

    def test_start_sets_turn_one(self):
        state = LxMState(MATCH_CONFIG)
        full = state.start(DUMMY_GAME)
        assert state.turn == 1
        assert state.phase == "TURN"
        assert full["lxm"]["turn"] == 1
        assert full["lxm"]["active_agent"] == "claude-alpha"


class TestActiveAgent:
    def test_alternates(self):
        state = LxMState(MATCH_CONFIG)
        state.start(DUMMY_GAME)
        assert state.get_active_agent() == "claude-alpha"  # turn 1
        state.advance_turn(DUMMY_GAME)
        assert state.get_active_agent() == "claude-beta"  # turn 2
        state.advance_turn(DUMMY_GAME)
        assert state.get_active_agent() == "claude-alpha"  # turn 3


class TestRecentMoves:
    def test_fifo_capped(self):
        state = LxMState(MATCH_CONFIG)  # recent_moves_count=3
        state.start(DUMMY_GAME)

        for i in range(5):
            state.record_move("agent", {"n": i}, f"move {i}")

        full = state.to_dict(DUMMY_GAME)
        recent = full["lxm"]["recent_moves"]
        assert len(recent) == 3
        assert recent[0]["move"]["n"] == 2  # oldest kept
        assert recent[2]["move"]["n"] == 4  # newest

    def test_record_includes_turn(self):
        state = LxMState(MATCH_CONFIG)
        state.start(DUMMY_GAME)
        state.record_move("claude-alpha", {"type": "place"}, "Placed X")
        recent = state.to_dict(DUMMY_GAME)["lxm"]["recent_moves"]
        assert recent[0]["turn"] == 1
        assert recent[0]["summary"] == "Placed X"


class TestToDict:
    def test_structure(self):
        state = LxMState(MATCH_CONFIG)
        state.start(DUMMY_GAME)
        full = state.to_dict(DUMMY_GAME)
        assert "lxm" in full
        assert "game" in full
        assert full["game"] == DUMMY_GAME
        assert full["lxm"]["agents"] == ["claude-alpha", "claude-beta"]
