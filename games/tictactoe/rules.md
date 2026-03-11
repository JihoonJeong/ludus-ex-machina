# Tic-Tac-Toe — LxM Game Rules

## Overview

Two players take turns placing marks (X or O) on a 3x3 grid.
First to get three in a row (horizontal, vertical, or diagonal) wins.
If the board fills up with no winner, the game is a draw.

## Your Mark

Check `state.json` → `game.current.marks` to see which mark is yours.
Seat 0 plays X (goes first). Seat 1 plays O.

## Board Representation

The board is a 3x3 array in `state.json` → `game.current.board`:

```
board[0][0] | board[0][1] | board[0][2]
-----------+-----------+-----------
board[1][0] | board[1][1] | board[1][2]
-----------+-----------+-----------
board[2][0] | board[2][1] | board[2][2]
```

Each cell is `null` (empty), `"X"`, or `"O"`.

## Move Format

Your `move` object must be:

```json
{
  "type": "place",
  "position": [row, col]
}
```

- `row`: 0, 1, or 2 (top to bottom)
- `col`: 0, 1, or 2 (left to right)
- The target cell must be empty (`null`)

Example: To place your mark in the center:
```json
{ "type": "place", "position": [1, 1] }
```

## Winning

Three of your marks in a row:
- Any row: [r,0], [r,1], [r,2]
- Any column: [0,c], [1,c], [2,c]
- Diagonals: [0,0],[1,1],[2,2] or [0,2],[1,1],[2,0]

## Evaluation

After the game, you will be asked to evaluate performance.

Rate on these axes:
- **strategy_rating** (1-5): How strategic were the moves?
- **mistakes**: List any obvious mistakes (missed wins, missed blocks)
- **overall_comment**: Free text assessment
