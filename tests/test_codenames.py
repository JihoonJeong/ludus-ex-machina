"""Tests for Codenames game engine."""

import copy
import pytest

from games.codenames.engine import CodenamesGame
from games.codenames.wordlist import WORD_LIST


AGENTS = [
    {"agent_id": "spy-r", "display_name": "Red Spy", "seat": 0, "team": "red", "role": "spymaster"},
    {"agent_id": "guess-r", "display_name": "Red Guess", "seat": 1, "team": "red", "role": "guesser"},
    {"agent_id": "spy-b", "display_name": "Blue Spy", "seat": 2, "team": "blue", "role": "spymaster"},
    {"agent_id": "guess-b", "display_name": "Blue Guess", "seat": 3, "team": "blue", "role": "guesser"},
]


@pytest.fixture
def game():
    return CodenamesGame()


@pytest.fixture
def state(game):
    game_state = game.initial_state(AGENTS)
    return {
        "lxm": {"turn": 1, "phase": "TURN", "agents": [a["agent_id"] for a in AGENTS]},
        "game": game_state,
    }


def _find_word_by_category(state, category):
    """Find an unrevealed word of the given category."""
    current = state["game"]["current"]
    for r, row in enumerate(current["board"]):
        for c, cell in enumerate(row):
            if not cell["revealed"] and current["answer_key"][r][c] == category:
                return cell["word"]
    return None


def _find_words_by_category(state, category, count=None):
    """Find all unrevealed words of the given category."""
    current = state["game"]["current"]
    words = []
    for r, row in enumerate(current["board"]):
        for c, cell in enumerate(row):
            if not cell["revealed"] and current["answer_key"][r][c] == category:
                words.append(cell["word"])
                if count and len(words) >= count:
                    return words
    return words


# --- Initial State Tests ---

class TestInitialState:
    def test_25_words(self, game):
        gs = game.initial_state(AGENTS)
        board = gs["current"]["board"]
        assert len(board) == 5
        for row in board:
            assert len(row) == 5

    def test_correct_category_counts(self, game):
        gs = game.initial_state(AGENTS)
        key = gs["current"]["answer_key"]
        flat = [cat for row in key for cat in row]
        assert flat.count("red") == 9
        assert flat.count("blue") == 8
        assert flat.count("neutral") == 7
        assert flat.count("assassin") == 1

    def test_teams_assigned(self, game):
        gs = game.initial_state(AGENTS)
        teams = gs["current"]["teams"]
        assert teams["red"]["spymaster"] == "spy-r"
        assert teams["red"]["guesser"] == "guess-r"
        assert teams["blue"]["spymaster"] == "spy-b"
        assert teams["blue"]["guesser"] == "guess-b"

    def test_red_starts(self, game):
        gs = game.initial_state(AGENTS)
        assert gs["current"]["active_team"] == "red"
        assert gs["current"]["active_role"] == "spymaster"

    def test_remaining_counts(self, game):
        gs = game.initial_state(AGENTS)
        assert gs["current"]["remaining"]["red"] == 9
        assert gs["current"]["remaining"]["blue"] == 8

    def test_all_words_unrevealed(self, game):
        gs = game.initial_state(AGENTS)
        for row in gs["current"]["board"]:
            for cell in row:
                assert cell["revealed"] is False
                assert cell["revealed_as"] is None

    def test_unique_words(self, game):
        gs = game.initial_state(AGENTS)
        words = [cell["word"] for row in gs["current"]["board"] for cell in row]
        assert len(set(words)) == 25

    def test_words_from_list(self, game):
        gs = game.initial_state(AGENTS)
        words = [cell["word"] for row in gs["current"]["board"] for cell in row]
        for w in words:
            assert w in WORD_LIST


# --- Validate Move Tests ---

class TestValidateClue:
    def test_valid_clue(self, game, state):
        move = {"type": "clue", "word": "ocean", "number": 3}
        result = game.validate_move(move, "spy-r", state)
        assert result["valid"] is True

    def test_clue_board_word(self, game, state):
        board_word = state["game"]["current"]["board"][0][0]["word"]
        move = {"type": "clue", "word": board_word, "number": 2}
        result = game.validate_move(move, "spy-r", state)
        assert result["valid"] is False
        assert "on the board" in result["message"]

    def test_clue_multi_word(self, game, state):
        move = {"type": "clue", "word": "deep ocean", "number": 2}
        result = game.validate_move(move, "spy-r", state)
        assert result["valid"] is False
        assert "single word" in result["message"]

    def test_clue_wrong_role(self, game, state):
        move = {"type": "clue", "word": "ocean", "number": 2}
        result = game.validate_move(move, "guess-r", state)
        assert result["valid"] is False
        assert "Not your turn" in result["message"]

    def test_clue_empty_word(self, game, state):
        move = {"type": "clue", "word": "", "number": 2}
        result = game.validate_move(move, "spy-r", state)
        assert result["valid"] is False

    def test_clue_invalid_number(self, game, state):
        move = {"type": "clue", "word": "ocean", "number": 10}
        result = game.validate_move(move, "spy-r", state)
        assert result["valid"] is False

    def test_clue_number_zero(self, game, state):
        move = {"type": "clue", "word": "ocean", "number": 0}
        result = game.validate_move(move, "spy-r", state)
        assert result["valid"] is True

    def test_clue_case_insensitive_board_check(self, game, state):
        board_word = state["game"]["current"]["board"][0][0]["word"]
        move = {"type": "clue", "word": board_word.lower(), "number": 1}
        result = game.validate_move(move, "spy-r", state)
        assert result["valid"] is False


class TestValidateGuess:
    def _setup_guesser_turn(self, state):
        """Set state to guesser's turn with guesses remaining."""
        state["game"]["current"]["active_role"] = "guesser"
        state["game"]["current"]["current_clue"] = {"word": "test", "number": 2}
        state["game"]["current"]["guesses_remaining"] = 3

    def test_valid_guess(self, game, state):
        self._setup_guesser_turn(state)
        word = state["game"]["current"]["board"][0][0]["word"]
        move = {"type": "guess", "word": word}
        result = game.validate_move(move, "guess-r", state)
        assert result["valid"] is True

    def test_guess_revealed_word(self, game, state):
        self._setup_guesser_turn(state)
        state["game"]["current"]["board"][0][0]["revealed"] = True
        word = state["game"]["current"]["board"][0][0]["word"]
        move = {"type": "guess", "word": word}
        result = game.validate_move(move, "guess-r", state)
        assert result["valid"] is False

    def test_guess_not_on_board(self, game, state):
        self._setup_guesser_turn(state)
        move = {"type": "guess", "word": "XYZNOTAWORD"}
        result = game.validate_move(move, "guess-r", state)
        assert result["valid"] is False

    def test_guess_wrong_role(self, game, state):
        self._setup_guesser_turn(state)
        word = state["game"]["current"]["board"][0][0]["word"]
        move = {"type": "guess", "word": word}
        result = game.validate_move(move, "spy-r", state)
        assert result["valid"] is False

    def test_pass_valid(self, game, state):
        self._setup_guesser_turn(state)
        move = {"type": "pass"}
        result = game.validate_move(move, "guess-r", state)
        assert result["valid"] is True

    def test_no_guesses_remaining(self, game, state):
        self._setup_guesser_turn(state)
        state["game"]["current"]["guesses_remaining"] = 0
        word = state["game"]["current"]["board"][0][0]["word"]
        move = {"type": "guess", "word": word}
        result = game.validate_move(move, "guess-r", state)
        assert result["valid"] is False


# --- Apply Move Tests ---

class TestApplyClue:
    def test_clue_stored(self, game, state):
        move = {"type": "clue", "word": "ocean", "number": 3}
        new_gs = game.apply_move(move, "spy-r", state)
        assert new_gs["current"]["current_clue"] == {"word": "ocean", "number": 3}

    def test_clue_switches_to_guesser(self, game, state):
        move = {"type": "clue", "word": "ocean", "number": 3}
        new_gs = game.apply_move(move, "spy-r", state)
        assert new_gs["current"]["active_role"] == "guesser"
        assert new_gs["current"]["active_team"] == "red"  # Same team

    def test_clue_sets_guesses(self, game, state):
        move = {"type": "clue", "word": "ocean", "number": 3}
        new_gs = game.apply_move(move, "spy-r", state)
        assert new_gs["current"]["guesses_remaining"] == 4  # number + 1

    def test_clue_recorded_in_history(self, game, state):
        move = {"type": "clue", "word": "ocean", "number": 3}
        new_gs = game.apply_move(move, "spy-r", state)
        assert len(new_gs["context"]["clue_history"]) == 1
        assert new_gs["context"]["clue_history"][0]["word"] == "ocean"


class TestApplyGuess:
    def _setup_for_guess(self, game, state):
        """Apply a clue to get to guesser phase."""
        move = {"type": "clue", "word": "testclue", "number": 2}
        new_gs = game.apply_move(move, "spy-r", state)
        state["game"] = new_gs
        return state

    def test_guess_correct(self, game, state):
        state = self._setup_for_guess(game, state)
        word = _find_word_by_category(state, "red")
        assert word is not None
        move = {"type": "guess", "word": word}
        new_gs = game.apply_move(move, "guess-r", state)
        # Should still be red's turn (correct guess, guesses remain)
        assert new_gs["current"]["active_team"] == "red"
        assert new_gs["current"]["active_role"] == "guesser"
        assert new_gs["current"]["remaining"]["red"] == 8  # 9 - 1

    def test_guess_opponent(self, game, state):
        state = self._setup_for_guess(game, state)
        word = _find_word_by_category(state, "blue")
        assert word is not None
        move = {"type": "guess", "word": word}
        new_gs = game.apply_move(move, "guess-r", state)
        # Turn should switch to blue spymaster
        assert new_gs["current"]["active_team"] == "blue"
        assert new_gs["current"]["active_role"] == "spymaster"
        assert new_gs["current"]["remaining"]["blue"] == 7  # 8 - 1

    def test_guess_neutral(self, game, state):
        state = self._setup_for_guess(game, state)
        word = _find_word_by_category(state, "neutral")
        assert word is not None
        move = {"type": "guess", "word": word}
        new_gs = game.apply_move(move, "guess-r", state)
        # Turn should switch to blue spymaster
        assert new_gs["current"]["active_team"] == "blue"
        assert new_gs["current"]["active_role"] == "spymaster"

    def test_guess_assassin(self, game, state):
        state = self._setup_for_guess(game, state)
        word = _find_word_by_category(state, "assassin")
        assert word is not None
        move = {"type": "guess", "word": word}
        new_gs = game.apply_move(move, "guess-r", state)
        # Assassin should be revealed
        found = False
        for row in new_gs["current"]["board"]:
            for cell in row:
                if cell["word"] == word:
                    assert cell["revealed"] is True
                    assert cell["revealed_as"] == "assassin"
                    found = True
        assert found

    def test_guess_reveals_word(self, game, state):
        state = self._setup_for_guess(game, state)
        word = _find_word_by_category(state, "red")
        move = {"type": "guess", "word": word}
        new_gs = game.apply_move(move, "guess-r", state)
        found = False
        for row in new_gs["current"]["board"]:
            for cell in row:
                if cell["word"] == word:
                    assert cell["revealed"] is True
                    assert cell["revealed_as"] == "red"
                    found = True
        assert found

    def test_guess_decrements_remaining(self, game, state):
        state = self._setup_for_guess(game, state)
        before = state["game"]["current"]["guesses_remaining"]
        word = _find_word_by_category(state, "red")
        move = {"type": "guess", "word": word}
        new_gs = game.apply_move(move, "guess-r", state)
        assert new_gs["current"]["guesses_remaining"] == before - 1

    def test_guess_recorded_in_history(self, game, state):
        state = self._setup_for_guess(game, state)
        word = _find_word_by_category(state, "red")
        move = {"type": "guess", "word": word}
        new_gs = game.apply_move(move, "guess-r", state)
        assert len(new_gs["context"]["guess_history"]) == 1
        entry = new_gs["context"]["guess_history"][0]
        assert entry["team"] == "red"
        assert entry["correct"] is True

    def test_guess_limit_switches_team(self, game, state):
        """When guesses_remaining hits 0 after correct guess, team switches."""
        move = {"type": "clue", "word": "testclue", "number": 1}
        new_gs = game.apply_move(move, "spy-r", state)
        state["game"] = new_gs
        assert state["game"]["current"]["guesses_remaining"] == 2

        # First correct guess
        word1 = _find_word_by_category(state, "red")
        move = {"type": "guess", "word": word1}
        new_gs = game.apply_move(move, "guess-r", state)
        state["game"] = new_gs
        assert new_gs["current"]["guesses_remaining"] == 1
        assert new_gs["current"]["active_team"] == "red"  # Still red's turn

        # Second correct guess — should exhaust guesses
        word2 = _find_word_by_category(state, "red")
        if word2:
            move = {"type": "guess", "word": word2}
            new_gs = game.apply_move(move, "guess-r", state)
            assert new_gs["current"]["active_team"] == "blue"


class TestApplyPass:
    def test_pass_switches_team(self, game, state):
        # Set up guesser turn
        move = {"type": "clue", "word": "testclue", "number": 2}
        new_gs = game.apply_move(move, "spy-r", state)
        state["game"] = new_gs

        move = {"type": "pass"}
        new_gs = game.apply_move(move, "guess-r", state)
        assert new_gs["current"]["active_team"] == "blue"
        assert new_gs["current"]["active_role"] == "spymaster"
        assert new_gs["current"]["current_clue"] is None
        assert new_gs["current"]["guesses_remaining"] == 0


# --- Game Over Tests ---

class TestIsOver:
    def test_not_over_initially(self, game, state):
        assert game.is_over(state) is False

    def test_over_red_found_all(self, game, state):
        state["game"]["current"]["remaining"]["red"] = 0
        assert game.is_over(state) is True

    def test_over_blue_found_all(self, game, state):
        state["game"]["current"]["remaining"]["blue"] = 0
        assert game.is_over(state) is True

    def test_over_assassin(self, game, state):
        # Reveal the assassin
        for r, row in enumerate(state["game"]["current"]["board"]):
            for c, cell in enumerate(row):
                if state["game"]["current"]["answer_key"][r][c] == "assassin":
                    cell["revealed"] = True
                    cell["revealed_as"] = "assassin"
        assert game.is_over(state) is True


# --- Get Result Tests ---

class TestGetResult:
    def test_red_wins_complete(self, game, state):
        state["game"]["current"]["remaining"]["red"] = 0
        result = game.get_result(state)
        assert result["winner"] == "red"
        assert result["outcome"] == "complete"
        assert result["scores"]["spy-r"] == 1.0
        assert result["scores"]["guess-r"] == 1.0
        assert result["scores"]["spy-b"] == 0.0
        assert result["scores"]["guess-b"] == 0.0

    def test_blue_wins_complete(self, game, state):
        state["game"]["current"]["remaining"]["blue"] = 0
        result = game.get_result(state)
        assert result["winner"] == "blue"
        assert result["scores"]["spy-b"] == 1.0

    def test_assassin_loss(self, game, state):
        state["game"]["context"]["key_events"].append({
            "type": "assassin",
            "team": "red",
            "word": "BOMB",
        })
        result = game.get_result(state)
        assert result["winner"] == "blue"
        assert result["outcome"] == "assassin"
        assert result["scores"]["spy-r"] == 0.0
        assert result["scores"]["guess-r"] == 0.0
        assert result["scores"]["spy-b"] == 1.0


# --- Get Active Agent Tests ---

class TestGetActiveAgent:
    def test_red_spymaster_first(self, game, state):
        agent = game.get_active_agent_id(state)
        assert agent == "spy-r"

    def test_red_guesser_after_clue(self, game, state):
        state["game"]["current"]["active_role"] = "guesser"
        agent = game.get_active_agent_id(state)
        assert agent == "guess-r"

    def test_blue_spymaster_after_switch(self, game, state):
        state["game"]["current"]["active_team"] = "blue"
        state["game"]["current"]["active_role"] = "spymaster"
        agent = game.get_active_agent_id(state)
        assert agent == "spy-b"

    def test_blue_guesser(self, game, state):
        state["game"]["current"]["active_team"] = "blue"
        state["game"]["current"]["active_role"] = "guesser"
        agent = game.get_active_agent_id(state)
        assert agent == "guess-b"

    def test_full_turn_sequence(self, game, state):
        """spy-r → guess-r → spy-b → guess-b → spy-r ..."""
        # Red spymaster
        assert game.get_active_agent_id(state) == "spy-r"

        # Give clue → red guesser
        new_gs = game.apply_move({"type": "clue", "word": "test", "number": 1}, "spy-r", state)
        state["game"] = new_gs
        assert game.get_active_agent_id(state) == "guess-r"

        # Pass → blue spymaster
        new_gs = game.apply_move({"type": "pass"}, "guess-r", state)
        state["game"] = new_gs
        assert game.get_active_agent_id(state) == "spy-b"

        # Give clue → blue guesser
        new_gs = game.apply_move({"type": "clue", "word": "other", "number": 1}, "spy-b", state)
        state["game"] = new_gs
        assert game.get_active_agent_id(state) == "guess-b"


# --- State Filtering Tests ---

class TestFilterState:
    def test_spymaster_sees_key(self, game, state):
        filtered = game.filter_state_for_agent(state, "spy-r")
        key = filtered["game"]["current"]["answer_key"]
        flat = [cat for row in key for cat in row]
        assert "unknown" not in flat
        assert "red" in flat
        assert "blue" in flat

    def test_guesser_masked(self, game, state):
        filtered = game.filter_state_for_agent(state, "guess-r")
        key = filtered["game"]["current"]["answer_key"]
        flat = [cat for row in key for cat in row]
        # All unrevealed → "unknown"
        assert all(cat == "unknown" for cat in flat)

    def test_revealed_visible_to_guesser(self, game, state):
        # Reveal the first cell
        actual_category = state["game"]["current"]["answer_key"][0][0]
        state["game"]["current"]["board"][0][0]["revealed"] = True
        state["game"]["current"]["board"][0][0]["revealed_as"] = actual_category
        filtered = game.filter_state_for_agent(state, "guess-r")
        key = filtered["game"]["current"]["answer_key"]
        assert key[0][0] == actual_category
        # Others still unknown
        assert key[0][1] == "unknown"

    def test_other_team_guesser_masked(self, game, state):
        filtered = game.filter_state_for_agent(state, "guess-b")
        key = filtered["game"]["current"]["answer_key"]
        flat = [cat for row in key for cat in row]
        assert all(cat == "unknown" for cat in flat)

    def test_filter_does_not_mutate_original(self, game, state):
        original_key = copy.deepcopy(state["game"]["current"]["answer_key"])
        game.filter_state_for_agent(state, "guess-r")
        assert state["game"]["current"]["answer_key"] == original_key


# --- Summarize Move Tests ---

class TestSummarizeMove:
    def test_summarize_clue(self, game, state):
        move = {"type": "clue", "word": "ocean", "number": 3}
        s = game.summarize_move(move, "spy-r", state)
        assert "ocean" in s
        assert "3" in s

    def test_summarize_pass(self, game, state):
        move = {"type": "pass"}
        s = game.summarize_move(move, "guess-r", state)
        assert "Passed" in s or "pass" in s.lower()


# --- Wordlist Tests ---

class TestWordlist:
    def test_enough_words(self):
        assert len(WORD_LIST) >= 400

    def test_all_uppercase(self):
        for w in WORD_LIST:
            assert w == w.upper(), f"{w} is not uppercase"

    def test_unique_words(self):
        assert len(set(WORD_LIST)) == len(WORD_LIST)


# --- Evaluation Schema ---

class TestEvaluationSchema:
    def test_schema_fields(self, game):
        schema = game.get_evaluation_schema()
        assert "fields" in schema
        fields = schema["fields"]
        assert "clue_quality" in fields
        assert "guess_accuracy" in fields
        assert "team_synergy" in fields
