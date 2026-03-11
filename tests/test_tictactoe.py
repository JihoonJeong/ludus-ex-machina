"""Tests for games/tictactoe/engine.py"""

from games.tictactoe.engine import TicTacToe


AGENTS = [
    {"agent_id": "claude-alpha", "display_name": "Alpha", "seat": 0},
    {"agent_id": "claude-beta", "display_name": "Beta", "seat": 1},
]


def make_state(game_state: dict) -> dict:
    """Wrap game state in full state.json structure."""
    return {
        "lxm": {"turn": 1, "phase": "TURN", "agents": ["claude-alpha", "claude-beta"]},
        "game": game_state,
    }


class TestInitialState:
    def test_board_is_empty(self):
        engine = TicTacToe()
        gs = engine.initial_state(AGENTS)
        for row in gs["current"]["board"]:
            assert row == [None, None, None]

    def test_marks_assigned(self):
        engine = TicTacToe()
        gs = engine.initial_state(AGENTS)
        assert gs["current"]["marks"]["claude-alpha"] == "X"
        assert gs["current"]["marks"]["claude-beta"] == "O"

    def test_context_initialized(self):
        engine = TicTacToe()
        gs = engine.initial_state(AGENTS)
        assert gs["context"]["move_count"] == 0
        assert gs["context"]["moves_history"] == []


class TestValidateMove:
    def setup_method(self):
        self.engine = TicTacToe()
        self.state = make_state(self.engine.initial_state(AGENTS))

    def test_valid_move(self):
        result = self.engine.validate_move({"type": "place", "position": [1, 1]}, "claude-alpha", self.state)
        assert result["valid"] is True

    def test_invalid_move_occupied(self):
        self.state["game"]["current"]["board"][1][1] = "X"
        result = self.engine.validate_move({"type": "place", "position": [1, 1]}, "claude-beta", self.state)
        assert result["valid"] is False
        assert "occupied" in result["message"].lower()

    def test_invalid_move_out_of_range(self):
        result = self.engine.validate_move({"type": "place", "position": [3, 0]}, "claude-alpha", self.state)
        assert result["valid"] is False
        assert "range" in result["message"].lower()

    def test_invalid_move_wrong_type(self):
        result = self.engine.validate_move({"type": "jump", "position": [0, 0]}, "claude-alpha", self.state)
        assert result["valid"] is False

    def test_invalid_move_missing_position(self):
        result = self.engine.validate_move({"type": "place"}, "claude-alpha", self.state)
        assert result["valid"] is False

    def test_invalid_move_bad_position_format(self):
        result = self.engine.validate_move({"type": "place", "position": "center"}, "claude-alpha", self.state)
        assert result["valid"] is False


class TestApplyMove:
    def test_place_mark(self):
        engine = TicTacToe()
        state = make_state(engine.initial_state(AGENTS))
        new_game = engine.apply_move({"type": "place", "position": [1, 1]}, "claude-alpha", state)
        assert new_game["current"]["board"][1][1] == "X"
        assert new_game["context"]["move_count"] == 1
        assert len(new_game["context"]["moves_history"]) == 1


class TestIsOver:
    def setup_method(self):
        self.engine = TicTacToe()

    def _make_board_state(self, board):
        return make_state({
            "current": {"board": board, "marks": {"claude-alpha": "X", "claude-beta": "O"}},
            "context": {"move_count": 0, "moves_history": []},
        })

    def test_win_row(self):
        board = [["X", "X", "X"], [None, "O", None], [None, "O", None]]
        assert self.engine.is_over(self._make_board_state(board)) is True

    def test_win_column(self):
        board = [["X", "O", None], ["X", "O", None], ["X", None, None]]
        assert self.engine.is_over(self._make_board_state(board)) is True

    def test_win_diagonal(self):
        board = [["X", "O", None], [None, "X", "O"], [None, None, "X"]]
        assert self.engine.is_over(self._make_board_state(board)) is True

    def test_draw(self):
        board = [["X", "O", "X"], ["X", "O", "O"], ["O", "X", "X"]]
        assert self.engine.is_over(self._make_board_state(board)) is True

    def test_not_over(self):
        board = [["X", None, None], [None, "O", None], [None, None, None]]
        assert self.engine.is_over(self._make_board_state(board)) is False


class TestGetResult:
    def setup_method(self):
        self.engine = TicTacToe()

    def _make_board_state(self, board):
        return make_state({
            "current": {"board": board, "marks": {"claude-alpha": "X", "claude-beta": "O"}},
            "context": {"move_count": 0, "moves_history": []},
        })

    def test_win_result(self):
        board = [["X", "X", "X"], [None, "O", None], [None, "O", None]]
        result = self.engine.get_result(self._make_board_state(board))
        assert result["outcome"] == "win"
        assert result["winner"] == "claude-alpha"
        assert result["scores"]["claude-alpha"] == 1
        assert result["scores"]["claude-beta"] == 0
        assert "row 0" in result["summary"]

    def test_draw_result(self):
        board = [["X", "O", "X"], ["X", "O", "O"], ["O", "X", "X"]]
        result = self.engine.get_result(self._make_board_state(board))
        assert result["outcome"] == "draw"
        assert result["winner"] is None
        assert result["scores"]["claude-alpha"] == 0


class TestSummarizeMove:
    def test_summary(self):
        engine = TicTacToe()
        state = make_state(engine.initial_state(AGENTS))
        summary = engine.summarize_move({"type": "place", "position": [1, 1]}, "claude-alpha", state)
        assert "X" in summary
        assert "(1, 1)" in summary
