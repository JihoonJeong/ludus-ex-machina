"""Chess game engine for LxM. Wraps python-chess."""

import chess
from pathlib import Path

from lxm.engine import LxMGame

PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
}

PIECE_NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}


class ChessGame(LxMGame):
    """Chess for LxM. Wraps python-chess."""

    def __init__(self):
        self._rules = (Path(__file__).parent / "rules.md").read_text(encoding="utf-8")

    def get_rules(self) -> str:
        return self._rules

    def get_active_agent_id(self, state: dict) -> str | None:
        """Return the agent who should move based on the FEN side-to-move."""
        game = state.get("game")
        if not game or not game.get("current"):
            return None
        side_to_move = game["current"].get("side_to_move")
        colors = game["current"].get("colors", {})
        for agent_id, color in colors.items():
            if color == side_to_move:
                return agent_id
        return None

    def initial_state(self, agents: list[dict]) -> dict:
        board = chess.Board()
        return {
            "current": self._build_current(board, agents, None),
            "context": {
                "move_count": 0,
                "captured_pieces": {"white": [], "black": []},
                "material_balance": 0,
                "phase": "opening",
                "key_events": [],
            },
        }

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        if move.get("type") != "chess_move":
            return {"valid": False, "message": "move.type must be 'chess_move'"}

        notation = move.get("notation")
        if not isinstance(notation, str) or not notation.strip():
            return {"valid": False, "message": "move.notation must be a non-empty string"}

        # Check correct side
        colors = state["game"]["current"]["colors"]
        side = colors.get(agent_id)
        expected_side = state["game"]["current"]["side_to_move"]
        if side != expected_side:
            return {"valid": False, "message": f"It's {expected_side}'s turn, but you are {side}"}

        board = chess.Board(state["game"]["current"]["fen"])
        parsed = self._parse_move(board, notation.strip())

        if parsed is None:
            legal = [board.uci(m) for m in list(board.legal_moves)[:10]]
            legal_str = ", ".join(legal)
            return {
                "valid": False,
                "message": f"Illegal or unrecognized move: '{notation}'. Legal moves include: {legal_str}",
            }

        return {"valid": True, "message": None}

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        import copy
        game = copy.deepcopy(state["game"])
        board = chess.Board(game["current"]["fen"])
        notation = move["notation"].strip()
        chess_move = self._parse_move(board, notation)

        # Gather pre-move info
        san = board.san(chess_move)
        is_capture = board.is_capture(chess_move)
        captured_piece = None
        if is_capture:
            captured_sq = chess_move.to_square
            # En passant
            if board.is_en_passant(chess_move):
                captured_sq = chess_move.to_square + (-8 if board.turn == chess.WHITE else 8)
            captured_piece = board.piece_at(captured_sq)
        is_castling = board.is_castling(chess_move)
        from_sq = chess.square_name(chess_move.from_square)
        to_sq = chess.square_name(chess_move.to_square)
        moving_piece = board.piece_at(chess_move.from_square)

        # Push move
        board.push(chess_move)

        is_check = board.is_check()
        agents = list(game["current"]["colors"].keys())

        # Build last_move info
        last_move = {
            "from": from_sq,
            "to": to_sq,
            "piece": moving_piece.symbol() if moving_piece else None,
            "captured": captured_piece.symbol() if captured_piece else None,
            "is_check": is_check,
            "is_castling": is_castling,
            "promotion": chess.piece_name(chess_move.promotion) if chess_move.promotion else None,
            "san": san,
        }

        # Update context
        ctx = game["context"]
        ctx["move_count"] += 1

        if is_capture and captured_piece:
            capturer_color = game["current"]["colors"][agent_id]
            ctx["captured_pieces"][capturer_color].append(captured_piece.symbol())

        ctx["material_balance"] = self._calc_material_balance(board)
        ctx["phase"] = self._calc_phase(ctx["move_count"], board)

        # Key events
        event = None
        if is_castling:
            side = "kingside" if chess_move.to_square > chess_move.from_square else "queenside"
            event = {"move": ctx["move_count"], "event": "castling", "agent": agent_id, "detail": side}
        elif is_capture and captured_piece:
            detail = f"{san}"
            if captured_piece:
                detail += f", captured {PIECE_NAMES.get(captured_piece.piece_type, '?')}"
            event = {"move": ctx["move_count"], "event": "capture", "agent": agent_id, "detail": detail}
        elif chess_move.promotion:
            event = {"move": ctx["move_count"], "event": "promotion", "agent": agent_id,
                      "detail": f"{san}, promoted to {chess.piece_name(chess_move.promotion)}"}

        if is_check and event is None:
            event = {"move": ctx["move_count"], "event": "check", "agent": agent_id, "detail": san}
        elif is_check and event:
            event["detail"] += " +"

        if event:
            ctx["key_events"].append(event)
            ctx["key_events"] = ctx["key_events"][-20:]

        game["current"] = self._build_current(board, None, last_move, game["current"]["colors"])

        return game

    def is_over(self, state: dict) -> bool:
        board = chess.Board(state["game"]["current"]["fen"])
        return board.is_game_over(claim_draw=True)

    def get_result(self, state: dict) -> dict:
        board = chess.Board(state["game"]["current"]["fen"])
        colors = state["game"]["current"]["colors"]
        # Invert: color -> agent_id
        color_to_agent = {v: k for k, v in colors.items()}
        move_count = state["game"]["context"]["move_count"]

        outcome = board.outcome(claim_draw=True)

        if outcome is None:
            # Max turns reached — evaluate by material
            balance = state["game"]["context"]["material_balance"]
            if balance > 0:
                winner = color_to_agent.get("white")
                return self._make_result("draw_max_turns", winner, colors,
                                          f"{winner} (White) wins on material (+{balance}) at turn limit")
            elif balance < 0:
                winner = color_to_agent.get("black")
                return self._make_result("draw_max_turns", winner, colors,
                                          f"{winner} (Black) wins on material ({balance}) at turn limit")
            else:
                return self._make_result("draw_max_turns", None, colors,
                                          f"Draw — equal material at turn limit ({move_count} moves)")

        # Map termination reason
        reason_map = {
            chess.Termination.CHECKMATE: "checkmate",
            chess.Termination.STALEMATE: "stalemate",
            chess.Termination.INSUFFICIENT_MATERIAL: "draw_insufficient",
            chess.Termination.FIFTY_MOVES: "draw_fifty_moves",
            chess.Termination.THREEFOLD_REPETITION: "draw_repetition",
        }
        reason = reason_map.get(outcome.termination, "unknown")

        if outcome.winner is not None:
            winner_color = "white" if outcome.winner == chess.WHITE else "black"
            winner = color_to_agent.get(winner_color)
            summary = f"{winner} ({winner_color.title()}) wins by {reason} in {move_count} moves"
            return self._make_result(reason, winner, colors, summary)
        else:
            summary = f"Draw — {reason} after {move_count} moves"
            return self._make_result(reason, None, colors, summary)

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        board = chess.Board(state["game"]["current"]["fen"])
        notation = move["notation"].strip()
        chess_move = self._parse_move(board, notation)
        if chess_move is None:
            return notation

        san = board.san(chess_move)
        is_capture = board.is_capture(chess_move)

        board.push(chess_move)
        if board.is_checkmate():
            return f"{san} — checkmate"
        if is_capture:
            return san
        return san

    def get_evaluation_schema(self) -> dict:
        return {
            "description": "Evaluate chess performance across these dimensions",
            "fields": {
                "opening_play": "1-5: Quality of opening choices. Center control, development, king safety.",
                "tactical_accuracy": "1-5: Did they spot captures, forks, pins, skewers?",
                "strategic_thinking": "1-5: Long-term planning, pawn structure, piece coordination.",
                "endgame_play": "1-5: If applicable. King activation, pawn promotion attempts.",
                "mistakes": "List specific moves that were errors, with brief explanation.",
                "best_move": "The single best move in the game, with explanation.",
                "overall_comment": "Free text assessment of play style and quality.",
            },
        }

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        """Build inline chess prompt with FEN, legal moves, and move format."""
        game = state["game"]
        current = game["current"]
        match_id = state.get("lxm", {}).get("match_id", "")

        fen = current["fen"]
        board = chess.Board(fen)
        side = current["colors"].get(agent_id, "?")
        legal_moves = [board.uci(m) for m in board.legal_moves]

        # Board visual
        visual = "\n".join(f"  {row}" for row in current["board_visual"])

        # Last move info
        last = current.get("last_move")
        last_str = f"{last['san']}" if last else "none"

        # Context
        ctx = game.get("context", {})
        move_count = ctx.get("move_count", 0)
        phase = ctx.get("phase", "opening")
        material = ctx.get("material_balance", 0)
        in_check = "YES" if current.get("in_check") else "no"

        lines = [
            f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}",
            f"Chess | Move #{move_count + 1} | Phase: {phase} | You are: {side.upper()}",
            f"",
            f"FEN: {fen}",
            f"Board:",
            visual,
            f"",
            f"Last move: {last_str}",
            f"In check: {in_check} | Material balance: {material:+d} (White perspective)",
            f"",
            f"Legal moves ({len(legal_moves)}): {' '.join(legal_moves)}",
            f"",
            f"Move format: UCI notation (e.g. e2e4, g1f3, e7e8q for promotion)",
            f"",
            f'Do NOT read any files. Write your move JSON to: moves/turn_{turn}_{agent_id}.json',
            f'Copy this exactly (replace YOUR_MOVE with a legal move from above):',
            f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
            f'"move":{{"type":"chess_move","notation":"YOUR_MOVE"}}}}',
        ]

        return "\n".join(lines)

    # ── Helpers ──

    @staticmethod
    def _parse_move(board: chess.Board, notation: str) -> chess.Move | None:
        """Try UCI first, then SAN."""
        try:
            m = chess.Move.from_uci(notation)
            if m in board.legal_moves:
                return m
        except (chess.InvalidMoveError, ValueError):
            pass
        try:
            return board.parse_san(notation)
        except (chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError, ValueError):
            pass
        return None

    @staticmethod
    def _board_visual(board: chess.Board) -> list[str]:
        """8 strings, rank 8 (top) to rank 1 (bottom)."""
        rows = []
        for rank in range(7, -1, -1):
            row = []
            for file in range(8):
                piece = board.piece_at(chess.square(file, rank))
                row.append(piece.symbol() if piece else ".")
            rows.append(" ".join(row))
        return rows

    def _build_current(self, board: chess.Board, agents: list[dict] | None,
                       last_move: dict | None, colors: dict | None = None) -> dict:
        if colors is None and agents:
            colors = {agents[0]["agent_id"]: "white", agents[1]["agent_id"]: "black"}
        return {
            "fen": board.fen(),
            "board_visual": self._board_visual(board),
            "colors": colors or {},
            "move_number": board.fullmove_number,
            "side_to_move": "white" if board.turn == chess.WHITE else "black",
            "in_check": board.is_check(),
            "legal_moves_count": len(list(board.legal_moves)),
            "last_move": last_move,
        }

    @staticmethod
    def _calc_material_balance(board: chess.Board) -> int:
        balance = 0
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece:
                val = PIECE_VALUES.get(piece.piece_type, 0)
                if piece.color == chess.WHITE:
                    balance += val
                else:
                    balance -= val
        return balance

    @staticmethod
    def _calc_phase(move_count: int, board: chess.Board) -> str:
        if move_count <= 10:
            return "opening"
        total_material = 0
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.piece_type != chess.KING:
                total_material += PIECE_VALUES.get(piece.piece_type, 0)
        if total_material <= 26:
            return "endgame"
        return "middlegame"

    @staticmethod
    def _make_result(outcome: str, winner: str | None, colors: dict, summary: str) -> dict:
        if winner:
            scores = {aid: (1.0 if aid == winner else 0.0) for aid in colors}
        else:
            scores = {aid: 0.5 for aid in colors}
        return {"outcome": outcome, "winner": winner, "scores": scores, "summary": summary}
