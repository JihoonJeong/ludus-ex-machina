# LxM Chess Game Spec v0.1

## Purpose

Add Chess as the second LxM game. Wraps the `python-chess` library with the LxM Game Engine interface. Also adds a chess renderer for the match viewer.

**Hand this to Cody and say "build this."**

**Prerequisites:**
- LxM core system working (orchestrator, envelope, state, adapter)
- Match viewer working (server, replay/live mode, tic-tac-toe renderer)
- `pip install python-chess`

---

## 1. File Structure

```
games/
└── chess/
    ├── engine.py              ← ChessGame(LxMGame) — wrapper around python-chess
    ├── rules.md               ← Agent-readable chess rules + LxM move format
    └── README.md

viewer/
└── static/
    └── renderers/
        └── chess.js           ← Chess board renderer for the viewer

viewer/
└── exporters/
    └── chess.py               ← Chess frame renderer for GIF/MP4 export
```

---

## 2. Game Engine: `games/chess/engine.py`

Wraps `python-chess`. The library handles all chess logic — legal moves, check/checkmate/stalemate detection, move parsing. The wrapper translates between python-chess and LxM formats.

```python
import chess
from pathlib import Path
from lxm.engine import LxMGame

class ChessGame(LxMGame):
    """
    Chess for LxM. Wraps python-chess.
    
    Internal state tracking:
        Uses a chess.Board() instance to track the real game state.
        The board is reconstructed from move history on each engine 
        initialization (since the engine may be stateless between turns).
    """
```

### 2.1 `get_rules()`

Returns contents of `games/chess/rules.md`.

### 2.2 `initial_state(agents)`

```python
def initial_state(self, agents: list[dict]) -> dict:
    """
    Returns:
    {
        "current": {
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "board_visual": [
                "r n b q k b n r",
                "p p p p p p p p",
                ". . . . . . . .",
                ". . . . . . . .",
                ". . . . . . . .",
                ". . . . . . . .",
                "P P P P P P P P",
                "R N B Q K B N R"
            ],
            "colors": {
                agents[0]["agent_id"]: "white",
                agents[1]["agent_id"]: "black"
            },
            "move_number": 1,
            "side_to_move": "white",
            "in_check": false,
            "legal_moves_count": 20
        },
        "context": {
            "move_count": 0,
            "captured_pieces": { "white": [], "black": [] },
            "material_balance": 0,
            "phase": "opening",
            "key_events": []
        }
    }
    
    Notes:
        - Seat 0 always plays White (goes first).
        - board_visual: 8 strings representing rows from rank 8 (top) to rank 1 (bottom).
          Uppercase = White, lowercase = Black, . = empty.
          This is for agent readability. The FEN is the canonical state.
        - legal_moves_count: tells the agent how many options they have.
    """
```

### 2.3 `validate_move(move, agent_id, state)`

```python
def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
    """
    Checks:
        1. move has "type" field equal to "chess_move"
        2. move has "notation" field (string)
        3. The agent is the correct side to move
        4. Reconstruct board from FEN in state
        5. Parse notation as UCI (e.g., "e2e4", "e7e8q" for promotion)
        6. Check if the move is legal via python-chess
    
    Accepts UCI notation: source_square + destination_square [+ promotion_piece]
        Examples: "e2e4", "g1f3", "e7e8q"
    
    Also accepts standard algebraic notation (SAN) as fallback:
        Examples: "e4", "Nf3", "O-O", "Qxd7#"
        Try UCI first, then SAN.
    
    Returns:
        {"valid": True, "message": None}
        or
        {"valid": False, "message": "Illegal move: e2e5 is not a legal move. Legal moves: e2e3, e2e4, g1f3, ..."}
    
    On rejection, include up to 10 legal moves in the message to help the agent.
    """
```

### 2.4 `apply_move(move, agent_id, state)`

```python
def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
    """
    Apply the move using python-chess.
    
    Steps:
        1. Reconstruct board from FEN
        2. Parse and push the move
        3. Generate new state
    
    Returns updated game block:
    {
        "current": {
            "fen": "new FEN string",
            "board_visual": [updated visual],
            "colors": {same as before},
            "move_number": updated,
            "side_to_move": "white" or "black",
            "in_check": bool,
            "legal_moves_count": int,
            "last_move": {
                "from": "e2",
                "to": "e4",
                "piece": "P",
                "captured": null,
                "is_check": false,
                "is_castling": false,
                "promotion": null,
                "san": "e4"
            }
        },
        "context": {
            "move_count": N,
            "captured_pieces": {
                "white": ["p", "n"],
                "black": ["P"]
            },
            "material_balance": +3,
            "phase": "opening" | "middlegame" | "endgame",
            "key_events": [
                {"move": 5, "event": "castling", "agent": "claude-alpha", "detail": "kingside"},
                {"move": 12, "event": "capture", "agent": "claude-beta", "detail": "Bxf7+, won bishop for pawn"},
                {"move": 20, "event": "promotion", "agent": "claude-alpha", "detail": "e8=Q"}
            ]
        }
    }
    
    Context tracking rules:
        - captured_pieces: updated whenever a capture occurs
        - material_balance: standard piece values (P=1, N=3, B=3, R=5, Q=9)
          Positive = White advantage, negative = Black advantage.
        - phase: 
            "opening" if move_count <= 10
            "endgame" if total material (excluding kings) <= 26 
                (both queens gone, or queen + minor piece vs same)
            "middlegame" otherwise
          (Simplified heuristic. Good enough for context.)
        - key_events: append on castling, capture, promotion, check.
          Keep only last 20 events to prevent unbounded growth.
    """
```

### 2.5 `is_over(state)`

```python
def is_over(self, state: dict) -> bool:
    """
    Reconstruct board from FEN. Return True if:
        - Checkmate
        - Stalemate
        - Insufficient material
        - Fifty-move rule
        - Threefold repetition (if detectable from FEN alone — 
          may need move history for this. If not feasible, skip.)
    
    python-chess handles all of these via board.is_game_over()
    
    Note: For threefold repetition, we need the full move history,
    not just the FEN. Reconstruct from log if needed, or track
    internally. Simplest approach: store the list of FENs in context.
    
    Also end if max_turns reached (from match_config).
    """
```

### 2.6 `get_result(state)`

```python
def get_result(self, state: dict) -> dict:
    """
    Returns:
    {
        "outcome": "checkmate" | "stalemate" | "draw_insufficient" | 
                   "draw_fifty_moves" | "draw_repetition" | "draw_max_turns",
        "winner": agent_id or None,
        "scores": { 
            agent_id_white: 1.0 or 0.5 or 0.0,
            agent_id_black: 1.0 or 0.5 or 0.0
        },
        "summary": "claude-alpha (White) wins by checkmate in 34 moves"
    }
    
    Scoring: Win=1.0, Draw=0.5, Loss=0.0 (standard chess scoring)
    """
```

### 2.7 `summarize_move(move, agent_id, state)`

```python
def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
    """
    Use python-chess to get the SAN notation.
    
    Returns: "e4" or "Nf3" or "O-O" or "Qxd7#"
    
    If a capture: "Bxf7+ (won bishop for pawn)"
    If checkmate: "Qh7# — checkmate"
    """
```

### 2.8 `get_evaluation_schema()`

```python
def get_evaluation_schema(self) -> dict:
    """
    Returns:
    {
        "description": "Evaluate chess performance across these dimensions",
        "fields": {
            "opening_play": "1-5: Quality of opening choices. Did they follow principles (center control, development, king safety)?",
            "tactical_accuracy": "1-5: Did they spot captures, forks, pins, skewers? Did they miss any?",
            "strategic_thinking": "1-5: Long-term planning, pawn structure, piece coordination.",
            "endgame_play": "1-5: If applicable. King activation, pawn promotion attempts.",
            "mistakes": "List specific moves that were errors, with brief explanation.",
            "best_move": "The single best move in the game, with explanation.",
            "overall_comment": "Free text assessment of play style and quality."
        }
    }
    """
```

---

## 3. Rules File: `games/chess/rules.md`

This is what the AI agent reads. Must be clear, complete, and formatted for LLM parsing.

```markdown
# Chess — LxM Game Rules

## Overview

Standard chess. Two players, White and Black. White moves first.
Capture the opponent's king (checkmate) to win.

## Your Color

Check `state.json` → `game.current.colors` to see your color.
Seat 0 plays White. Seat 1 plays Black.

## Board Representation

The board is in `state.json` → `game.current.board_visual`:
- 8 rows, from rank 8 (top/Black's side) to rank 1 (bottom/White's side)
- Uppercase letters = White pieces (P, N, B, R, Q, K)
- Lowercase letters = Black pieces (p, n, b, r, q, k)
- Dots (.) = empty squares
- Columns are a–h from left to right

The canonical state is the FEN string in `game.current.fen`.

## Move Format

Your `move` object must be:

```json
{
  "type": "chess_move",
  "notation": "e2e4"
}
```

**Notation:** UCI format preferred.
- Normal move: source + destination, e.g., `"e2e4"`, `"g1f3"`
- Pawn promotion: add piece letter, e.g., `"e7e8q"` (promote to queen)
- Castling: king's move, e.g., `"e1g1"` (White kingside), `"e1c1"` (White queenside)

Standard algebraic notation (SAN) is also accepted as fallback:
- `"e4"`, `"Nf3"`, `"O-O"`, `"Bxf7+"`, `"e8=Q"`

**Use UCI for reliability.** It's unambiguous and easier to validate.

## Game State Context

`state.json` → `game.current` gives you:
- `fen`: Full board state in FEN notation
- `board_visual`: Human-readable board display
- `side_to_move`: "white" or "black"
- `in_check`: Whether the current side is in check
- `legal_moves_count`: How many legal moves you have
- `last_move`: Details of the previous move (from, to, piece, captured, check, castling, promotion, SAN)

`state.json` → `game.context` gives you:
- `captured_pieces`: What each side has captured
- `material_balance`: Positive = White advantage (P=1, N=3, B=3, R=5, Q=9)
- `phase`: "opening", "middlegame", or "endgame"
- `key_events`: Notable events (castles, captures, promotions, checks)

## Winning Conditions

- **Checkmate**: Your opponent's king is in check with no legal escape. You win.
- **Stalemate**: Your opponent has no legal moves but is not in check. Draw.
- **Insufficient material**: Neither side can checkmate (e.g., K vs K). Draw.
- **Fifty-move rule**: 50 moves with no capture or pawn move. Draw.
- **Max turns**: If the match reaches the turn limit, the position is evaluated by material. Higher material wins; equal material = draw.

## Evaluation

After the game, evaluate on these axes:
- **opening_play** (1-5): Opening quality — center control, development, king safety
- **tactical_accuracy** (1-5): Spotting and executing tactics (forks, pins, skewers)
- **strategic_thinking** (1-5): Long-term planning, pawn structure, piece coordination
- **endgame_play** (1-5): King activation, pawn promotion, technique (if applicable)
- **mistakes**: List specific erroneous moves with brief explanations
- **best_move**: Single best move of the game, with explanation
- **overall_comment**: Free text assessment
```

---

## 4. Match Configuration

Default chess match_config additions:

```json
{
  "game": {
    "name": "chess",
    "version": "1.0"
  },
  "time_model": {
    "type": "turn_based",
    "turn_order": "sequential",
    "max_turns": 200,
    "timeout_seconds": 120,
    "timeout_action": "forfeit",
    "max_retries": 2
  },
  "history": {
    "recent_moves_count": 10
  }
}
```

Notes:
- `max_turns: 200` — 100 full moves per side. Most games end well before this.
- `timeout_action: "forfeit"` — chess has no meaningful "pass". If you can't move, forfeit.
- `recent_moves_count: 10` — more history than tic-tac-toe, because chess has deeper patterns.

### CLI Usage

```bash
python scripts/run_match.py --game chess --agents claude-alpha claude-beta
python scripts/run_match.py --game chess --agents claude-alpha claude-beta --model opus --timeout 180
```

---

## 5. Viewer: Chess Renderer

File: `viewer/static/renderers/chess.js`

### 5.1 Board Drawing

- 8×8 grid with alternating light/dark square colors
- Light squares: #f0d9b5 (warm beige)
- Dark squares: #b58863 (warm brown)
- These are standard chess.com/lichess-inspired colors
- File labels (a–h) at bottom, rank labels (1–8) on left side

### 5.2 Pieces

Use Unicode chess characters, rendered at large font size centered in squares:

```
White: ♔ ♕ ♖ ♗ ♘ ♙
Black: ♚ ♛ ♜ ♝ ♞ ♟
```

Character mapping:
```javascript
const PIECE_CHARS = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
};
```

Render with slight text shadow for visibility on both light and dark squares.

### 5.3 State Parsing

The renderer parses the `board_visual` array from state:

```javascript
initialState(matchConfig) {
    return {
        board: [
            ['r','n','b','q','k','b','n','r'],
            ['p','p','p','p','p','p','p','p'],
            ['.','.','.','.','.','.','.','.',],
            ['.','.','.','.','.','.','.','.',],
            ['.','.','.','.','.','.','.','.',],
            ['.','.','.','.','.','.','.','.',],
            ['P','P','P','P','P','P','P','P'],
            ['R','N','B','Q','K','B','N','R']
        ],
        colors: matchConfig.agents.reduce((acc, a) => {
            acc[a.agent_id] = a.seat === 0 ? 'white' : 'black';
            return acc;
        }, {})
    };
}
```

### 5.4 applyMove

```javascript
applyMove(state, logEntry) {
    /**
     * Parse the move from logEntry.envelope.move.
     * 
     * Use game.current.last_move from the state if available
     * (it has from/to/piece/captured info).
     * 
     * Alternatively, parse UCI notation:
     *   "e2e4" → from=[6,4], to=[4,4] (board coords)
     * 
     * Handle special moves:
     *   - Castling: also move the rook
     *   - En passant: remove the captured pawn
     *   - Promotion: replace pawn with promoted piece
     * 
     * Simplest approach: just use board_visual from the state
     * that the engine produces, rather than trying to replay
     * chess logic in JavaScript. The engine already computed
     * the board — just use it.
     * 
     * Recommended: store the engine's board_visual directly
     * as the renderer state. applyMove becomes:
     */
    
    // Parse board_visual from the log entry's resulting state
    // This requires the orchestrator to include post-move state in log
    // OR the renderer reconstructs from FEN
    
    // Simplest: parse FEN to board array
    const fen = logEntry.envelope.move._resulting_fen; // see Section 5.6
    return { ...state, board: fenToBoard(fen) };
}
```

### 5.5 Highlighting

- **Last move:** Highlight source and destination squares with a semi-transparent overlay (e.g., yellow-green with 40% opacity)
- **Check:** If `in_check` is true, highlight the checked king's square in red
- **Captured piece:** Brief flash animation on the captured square

### 5.6 Log Entry Enhancement for Viewer

The viewer needs to reconstruct board state from log entries. Two approaches:

**Approach A: Store FEN in each log entry.**
Add the resulting FEN to each log entry in log.json. The orchestrator already has it after `apply_move`. This is the simplest for the viewer.

Enhancement to orchestrator log entry:
```json
{
    "turn": 5,
    "agent_id": "claude-alpha",
    "envelope": { ... },
    "validation": { ... },
    "post_move_state": {
        "fen": "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2",
        "board_visual": ["..."],
        "last_move": { "from": "g8", "to": "f6", "piece": "n", "san": "Nf6" }
    },
    "timestamp": "..."
}
```

**Approach B: Replay moves in JavaScript.**
Import a JS chess library (e.g., chess.js) and replay all moves. More complex, adds a dependency.

**Use Approach A.** It's simpler and works for all games — just include post-move state in the log. This is a small change to the orchestrator and benefits every game, not just chess.

**Orchestrator change required:**
In `append_log`, include `post_move_state` with the game-relevant visual state. The exact fields are game-specific — the engine provides them. For tic-tac-toe this would be the board array; for chess, FEN + board_visual + last_move.

This is a **one-time orchestrator enhancement** that every future game benefits from.

### 5.7 Move Summary

```javascript
formatMoveSummary(logEntry) {
    // Use SAN from the move result if available
    const lastMove = logEntry.post_move_state?.last_move;
    if (lastMove?.san) {
        let text = lastMove.san;
        if (lastMove.captured) text += ` (captured ${lastMove.captured})`;
        return text;
    }
    // Fallback: raw notation
    return logEntry.envelope.move.notation;
}
```

### 5.8 Result Display

- **Checkmate:** Highlight the mated king's square in red, display "Checkmate" overlay
- **Stalemate/Draw:** Gray overlay with "Draw — {reason}"
- **Winning line:** Not applicable for chess (unlike tic-tac-toe)

### 5.9 Side Panel Additions

For chess, the viewer side panel should also show:
- **Captured pieces** for each side (from `game.context.captured_pieces`)
- **Material balance** bar (visual, from `game.context.material_balance`)
- **Game phase** indicator (Opening / Middlegame / Endgame)

---

## 6. Video Export: Chess Frame Renderer

File: `viewer/exporters/chess.py`

Python renderer for GIF/MP4 export. Mirrors the JS renderer logic.

### Board Drawing (Pillow)

```python
def render_frame(self, state, turn, agents, last_move) -> PIL.Image:
    """
    Render an 800x600 image:
    
    Layout:
    - Board: 480x480, centered left
    - Right panel: agent names, captured pieces, material balance, move text
    - Top: "Chess — Turn {n}/{max}" + agent labels
    - Bottom: "LxM — Ludus Ex Machina"
    
    Board rendering:
    - Draw 8x8 grid with alternating colors
    - Draw piece characters using a Unicode-capable font
      (DejaVu Sans or Noto Sans, should be pre-installed on most systems)
    - Highlight last move squares
    - Highlight check
    
    Right panel:
    - Agent names with colors (White/Black indicators)
    - Captured pieces displayed as Unicode characters
    - Material balance: simple +N or -N display
    - Last move in SAN notation
    """
```

---

## 7. Implementation Order

```
Step 1: games/chess/engine.py + rules.md
        → ChessGame class wrapping python-chess
        → Unit tests for all engine methods

Step 2: Orchestrator enhancement — post_move_state in log entries
        → Small change to append_log in orchestrator.py
        → Update tic-tac-toe to also include post_move_state
        → Verify existing tic-tac-toe tests still pass

Step 3: viewer/static/renderers/chess.js
        → Chess board rendering in the web viewer
        → Test with a manually created log.json if needed

Step 4: viewer/exporters/chess.py
        → Frame renderer for GIF/MP4 export

Step 5: Integration test
        → Two Claude Code instances play chess
        → Watch in viewer (live mode)
        → Export replay as GIF

Step 6: Verify with multiple models (preparation for cross-model)
        → Test with --model haiku, --model sonnet, --model opus
        → Confirm all models can read rules.md and submit valid moves
```

### Unit Tests for Chess Engine

```
test_initial_state           — Correct FEN, visual board, colors
test_valid_move_uci          — "e2e4" accepted
test_valid_move_san          — "Nf3" accepted as fallback
test_invalid_move_notation   — "xyz" rejected with message
test_invalid_move_illegal    — "e1e3" (king can't jump) rejected, legal moves listed
test_invalid_move_wrong_side — Black tries to move on White's turn
test_apply_move_basic        — Board updates correctly after e2e4
test_apply_move_capture      — Captured piece tracked in context
test_apply_move_castling     — King and rook both move
test_apply_move_promotion    — Pawn replaced with promoted piece
test_apply_move_en_passant   — Captured pawn removed correctly
test_is_over_checkmate       — Fool's mate detected (f3, e5, g4, Qh4#)
test_is_over_stalemate       — Stalemate position detected
test_is_over_insufficient    — K vs K detected
test_get_result_checkmate    — Winner, scores, summary correct
test_get_result_draw         — Draw result, both get 0.5
test_context_material        — Material balance updates on captures
test_context_phase           — Phase transitions (opening → middlegame → endgame)
test_context_key_events      — Castling, captures logged as events
test_summarize_move          — SAN notation returned
```

**Success criteria for Step 5:**
Two Claude Code instances complete a full chess game. All moves are legal (no retries needed for illegal moves). The viewer shows the game with proper piece rendering, move highlighting, and captured pieces. GIF export produces a watchable replay.

---

## 8. Known Considerations

**Context window usage:** Chess rules.md + PROTOCOL.md + state.json is more content than tic-tac-toe. With `recent_moves_count: 10`, the agent's context load is still manageable. Monitor if agents start struggling with long games (50+ moves).

**Model chess ability:** Different models have different chess skill levels. Haiku will likely play worse than Opus. This is expected and is valuable data. Don't try to equalize — let the Core difference show.

**Move notation reliability:** LLMs sometimes produce ambiguous or creative notation. The SAN fallback (after UCI attempt) helps, but we may see retry rates vary by model. **Track retry rates per model** — this is a Compliance axis measurement.

**Long games:** Chess games can theoretically go very long. The `max_turns: 200` cap prevents infinite games. If a game hits this limit, evaluate by material (higher material wins). This is a pragmatic decision, not perfect chess rules.

**Threefold repetition:** Detecting this requires tracking all positions, not just the current FEN. Store FEN history in context (e.g., `"fen_history": ["fen1", "fen2", ...]`). python-chess can detect this if given the full move sequence — reconstruct from log.json at each turn.

---

*LxM Chess Game Spec v0.1*
*"The classic benchmark, now in the arena."*
