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
