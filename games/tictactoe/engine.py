"""Tic-Tac-Toe game engine for LxM."""

import copy
from pathlib import Path

from lxm.engine import LxMGame


WIN_LINES = [
    # Rows
    [(0, 0), (0, 1), (0, 2)],
    [(1, 0), (1, 1), (1, 2)],
    [(2, 0), (2, 1), (2, 2)],
    # Columns
    [(0, 0), (1, 0), (2, 0)],
    [(0, 1), (1, 1), (2, 1)],
    [(0, 2), (1, 2), (2, 2)],
    # Diagonals
    [(0, 0), (1, 1), (2, 2)],
    [(0, 2), (1, 1), (2, 0)],
]


class TicTacToe(LxMGame):

    def __init__(self):
        self._rules = (Path(__file__).parent / "rules.md").read_text()

    def get_rules(self) -> str:
        return self._rules

    def initial_state(self, agents: list[dict]) -> dict:
        return {
            "current": {
                "board": [[None, None, None], [None, None, None], [None, None, None]],
                "marks": {
                    agents[0]["agent_id"]: "X",
                    agents[1]["agent_id"]: "O",
                },
            },
            "context": {
                "move_count": 0,
                "moves_history": [],
            },
        }

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        if move.get("type") != "place":
            return {"valid": False, "message": "move.type must be 'place'"}

        pos = move.get("position")
        if not isinstance(pos, list) or len(pos) != 2:
            return {"valid": False, "message": "move.position must be [row, col]"}

        row, col = pos
        if not (isinstance(row, int) and isinstance(col, int)):
            return {"valid": False, "message": "row and col must be integers"}

        if not (0 <= row <= 2 and 0 <= col <= 2):
            return {"valid": False, "message": f"Position [{row}, {col}] out of range (must be 0-2)"}

        board = state["game"]["current"]["board"]
        if board[row][col] is not None:
            return {"valid": False, "message": f"Cell [{row}, {col}] is already occupied by '{board[row][col]}'"}

        return {"valid": True, "message": None}

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = copy.deepcopy(state["game"])
        row, col = move["position"]
        mark = game["current"]["marks"][agent_id]
        game["current"]["board"][row][col] = mark
        game["context"]["move_count"] += 1
        game["context"]["moves_history"].append({
            "turn": state["lxm"]["turn"],
            "agent_id": agent_id,
            "position": [row, col],
            "mark": mark,
        })
        return game

    def is_over(self, state: dict) -> bool:
        board = state["game"]["current"]["board"]
        # Check for winner
        for line in WIN_LINES:
            vals = [board[r][c] for r, c in line]
            if vals[0] is not None and vals[0] == vals[1] == vals[2]:
                return True
        # Check for full board
        for row in board:
            if None in row:
                return False
        return True

    def get_result(self, state: dict) -> dict:
        board = state["game"]["current"]["board"]
        marks = state["game"]["current"]["marks"]
        # Invert marks dict: mark -> agent_id
        mark_to_agent = {v: k for k, v in marks.items()}

        for line in WIN_LINES:
            vals = [board[r][c] for r, c in line]
            if vals[0] is not None and vals[0] == vals[1] == vals[2]:
                winner_mark = vals[0]
                winner = mark_to_agent[winner_mark]
                # Describe the winning line
                line_desc = self._describe_line(line)
                scores = {aid: (1 if aid == winner else 0) for aid in marks}
                return {
                    "outcome": "win",
                    "winner": winner,
                    "scores": scores,
                    "summary": f"{winner} ({winner_mark}) wins by {line_desc}",
                }

        # Draw
        scores = {aid: 0 for aid in marks}
        return {
            "outcome": "draw",
            "winner": None,
            "scores": scores,
            "summary": "Draw — board full",
        }

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        mark = state["game"]["current"]["marks"][agent_id]
        row, col = move["position"]
        return f"Placed {mark} at ({row}, {col})"

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        """Build inline tic-tac-toe prompt with board state and valid positions."""
        game = state["game"]
        current = game["current"]
        match_id = state.get("lxm", {}).get("match_id", "")

        board = current["board"]
        mark = current["marks"][agent_id]

        # Render board
        board_lines = []
        for r in range(3):
            row_cells = []
            for c in range(3):
                cell = board[r][c]
                row_cells.append(cell if cell else ".")
            board_lines.append(f"  {' | '.join(row_cells)}")

        board_str = "\n".join(board_lines)

        # Valid positions
        valid = []
        for r in range(3):
            for c in range(3):
                if board[r][c] is None:
                    valid.append(f"[{r}, {c}]")

        valid_str = ", ".join(valid)

        lines = [
            f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}",
            f"Tic-Tac-Toe | You are: {mark}",
            f"",
            f"Board:",
            board_str,
            f"",
            f"Valid positions: {valid_str}",
            f"Position format: [row, col] where row and col are 0-2",
            f"",
            f'Do NOT read any files. Write your move JSON to: moves/turn_{turn}_{agent_id}.json',
            f'Copy this exactly (replace ROW and COL with your chosen position):',
            f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
            f'"move":{{"type":"place","position":[ROW, COL]}}}}',
        ]

        return "\n".join(lines)

    def get_evaluation_schema(self) -> dict:
        return {
            "description": "Rate each player's tic-tac-toe performance",
            "fields": {
                "strategy_rating": "1-5 scale, how strategic were the moves?",
                "mistakes": "List any obvious mistakes (missed wins, missed blocks)",
                "overall_comment": "Free text assessment",
            },
        }

    @staticmethod
    def _describe_line(line: list[tuple[int, int]]) -> str:
        rows = [r for r, c in line]
        cols = [c for r, c in line]
        if rows[0] == rows[1] == rows[2]:
            return f"row {rows[0]}"
        if cols[0] == cols[1] == cols[2]:
            return f"column {cols[0]}"
        if line == [(0, 0), (1, 1), (2, 2)]:
            return "diagonal (top-left to bottom-right)"
        return "diagonal (top-right to bottom-left)"
