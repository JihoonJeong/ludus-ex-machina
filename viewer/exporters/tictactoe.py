"""Tic-Tac-Toe frame renderer for replay export (Pillow)."""

import copy
from PIL import Image, ImageDraw, ImageFont

from viewer.exporters.base import FrameRenderer

# Colors (matching the web viewer dark theme)
BG_COLOR = (15, 15, 26)
BOARD_BG = (26, 26, 46)
GRID_COLOR = (42, 42, 74)
X_COLOR = (0, 212, 255)
O_COLOR = (255, 107, 53)
TEXT_COLOR = (224, 224, 224)
MUTED_COLOR = (136, 136, 170)
HIGHLIGHT_COLOR = (255, 215, 0)
WIN_LINE_COLOR = (255, 215, 0)
FOOTER_COLOR = (85, 85, 119)

# Layout constants
WIDTH = 800
HEIGHT = 600
BOARD_SIZE = 360
CELL_SIZE = BOARD_SIZE // 3
BOARD_X = (WIDTH - BOARD_SIZE) // 2
BOARD_Y = 100
MARK_PAD = 22
LINE_WIDTH = 3


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a monospace font, fall back to default."""
    for name in ["Menlo", "Monaco", "Consolas", "DejaVuSansMono", "Courier"]:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    # Try common paths
    for path in [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


FONT_TITLE = _get_font(18)
FONT_SUBTITLE = _get_font(14)
FONT_MARK = _get_font(48)
FONT_MOVE = _get_font(14)
FONT_FOOTER = _get_font(12)

WIN_LINES = [
    [(0, 0), (0, 1), (0, 2)], [(1, 0), (1, 1), (1, 2)], [(2, 0), (2, 1), (2, 2)],
    [(0, 0), (1, 0), (2, 0)], [(0, 1), (1, 1), (2, 1)], [(0, 2), (1, 2), (2, 2)],
    [(0, 0), (1, 1), (2, 2)], [(0, 2), (1, 1), (2, 0)],
]


class TicTacToeFrameRenderer(FrameRenderer):

    def initial_state(self, match_config: dict) -> dict:
        agents = match_config.get("agents", [])
        marks = {}
        if len(agents) >= 2:
            marks[agents[0]["agent_id"]] = "X"
            marks[agents[1]["agent_id"]] = "O"
        return {
            "board": [[None] * 3 for _ in range(3)],
            "marks": marks,
        }

    def apply_move(self, state: dict, log_entry: dict) -> dict:
        new_board = [row[:] for row in state["board"]]
        move = log_entry["envelope"]["move"]
        if move.get("type") == "pass":
            return {**state, "board": new_board}
        r, c = move["position"]
        mark = state["marks"].get(log_entry["agent_id"], "?")
        new_board[r][c] = mark
        return {**state, "board": new_board}

    def render_frame(self, state, turn, total_turns, agents, last_move):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Header
        agent_names = " vs ".join(
            f"{a.get('display_name', a['agent_id'])} ({state['marks'].get(a['agent_id'], '?')})"
            for a in agents
        )
        title = f"Tic-Tac-Toe — Turn {turn}/{total_turns}"
        draw.text((WIDTH // 2, 24), title, fill=TEXT_COLOR, font=FONT_TITLE, anchor="mt")
        draw.text((WIDTH // 2, 50), agent_names, fill=MUTED_COLOR, font=FONT_SUBTITLE, anchor="mt")

        # Board background
        draw.rectangle(
            [BOARD_X - 8, BOARD_Y - 8, BOARD_X + BOARD_SIZE + 8, BOARD_Y + BOARD_SIZE + 8],
            fill=BOARD_BG,
        )

        # Grid lines
        for i in range(1, 3):
            x = BOARD_X + i * CELL_SIZE
            draw.line([(x, BOARD_Y), (x, BOARD_Y + BOARD_SIZE)], fill=GRID_COLOR, width=2)
            y = BOARD_Y + i * CELL_SIZE
            draw.line([(BOARD_X, y), (BOARD_X + BOARD_SIZE, y)], fill=GRID_COLOR, width=2)

        # Highlight last move cell background
        last_pos = None
        if last_move and last_move["envelope"]["move"].get("type") == "place":
            last_pos = tuple(last_move["envelope"]["move"]["position"])
            lr, lc = last_pos
            cell_x = BOARD_X + lc * CELL_SIZE
            cell_y = BOARD_Y + lr * CELL_SIZE
            draw.rectangle(
                [cell_x + 2, cell_y + 2, cell_x + CELL_SIZE - 2, cell_y + CELL_SIZE - 2],
                fill=(40, 40, 64),
            )

        # Marks
        for r in range(3):
            for c in range(3):
                mark = state["board"][r][c]
                if not mark:
                    continue
                cx = BOARD_X + c * CELL_SIZE + CELL_SIZE // 2
                cy = BOARD_Y + r * CELL_SIZE + CELL_SIZE // 2
                is_last = last_pos == (r, c)

                if mark == "X":
                    self._draw_x(draw, cx, cy, X_COLOR, is_last)
                else:
                    self._draw_o(draw, cx, cy, O_COLOR, is_last)

        # Move info
        if last_move:
            agent_id = last_move["agent_id"]
            mark = state["marks"].get(agent_id, "?")
            move = last_move["envelope"]["move"]
            if move.get("type") == "place":
                pos = move["position"]
                move_text = f"▶ {agent_id} ({mark}): Placed at ({pos[0]}, {pos[1]})"
            else:
                move_text = f"▶ {agent_id}: passed (timeout)"
            draw.text((WIDTH // 2, BOARD_Y + BOARD_SIZE + 30), move_text,
                       fill=TEXT_COLOR, font=FONT_MOVE, anchor="mt")

        # Footer
        draw.text((WIDTH // 2, HEIGHT - 20), "LxM — Ludus Ex Machina",
                   fill=FOOTER_COLOR, font=FONT_FOOTER, anchor="mb")

        return img

    def render_result_frame(self, state, result, agents, total_turns):
        img = self.render_frame(state, total_turns, total_turns, agents, None)
        draw = ImageDraw.Draw(img)

        # Draw win line if applicable
        if result.get("outcome") == "win":
            win_line = self._find_win_line(state["board"])
            if win_line:
                self._draw_win_line(draw, win_line)

        # Result overlay
        summary = result.get("summary", "Game Over")
        text_w = draw.textlength(summary, font=FONT_TITLE)
        box_pad = 16
        box_x = WIDTH // 2 - text_w // 2 - box_pad
        box_y = BOARD_Y + BOARD_SIZE + 20
        draw.rectangle(
            [box_x, box_y, box_x + text_w + box_pad * 2, box_y + 40],
            fill=(15, 15, 26, 230), outline=HIGHLIGHT_COLOR, width=2,
        )
        draw.text((WIDTH // 2, box_y + 20), summary,
                   fill=HIGHLIGHT_COLOR, font=FONT_TITLE, anchor="mm")

        return img

    def _draw_x(self, draw: ImageDraw.Draw, cx, cy, color, highlight=False):
        s = CELL_SIZE // 2 - MARK_PAD
        w = 5 if highlight else 4
        draw.line([(cx - s, cy - s), (cx + s, cy + s)], fill=color, width=w)
        draw.line([(cx + s, cy - s), (cx - s, cy + s)], fill=color, width=w)

    def _draw_o(self, draw: ImageDraw.Draw, cx, cy, color, highlight=False):
        s = CELL_SIZE // 2 - MARK_PAD
        w = 5 if highlight else 4
        draw.ellipse([cx - s, cy - s, cx + s, cy + s], outline=color, width=w)

    def _find_win_line(self, board):
        for line in WIN_LINES:
            vals = [board[r][c] for r, c in line]
            if vals[0] and vals[0] == vals[1] == vals[2]:
                return line
        return None

    def _draw_win_line(self, draw: ImageDraw.Draw, line):
        def to_xy(rc):
            r, c = rc
            return (
                BOARD_X + c * CELL_SIZE + CELL_SIZE // 2,
                BOARD_Y + r * CELL_SIZE + CELL_SIZE // 2,
            )
        start = to_xy(line[0])
        end = to_xy(line[2])
        draw.line([start, end], fill=WIN_LINE_COLOR, width=6)
