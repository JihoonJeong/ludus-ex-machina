# LxM Implementation Spec v0.1

## Purpose

This document is a complete implementation specification for Ludus Ex Machina (LxM). Hand this to Claude Code and say "build this."

**Target:** A working system where two Claude Code CLI instances play tic-tac-toe against each other via the LxM protocol.

**Prerequisites:** Python 3.11+, Claude Code CLI installed and authenticated.

**Reference:** `PROTOCOL.md v0.2` defines the agent-facing protocol. This spec defines the builder-facing implementation.

---

## 1. Project Structure

```
ludus-ex-machina/
├── PROTOCOL.md                 ← Universal protocol (agents read this)
├── lxm/                        ← Core library
│   ├── __init__.py
│   ├── engine.py               ← Abstract game engine interface
│   ├── orchestrator.py         ← Match orchestrator
│   ├── envelope.py             ← Envelope parsing and validation
│   ├── state.py                ← State management (lxm block)
│   └── adapters/
│       ├── __init__.py
│       └── claude_code.py      ← Claude Code CLI adapter
├── games/                      ← Game implementations
│   └── tictactoe/
│       ├── engine.py           ← TicTacToe(LxMGame)
│       ├── rules.md            ← Agent-readable rules
│       └── README.md
├── agents/                     ← Shell storage (not execution directory)
│   ├── claude-alpha/
│   │   └── shell.md            ← Hard Shell instructions
│   └── claude-beta/
│       └── shell.md
├── matches/                    ← Match folders (created at runtime)
├── scripts/
│   └── run_match.py            ← CLI entry point
├── tests/
│   └── test_tictactoe.py       ← Unit tests (no CLI agents needed)
└── README.md
```

---

## 2. Game Engine Interface

File: `lxm/engine.py`

```python
from abc import ABC, abstractmethod
from typing import Any

class LxMGame(ABC):
    """
    Abstract base class for all LxM games.
    Every game must implement these methods.
    The orchestrator calls ONLY these methods — nothing else.
    """

    @abstractmethod
    def get_rules(self) -> str:
        """
        Return the contents of rules.md for this game.
        Called once at match setup to copy rules.md into the match folder.
        """
        pass

    @abstractmethod
    def initial_state(self, agents: list[dict]) -> dict:
        """
        Generate the initial game state.

        Args:
            agents: List of agent configs from match_config.
                    Each has: agent_id, display_name, seat

        Returns:
            The initial `game` block for state.json:
            {
                "current": { ... },
                "context": { ... }
            }

        Notes:
            - The `lxm` block is managed by the orchestrator, not the engine.
            - The engine only produces the `game` block.
        """
        pass

    @abstractmethod
    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        """
        Validate a move payload (the `move` field from the envelope).

        Args:
            move: The `move` object from the agent's envelope.
            agent_id: Who submitted it.
            state: The full state.json content (both lxm and game blocks).

        Returns:
            {
                "valid": bool,
                "message": str or None  # Rejection reason if invalid
            }

        Notes:
            - Envelope validation (protocol, match_id, agent_id, turn) is
              handled by the orchestrator. This method only validates
              the game-specific move payload.
            - Return a clear message on rejection — it will be shown to the
              agent in the retry prompt.
        """
        pass

    @abstractmethod
    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        """
        Apply a validated move and return the updated game state.

        Args:
            move: The validated `move` object.
            agent_id: Who submitted it.
            state: The full state.json content.

        Returns:
            Updated `game` block:
            {
                "current": { ... },  # Updated snapshot
                "context": { ... }   # Updated accumulated facts
            }

        Notes:
            - Only called after validate_move returns valid=True.
            - Must update both `current` and `context`.
            - The orchestrator handles updating the `lxm` block.
        """
        pass

    @abstractmethod
    def is_over(self, state: dict) -> bool:
        """
        Check if the game has ended.

        Args:
            state: The full state.json content.

        Returns:
            True if the game is over (win, draw, or other terminal condition).
        """
        pass

    @abstractmethod
    def get_result(self, state: dict) -> dict:
        """
        Get the final result of a completed game.

        Args:
            state: The full state.json content.

        Returns:
            {
                "outcome": str,         # "win", "draw", "timeout", etc.
                "winner": str or None,   # agent_id of winner, None if draw
                "scores": {              # agent_id -> score (game-specific)
                    "claude-alpha": 1,
                    "claude-beta": 0
                },
                "summary": str           # One-line human-readable summary
            }

        Notes:
            - Only called after is_over returns True.
        """
        pass

    @abstractmethod
    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        """
        Create a short text summary of a move for recent_moves.

        Args:
            move: The move object.
            agent_id: Who made it.
            state: State BEFORE the move was applied.

        Returns:
            A short string summary, e.g. "Placed X at center (1,1)"

        Notes:
            - Used by the orchestrator to populate lxm.recent_moves.
            - Keep it concise — one line.
        """
        pass

    @abstractmethod
    def get_evaluation_schema(self) -> dict:
        """
        Return the evaluation schema for post-game assessment.

        Returns:
            A JSON-serializable dict describing what evaluations should contain.
            Included in rules.md "Evaluation" section.

        Notes:
            - This defines what agents should write in their evaluation.evaluation field.
            - Can be as simple or complex as the game needs.
        """
        pass
```

---

## 3. Envelope Module

File: `lxm/envelope.py`

Handles parsing and validating the universal envelope.

### 3.1 Parsing

The orchestrator needs to extract a move envelope from two sources:

**From file:**
```python
def parse_from_file(filepath: str) -> dict | None:
    """
    Read and parse a JSON file as an envelope.
    Returns the parsed dict or None if file doesn't exist or isn't valid JSON.
    """
```

**From stdout:**
```python
def parse_from_stdout(output: str) -> dict | None:
    """
    Extract the first valid JSON object containing a "protocol" field
    from a string of stdout output.

    The output may contain thinking text, commentary, markdown fences,
    or other noise. This function must find the JSON envelope within it.

    Strategy:
    1. Try to find JSON between ```json ... ``` fences first.
    2. Then try to find any { ... } block that parses as JSON and contains "protocol".
    3. Return None if nothing found.
    """
```

### 3.2 Validation

```python
def validate_envelope(envelope: dict, match_config: dict) -> dict:
    """
    Validate the universal envelope fields (NOT the game-specific move payload).

    Checks:
    - "protocol" matches match_config.protocol_version
    - "match_id" matches match_config.match_id
    - "agent_id" matches current active_agent
    - "turn" matches current turn number
    - "move" field exists and is a dict

    Returns:
        {
            "valid": bool,
            "message": str or None  # Reason if invalid
        }
    """
```

---

## 4. State Management

File: `lxm/state.py`

Manages the `lxm` block of state.json. The `game` block is managed by the game engine.

```python
class LxMState:
    """
    Manages the lxm block in state.json and coordinates with the game engine.
    """

    def __init__(self, match_config: dict):
        """
        Initialize from match_config.

        Sets up:
        - turn = 0
        - phase = "READY"
        - agents list from match_config
        - recent_moves = []
        - recent_moves_count from match_config.history.recent_moves_count (default 5)
        """

    def start(self, game_state: dict) -> dict:
        """
        Transition to first turn.
        Returns complete state.json content (lxm + game blocks).
        """

    def get_active_agent(self) -> str:
        """Return the agent_id whose turn it is."""

    def record_move(self, agent_id: str, move: dict, summary: str) -> None:
        """
        Record a move in recent_moves (FIFO, capped at recent_moves_count).
        Stores the original move payload and summary.
        """

    def advance_turn(self, game_state: dict) -> dict:
        """
        Move to the next turn. Update active_agent based on turn_order.
        Returns updated complete state.json content.
        """

    def to_dict(self, game_state: dict) -> dict:
        """
        Return the complete state.json structure:
        {
            "lxm": { ... },
            "game": game_state
        }
        """
```

---

## 5. Agent Adapter

File: `lxm/adapters/claude_code.py`

The adapter translates between the orchestrator and a specific CLI agent type.

```python
class ClaudeCodeAdapter:
    """
    Adapter for calling Claude Code CLI as a game agent.
    """

    def __init__(self, agent_config: dict, shell_path: str | None = None):
        """
        Args:
            agent_config: From match_config.agents[i].
                          Has: agent_id, display_name, seat
                          May also have: model (default "sonnet")
            shell_path: Path to the Hard Shell file (e.g. agents/claude-alpha/shell.md).
                        If None, no Hard Shell is injected.
        """

    def invoke(self, match_dir: str, prompt: str) -> dict:
        """
        Invoke Claude Code CLI to make a move.

        Args:
            match_dir: Absolute path to the match folder (working directory).
            prompt: The invocation prompt (from PROTOCOL.md Section 4).

        Implementation:
            1. Build the command:
               claude -p --model {model} --output-format json "{prompt}"

               If shell_path is provided, prepend shell content to the prompt
               as a system-level instruction block:

               [HARD SHELL - Your strategic identity]
               {shell content}
               [END HARD SHELL]

               {invocation prompt}

            2. Execute with subprocess:
               - cwd = match_dir
               - timeout = match_config.time_model.timeout_seconds
               - capture stdout and stderr

            3. Return:
               {
                   "stdout": str,
                   "stderr": str,
                   "exit_code": int,
                   "timed_out": bool
               }

        Notes:
            - Claude Code's --output-format json returns structured output.
              The actual text response is in the "result" field.
              Parse accordingly.
            - If the invocation times out, return timed_out=True.
            - Claude Code may need --dangerously-skip-permissions for
              file write access. Confirm during testing.
              The human operator grants this permission at match start.
        """
```

### 5.1 Invocation Prompt Templates

The adapter uses these templates (matching PROTOCOL.md Section 4):

**Normal turn:**
```
[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}
It is your turn.
1. Read PROTOCOL.md for universal rules.
2. Read rules.md for game-specific rules.
3. Read state.json for current situation.
4. Submit your move by writing to: moves/turn_{turn}_{agent_id}.json
```

**Retry:**
```
[LxM RETRY] Match: {match_id} | Agent: {agent_id} | Turn: {turn}
Attempt: {n} of {max_attempts}
Reason: {rejection_reason}
Submit a corrected move to: moves/turn_{turn}_{agent_id}.json
```

**Evaluation:**
```
[LxM EVAL] Match: {match_id} | Agent: {agent_id}
The match is over. Perform your evaluation.
1. Read rules.md Section "Evaluation" for evaluation criteria.
2. Read log.json for complete match history.
3. Write self-evaluation to: evals/self_{agent_id}.json
4. Write cross-evaluation for each opponent to: evals/cross_{agent_id}_on_{target_id}.json
```

---

## 6. Orchestrator

File: `lxm/orchestrator.py`

The main match runner.

```python
class Orchestrator:
    """
    Manages a complete match from setup to evaluation.
    """

    def __init__(self, game: LxMGame, match_config: dict, adapters: dict[str, ClaudeCodeAdapter]):
        """
        Args:
            game: An instance of a LxMGame implementation.
            match_config: The complete match configuration dict.
            adapters: Map of agent_id -> adapter instance.
        """
```

### 6.1 Match Setup

```python
def setup_match(self) -> str:
    """
    Create the match folder and initialize all files.

    Steps:
        1. Create matches/{match_id}/ directory
        2. Create subdirectories: moves/, evals/
        3. Copy PROTOCOL.md into match folder
        4. Write rules.md (from game.get_rules())
        5. Write match_config.json
        6. Generate initial game state (game.initial_state())
        7. Write state.json (lxm block + game block)
        8. Write empty log.json ([])
        9. Set phase to "READY"

    Returns:
        Absolute path to the match folder.
    """
```

### 6.2 Main Loop

```python
def run(self) -> dict:
    """
    Run the complete match. Returns the final result.

    Main loop:
        1. Determine active agent (from state)
        2. Invoke agent via adapter
        3. Collect move (file first, then stdout)
        4. Validate envelope (envelope.validate_envelope)
        5. Validate payload (game.validate_move)
        6. If invalid: retry up to max_retries, then apply timeout_action
        7. If valid: apply move (game.apply_move)
        8. Generate move summary (game.summarize_move)
        9. Update state.json (lxm block + new game state)
        10. Append to log.json
        11. Check game over (game.is_over)
        12. If over: break. If not: advance turn, go to 1.
        13. Write result.json (game.get_result)
        14. Run post-game evaluation
        15. Return result

    Logging:
        - Print turn-by-turn progress to console
        - Format: [Turn {n}] {agent_id}: {move_summary}
    """
```

### 6.3 Move Collection

```python
def collect_move(self, match_dir: str, agent_id: str, turn: int, invoke_result: dict) -> dict | None:
    """
    Attempt to collect a valid envelope from the agent's output.

    Resolution order:
        1. Check for file: moves/turn_{turn}_{agent_id}.json
        2. If not found: parse stdout from invoke_result

    Returns:
        Parsed envelope dict, or None if nothing found.

    Notes:
        - Delete the move file after reading (prevents stale files from
          being picked up on retry).
    """
```

### 6.4 Retry Logic

```python
def handle_invalid_move(self, match_dir: str, agent_id: str, turn: int,
                         reason: str, attempt: int, max_attempts: int) -> dict | None:
    """
    Re-invoke agent with retry prompt.

    Args:
        reason: Why the previous attempt was rejected.
        attempt: Current attempt number (starting from 2).
        max_attempts: Total allowed (1 + max_retries from config).

    Returns:
        Valid envelope dict, or None if all retries exhausted.
    """
```

### 6.5 Timeout Handling

```python
def handle_timeout(self, agent_id: str, state: dict) -> dict:
    """
    Apply timeout_action from match_config.

    "no_op": Return a pass move: {"type": "pass"}
             Log it as a timeout pass.
    "forfeit": End the game. The other agent wins.
    "random": Not implemented for v0.1. Treat as no_op.
    """
```

### 6.6 Post-Game Evaluation

```python
def run_evaluation(self, match_dir: str) -> None:
    """
    Invoke each agent for post-game evaluation.

    For each agent:
        1. Invoke with evaluation prompt
        2. Collect self-eval from evals/self_{agent_id}.json
        3. Collect cross-evals from evals/cross_{agent_id}_on_{target}.json
        4. No validation — evaluations are free-form per rules.md

    Notes:
        - Evaluation is best-effort. If an agent fails to produce evaluations,
          log the failure but don't crash.
        - Evaluations are bonus data, not critical path.
    """
```

### 6.7 Log Management

```python
def append_log(self, match_dir: str, entry: dict) -> None:
    """
    Append a log entry to log.json.

    Entry format:
    {
        "turn": int,
        "agent_id": str,
        "envelope": dict,          # The full submitted envelope
        "validation": {
            "envelope_valid": bool,
            "payload_valid": bool,
            "engine_message": str or None
        },
        "result": "accepted" | "rejected" | "timeout",
        "attempt": int,            # Which attempt this was (1-based)
        "timestamp": str           # ISO 8601 UTC
    }
    """
```

---

## 7. Tic-Tac-Toe Game Engine

File: `games/tictactoe/engine.py`

The simplest possible game to validate the entire pipeline.

### 7.1 Game Rules

3x3 grid. Two players: X (seat 0) and O (seat 1). Alternate turns placing marks. First to get 3 in a row (horizontal, vertical, diagonal) wins. If board fills with no winner, it's a draw.

### 7.2 Move Payload Schema

```json
{
  "type": "place",
  "position": [row, col]   // 0-indexed, e.g. [0, 0] = top-left
}
```

### 7.3 Implementation

```python
class TicTacToe(LxMGame):

    def __init__(self):
        self._rules = open(Path(__file__).parent / "rules.md").read()

    def get_rules(self) -> str:
        return self._rules

    def initial_state(self, agents: list[dict]) -> dict:
        """
        Returns:
        {
            "current": {
                "board": [[null, null, null],
                          [null, null, null],
                          [null, null, null]],
                "marks": {
                    agents[0]["agent_id"]: "X",
                    agents[1]["agent_id"]: "O"
                }
            },
            "context": {
                "move_count": 0,
                "moves_history": []
            }
        }
        """

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        """
        Checks:
        - move["type"] == "place"
        - move["position"] is a list of two ints
        - position is within [0-2, 0-2]
        - the target cell is empty (null)
        """

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        """
        Places the agent's mark on the board.
        Updates context.move_count and context.moves_history.

        context.moves_history is a list of:
        {"turn": N, "agent_id": str, "position": [r, c], "mark": "X"|"O"}
        """

    def is_over(self, state: dict) -> bool:
        """
        True if:
        - Three in a row exists (win), OR
        - Board is full (draw)
        """

    def get_result(self, state: dict) -> dict:
        """
        Returns:
        {
            "outcome": "win" or "draw",
            "winner": agent_id or None,
            "scores": { agent_id: 1/0 for each agent },
            "summary": "claude-alpha (X) wins by row 0" or "Draw — board full"
        }
        """

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        """
        Returns: "Placed X at (1, 2)" or similar.
        """

    def get_evaluation_schema(self) -> dict:
        """
        Returns:
        {
            "description": "Rate each player's tic-tac-toe performance",
            "fields": {
                "strategy_rating": "1-5 scale, how strategic were the moves?",
                "mistakes": "List any obvious mistakes (missed wins, missed blocks)",
                "overall_comment": "Free text assessment"
            }
        }
        """
```

### 7.4 rules.md

File: `games/tictactoe/rules.md`

This is what the agent reads. Write it for an AI reader:

```markdown
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
```

---

## 8. CLI Entry Point

File: `scripts/run_match.py`

```python
"""
Usage:
    python scripts/run_match.py --game tictactoe --agents claude-alpha claude-beta

    Optional:
    --match-id custom_name        (default: auto-generated timestamp)
    --model sonnet                (default: sonnet, applied to all Claude agents)
    --timeout 120                 (default: 120 seconds)
    --max-retries 2               (default: 2)
    --recent-moves 5              (default: 5)
    --skip-eval                   (skip post-game evaluation)
"""
```

**Implementation steps:**

1. Parse arguments
2. Load game engine: `games/{game}/engine.py`
3. Load agent shells: `agents/{agent_id}/shell.md` (if exists)
4. Build match_config:

```python
match_config = {
    "protocol_version": "lxm-v0.2",
    "match_id": match_id,
    "game": {
        "name": args.game,
        "version": "1.0"
    },
    "time_model": {
        "type": "turn_based",
        "turn_order": "sequential",
        "max_turns": 9,          # game-specific, engine can override
        "timeout_seconds": args.timeout,
        "timeout_action": "no_op",
        "max_retries": args.max_retries
    },
    "agents": [
        {"agent_id": agent_ids[0], "display_name": ..., "seat": 0},
        {"agent_id": agent_ids[1], "display_name": ..., "seat": 1}
    ],
    "history": {
        "recent_moves_count": args.recent_moves
    }
}
```

5. Create adapters for each agent
6. Create orchestrator
7. Run: `orchestrator.setup_match()` then `orchestrator.run()`
8. Print result summary

---

## 9. Unit Tests (No CLI Required)

File: `tests/test_tictactoe.py`

Test the game engine and orchestrator logic without invoking any CLI agents. Use mock adapters.

### Test Cases

**Game engine:**
- `test_initial_state`: Board is empty, marks assigned correctly
- `test_valid_move`: Placing on empty cell succeeds
- `test_invalid_move_occupied`: Placing on occupied cell fails with message
- `test_invalid_move_out_of_range`: Position [3, 0] fails
- `test_invalid_move_format`: Missing "type" or "position" field fails
- `test_win_row`: Three in a row detected
- `test_win_column`: Three in a column detected
- `test_win_diagonal`: Diagonal win detected
- `test_draw`: Full board, no winner
- `test_get_result_win`: Correct winner and scores
- `test_get_result_draw`: Outcome "draw", no winner

**Envelope:**
- `test_parse_from_file`: Valid JSON file parsed
- `test_parse_from_stdout_clean`: Clean JSON in stdout
- `test_parse_from_stdout_noisy`: JSON mixed with thinking text and markdown
- `test_validate_envelope_valid`: All fields correct
- `test_validate_envelope_wrong_turn`: Turn number mismatch rejected

**State:**
- `test_initial_lxm_state`: Turn 0, phase READY
- `test_advance_turn`: Active agent rotates correctly
- `test_recent_moves_fifo`: Oldest move dropped when exceeding count

**Orchestrator (with mock adapter):**
- `test_full_game_mock`: Simulate a complete game with predetermined moves
- `test_retry_on_invalid`: Mock adapter returns bad move, then good move
- `test_timeout`: Mock adapter times out, no_op applied

### Mock Adapter

```python
class MockAdapter:
    """
    Returns predetermined moves for testing.

    Usage:
        adapter = MockAdapter(moves=[
            {"type": "place", "position": [1, 1]},
            {"type": "place", "position": [0, 0]},
        ])
    """

    def __init__(self, moves: list[dict]):
        self._moves = iter(moves)

    def invoke(self, match_dir: str, prompt: str) -> dict:
        move = next(self._moves)
        envelope = {
            "protocol": "lxm-v0.2",
            # ... fill from prompt parsing
            "move": move
        }
        return {
            "stdout": json.dumps(envelope),
            "stderr": "",
            "exit_code": 0,
            "timed_out": False
        }
```

---

## 10. Expected Match Flow (End-to-End)

Here's exactly what happens when you run:
```bash
python scripts/run_match.py --game tictactoe --agents claude-alpha claude-beta
```

### Setup Phase

```
1. Create matches/match_20250315_143022/
2. Create subdirs: moves/, evals/
3. Copy PROTOCOL.md → match folder
4. Write rules.md (from TicTacToe.get_rules())
5. Write match_config.json
6. Generate initial state (empty board)
7. Write state.json
8. Write log.json (empty array)
```

### Turn 1 (claude-alpha, X)

```
1. Read state → active_agent = claude-alpha
2. Build prompt:
   "[LxM] Match: match_20250315_143022 | Agent: claude-alpha | Turn: 1
    It is your turn.
    1. Read PROTOCOL.md for universal rules.
    2. Read rules.md for game-specific rules.
    3. Read state.json for current situation.
    4. Submit your move by writing to: moves/turn_1_claude-alpha.json"
3. Prepend Hard Shell (if agents/claude-alpha/shell.md exists)
4. Execute:
   cd matches/match_20250315_143022 && claude -p --model sonnet "{prompt}"
5. Claude Code:
   - Reads PROTOCOL.md (learns the system)
   - Reads rules.md (learns tic-tac-toe)
   - Reads state.json (sees empty board, confirms it's X)
   - Decides to play center
   - Writes moves/turn_1_claude-alpha.json:
     {
       "protocol": "lxm-v0.2",
       "match_id": "match_20250315_143022",
       "agent_id": "claude-alpha",
       "turn": 1,
       "move": {"type": "place", "position": [1, 1]},
       "meta": {"reasoning_summary": "Center is optimal opening"}
     }
6. Orchestrator reads moves/turn_1_claude-alpha.json
7. Validate envelope → OK
8. Validate payload (game.validate_move) → OK
9. Apply move (game.apply_move) → Board updated, X at center
10. Generate summary: "Placed X at (1, 1)"
11. Update state.json (new board + lxm.recent_moves)
12. Append to log.json
13. Check game over → No
14. Advance turn → active_agent = claude-beta
15. Console: [Turn 1] claude-alpha: Placed X at (1, 1)
```

### Turn 2 (claude-beta, O)

```
Same flow. claude-beta reads state.json, sees X at center, decides response.
```

### ... continues until win or draw ...

### Game End

```
1. game.is_over() returns True
2. game.get_result() → { outcome: "win", winner: "claude-alpha", ... }
3. Write result.json
4. Console: [Result] claude-alpha (X) wins by diagonal
5. Run evaluation phase (invoke each agent with eval prompt)
6. Console: Match complete. Files in matches/match_20250315_143022/
```

---

## 11. Implementation Order

Build in this order. Each step should be testable before moving on.

```
Step 1: lxm/envelope.py + tests
        → Can parse and validate envelopes

Step 2: lxm/engine.py (abstract class only)
        → Interface defined, no implementation

Step 3: games/tictactoe/engine.py + rules.md + tests
        → Game logic works with mock data

Step 4: lxm/state.py + tests
        → State management works

Step 5: lxm/orchestrator.py + tests (with MockAdapter)
        → Full game loop works without any CLI

Step 6: lxm/adapters/claude_code.py
        → CLI adapter built

Step 7: scripts/run_match.py
        → CLI entry point

Step 8: Integration test
        → Two Claude Code instances play tic-tac-toe
```

**Success criteria for Step 8:**
Two Claude Code CLI instances complete a full tic-tac-toe game. Both agents read PROTOCOL.md and rules.md, submit valid moves via file, and the game reaches a terminal state (win or draw). The match folder contains state.json, log.json, result.json, and move files for every turn.

---

## 12. Open Questions for Testing

These will be resolved during implementation. Document findings.

1. **Claude Code `-p` flag behavior:** Does `--output-format json` wrap the response? What's the exact format?
2. **File permissions:** Is `--dangerously-skip-permissions` required for file writes in the match folder? Or does normal `-p` mode allow it?
3. **Shell injection method:** Does prepending shell content to the prompt work reliably? Or is there a better method (e.g., `--system-prompt` flag)?
4. **Stdout noise:** How much non-JSON content does Claude Code produce in `-p` mode? Is the JSON extraction logic robust enough?
5. **First-turn PROTOCOL.md reading:** Do agents reliably read PROTOCOL.md on first invocation, or do they skip it after the first game?

---

*LxM Implementation Spec v0.1*
*Target: Two Claude Code agents playing tic-tac-toe*
