"""Tests for Texas Hold'em Poker engine."""

import copy
import pytest
import random

from games.poker.engine import PokerGame
from games.poker.hand_eval import evaluate_hand, find_winners, compare_hands
from games.poker.pot_manager import calculate_side_pots, distribute_pots


# ──────────────────────────────────────
# Helpers
# ──────────────────────────────────────

def make_agents(n=4):
    names = ["alice", "bob", "carol", "dave", "eve", "frank", "grace"][:n]
    return [{"agent_id": name, "display_name": name.title(), "seat": i}
            for i, name in enumerate(names)]


def make_game_state(n=4):
    """Create a game with initial state wrapped in the full state dict."""
    game = PokerGame()
    agents = make_agents(n)
    game_block = game.initial_state(agents)
    state = {"game": game_block}
    return game, state


def do_move(game, state, action, agent_id=None, amount=None):
    """Apply a move and update state in-place."""
    if agent_id is None:
        agent_id = state["game"]["current"]["action_on"]
    move = {"type": "poker_action", "action": action}
    if amount is not None:
        move["amount"] = amount
    result = game.validate_move(move, agent_id, state)
    assert result["valid"], f"Move {move} by {agent_id} invalid: {result['message']}"
    state["game"] = game.apply_move(move, agent_id, state)
    return state


# ──────────────────────────────────────
# Hand Evaluation Tests
# ──────────────────────────────────────

class TestHandEvaluation:
    def test_royal_flush(self):
        ev = evaluate_hand(["Ah", "Kh"], ["Qh", "Jh", "Th", "2c", "3d"])
        assert ev["rank_name"] == "Royal Flush"
        assert ev["score"] == 1  # Best possible hand

    def test_four_of_a_kind(self):
        ev = evaluate_hand(["Ah", "Ad"], ["As", "Ac", "2h", "3d", "7c"])
        assert ev["rank_name"] == "Four of a Kind"

    def test_full_house(self):
        ev = evaluate_hand(["Ah", "Ad"], ["As", "Kc", "Kh", "3d", "7c"])
        assert ev["rank_name"] == "Full House"

    def test_flush(self):
        ev = evaluate_hand(["Ah", "9h"], ["Kh", "5h", "2h", "3d", "7c"])
        assert ev["rank_name"] == "Flush"

    def test_straight(self):
        ev = evaluate_hand(["9h", "8d"], ["7c", "6s", "5h", "2d", "Kc"])
        assert ev["rank_name"] == "Straight"

    def test_two_pair(self):
        ev = evaluate_hand(["Ah", "Kd"], ["As", "Kc", "2h", "3d", "7c"])
        assert ev["rank_name"] == "Two Pair"

    def test_one_pair(self):
        ev = evaluate_hand(["Ah", "Kd"], ["As", "2c", "5h", "3d", "7c"])
        assert ev["rank_name"] == "Pair"

    def test_high_card(self):
        ev = evaluate_hand(["Ah", "Kd"], ["9s", "2c", "5h", "3d", "7c"])
        assert ev["rank_name"] == "High Card"

    def test_compare_hands(self):
        hands = {
            "alice": ["Ah", "Kh"],  # Flush
            "bob": ["2c", "3d"],    # High card
        }
        community = ["Qh", "Jh", "9h", "5c", "8d"]
        ranked = compare_hands(hands, community)
        assert ranked[0][0] == "alice"

    def test_find_winners_single(self):
        hands = {
            "alice": ["Ah", "Kh"],
            "bob": ["2c", "3d"],
        }
        community = ["Qh", "Jh", "9h", "5c", "8d"]
        winners = find_winners(hands, community)
        assert winners == ["alice"]

    def test_find_winners_tie(self):
        # Both have same kicker via community
        hands = {
            "alice": ["2c", "3d"],
            "bob": ["2h", "3s"],
        }
        community = ["Ah", "Kd", "Qs", "Jc", "9h"]
        winners = find_winners(hands, community)
        assert len(winners) == 2

    def test_kicker_comparison(self):
        hands = {
            "alice": ["Ah", "Kd"],  # Pair of aces, K kicker
            "bob": ["As", "2c"],    # Pair of aces, low kicker
        }
        community = ["Ad", "9h", "7c", "5s", "3d"]
        # Both have trip aces actually — wait no, only one A on board
        # alice: pair of aces (Ah + Ad), bob: pair of aces (As + Ad)
        # Kicker: alice K, bob 9 from board
        winners = find_winners(hands, community)
        assert winners == ["alice"]


# ──────────────────────────────────────
# Pot Manager Tests
# ──────────────────────────────────────

class TestPotManager:
    def test_simple_pot(self):
        players = {
            "alice": {"total_bet_this_hand": 100, "status": "active"},
            "bob": {"total_bet_this_hand": 100, "status": "active"},
        }
        pots = calculate_side_pots(players)
        total = sum(p["amount"] for p in pots)
        assert total == 200

    def test_all_in_side_pot(self):
        players = {
            "alice": {"total_bet_this_hand": 50, "status": "all_in"},
            "bob": {"total_bet_this_hand": 100, "status": "active"},
            "carol": {"total_bet_this_hand": 100, "status": "active"},
        }
        pots = calculate_side_pots(players)
        # Main pot: 50*3 = 150, eligible: all 3
        # Side pot: 50*2 = 100, eligible: bob, carol
        assert len(pots) == 2
        assert pots[0]["amount"] == 150
        assert set(pots[0]["eligible"]) == {"alice", "bob", "carol"}
        assert pots[1]["amount"] == 100
        assert set(pots[1]["eligible"]) == {"bob", "carol"}

    def test_multiple_side_pots(self):
        players = {
            "alice": {"total_bet_this_hand": 30, "status": "all_in"},
            "bob": {"total_bet_this_hand": 70, "status": "all_in"},
            "carol": {"total_bet_this_hand": 100, "status": "active"},
        }
        pots = calculate_side_pots(players)
        # Pot 1: 30*3 = 90, all three
        # Pot 2: 40*2 = 80, bob + carol
        # Pot 3: 30*1 = 30, carol only
        assert len(pots) == 3
        total = sum(p["amount"] for p in pots)
        assert total == 200

    def test_folded_money_stays(self):
        players = {
            "alice": {"total_bet_this_hand": 100, "status": "active"},
            "bob": {"total_bet_this_hand": 50, "status": "folded"},
        }
        pots = calculate_side_pots(players)
        total = sum(p["amount"] for p in pots)
        assert total == 150
        # Only alice eligible
        for pot in pots:
            assert "bob" not in pot["eligible"]

    def test_distribute_simple(self):
        pots = [{"amount": 200, "eligible": ["alice", "bob"]}]
        winnings = distribute_pots(pots, [["alice"]])
        assert winnings == {"alice": 200}

    def test_distribute_split(self):
        pots = [{"amount": 200, "eligible": ["alice", "bob"]}]
        winnings = distribute_pots(pots, [["alice", "bob"]])
        assert winnings["alice"] == 100
        assert winnings["bob"] == 100


# ──────────────────────────────────────
# Initial State Tests
# ──────────────────────────────────────

class TestInitialState:
    def test_player_count(self):
        game, state = make_game_state(4)
        assert len(state["game"]["current"]["players"]) == 4

    def test_starting_chips(self):
        game, state = make_game_state(4)
        for p in state["game"]["current"]["players"].values():
            # Chips may be reduced by blinds
            assert p["chips"] <= 1000

    def test_hole_cards_dealt(self):
        game, state = make_game_state(4)
        for pid, p in state["game"]["current"]["players"].items():
            if p["status"] != "eliminated":
                assert len(p["hole_cards"]) == 2

    def test_blinds_posted(self):
        game, state = make_game_state(4)
        current = state["game"]["current"]
        assert current["pot"] == 30  # 10 + 20

    def test_phase_is_preflop(self):
        game, state = make_game_state(4)
        assert state["game"]["current"]["phase"] == "pre_flop"

    def test_action_on_set(self):
        game, state = make_game_state(4)
        assert state["game"]["current"]["action_on"] is not None

    def test_2_player(self):
        game, state = make_game_state(2)
        assert len(state["game"]["current"]["players"]) == 2
        assert state["game"]["current"]["pot"] == 30

    def test_6_player(self):
        game, state = make_game_state(6)
        assert len(state["game"]["current"]["players"]) == 6

    def test_invalid_player_count(self):
        game = PokerGame()
        with pytest.raises(ValueError):
            game.initial_state(make_agents(1))
        with pytest.raises(ValueError):
            game.initial_state(make_agents(7))


# ──────────────────────────────────────
# Move Validation Tests
# ──────────────────────────────────────

class TestValidateMove:
    def test_valid_fold(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        result = game.validate_move(
            {"type": "poker_action", "action": "fold"}, agent, state
        )
        assert result["valid"]

    def test_valid_call(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        result = game.validate_move(
            {"type": "poker_action", "action": "call"}, agent, state
        )
        assert result["valid"]

    def test_valid_raise(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        result = game.validate_move(
            {"type": "poker_action", "action": "raise", "amount": 40}, agent, state
        )
        assert result["valid"]

    def test_valid_all_in(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        result = game.validate_move(
            {"type": "poker_action", "action": "all_in"}, agent, state
        )
        assert result["valid"]

    def test_invalid_check_with_bet(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        # There's a big blind to call
        result = game.validate_move(
            {"type": "poker_action", "action": "check"}, agent, state
        )
        assert not result["valid"]
        assert "Cannot check" in result["message"]

    def test_invalid_call_no_bet(self):
        # After everyone checks post-flop, calling is invalid
        game, state = make_game_state(2)
        # Get through pre-flop to flop where current_bet = 0
        # In heads-up, pre-flop: dealer/SB acts first
        agent = state["game"]["current"]["action_on"]
        do_move(game, state, "call")  # SB calls BB
        # Now BB can check
        agent = state["game"]["current"]["action_on"]
        do_move(game, state, "check")  # BB checks, flop deals
        # Now on flop, first player can't call (nothing to call)
        if state["game"]["current"]["phase"] == "flop":
            agent = state["game"]["current"]["action_on"]
            result = game.validate_move(
                {"type": "poker_action", "action": "call"}, agent, state
            )
            assert not result["valid"]
            assert "Nothing to call" in result["message"]

    def test_invalid_raise_too_small(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        result = game.validate_move(
            {"type": "poker_action", "action": "raise", "amount": 25}, agent, state
        )
        assert not result["valid"]
        assert "Raise too small" in result["message"]

    def test_invalid_raise_no_chips(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        result = game.validate_move(
            {"type": "poker_action", "action": "raise", "amount": 5000}, agent, state
        )
        assert not result["valid"]
        assert "Not enough chips" in result["message"]

    def test_invalid_type(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        result = game.validate_move(
            {"type": "wrong", "action": "fold"}, agent, state
        )
        assert not result["valid"]

    def test_invalid_action(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        result = game.validate_move(
            {"type": "poker_action", "action": "bluff"}, agent, state
        )
        assert not result["valid"]


# ──────────────────────────────────────
# Hand Flow Tests
# ──────────────────────────────────────

class TestHandFlow:
    def test_preflop_to_flop(self):
        """All players call, flop should be dealt."""
        game, state = make_game_state(2)
        # Heads-up: SB/dealer acts first pre-flop
        do_move(game, state, "call")   # SB calls
        do_move(game, state, "check")  # BB checks
        assert state["game"]["current"]["phase"] == "flop"
        assert len(state["game"]["current"]["community_cards"]) == 3

    def test_flop_to_turn(self):
        game, state = make_game_state(2)
        do_move(game, state, "call")
        do_move(game, state, "check")
        # Flop
        do_move(game, state, "check")
        do_move(game, state, "check")
        assert state["game"]["current"]["phase"] == "turn"
        assert len(state["game"]["current"]["community_cards"]) == 4

    def test_turn_to_river(self):
        game, state = make_game_state(2)
        do_move(game, state, "call")
        do_move(game, state, "check")
        do_move(game, state, "check")
        do_move(game, state, "check")
        # Turn
        do_move(game, state, "check")
        do_move(game, state, "check")
        assert state["game"]["current"]["phase"] == "river"
        assert len(state["game"]["current"]["community_cards"]) == 5

    def test_full_hand_to_showdown(self):
        """Check through all rounds — should complete hand."""
        game, state = make_game_state(2)
        do_move(game, state, "call")
        do_move(game, state, "check")
        # Flop
        do_move(game, state, "check")
        do_move(game, state, "check")
        # Turn
        do_move(game, state, "check")
        do_move(game, state, "check")
        # River
        do_move(game, state, "check")
        do_move(game, state, "check")
        # Hand should be complete, new hand started
        current = state["game"]["current"]
        assert current["hand_number"] == 2
        assert state["game"]["context"]["hands_played"] == 1

    def test_fold_wins(self):
        """Everyone folds to one player."""
        game, state = make_game_state(4)
        do_move(game, state, "fold")
        do_move(game, state, "fold")
        do_move(game, state, "fold")
        # Last player wins, new hand starts
        assert state["game"]["current"]["hand_number"] == 2
        assert len(state["game"]["context"]["bluff_history"]) == 1

    def test_raise_resets_action(self):
        """After a raise, other players must act again."""
        game, state = make_game_state(2)
        agent1 = state["game"]["current"]["action_on"]
        do_move(game, state, "raise", amount=60)
        agent2 = state["game"]["current"]["action_on"]
        assert agent2 != agent1
        # Still in pre_flop
        assert state["game"]["current"]["phase"] == "pre_flop"


# ──────────────────────────────────────
# Multi-Hand Tests
# ──────────────────────────────────────

class TestMultiHand:
    def test_dealer_button_moves(self):
        game, state = make_game_state(2)
        d1 = state["game"]["current"]["dealer_seat"]
        # Play through a hand (everyone folds)
        do_move(game, state, "fold")
        d2 = state["game"]["current"]["dealer_seat"]
        assert d1 != d2

    def test_chip_carryover(self):
        """Chips carry from one hand to the next."""
        game, state = make_game_state(2)
        # Record initial total chips
        total_before = sum(
            p["chips"] + p["total_bet_this_hand"]
            for p in state["game"]["current"]["players"].values()
        )
        do_move(game, state, "fold")
        total_after = sum(
            p["chips"] + p["total_bet_this_hand"]
            for p in state["game"]["current"]["players"].values()
        )
        # Total chips in the system should be conserved
        assert total_before == total_after

    def test_blind_increase(self):
        game, state = make_game_state(2)
        initial_blinds = state["game"]["current"]["blinds"].copy()
        # Play 10 hands (fold immediately each time)
        for _ in range(10):
            do_move(game, state, "fold")
        new_blinds = state["game"]["current"]["blinds"]
        assert new_blinds["big"] > initial_blinds["big"]

    def test_elimination(self):
        """Player with 0 chips is eliminated."""
        game, state = make_game_state(2)
        # Force one player to have very few chips
        players = state["game"]["current"]["players"]
        seat_order = state["game"]["current"]["seat_order"]
        target = seat_order[1]
        players[target]["chips"] = 0
        # The player posted as blind should have 0 chips + blind amount
        # Let's just set up a scenario where fold eliminates
        # Simpler: use all_in with tiny stack
        game2, state2 = make_game_state(2)
        p = state2["game"]["current"]["players"]
        # Give one player minimal chips (just the blind they already posted)
        for pid in state2["game"]["current"]["seat_order"]:
            if p[pid]["chips"] > 100:
                p[pid]["chips"] = 5  # Very few chips left after blind
                break
        # Play until someone busts
        for _ in range(50):
            if game2.is_over(state2):
                break
            agent = state2["game"]["current"]["action_on"]
            if agent is None:
                break
            do_move(game2, state2, "all_in")
        # At least one player should be eliminated
        assert len(state2["game"]["context"]["elimination_order"]) >= 1

    def test_game_over(self):
        """Game ends when only 1 player remains."""
        game, state = make_game_state(2)
        # Give player 2 very few chips
        seat_order = state["game"]["current"]["seat_order"]
        players = state["game"]["current"]["players"]
        players[seat_order[1]]["chips"] = 1  # After blind, will be 0
        # Play until game over
        for _ in range(100):
            if game.is_over(state):
                break
            agent = state["game"]["current"]["action_on"]
            if agent is None:
                break
            do_move(game, state, "all_in")
        assert game.is_over(state)


# ──────────────────────────────────────
# State Filtering Tests
# ──────────────────────────────────────

class TestFilterState:
    def test_own_cards_visible(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["seat_order"][0]
        filtered = game.filter_state_for_agent(state, agent)
        hole = filtered["game"]["current"]["players"][agent]["hole_cards"]
        assert hole[0] != "??"

    def test_other_cards_hidden(self):
        game, state = make_game_state(4)
        seat_order = state["game"]["current"]["seat_order"]
        agent = seat_order[0]
        other = seat_order[1]
        filtered = game.filter_state_for_agent(state, agent)
        hole = filtered["game"]["current"]["players"][other]["hole_cards"]
        assert hole == ["??", "??"]

    def test_community_visible(self):
        game, state = make_game_state(2)
        do_move(game, state, "call")
        do_move(game, state, "check")
        agent = state["game"]["current"]["seat_order"][0]
        filtered = game.filter_state_for_agent(state, agent)
        assert len(filtered["game"]["current"]["community_cards"]) == 3

    def test_deck_hidden(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["seat_order"][0]
        filtered = game.filter_state_for_agent(state, agent)
        assert "deck" not in filtered["game"]["current"]

    def test_no_mutation(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["seat_order"][0]
        original_cards = state["game"]["current"]["players"][agent]["hole_cards"][:]
        game.filter_state_for_agent(state, agent)
        assert state["game"]["current"]["players"][agent]["hole_cards"] == original_cards


# ──────────────────────────────────────
# Summarize / Evaluation Tests
# ──────────────────────────────────────

class TestSummarizeAndEval:
    def test_summarize_fold(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        s = game.summarize_move(
            {"type": "poker_action", "action": "fold"}, agent, state
        )
        assert "folded" in s

    def test_summarize_raise(self):
        game, state = make_game_state(4)
        agent = state["game"]["current"]["action_on"]
        s = game.summarize_move(
            {"type": "poker_action", "action": "raise", "amount": 100},
            agent, state,
        )
        assert "raised to 100" in s

    def test_evaluation_schema(self):
        game = PokerGame()
        schema = game.get_evaluation_schema()
        assert "hand_reading" in schema["fields"]
        assert "bluffing" in schema["fields"]

    def test_get_rules(self):
        game = PokerGame()
        rules = game.get_rules()
        assert "Texas Hold'em" in rules


# ──────────────────────────────────────
# Integration: Full 2-Player Game
# ──────────────────────────────────────

class TestIntegration:
    def test_two_player_full_game(self):
        """Play a complete 2-player game using random actions."""
        random.seed(42)
        game, state = make_game_state(2)

        for turn in range(2000):
            if game.is_over(state):
                break

            agent = state["game"]["current"]["action_on"]
            if agent is None:
                break

            player = state["game"]["current"]["players"][agent]
            current = state["game"]["current"]
            to_call = current["current_bet"] - player["current_bet"]

            # Pick a random valid action
            actions = ["fold", "all_in"]
            if to_call <= 0:
                actions.append("check")
            if to_call > 0 and player["chips"] >= to_call:
                actions.append("call")

            action = random.choice(actions)
            do_move(game, state, action)

        assert game.is_over(state)
        result = game.get_result(state)
        assert result["winner"] is not None
        assert result["outcome"] in ("tournament_complete", "hand_limit")
        assert state["game"]["context"]["hands_played"] >= 1

    def test_four_player_full_game(self):
        """Play a complete 4-player game."""
        random.seed(123)
        game, state = make_game_state(4)

        for turn in range(5000):
            if game.is_over(state):
                break

            agent = state["game"]["current"]["action_on"]
            if agent is None:
                break

            player = state["game"]["current"]["players"][agent]
            current = state["game"]["current"]
            to_call = current["current_bet"] - player["current_bet"]

            # Always go all_in to finish quickly
            do_move(game, state, "all_in")

        assert game.is_over(state)
        result = game.get_result(state)
        assert result["winner"] is not None
        assert len(result["ranking"]) == 4
        # May end by elimination (3 eliminated) or hand limit (fewer)
        assert len(state["game"]["context"]["elimination_order"]) >= 1
