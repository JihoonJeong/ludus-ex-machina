"""Tests for games/chess/engine.py"""

import chess
from games.chess.engine import ChessGame

AGENTS = [
    {"agent_id": "white-player", "display_name": "White", "seat": 0},
    {"agent_id": "black-player", "display_name": "Black", "seat": 1},
]


def make_state(game_state: dict) -> dict:
    return {
        "lxm": {"turn": 1, "phase": "TURN", "agents": ["white-player", "black-player"]},
        "game": game_state,
    }


class TestInitialState:
    def test_correct_fen(self):
        engine = ChessGame()
        gs = engine.initial_state(AGENTS)
        assert gs["current"]["fen"] == chess.STARTING_FEN

    def test_visual_board(self):
        engine = ChessGame()
        gs = engine.initial_state(AGENTS)
        assert gs["current"]["board_visual"][0] == "r n b q k b n r"
        assert gs["current"]["board_visual"][7] == "R N B Q K B N R"

    def test_colors(self):
        engine = ChessGame()
        gs = engine.initial_state(AGENTS)
        assert gs["current"]["colors"]["white-player"] == "white"
        assert gs["current"]["colors"]["black-player"] == "black"

    def test_initial_context(self):
        engine = ChessGame()
        gs = engine.initial_state(AGENTS)
        assert gs["context"]["move_count"] == 0
        assert gs["context"]["material_balance"] == 0
        assert gs["context"]["phase"] == "opening"


class TestValidateMove:
    def setup_method(self):
        self.engine = ChessGame()
        self.state = make_state(self.engine.initial_state(AGENTS))

    def test_valid_uci(self):
        result = self.engine.validate_move(
            {"type": "chess_move", "notation": "e2e4"}, "white-player", self.state)
        assert result["valid"] is True

    def test_valid_san(self):
        result = self.engine.validate_move(
            {"type": "chess_move", "notation": "Nf3"}, "white-player", self.state)
        assert result["valid"] is True

    def test_invalid_notation(self):
        result = self.engine.validate_move(
            {"type": "chess_move", "notation": "xyz"}, "white-player", self.state)
        assert result["valid"] is False
        assert "legal moves" in result["message"].lower()

    def test_illegal_move(self):
        result = self.engine.validate_move(
            {"type": "chess_move", "notation": "e1e3"}, "white-player", self.state)
        assert result["valid"] is False

    def test_wrong_side(self):
        result = self.engine.validate_move(
            {"type": "chess_move", "notation": "e7e5"}, "black-player", self.state)
        assert result["valid"] is False
        assert "white's turn" in result["message"].lower()

    def test_wrong_type(self):
        result = self.engine.validate_move(
            {"type": "place", "notation": "e2e4"}, "white-player", self.state)
        assert result["valid"] is False

    def test_missing_notation(self):
        result = self.engine.validate_move(
            {"type": "chess_move"}, "white-player", self.state)
        assert result["valid"] is False


class TestApplyMove:
    def setup_method(self):
        self.engine = ChessGame()
        self.state = make_state(self.engine.initial_state(AGENTS))

    def test_basic_move(self):
        new_game = self.engine.apply_move(
            {"type": "chess_move", "notation": "e2e4"}, "white-player", self.state)
        assert "4P3" in new_game["current"]["fen"]  # Pawn on e4
        assert new_game["current"]["side_to_move"] == "black"
        assert new_game["context"]["move_count"] == 1
        assert new_game["current"]["last_move"]["san"] == "e4"

    def test_capture_tracked(self):
        # Play a sequence leading to a capture
        engine = ChessGame()
        state = make_state(engine.initial_state(AGENTS))

        # 1. e4
        game = engine.apply_move({"type": "chess_move", "notation": "e2e4"}, "white-player", state)
        state = make_state(game)
        # 2. d5
        game = engine.apply_move({"type": "chess_move", "notation": "d7d5"}, "black-player", state)
        state = make_state(game)
        # 3. exd5 (capture)
        game = engine.apply_move({"type": "chess_move", "notation": "e4d5"}, "white-player", state)

        assert "p" in game["context"]["captured_pieces"]["white"]  # White captured a black pawn
        assert game["context"]["material_balance"] == 1  # White up 1

    def test_castling(self):
        engine = ChessGame()
        # Set up a position where White can castle kingside
        board = chess.Board("r1bqkbnr/pppppppp/2n5/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
        # Can't castle yet — bishop in the way. Let's use a clean position.
        board = chess.Board("r1bqk2r/ppppbppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        state = make_state({
            "current": engine._build_current(board, AGENTS, None),
            "context": {"move_count": 6, "captured_pieces": {"white": [], "black": []},
                        "material_balance": 0, "phase": "opening", "key_events": []},
        })
        game = engine.apply_move({"type": "chess_move", "notation": "e1g1"}, "white-player", state)
        assert game["current"]["last_move"]["is_castling"] is True
        assert any(e["event"] == "castling" for e in game["context"]["key_events"])

    def test_promotion(self):
        engine = ChessGame()
        # White pawn on e7, ready to promote
        board = chess.Board("8/4P3/8/8/8/8/8/4K2k w - - 0 1")
        state = make_state({
            "current": engine._build_current(board, AGENTS, None),
            "context": {"move_count": 50, "captured_pieces": {"white": [], "black": []},
                        "material_balance": 1, "phase": "endgame", "key_events": []},
        })
        game = engine.apply_move({"type": "chess_move", "notation": "e7e8q"}, "white-player", state)
        assert game["current"]["last_move"]["promotion"] == "queen"

    def test_en_passant(self):
        engine = ChessGame()
        # Set up en passant position
        board = chess.Board("rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3")
        state = make_state({
            "current": engine._build_current(board, AGENTS, None),
            "context": {"move_count": 4, "captured_pieces": {"white": [], "black": []},
                        "material_balance": 0, "phase": "opening", "key_events": []},
        })
        game = engine.apply_move({"type": "chess_move", "notation": "f5e6"}, "white-player", state)
        assert game["current"]["last_move"]["captured"] == "p"


class TestIsOver:
    def test_checkmate_fools_mate(self):
        engine = ChessGame()
        state = make_state(engine.initial_state(AGENTS))
        moves = [("e2e4", "white-player"), ("e7e5", "black-player"),
                 ("d1h5", "white-player"), ("b8c6", "black-player"),
                 ("f1c4", "white-player"), ("g8f6", "black-player"),
                 ("h5f7", "white-player")]  # Scholar's mate

        for notation, agent in moves:
            game = engine.apply_move({"type": "chess_move", "notation": notation}, agent, state)
            state = make_state(game)

        assert engine.is_over(state) is True

    def test_stalemate(self):
        engine = ChessGame()
        board = chess.Board("k7/8/1K6/8/8/8/8/1Q6 b - - 0 1")
        # Not stalemate yet — let me use a real one
        board = chess.Board("k7/8/2K5/8/8/8/8/1Q6 b - - 0 1")
        # Actually need a proper stalemate: black king on a8, white king on c7, white queen on b6
        # No — let me just use a known one
        board = chess.Board("k7/8/1QK5/8/8/8/8/8 b - - 0 1")
        state = make_state({
            "current": engine._build_current(board, AGENTS, None),
            "context": {"move_count": 50, "captured_pieces": {"white": [], "black": []},
                        "material_balance": 9, "phase": "endgame", "key_events": []},
        })
        assert engine.is_over(state) is True

    def test_insufficient_material(self):
        engine = ChessGame()
        board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")  # K vs K
        state = make_state({
            "current": engine._build_current(board, AGENTS, None),
            "context": {"move_count": 80, "captured_pieces": {"white": [], "black": []},
                        "material_balance": 0, "phase": "endgame", "key_events": []},
        })
        assert engine.is_over(state) is True

    def test_not_over(self):
        engine = ChessGame()
        state = make_state(engine.initial_state(AGENTS))
        assert engine.is_over(state) is False


class TestGetResult:
    def test_checkmate_result(self):
        engine = ChessGame()
        state = make_state(engine.initial_state(AGENTS))
        # Scholar's mate
        moves = [("e2e4", "white-player"), ("e7e5", "black-player"),
                 ("d1h5", "white-player"), ("b8c6", "black-player"),
                 ("f1c4", "white-player"), ("g8f6", "black-player"),
                 ("h5f7", "white-player")]
        for notation, agent in moves:
            game = engine.apply_move({"type": "chess_move", "notation": notation}, agent, state)
            state = make_state(game)

        result = engine.get_result(state)
        assert result["outcome"] == "checkmate"
        assert result["winner"] == "white-player"
        assert result["scores"]["white-player"] == 1.0
        assert result["scores"]["black-player"] == 0.0

    def test_draw_result(self):
        engine = ChessGame()
        board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        state = make_state({
            "current": engine._build_current(board, AGENTS, None),
            "context": {"move_count": 80, "captured_pieces": {"white": [], "black": []},
                        "material_balance": 0, "phase": "endgame", "key_events": []},
        })
        result = engine.get_result(state)
        assert "draw" in result["outcome"]
        assert result["winner"] is None
        assert result["scores"]["white-player"] == 0.5


class TestContext:
    def test_phase_transition(self):
        engine = ChessGame()
        # Opening
        assert engine._calc_phase(5, chess.Board()) == "opening"
        # Middlegame
        assert engine._calc_phase(15, chess.Board()) == "middlegame"
        # Endgame (K vs K)
        assert engine._calc_phase(50, chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")) == "endgame"

    def test_material_balance(self):
        engine = ChessGame()
        # Starting position — equal
        assert engine._calc_material_balance(chess.Board()) == 0
        # Remove black queen
        board = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        assert engine._calc_material_balance(board) == 9


class TestSummarizeMove:
    def test_basic(self):
        engine = ChessGame()
        state = make_state(engine.initial_state(AGENTS))
        summary = engine.summarize_move({"type": "chess_move", "notation": "e2e4"}, "white-player", state)
        assert summary == "e4"

    def test_checkmate_summary(self):
        engine = ChessGame()
        state = make_state(engine.initial_state(AGENTS))
        moves = [("e2e4", "white-player"), ("e7e5", "black-player"),
                 ("d1h5", "white-player"), ("b8c6", "black-player"),
                 ("f1c4", "white-player"), ("g8f6", "black-player")]
        for notation, agent in moves:
            game = engine.apply_move({"type": "chess_move", "notation": notation}, agent, state)
            state = make_state(game)
        summary = engine.summarize_move(
            {"type": "chess_move", "notation": "h5f7"}, "white-player", state)
        assert "checkmate" in summary.lower()
