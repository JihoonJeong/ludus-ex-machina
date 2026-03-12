"""Tests for Trust Game engine."""

import pytest
from games.trustgame.engine import TrustGame


@pytest.fixture
def game():
    return TrustGame()


@pytest.fixture
def agents():
    return [
        {"agent_id": "alice", "display_name": "Alice", "seat": 0},
        {"agent_id": "bob", "display_name": "Bob", "seat": 1},
    ]


@pytest.fixture
def initial(game, agents):
    return game.initial_state(agents)


def make_state(game_block, max_turns=40):
    return {"game": game_block, "lxm": {"max_turns": max_turns}}


class TestInitialState:
    def test_scores_zero(self, initial):
        assert initial["current"]["scores"] == {"alice": 0, "bob": 0}

    def test_round_one(self, initial):
        assert initial["current"]["round"] == 1

    def test_no_pending_move(self, initial):
        assert initial["current"]["pending_move"] is None

    def test_empty_history(self, initial):
        assert initial["context"]["history"] == []

    def test_patterns_zero(self, initial):
        p = initial["context"]["patterns"]
        assert p == {"mutual_cooperate": 0, "mutual_defect": 0, "betrayals": 0}


class TestValidateMove:
    def test_cooperate(self, game, initial):
        result = game.validate_move({"type": "choice", "action": "cooperate"}, "alice", make_state(initial))
        assert result["valid"] is True

    def test_defect(self, game, initial):
        result = game.validate_move({"type": "choice", "action": "defect"}, "alice", make_state(initial))
        assert result["valid"] is True

    def test_invalid_type(self, game, initial):
        result = game.validate_move({"type": "move", "action": "cooperate"}, "alice", make_state(initial))
        assert result["valid"] is False

    def test_invalid_action(self, game, initial):
        result = game.validate_move({"type": "choice", "action": "betray"}, "alice", make_state(initial))
        assert result["valid"] is False

    def test_missing_action(self, game, initial):
        result = game.validate_move({"type": "choice"}, "alice", make_state(initial))
        assert result["valid"] is False


class TestApplyMove:
    def test_first_move_sets_pending(self, game, initial):
        state = make_state(initial)
        result = game.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
        assert result["current"]["pending_move"]["agent_id"] == "alice"
        assert result["current"]["pending_move"]["action"] == "cooperate"
        assert result["current"]["scores"] == {"alice": 0, "bob": 0}  # Unchanged

    def test_first_move_no_score_change(self, game, initial):
        state = make_state(initial)
        result = game.apply_move({"type": "choice", "action": "defect"}, "alice", state)
        assert result["context"]["rounds_played"] == 0

    def test_cc_payoff(self, game, initial):
        state = make_state(initial)
        after_a = game.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
        state2 = make_state(after_a)
        after_b = game.apply_move({"type": "choice", "action": "cooperate"}, "bob", state2)
        assert after_b["current"]["scores"] == {"alice": 3, "bob": 3}

    def test_cd_payoff(self, game, initial):
        state = make_state(initial)
        after_a = game.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
        state2 = make_state(after_a)
        after_b = game.apply_move({"type": "choice", "action": "defect"}, "bob", state2)
        assert after_b["current"]["scores"] == {"alice": 0, "bob": 5}

    def test_dc_payoff(self, game, initial):
        state = make_state(initial)
        after_a = game.apply_move({"type": "choice", "action": "defect"}, "alice", state)
        state2 = make_state(after_a)
        after_b = game.apply_move({"type": "choice", "action": "cooperate"}, "bob", state2)
        assert after_b["current"]["scores"] == {"alice": 5, "bob": 0}

    def test_dd_payoff(self, game, initial):
        state = make_state(initial)
        after_a = game.apply_move({"type": "choice", "action": "defect"}, "alice", state)
        state2 = make_state(after_a)
        after_b = game.apply_move({"type": "choice", "action": "defect"}, "bob", state2)
        assert after_b["current"]["scores"] == {"alice": 1, "bob": 1}

    def test_round_advances(self, game, initial):
        state = make_state(initial)
        after_a = game.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
        state2 = make_state(after_a)
        after_b = game.apply_move({"type": "choice", "action": "cooperate"}, "bob", state2)
        assert after_b["current"]["round"] == 2
        assert after_b["current"]["pending_move"] is None

    def test_history_tracking(self, game, initial):
        state = make_state(initial)
        after_a = game.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
        state2 = make_state(after_a)
        after_b = game.apply_move({"type": "choice", "action": "defect"}, "bob", state2)
        assert len(after_b["context"]["history"]) == 1
        h = after_b["context"]["history"][0]
        assert h["alice"] == "cooperate"
        assert h["bob"] == "defect"
        assert h["payoffs"] == {"alice": 0, "bob": 5}

    def test_cooperation_rate(self, game, initial):
        # Play 2 rounds: both cooperate, then alice defects
        state = make_state(initial)
        # Round 1: CC
        s1 = game.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
        s2 = game.apply_move({"type": "choice", "action": "cooperate"}, "bob", make_state(s1))
        # Round 2: DC
        s3 = game.apply_move({"type": "choice", "action": "defect"}, "alice", make_state(s2))
        s4 = game.apply_move({"type": "choice", "action": "cooperate"}, "bob", make_state(s3))
        assert s4["context"]["cooperation_rate"]["alice"] == 0.5
        assert s4["context"]["cooperation_rate"]["bob"] == 1.0

    def test_pattern_tracking(self, game, initial):
        state = make_state(initial)
        # Round 1: CC → mutual_cooperate
        s1 = game.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
        s2 = game.apply_move({"type": "choice", "action": "cooperate"}, "bob", make_state(s1))
        # Round 2: DD → mutual_defect
        s3 = game.apply_move({"type": "choice", "action": "defect"}, "alice", make_state(s2))
        s4 = game.apply_move({"type": "choice", "action": "defect"}, "bob", make_state(s3))
        # Round 3: CD → betrayal
        s5 = game.apply_move({"type": "choice", "action": "cooperate"}, "alice", make_state(s4))
        s6 = game.apply_move({"type": "choice", "action": "defect"}, "bob", make_state(s5))
        p = s6["context"]["patterns"]
        assert p["mutual_cooperate"] == 1
        assert p["mutual_defect"] == 1
        assert p["betrayals"] == 1


class TestIsOver:
    def test_not_over(self, game, initial):
        state = make_state(initial, max_turns=40)
        assert game.is_over(state) is False

    def test_over_at_max(self, game, agents):
        g = TrustGame()
        init = g.initial_state(agents)
        # Simulate 20 rounds
        current_game = init
        for _ in range(20):
            state = make_state(current_game, max_turns=40)
            current_game = g.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
            state2 = make_state(current_game, max_turns=40)
            current_game = g.apply_move({"type": "choice", "action": "cooperate"}, "bob", state2)
        final = make_state(current_game, max_turns=40)
        assert g.is_over(final) is True


class TestGetResult:
    def test_win(self, game, agents):
        g = TrustGame()
        init = g.initial_state(agents)
        # Alice defects, Bob cooperates → Alice gets 5, Bob gets 0
        state = make_state(init, max_turns=2)
        s1 = g.apply_move({"type": "choice", "action": "defect"}, "alice", state)
        s2 = g.apply_move({"type": "choice", "action": "cooperate"}, "bob", make_state(s1, max_turns=2))
        result = g.get_result(make_state(s2, max_turns=2))
        assert result["outcome"] == "win"
        assert result["winner"] == "alice"
        assert result["scores"]["alice"] == 5.0
        assert result["scores"]["bob"] == 0.0

    def test_draw(self, game, agents):
        g = TrustGame()
        init = g.initial_state(agents)
        state = make_state(init, max_turns=2)
        s1 = g.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
        s2 = g.apply_move({"type": "choice", "action": "cooperate"}, "bob", make_state(s1, max_turns=2))
        result = g.get_result(make_state(s2, max_turns=2))
        assert result["outcome"] == "draw"
        assert result["winner"] is None


class TestSummarizeMove:
    def test_first_move(self, game, initial):
        state = make_state(initial)
        summary = game.summarize_move({"type": "choice", "action": "cooperate"}, "alice", state)
        assert "cooperate" in summary
        assert "Round 1" in summary

    def test_resolving_move(self, game, initial):
        state = make_state(initial)
        after_a = game.apply_move({"type": "choice", "action": "cooperate"}, "alice", state)
        state2 = make_state(after_a)
        summary = game.summarize_move({"type": "choice", "action": "defect"}, "bob", state2)
        assert "resolved" in summary
        assert "0/5" in summary


class TestStateFiltering:
    def test_pending_hidden_from_second_agent(self, game, initial):
        state = make_state(initial)
        after_a = game.apply_move({"type": "choice", "action": "defect"}, "alice", state)
        full_state = make_state(after_a)
        filtered = game.filter_state_for_agent(full_state, "bob")
        assert filtered["game"]["current"]["pending_move"] == "submitted"

    def test_pending_visible_to_first_agent(self, game, initial):
        state = make_state(initial)
        after_a = game.apply_move({"type": "choice", "action": "defect"}, "alice", state)
        full_state = make_state(after_a)
        filtered = game.filter_state_for_agent(full_state, "alice")
        assert filtered["game"]["current"]["pending_move"]["action"] == "defect"

    def test_no_pending_no_filter(self, game, initial):
        state = make_state(initial)
        filtered = game.filter_state_for_agent(state, "alice")
        assert filtered["game"]["current"]["pending_move"] is None
