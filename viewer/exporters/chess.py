"""Chess frame renderer for replay export (Pillow)."""

from PIL import Image, ImageDraw, ImageFont

from viewer.exporters.base import FrameRenderer

# Colors
BG_COLOR = (15, 15, 26)
LIGHT_SQ = (240, 217, 181)
DARK_SQ = (181, 136, 99)
HIGHLIGHT_FROM = (205, 210, 106)
HIGHLIGHT_TO = (170, 162, 58)
CHECK_COLOR = (255, 50, 50)
TEXT_COLOR = (224, 224, 224)
MUTED_COLOR = (136, 136, 170)
HIGHLIGHT_RESULT = (255, 215, 0)
FOOTER_COLOR = (85, 85, 119)
WHITE_PIECE_COLOR = (255, 255, 255)
BLACK_PIECE_COLOR = (30, 30, 30)

# Layout
WIDTH = 800
HEIGHT = 600
BOARD_SIZE = 400
SQ_SIZE = BOARD_SIZE // 8
BOARD_X = 40
BOARD_Y = 80

# Unicode chess pieces
PIECE_CHARS = {
    'K': '\u2654', 'Q': '\u2655', 'R': '\u2656', 'B': '\u2657', 'N': '\u2658', 'P': '\u2659',
    'k': '\u265A', 'q': '\u265B', 'r': '\u265C', 'b': '\u265D', 'n': '\u265E', 'p': '\u265F',
}


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ["Menlo", "Monaco", "Consolas", "DejaVuSansMono", "Courier"]:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    for path in [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _get_piece_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a font that renders Unicode chess pieces well."""
    for path in [
        "/System/Library/Fonts/Apple Symbols.ttf",
        "/System/Library/Fonts/Supplemental/Apple Symbols.ttf",
        "/System/Library/Fonts/LastResort.otf",
        "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    # Try by name
    for name in ["Arial Unicode MS", "DejaVu Sans", "Noto Sans Symbols2", "Symbola"]:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return _get_font(size)


FONT_TITLE = _get_font(16)
FONT_SUBTITLE = _get_font(12)
FONT_PIECE = _get_piece_font(SQ_SIZE - 10)
FONT_LABEL = _get_font(10)
FONT_MOVE = _get_font(13)
FONT_FOOTER = _get_font(11)
FONT_PANEL = _get_font(12)
FONT_PANEL_SMALL = _get_font(11)


class ChessFrameRenderer(FrameRenderer):

    def initial_state(self, match_config: dict) -> dict:
        agents = match_config.get("agents", [])
        colors = {}
        if len(agents) >= 2:
            colors[agents[0]["agent_id"]] = "white"
            colors[agents[1]["agent_id"]] = "black"
        return {
            "board": self._starting_board(),
            "colors": colors,
            "last_move": None,
            "in_check": False,
            "side_to_move": "white",
            "captured": {"white": [], "black": []},
            "material_balance": 0,
            "phase": "opening",
        }

    def apply_move(self, state: dict, log_entry: dict) -> dict:
        post = log_entry.get("post_move_state")
        new_state = {**state}
        if post:
            bv = post.get("board_visual")
            if bv:
                new_state["board"] = [row.split(" ") for row in bv]
            new_state["last_move"] = post.get("last_move")
            new_state["in_check"] = post.get("in_check", False)
            new_state["side_to_move"] = post.get("side_to_move", "white")
        return new_state

    def render_frame(self, state, turn, total_turns, agents, last_move_entry):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Header
        agent_names = " vs ".join(
            f"{a.get('display_name', a['agent_id'])} ({state['colors'].get(a['agent_id'], '?')})"
            for a in agents
        )
        title = f"Chess \u2014 Turn {turn}/{total_turns}"
        draw.text((WIDTH // 2, 20), title, fill=TEXT_COLOR, font=FONT_TITLE, anchor="mt")
        draw.text((WIDTH // 2, 42), agent_names, fill=MUTED_COLOR, font=FONT_SUBTITLE, anchor="mt")

        # Draw board
        self._draw_board(draw, state)

        # Right panel
        panel_x = BOARD_X + BOARD_SIZE + 30
        self._draw_panel(draw, state, agents, last_move_entry, panel_x)

        # Footer
        draw.text((WIDTH // 2, HEIGHT - 16), "LxM \u2014 Ludus Ex Machina",
                   fill=FOOTER_COLOR, font=FONT_FOOTER, anchor="mb")

        return img

    def render_result_frame(self, state, result, agents, total_turns):
        img = self.render_frame(state, total_turns, total_turns, agents, None)
        draw = ImageDraw.Draw(img)

        summary = result.get("summary", "Game Over")
        text_w = draw.textlength(summary, font=FONT_TITLE)
        box_pad = 16
        box_x = WIDTH // 2 - text_w // 2 - box_pad
        box_y = HEIGHT - 60
        draw.rectangle(
            [box_x, box_y, box_x + text_w + box_pad * 2, box_y + 32],
            fill=BG_COLOR, outline=HIGHLIGHT_RESULT, width=2,
        )
        draw.text((WIDTH // 2, box_y + 16), summary,
                   fill=HIGHLIGHT_RESULT, font=FONT_TITLE, anchor="mm")

        return img

    def _draw_board(self, draw: ImageDraw.Draw, state: dict):
        board = state["board"]
        lm = state.get("last_move")

        # Parse last move squares
        from_coords = self._algebraic_to_rc(lm["from"]) if lm and lm.get("from") else None
        to_coords = self._algebraic_to_rc(lm["to"]) if lm and lm.get("to") else None

        for r in range(8):
            for f in range(8):
                x = BOARD_X + f * SQ_SIZE
                y = BOARD_Y + r * SQ_SIZE

                # Square color
                is_light = (r + f) % 2 == 0
                color = LIGHT_SQ if is_light else DARK_SQ

                # Highlight last move
                if from_coords and from_coords == (r, f):
                    color = HIGHLIGHT_FROM
                elif to_coords and to_coords == (r, f):
                    color = HIGHLIGHT_TO

                draw.rectangle([x, y, x + SQ_SIZE, y + SQ_SIZE], fill=color)

                # Check highlight
                if state.get("in_check"):
                    king_char = 'K' if state["side_to_move"] == "white" else 'k'
                    if r < len(board) and f < len(board[r]) and board[r][f] == king_char:
                        draw.rectangle([x + 2, y + 2, x + SQ_SIZE - 2, y + SQ_SIZE - 2],
                                       outline=CHECK_COLOR, width=3)

                # Piece
                if r < len(board) and f < len(board[r]):
                    piece = board[r][f]
                    if piece and piece != '.':
                        ch = PIECE_CHARS.get(piece)
                        if ch:
                            px = x + SQ_SIZE // 2
                            py = y + SQ_SIZE // 2
                            # Shadow
                            draw.text((px + 1, py + 1), ch, fill=(0, 0, 0),
                                       font=FONT_PIECE, anchor="mm")
                            piece_color = WHITE_PIECE_COLOR if piece.isupper() else BLACK_PIECE_COLOR
                            draw.text((px, py), ch, fill=piece_color,
                                       font=FONT_PIECE, anchor="mm")

        # File labels
        for f in range(8):
            lx = BOARD_X + f * SQ_SIZE + SQ_SIZE // 2
            draw.text((lx, BOARD_Y + BOARD_SIZE + 6), "abcdefgh"[f],
                       fill=MUTED_COLOR, font=FONT_LABEL, anchor="mt")
        # Rank labels
        for r in range(8):
            ly = BOARD_Y + r * SQ_SIZE + SQ_SIZE // 2
            draw.text((BOARD_X - 10, ly), str(8 - r),
                       fill=MUTED_COLOR, font=FONT_LABEL, anchor="mm")

    def _draw_panel(self, draw, state, agents, last_move_entry, x):
        y = BOARD_Y
        colors = state.get("colors", {})

        for a in agents:
            aid = a.get("agent_id", "?")
            color = colors.get(aid, "?")
            icon = "\u2654" if color == "white" else "\u265A"
            name = a.get("display_name", aid)
            draw.text((x, y), f"{icon} {name}", fill=TEXT_COLOR, font=FONT_PANEL)
            y += 22

        y += 10

        # Captured pieces
        cap = state.get("captured", {"white": [], "black": []})
        for side in ["white", "black"]:
            pieces = cap.get(side, [])
            if pieces:
                chars = "".join(PIECE_CHARS.get(p, p) for p in pieces)
                label = f"{'W' if side == 'white' else 'B'} captured: {chars}"
                draw.text((x, y), label, fill=MUTED_COLOR, font=FONT_PANEL_SMALL)
                y += 18

        y += 10

        # Material balance
        bal = state.get("material_balance", 0)
        if bal > 0:
            bal_text = f"Material: White +{bal}"
        elif bal < 0:
            bal_text = f"Material: Black +{abs(bal)}"
        else:
            bal_text = "Material: Equal"
        draw.text((x, y), bal_text, fill=MUTED_COLOR, font=FONT_PANEL_SMALL)
        y += 18

        # Phase
        phase = state.get("phase", "opening")
        draw.text((x, y), f"Phase: {phase}", fill=MUTED_COLOR, font=FONT_PANEL_SMALL)
        y += 26

        # Last move
        if last_move_entry:
            lm = last_move_entry.get("post_move_state", {}).get("last_move", {})
            san = lm.get("san", last_move_entry.get("envelope", {}).get("move", {}).get("notation", ""))
            aid = last_move_entry.get("agent_id", "?")
            if san:
                draw.text((x, y), f"Last: {aid}", fill=TEXT_COLOR, font=FONT_PANEL_SMALL)
                y += 16
                draw.text((x, y), f"  {san}", fill=HIGHLIGHT_RESULT, font=FONT_PANEL)
                y += 20

    @staticmethod
    def _starting_board():
        return [
            ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
            ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
            ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R'],
        ]

    @staticmethod
    def _algebraic_to_rc(sq: str):
        if not sq or len(sq) < 2:
            return None
        f = ord(sq[0]) - ord('a')
        r = 8 - int(sq[1])
        if 0 <= f <= 7 and 0 <= r <= 7:
            return (r, f)
        return None
