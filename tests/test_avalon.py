"""Tests for Avalon game engine."""

import copy
import pytest
from games.avalon.engine import AvalonGame, ROLE_DISTRIBUTION, QUEST_SIZES


@pytest.fixture
def game():
    return AvalonGame()


@pytest.fixture
def agents_5():
    return [{"agent_id": f"p{i}", "display_name": f"Player {i}", "seat": i} for i in range(5)]


@pytest.fixture
def agents_6():
    return [{"agent_id": f"p{i}", "display_name": f"Player {i}", "seat": i} for i in range(6)]


def make_state(game, agents):
    """Create a full state dict with game wrapper."""
    raw = game.initial_state(agents)
    return {"game": raw, "lxm": {"turn": 1, "match_id": "test"}}


def force_roles(state, good_ids, evil_ids):
    """Override random role assignment for deterministic tests."""
    current = state["game"]["current"]
    for pid in good_ids:
        current["players"][pid]["role"] = "good"
    for pid in evil_ids:
        current["players"][pid]["role"] = "evil"
    current["evil_players"] = list(evil_ids)


# ── Role Assignment ──────────────────────────────────────


class TestRoleAssignment:
    def test_5player_roles(self, game, agents_5):
        state = make_state(game, agents_5)
        players = state["game"]["current"]["players"]
        roles = [p["role"] for p in players.values()]
        assert roles.count("good") == 3
        assert roles.count("evil") == 2

    def test_6player_roles(self, game, agents_6):
        state = make_state(game, agents_6)
        players = state["game"]["current"]["players"]
        roles = [p["role"] for p in players.values()]
        assert roles.count("good") == 4
        assert roles.count("evil") == 2

    def test_evil_sees_evil(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])

        filtered = game.filter_state_for_agent(state, "p3")
        current = filtered["game"]["current"]
        # Evil player sees evil_players list
        assert set(current["evil_players"]) == {"p3", "p4"}
        # Evil player sees all roles
        assert current["players"]["p0"]["role"] == "good"
        assert current["players"]["p3"]["role"] == "evil"
        assert current["players"]["p4"]["role"] == "evil"

    def test_good_sees_nothing(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])

        filtered = game.filter_state_for_agent(state, "p0")
        current = filtered["game"]["current"]
        # Good player sees own role
        assert current["players"]["p0"]["role"] == "good"
        # Others are "unknown"
        assert current["players"]["p1"]["role"] == "unknown"
        assert current["players"]["p3"]["role"] == "unknown"
        assert current["players"]["p4"]["role"] == "unknown"
        # Evil list hidden
        assert current["evil_players"] == []


# ── Proposal Phase ───────────────────────────────────────


class TestProposal:
    def test_valid_proposal(self, game, agents_5):
        state = make_state(game, agents_5)
        # Quest 1 needs 2 players
        move = {"type": "proposal", "team": ["p0", "p1"]}
        result = game.validate_move(move, "p0", state)
        assert result["valid"]

    def test_invalid_proposal_size(self, game, agents_5):
        state = make_state(game, agents_5)
        # Quest 1 needs 2, but proposing 3
        move = {"type": "proposal", "team": ["p0", "p1", "p2"]}
        result = game.validate_move(move, "p0", state)
        assert not result["valid"]
        assert "2 members" in result["message"]

    def test_invalid_proposal_member(self, game, agents_5):
        state = make_state(game, agents_5)
        move = {"type": "proposal", "team": ["p0", "unknown_player"]}
        result = game.validate_move(move, "p0", state)
        assert not result["valid"]
        assert "Unknown player" in result["message"]

    def test_only_leader_proposes(self, game, agents_5):
        state = make_state(game, agents_5)
        # p0 is leader, p1 tries to propose
        move = {"type": "proposal", "team": ["p0", "p1"]}
        result = game.validate_move(move, "p1", state)
        assert not result["valid"]
        assert "leader" in result["message"].lower()

    def test_duplicate_team_members(self, game, agents_5):
        state = make_state(game, agents_5)
        move = {"type": "proposal", "team": ["p0", "p0"]}
        result = game.validate_move(move, "p0", state)
        assert not result["valid"]
        assert "Duplicate" in result["message"]

    def test_proposal_transitions_to_vote(self, game, agents_5):
        state = make_state(game, agents_5)
        move = {"type": "proposal", "team": ["p0", "p1"]}
        new_game_state = game.apply_move(move, "p0", state)
        assert new_game_state["current"]["phase"] == "vote"
        assert new_game_state["current"]["proposed_team"] == ["p0", "p1"]
        assert len(new_game_state["current"]["votes_pending"]) == 5


# ── Voting Phase ─────────────────────────────────────────


class TestVoting:
    def _setup_vote_phase(self, game, agents_5):
        """Get to vote phase with team [p0, p1]."""
        state = make_state(game, agents_5)
        proposal = {"type": "proposal", "team": ["p0", "p1"]}
        new_gs = game.apply_move(proposal, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]
        return state

    def test_valid_vote(self, game, agents_5):
        state = self._setup_vote_phase(game, agents_5)
        move = {"type": "vote", "choice": "approve"}
        result = game.validate_move(move, "p0", state)
        assert result["valid"]

    def test_invalid_vote(self, game, agents_5):
        state = self._setup_vote_phase(game, agents_5)
        move = {"type": "vote", "choice": "maybe"}
        result = game.validate_move(move, "p0", state)
        assert not result["valid"]

    def test_votes_masked(self, game, agents_5):
        state = self._setup_vote_phase(game, agents_5)
        # p0 votes
        vote = {"type": "vote", "choice": "approve"}
        new_gs = game.apply_move(vote, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        # p1 sees p0's vote as "submitted"
        filtered = game.filter_state_for_agent(state, "p1")
        assert filtered["game"]["current"]["votes_cast"]["p0"] == "submitted"

    def test_majority_approve(self, game, agents_5):
        state = self._setup_vote_phase(game, agents_5)
        # 3 approve, 2 reject → approved (majority)
        for i, choice in enumerate(["approve", "approve", "approve", "reject", "reject"]):
            vote = {"type": "vote", "choice": choice}
            new_gs = game.apply_move(vote, f"p{i}", state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

        assert state["game"]["current"]["phase"] == "quest"

    def test_majority_reject(self, game, agents_5):
        state = self._setup_vote_phase(game, agents_5)
        # 2 approve, 3 reject → rejected
        for i, choice in enumerate(["approve", "approve", "reject", "reject", "reject"]):
            vote = {"type": "vote", "choice": choice}
            new_gs = game.apply_move(vote, f"p{i}", state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

        assert state["game"]["current"]["phase"] == "propose"
        assert state["game"]["current"]["consecutive_rejections"] == 1
        # Leader should have advanced
        assert state["game"]["current"]["leader"] == "p1"

    def test_five_rejections_evil_wins(self, game, agents_5):
        state = make_state(game, agents_5)

        for rejection_round in range(5):
            # Propose
            leader = state["game"]["current"]["leader"]
            proposal = {"type": "proposal", "team": ["p0", "p1"]}
            new_gs = game.apply_move(proposal, leader, state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

            # All reject
            for i in range(5):
                vote = {"type": "vote", "choice": "reject"}
                new_gs = game.apply_move(vote, f"p{i}", state)
                state["game"]["current"] = new_gs["current"]
                state["game"]["context"] = new_gs["context"]

        assert game.is_over(state)
        result = game.get_result(state)
        assert result["winner"] == "evil"
        assert "rejection" in result["summary"].lower()


# ── Quest Phase ──────────────────────────────────────────


class TestQuest:
    def _setup_quest_phase(self, game, agents_5, team=None):
        """Get to quest phase with approved team."""
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])

        team = team or ["p0", "p3"]
        proposal = {"type": "proposal", "team": team}
        new_gs = game.apply_move(proposal, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        # All approve
        for i in range(5):
            vote = {"type": "vote", "choice": "approve"}
            new_gs = game.apply_move(vote, f"p{i}", state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

        assert state["game"]["current"]["phase"] == "quest"
        return state

    def test_good_must_succeed(self, game, agents_5):
        state = self._setup_quest_phase(game, agents_5, team=["p0", "p3"])
        # p0 is good, tries to sabotage
        move = {"type": "quest_action", "choice": "sabotage"}
        result = game.validate_move(move, "p0", state)
        assert not result["valid"]
        assert "Good players cannot sabotage" in result["message"]

    def test_evil_can_sabotage(self, game, agents_5):
        state = self._setup_quest_phase(game, agents_5, team=["p0", "p3"])
        move = {"type": "quest_action", "choice": "sabotage"}
        result = game.validate_move(move, "p3", state)
        assert result["valid"]

    def test_evil_can_succeed(self, game, agents_5):
        state = self._setup_quest_phase(game, agents_5, team=["p0", "p3"])
        move = {"type": "quest_action", "choice": "success"}
        result = game.validate_move(move, "p3", state)
        assert result["valid"]

    def test_quest_success(self, game, agents_5):
        state = self._setup_quest_phase(game, agents_5, team=["p0", "p3"])
        # Both play success
        for pid in ["p0", "p3"]:
            move = {"type": "quest_action", "choice": "success"}
            new_gs = game.apply_move(move, pid, state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

        assert state["game"]["context"]["good_wins"] == 1
        assert state["game"]["context"]["evil_wins"] == 0
        assert state["game"]["current"]["quest_results"][-1] is True

    def test_quest_fail(self, game, agents_5):
        state = self._setup_quest_phase(game, agents_5, team=["p0", "p3"])
        # p0 success, p3 sabotage
        move_s = {"type": "quest_action", "choice": "success"}
        new_gs = game.apply_move(move_s, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        move_f = {"type": "quest_action", "choice": "sabotage"}
        new_gs = game.apply_move(move_f, "p3", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        assert state["game"]["context"]["evil_wins"] == 1
        assert state["game"]["context"]["good_wins"] == 0
        assert state["game"]["current"]["quest_results"][-1] is False

    def test_quest_actions_masked(self, game, agents_5):
        state = self._setup_quest_phase(game, agents_5, team=["p0", "p3"])
        # p0 plays success
        move = {"type": "quest_action", "choice": "success"}
        new_gs = game.apply_move(move, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        # p3 sees p0's action as "submitted"
        filtered = game.filter_state_for_agent(state, "p3")
        assert filtered["game"]["current"]["quest_actions"]["p0"] == "submitted"


# ── Game Flow ────────────────────────────────────────────


class TestGameFlow:
    def _play_quest(self, game, state, team, votes, quest_actions):
        """Play one complete quest: propose → vote → quest."""
        leader = state["game"]["current"]["leader"]
        proposal = {"type": "proposal", "team": team}
        new_gs = game.apply_move(proposal, leader, state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        # Vote
        seat_order = state["game"]["current"]["seat_order"]
        for i, pid in enumerate(seat_order):
            choice = votes[i] if i < len(votes) else "approve"
            vote = {"type": "vote", "choice": choice}
            new_gs = game.apply_move(vote, pid, state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

        # Quest
        for pid, action in quest_actions.items():
            move = {"type": "quest_action", "choice": action}
            new_gs = game.apply_move(move, pid, state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

    def test_three_good_wins(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])
        all_approve = ["approve"] * 5

        # Quest 1: team [p0, p1], all success
        self._play_quest(game, state, ["p0", "p1"], all_approve,
                         {"p0": "success", "p1": "success"})
        assert state["game"]["context"]["good_wins"] == 1

        # Quest 2: team [p0, p1, p2], all success
        self._play_quest(game, state, ["p0", "p1", "p2"], all_approve,
                         {"p0": "success", "p1": "success", "p2": "success"})
        assert state["game"]["context"]["good_wins"] == 2

        # Quest 3: team [p0, p2], all success
        self._play_quest(game, state, ["p0", "p2"], all_approve,
                         {"p0": "success", "p2": "success"})
        assert state["game"]["context"]["good_wins"] == 3
        assert game.is_over(state)
        result = game.get_result(state)
        assert result["winner"] == "good"

    def test_three_evil_wins(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])
        all_approve = ["approve"] * 5

        # Quest 1: team [p0, p3], p3 sabotages
        self._play_quest(game, state, ["p0", "p3"], all_approve,
                         {"p0": "success", "p3": "sabotage"})
        assert state["game"]["context"]["evil_wins"] == 1

        # Quest 2: team [p1, p3, p4], p3 sabotages
        self._play_quest(game, state, ["p1", "p3", "p4"], all_approve,
                         {"p1": "success", "p3": "sabotage", "p4": "success"})
        assert state["game"]["context"]["evil_wins"] == 2

        # Quest 3: team [p2, p4], p4 sabotages
        self._play_quest(game, state, ["p2", "p4"], all_approve,
                         {"p2": "success", "p4": "sabotage"})
        assert state["game"]["context"]["evil_wins"] == 3
        assert game.is_over(state)
        result = game.get_result(state)
        assert result["winner"] == "evil"

    def test_leader_rotation(self, game, agents_5):
        state = make_state(game, agents_5)
        assert state["game"]["current"]["leader"] == "p0"

        # Propose and get rejected
        proposal = {"type": "proposal", "team": ["p0", "p1"]}
        new_gs = game.apply_move(proposal, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        for i in range(5):
            vote = {"type": "vote", "choice": "reject"}
            new_gs = game.apply_move(vote, f"p{i}", state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

        # Leader should advance to p1
        assert state["game"]["current"]["leader"] == "p1"

    def test_leader_rotation_after_quest(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])
        all_approve = ["approve"] * 5

        assert state["game"]["current"]["leader"] == "p0"

        # Complete a quest
        self._play_quest(game, state, ["p0", "p1"], all_approve,
                         {"p0": "success", "p1": "success"})

        # Leader should advance after quest
        assert state["game"]["current"]["leader"] == "p1"

    def test_leader_wraps_around(self, game, agents_5):
        state = make_state(game, agents_5)
        # Set leader to p4 (last player)
        state["game"]["current"]["leader_index"] = 4
        state["game"]["current"]["leader"] = "p4"
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])
        all_approve = ["approve"] * 5

        self._play_quest(game, state, ["p0", "p1"], all_approve,
                         {"p0": "success", "p1": "success"})

        # Should wrap to p0
        assert state["game"]["current"]["leader"] == "p0"


# ── State Filtering ──────────────────────────────────────


class TestStateFiltering:
    def test_filter_good_player(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])

        filtered = game.filter_state_for_agent(state, "p0")
        current = filtered["game"]["current"]
        assert current["players"]["p0"]["role"] == "good"
        for pid in ["p1", "p2", "p3", "p4"]:
            assert current["players"][pid]["role"] == "unknown"
        assert current["evil_players"] == []

    def test_filter_evil_player(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])

        filtered = game.filter_state_for_agent(state, "p3")
        current = filtered["game"]["current"]
        assert current["players"]["p0"]["role"] == "good"
        assert current["players"]["p3"]["role"] == "evil"
        assert current["players"]["p4"]["role"] == "evil"
        assert set(current["evil_players"]) == {"p3", "p4"}

    def test_filter_during_vote(self, game, agents_5):
        state = make_state(game, agents_5)
        # Get to vote phase
        proposal = {"type": "proposal", "team": ["p0", "p1"]}
        new_gs = game.apply_move(proposal, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        # p0 votes
        vote = {"type": "vote", "choice": "approve"}
        new_gs = game.apply_move(vote, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        # p1 filters — p0's vote should be masked
        filtered = game.filter_state_for_agent(state, "p1")
        assert filtered["game"]["current"]["votes_cast"]["p0"] == "submitted"

        # p0 filters — sees own vote
        filtered = game.filter_state_for_agent(state, "p0")
        assert filtered["game"]["current"]["votes_cast"]["p0"] == "approve"

    def test_filter_during_quest(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])

        # Get to quest phase
        proposal = {"type": "proposal", "team": ["p0", "p3"]}
        new_gs = game.apply_move(proposal, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        for i in range(5):
            vote = {"type": "vote", "choice": "approve"}
            new_gs = game.apply_move(vote, f"p{i}", state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

        # p0 plays success
        move = {"type": "quest_action", "choice": "success"}
        new_gs = game.apply_move(move, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        # p3 filters — p0's action masked
        filtered = game.filter_state_for_agent(state, "p3")
        assert filtered["game"]["current"]["quest_actions"]["p0"] == "submitted"


# ── Active Agent ─────────────────────────────────────────


class TestActiveAgent:
    def test_propose_phase_returns_leader(self, game, agents_5):
        state = make_state(game, agents_5)
        assert game.get_active_agent_id(state) == "p0"

    def test_vote_phase_returns_pending(self, game, agents_5):
        state = make_state(game, agents_5)
        proposal = {"type": "proposal", "team": ["p0", "p1"]}
        new_gs = game.apply_move(proposal, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        assert game.get_active_agent_id(state) == "p0"  # First in pending

    def test_quest_phase_returns_team_member(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])

        # Get to quest phase
        proposal = {"type": "proposal", "team": ["p0", "p3"]}
        new_gs = game.apply_move(proposal, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        for i in range(5):
            vote = {"type": "vote", "choice": "approve"}
            new_gs = game.apply_move(vote, f"p{i}", state)
            state["game"]["current"] = new_gs["current"]
            state["game"]["context"] = new_gs["context"]

        # Active agent should be first team member
        assert game.get_active_agent_id(state) == "p0"


# ── Inline Prompt ────────────────────────────────────────


class TestInlinePrompt:
    def test_prompt_contains_role_info(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])

        # Good player prompt
        filtered = game.filter_state_for_agent(state, "p0")
        prompt = game.build_inline_prompt("p0", filtered, 1)
        assert "GOOD" in prompt
        assert "do NOT know" in prompt.lower() or "do not know" in prompt.lower()

        # Evil player prompt
        filtered = game.filter_state_for_agent(state, "p3")
        prompt = game.build_inline_prompt("p3", filtered, 1)
        assert "EVIL" in prompt
        assert "p4" in prompt  # Should see ally

    def test_prompt_contains_move_template(self, game, agents_5):
        state = make_state(game, agents_5)
        prompt = game.build_inline_prompt("p0", state, 1)
        assert "lxm-v0.2" in prompt
        assert "proposal" in prompt

    def test_prompt_vote_phase(self, game, agents_5):
        state = make_state(game, agents_5)
        proposal = {"type": "proposal", "team": ["p0", "p1"]}
        new_gs = game.apply_move(proposal, "p0", state)
        state["game"]["current"] = new_gs["current"]
        state["game"]["context"] = new_gs["context"]

        prompt = game.build_inline_prompt("p1", state, 2)
        assert "VOTE" in prompt
        assert "approve" in prompt
        assert "reject" in prompt


# ── Edge Cases ───────────────────────────────────────────


class TestEdgeCases:
    def test_invalid_player_count(self, game):
        agents = [{"agent_id": f"p{i}", "display_name": f"P{i}", "seat": i} for i in range(4)]
        with pytest.raises(ValueError, match="5-10 players"):
            game.initial_state(agents)

    def test_summarize_move(self, game, agents_5):
        state = make_state(game, agents_5)
        move = {"type": "proposal", "team": ["p0", "p1"]}
        summary = game.summarize_move(move, "p0", state)
        assert "p0" in summary
        assert "proposes" in summary

    def test_get_result_includes_roles(self, game, agents_5):
        state = make_state(game, agents_5)
        force_roles(state, ["p0", "p1", "p2"], ["p3", "p4"])
        state["game"]["context"]["good_wins"] = 3
        result = game.get_result(state)
        roles = result["analysis"]["roles_revealed"]
        assert roles["p0"] == "good"
        assert roles["p3"] == "evil"

    def test_timeout_moves(self, game, agents_5):
        state = make_state(game, agents_5)
        game_state = state["game"]["current"]

        # Propose timeout
        move = game.get_timeout_move("p0", game_state)
        assert move["type"] == "proposal"
        assert len(move["team"]) == 2

        # Vote timeout
        game_state["phase"] = "vote"
        move = game.get_timeout_move("p0", game_state)
        assert move["type"] == "vote"
        assert move["choice"] == "reject"

        # Quest timeout
        game_state["phase"] = "quest"
        move = game.get_timeout_move("p0", game_state)
        assert move["type"] == "quest_action"
        assert move["choice"] == "success"
