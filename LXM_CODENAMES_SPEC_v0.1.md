# LxM Codenames Spec v0.1

## Purpose

Add **Codenames** as the fourth LxM game. Opens the "team cooperation + language" category. Requires **architecture upgrades**: multi-agent (4 players), asymmetric information (spymaster sees answer key), team structure, and role-based turns.

This is **Phase 1c Step 2** in the Platform Spec — the first game that requires structural changes to the orchestrator and protocol.

**Hand this to Cody and say "build this."**

**Prerequisites:**
- LxM core system with `filter_state_for_agent` support (added in Trust Game)
- Match viewer with game-specific renderers
- Effort estimate: 1-2 weeks (game + architecture upgrades)

---

## 1. Game Rules

Codenames is a 2v2 word game. A 5×5 grid of 25 words is laid out. Each word is secretly assigned to one of four categories: Red team (8 or 9), Blue team (8 or 9), Neutral (7), or Assassin (1).

**Teams:**
- Red team: 1 Spymaster + 1 Guesser
- Blue team: 1 Spymaster + 1 Guesser

**Turn structure:**
1. Active team's Spymaster gives a one-word clue + a number (how many board words relate to the clue)
2. Active team's Guesser makes guesses one at a time (up to clue_number + 1 guesses)
3. Each guess reveals the word's category. If the guess is wrong team, neutral, or assassin — turn ends.
4. Teams alternate.

**Winning conditions:**
- A team reveals all their words → that team wins
- A team reveals the Assassin → that team loses immediately

**Why this game matters for LxM:**
- **Asymmetric information**: Spymaster sees the full answer key; Guesser sees only revealed words
- **Language as game mechanism**: Clue quality directly determines success — LLMs' core ability
- **Team cooperation**: Spymaster must model what the Guesser will associate with the clue
- **4 agents**: First multi-team game in LxM

---

## 2. Architecture Upgrades Required

### 2.1 Team Structure in match_config

Current match_config has a flat `agents` array with `seat`. Codenames needs teams and roles.

**Change:** Add optional `teams` field to match_config. When present, the orchestrator uses team-based turn logic instead of simple seat rotation.

```json
{
  "agents": [
    {"agent_id": "opus-spy-r", "display_name": "Opus Spymaster", "seat": 0, "team": "red", "role": "spymaster"},
    {"agent_id": "haiku-guess-r", "display_name": "Haiku Guesser", "seat": 1, "team": "red", "role": "guesser"},
    {"agent_id": "sonnet-spy-b", "display_name": "Sonnet Spymaster", "seat": 2, "team": "blue", "role": "spymaster"},
    {"agent_id": "haiku-guess-b", "display_name": "Haiku Guesser B", "seat": 3, "team": "blue", "role": "guesser"}
  ],
  "teams": {
    "red": {"spymaster": "opus-spy-r", "guesser": "haiku-guess-r"},
    "blue": {"spymaster": "sonnet-spy-b", "guesser": "haiku-guess-b"}
  }
}
```

**Backward compatibility:** Games without `teams` field work exactly as before (Chess, Trust Game, etc.).

### 2.2 Role-Based Turn Order

Current orchestrator rotates by seat index: `(turn-1) % len(agents)`. Codenames needs a different pattern:

```
Turn 1: Red Spymaster gives clue
Turn 2: Red Guesser guesses (may take multiple sub-turns)
Turn 3: Blue Spymaster gives clue
Turn 4: Blue Guesser guesses
Turn 5: Red Spymaster...
```

**Solution:** Add a new turn_order type: `"team_alternating"`.

```json
"time_model": {
  "type": "turn_based",
  "turn_order": "team_alternating",
  "max_turns": 50,
  "timeout_seconds": 120,
  "timeout_action": "no_op",
  "max_retries": 2
}
```

The game engine controls the actual sequence via `get_active_agent_id(state)` — a new optional method that overrides the orchestrator's default rotation when the game needs custom turn logic.

### 2.3 Engine Interface Extension

Add one optional method to `LxMGame`:

```python
class LxMGame(ABC):
    # ... existing methods ...

    def get_active_agent_id(self, state: dict) -> str | None:
        """
        Override orchestrator's default turn rotation.
        Return the agent_id who should move next, or None to use default rotation.
        
        Games with custom turn logic (Codenames: spymaster→guesser within a team turn)
        implement this. Games with simple rotation (Chess, Trust Game) don't need to.
        """
        return None  # Default: let orchestrator handle it
```

### 2.4 Asymmetric State Filtering (extends Trust Game pattern)

Trust Game introduced `filter_state_for_agent` to mask `pending_move`. Codenames extends this to mask the entire answer key from guessers.

The orchestrator already calls `filter_state_for_agent` before writing state.json. No orchestrator change needed — just a richer implementation in the game engine.

### 2.5 Orchestrator Changes Summary

| Change | Type | Description |
|--------|------|-------------|
| `teams` in match_config | Additive | Optional field, ignored by existing games |
| `team_alternating` turn_order | Additive | New enum value, existing values unchanged |
| `get_active_agent_id` method | Additive | Optional method with default fallback |
| LxMState modifications | Minor | Support `get_active_agent_id` override from engine |

All changes are backward-compatible. Existing games continue to work without modification.

### 2.6 LxMState Changes

```python
class LxMState:
    def __init__(self, match_config: dict, game: LxMGame = None):
        # ... existing init ...
        self._game = game  # Reference to game engine for custom turn logic
    
    def get_active_agent(self, game_state: dict = None) -> str:
        """Return the agent_id whose turn it is."""
        # Check if game engine overrides turn order
        if self._game and game_state:
            custom = self._game.get_active_agent_id(
                self.to_dict(game_state)
            )
            if custom is not None:
                return custom
        
        # Default: seat rotation
        idx = (self._turn - 1) % len(self._agents)
        return self._agents[idx]
```

The orchestrator passes `game_state` when calling `get_active_agent`. Existing callers that don't pass it get the default behavior.

---

## 3. File Structure

```
games/
└── codenames/
    ├── engine.py          ← CodenamesGame(LxMGame)
    ├── rules.md           ← Agent-readable rules
    ├── wordlist.py        ← Standard word list (400 words)
    └── README.md

viewer/
└── static/
    └── renderers/
        └── codenames.js   ← Codenames board renderer

viewer/
└── exporters/
    └── codenames.py       ← Frame renderer for GIF/MP4
```

---

## 4. Game Engine: `games/codenames/engine.py`

### 4.1 Word List

A standard set of ~400 Codenames-style words (concrete nouns, common enough for association). Sourced from open Codenames word lists or manually curated.

Each game randomly selects 25 words and assigns:
- 9 words to the starting team (red goes first → red gets 9)
- 8 words to the other team
- 7 neutral words
- 1 assassin

### 4.2 `initial_state(agents)`

```python
def initial_state(self, agents: list[dict]) -> dict:
    # Build team mapping from agent configs
    teams = self._build_teams(agents)  # {red: {spymaster, guesser}, blue: {spymaster, guesser}}
    
    # Generate board
    words = random.sample(WORD_LIST, 25)
    board = self._create_board(words)  # 5x5 grid of {word, category, revealed}
    
    # Determine starting team (team with 9 words)
    starting_team = "red"
    
    return {
        "current": {
            "board": [
                [{"word": w, "revealed": False, "revealed_as": None} for w in row]
                for row in self._grid_words(words)
            ],
            "answer_key": [
                [category for category in row]
                for row in self._grid_categories(words, board)
            ],
            "active_team": starting_team,
            "active_role": "spymaster",  # spymaster gives clue, then guesser guesses
            "current_clue": None,        # set by spymaster: {"word": "ocean", "number": 3}
            "guesses_remaining": 0,
            "teams": teams,
            "remaining": {
                "red": 9,
                "blue": 8,
            },
        },
        "context": {
            "clue_history": [],      # all clues given
            "guess_history": [],     # all guesses made
            "turns_played": 0,
            "key_events": [],
        },
    }
```

### 4.3 `filter_state_for_agent(state, agent_id)`

This is the critical asymmetric information implementation.

```python
def filter_state_for_agent(self, state: dict, agent_id: str) -> dict:
    import copy
    filtered = copy.deepcopy(state)
    game = filtered["game"]
    current = game["current"]
    teams = current["teams"]
    
    # Determine this agent's role
    role = self._get_agent_role(agent_id, teams)
    
    if role == "guesser":
        # Guessers CANNOT see the answer key
        # Replace unrevealed categories with "unknown"
        answer_key = current["answer_key"]
        board = current["board"]
        masked_key = []
        for r, row in enumerate(answer_key):
            masked_row = []
            for c, category in enumerate(row):
                if board[r][c]["revealed"]:
                    masked_row.append(category)  # Already revealed — visible to all
                else:
                    masked_row.append("unknown")
            masked_row.append(masked_row)
        filtered["game"]["current"]["answer_key"] = masked_key
    
    # Spymasters see everything (they need the key to give clues)
    
    return filtered
```

### 4.4 `get_active_agent_id(state)`

Custom turn logic for Codenames:

```python
def get_active_agent_id(self, state: dict) -> str | None:
    game = state["game"]
    current = game["current"]
    teams = current["teams"]
    active_team = current["active_team"]
    active_role = current["active_role"]
    
    team_data = teams[active_team]
    return team_data[active_role]
```

### 4.5 `validate_move(move, agent_id, state)`

Two move types depending on role:

**Spymaster move (give clue):**
```json
{
  "type": "clue",
  "word": "ocean",
  "number": 3
}
```

Validation:
- `type` must be `"clue"`
- `word` must be a single word (no spaces, no hyphens except standard compound words)
- `word` must NOT be any word currently on the board (unrevealed)
- `number` must be an integer, 0-9 (0 is legal in Codenames — means "unlimited but this clue relates to 0 specific words")
- Agent must be the active team's spymaster

**Guesser move (guess a word):**
```json
{
  "type": "guess",
  "word": "beach"
}
```

Or to end guessing voluntarily:
```json
{
  "type": "pass"
}
```

Validation:
- `type` must be `"guess"` or `"pass"`
- If guess: `word` must be an unrevealed word on the board (exact match, case-insensitive)
- Agent must be the active team's guesser
- `guesses_remaining` must be > 0 (unless pass)

### 4.6 `apply_move(move, agent_id, state)`

**If spymaster clue:**
- Store clue in `current.current_clue`
- Set `guesses_remaining` to `clue_number + 1`
- Switch `active_role` to `"guesser"`
- Append to `context.clue_history`

**If guesser guess:**
- Reveal the word on the board (set `revealed = True`, `revealed_as = category`)
- Decrement `guesses_remaining`
- Check what category was revealed:
  - **Own team's word**: Continue guessing (guesses_remaining > 0)
  - **Opponent's word**: Turn ends. Switch to other team.
  - **Neutral**: Turn ends. Switch to other team.
  - **Assassin**: Game over. Guessing team loses.
- Decrement `remaining` count for the revealed category
- Append to `context.guess_history`

**If guesser pass:**
- Turn ends. Switch to other team.
- Reset `active_role` to `"spymaster"`, `current_clue` to null

**Team switch logic:**
```python
def _switch_team(self, current):
    next_team = "blue" if current["active_team"] == "red" else "red"
    current["active_team"] = next_team
    current["active_role"] = "spymaster"
    current["current_clue"] = None
    current["guesses_remaining"] = 0
```

### 4.7 `is_over(state)`

```python
def is_over(self, state: dict) -> bool:
    game = state["game"]
    current = game["current"]
    remaining = current["remaining"]
    
    # A team found all their words
    if remaining["red"] == 0 or remaining["blue"] == 0:
        return True
    
    # Assassin was revealed (check board for revealed assassin)
    for row in current["board"]:
        for cell in row:
            if cell["revealed"] and cell["revealed_as"] == "assassin":
                return True
    
    return False
```

### 4.8 `get_result(state)`

```python
def get_result(self, state: dict) -> dict:
    game = state["game"]
    current = game["current"]
    remaining = current["remaining"]
    teams = current["teams"]
    
    # Check for assassin
    assassin_hit_by = None
    for row_idx, row in enumerate(current["board"]):
        for col_idx, cell in enumerate(row):
            if cell["revealed"] and cell["revealed_as"] == "assassin":
                # Find which team's guesser revealed it
                assassin_hit_by = self._find_assassin_revealer(game)
    
    if assassin_hit_by:
        loser = assassin_hit_by
        winner = "blue" if loser == "red" else "red"
        outcome = "assassin"
        summary = f"Team {winner} wins — Team {loser} hit the assassin!"
    elif remaining["red"] == 0:
        winner = "red"
        outcome = "complete"
        summary = f"Team red found all their words!"
    elif remaining["blue"] == 0:
        winner = "blue"
        outcome = "complete"
        summary = f"Team blue found all their words!"
    else:
        winner = None
        outcome = "unknown"
        summary = "Game ended without clear winner"
    
    # Score: winning team members get 1, losing team gets 0
    scores = {}
    for team_name, team_agents in teams.items():
        for role, aid in team_agents.items():
            scores[aid] = 1.0 if team_name == winner else 0.0
    
    return {
        "outcome": outcome,
        "winner": winner,
        "winning_team": winner,
        "scores": scores,
        "summary": summary,
    }
```

### 4.9 `summarize_move(move, agent_id, state)`

```python
def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
    if move["type"] == "clue":
        return f"Clue: \"{move['word']}\" for {move['number']}"
    elif move["type"] == "guess":
        word = move["word"]
        # Look up what category this word is
        category = self._get_word_category(word, state)
        return f"Guessed \"{word}\" → {category}"
    elif move["type"] == "pass":
        return "Passed (ended guessing)"
    return str(move)
```

### 4.10 `get_evaluation_schema()`

```python
def get_evaluation_schema(self) -> dict:
    return {
        "description": "Evaluate Codenames performance by role",
        "fields": {
            "clue_quality": "1-5: How creative and effective were the spymaster's clues?",
            "clue_risk": "1-5: Did the spymaster take appropriate risks (multi-word clues vs safe single-word)?",
            "guess_accuracy": "1-5: Did the guesser correctly interpret the clues?",
            "team_synergy": "1-5: How well did the spymaster-guesser pair coordinate?",
            "assassin_awareness": "Did the spymaster avoid clues that might lead to the assassin?",
            "best_clue": "The single best clue of the game and why",
            "worst_clue": "The most misleading or ineffective clue and why",
            "overall_comment": "Free text assessment",
        },
    }
```

---

## 5. Rules File: `games/codenames/rules.md`

```markdown
# Codenames — LxM Game Rules

## Overview

Two teams (Red and Blue) compete to find their secret words on a 5×5 board.
Each team has a Spymaster (who gives clues) and a Guesser (who guesses words).
The Spymaster knows which words belong to which team. The Guesser does not.

## Teams and Roles

Check `state.json` → `game.current.teams` to see your team and role.

- **Spymaster**: You can see `game.current.answer_key` — the full color map. Your job is to give clues that help your Guesser find your team's words without touching the opponent's words or the Assassin.
- **Guesser**: You see `game.current.answer_key` with unrevealed words as `"unknown"`. You rely on the Spymaster's clue to guess.

## Board

`state.json` → `game.current.board`: A 5×5 grid. Each cell has:
- `word`: The word displayed
- `revealed`: Whether it has been guessed
- `revealed_as`: The category (only visible after reveal): `"red"`, `"blue"`, `"neutral"`, or `"assassin"`

## Answer Key (Spymaster only)

`state.json` → `game.current.answer_key`: A 5×5 grid of categories.
- For Spymasters: shows the true category of every word
- For Guessers: unrevealed words show as `"unknown"`

## Turn Structure

Each team's turn has two phases:

**Phase 1 — Spymaster gives a clue:**
```json
{
  "type": "clue",
  "word": "ocean",
  "number": 3
}
```
- `word`: A single word. Must NOT be any word currently on the board.
- `number`: How many board words relate to this clue (0-9).

**Phase 2 — Guesser guesses:**
```json
{
  "type": "guess",
  "word": "beach"
}
```
- Guess one word at a time. The word must be on the board and unrevealed.
- You get `number + 1` guesses maximum.
- After each guess, the word is revealed:
  - **Your team's word**: Correct! You may continue guessing.
  - **Opponent's word**: Wrong. Your turn ends.
  - **Neutral word**: Wrong. Your turn ends.
  - **Assassin**: Your team loses immediately.

To stop guessing before using all guesses:
```json
{
  "type": "pass"
}
```

## Game State

`state.json` → `game.current`:
- `active_team`: Which team's turn it is (`"red"` or `"blue"`)
- `active_role`: `"spymaster"` (giving clue) or `"guesser"` (guessing)
- `current_clue`: The current clue (null if waiting for spymaster)
- `guesses_remaining`: How many guesses left this turn
- `remaining`: How many words each team still needs to find

`state.json` → `game.context`:
- `clue_history`: All clues given so far (by both teams)
- `guess_history`: All guesses made and their results

## Winning

- Find all your team's words → you win
- Hit the Assassin → you lose immediately
- The other team finds all their words first → you lose

## Strategy Tips for Spymaster

- Connect multiple words with one clue to go faster
- Avoid clues that could lead to the Assassin or opponent's words
- Consider what your Guesser will associate — not just what YOU associate

## Strategy Tips for Guesser

- The number tells you how many words the Spymaster is connecting
- Start with the most obvious connection
- If unsure, pass rather than risk hitting the Assassin
- Previous clues may still have unrevealed matches

## Evaluation

After the game, evaluate on these axes:
- **clue_quality** (1-5): Creativity and effectiveness of clues
- **clue_risk** (1-5): Appropriate risk-taking in multi-word clues
- **guess_accuracy** (1-5): Correct interpretation of clues
- **team_synergy** (1-5): Spymaster-Guesser coordination
- **assassin_awareness**: Did the spymaster avoid dangerous clues?
- **best_clue**: Best clue of the game and why
- **worst_clue**: Most misleading clue and why
- **overall_comment**: Free text assessment
```

---

## 6. Match Configuration

```json
{
  "protocol_version": "lxm-v0.2",
  "match_id": "codenames_001",
  "game": {"name": "codenames", "version": "1.0"},
  "time_model": {
    "type": "turn_based",
    "turn_order": "team_alternating",
    "max_turns": 50,
    "timeout_seconds": 120,
    "timeout_action": "no_op",
    "max_retries": 2
  },
  "agents": [
    {"agent_id": "opus-spy-r", "display_name": "Opus Spymaster", "seat": 0, "team": "red", "role": "spymaster"},
    {"agent_id": "haiku-guess-r", "display_name": "Haiku Guesser", "seat": 1, "team": "red", "role": "guesser"},
    {"agent_id": "sonnet-spy-b", "display_name": "Sonnet Spymaster", "seat": 2, "team": "blue", "role": "spymaster"},
    {"agent_id": "haiku-guess-b", "display_name": "Haiku Guesser B", "seat": 3, "team": "blue", "role": "guesser"}
  ],
  "teams": {
    "red": {"spymaster": "opus-spy-r", "guesser": "haiku-guess-r"},
    "blue": {"spymaster": "sonnet-spy-b", "guesser": "haiku-guess-b"}
  },
  "history": {"recent_moves_count": 15}
}
```

### CLI Usage

```bash
# Run a Codenames match
lxm match run --game codenames \
  --agents opus-spy-r haiku-guess-r sonnet-spy-b haiku-guess-b

# With model specification
lxm match run --game codenames \
  --agents opus-spy-r:opus haiku-guess-r:haiku sonnet-spy-b:sonnet haiku-guess-b:haiku
```

### Interesting Model Combinations

| Setup | What it tests |
|-------|--------------|
| Opus spymaster + Haiku guesser vs same | Does a smarter spymaster give better clues? |
| Haiku spymaster + Opus guesser vs same | Does a smarter guesser compensate for simpler clues? |
| Same model all 4 (Sonnet) | Pure team dynamics, no Core advantage |
| Mixed: Opus+Haiku vs Sonnet+Sonnet | Asymmetric Core vs balanced Core |

---

## 7. Viewer: Codenames Renderer

### Visual Design

```
┌──────────────────────────────────────────────────────────────┐
│  Codenames — Red: 5 remaining | Blue: 4 remaining            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐              │
│  │BEACH │ │ DOG  │ │CRANE │ │PRESS │ │MOON  │              │
│  │      │ │  🔴  │ │      │ │  🔵  │ │      │              │
│  ├──────┤ ├──────┤ ├──────┤ ├──────┤ ├──────┤              │
│  │SPRING│ │BANK  │ │PLATE │ │WAVE  │ │ROCK  │              │
│  │      │ │  💀  │ │  ⬜  │ │  🔴  │ │      │              │
│  ├──────┤ ├──────┤ ├──────┤ ├──────┤ ├──────┤              │
│  │ CAP  │ │ORGAN │ │MATCH │ │TRIP  │ │BOLT  │              │
│  │      │ │      │ │  🔴  │ │      │ │  🔵  │              │
│  ├──────┤ ├──────┤ ├──────┤ ├──────┤ ├──────┤              │
│  │DRILL │ │ NET  │ │DRAFT │ │IRON  │ │PITCH │              │
│  │  🔵  │ │      │ │      │ │  🔴  │ │      │              │
│  ├──────┤ ├──────┤ ├──────┤ ├──────┤ ├──────┤              │
│  │STICK │ │POINT │ │BLOCK │ │CYCLE │ │LEMON │              │
│  │      │ │  🔵  │ │      │ │      │ │  ⬜  │              │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘              │
│                                                              │
│  🔴 Red Team          │  🔵 Blue Team                        │
│  Spy: opus-spy-r      │  Spy: sonnet-spy-b                   │
│  Guess: haiku-guess-r  │  Guess: haiku-guess-b                │
│                                                              │
│  Current: 🔴 Spymaster's turn                                │
│  Last clue: "WATER" for 3                                    │
│  Guesses: BEACH ✓, WAVE ✓, 1 remaining                      │
│                                                              │
│  Clue History:                                               │
│  🔴 T1: "WATER" 3 → BEACH✓ WAVE✓ (1 left)                  │
│  🔵 T2: "POWER" 2 → PRESS✓ BOLT✓                            │
│  🔴 T3: "ANIMAL" 1 → NET✗ (neutral, turn ends)              │
└──────────────────────────────────────────────────────────────┘
```

### Rendering Rules

**Unrevealed words:** White/light background with word text. No color hint.

**Revealed words:** Background colored by category:
- Red: red/coral background
- Blue: blue/teal background
- Neutral: gray background
- Assassin: black background with skull

**Spymaster view mode (toggle):** Option to show the full answer key with faded colors for unrevealed words. For replay/analysis, not shown to guessers during live play.

**Current action highlight:** Active team's panel highlighted. Current clue prominently displayed. Guess count shown.

**Clue history:** Scrollable list showing all clues and their resulting guesses.

---

## 8. ELO Considerations for Team Games

Current ELO system is 1v1. Codenames is 2v2. Options:

**Option A: Team ELO** — Each team has an ELO (average of members). Winning team gains, losing team loses. Simple but doesn't distinguish spymaster from guesser.

**Option B: Individual ELO with team adjustment** — Each player gains/loses ELO, but weighted by role. If the spymaster gave great clues but the guesser missed them, the guesser loses more.

**Option C: Separate role ELO** — Each agent has a spymaster-ELO and a guesser-ELO. Most informative but complex.

**Recommendation: Option A for v1.** Keep it simple. All team members share the win/loss. We can add role-specific analysis in post-game evaluation without complicating the ELO system.

```python
# Team game ELO: average team ELO, then standard calculation
red_elo = average(red_spymaster.elo, red_guesser.elo)
blue_elo = average(blue_spymaster.elo, blue_guesser.elo)
delta = standard_elo_delta(red_elo, blue_elo, winner="red")
# Apply delta equally to all team members
```

---

## 9. Unit Tests

### Engine Tests

```
test_initial_state              — 25 words, correct category counts (9/8/7/1)
test_initial_state_teams        — Teams and roles correctly assigned
test_validate_clue_valid        — Single word + number accepted
test_validate_clue_board_word   — Clue word that's on the board rejected
test_validate_clue_multi_word   — Multi-word clue rejected
test_validate_clue_wrong_role   — Guesser trying to give clue rejected
test_validate_guess_valid       — Unrevealed board word accepted
test_validate_guess_revealed    — Already-revealed word rejected
test_validate_guess_not_on_board — Word not on board rejected
test_validate_guess_wrong_role  — Spymaster trying to guess rejected
test_validate_pass              — Pass move accepted for guesser
test_apply_clue                 — Clue stored, role switches to guesser
test_apply_guess_correct        — Own team word: revealed, continue
test_apply_guess_opponent       — Opponent word: revealed, turn ends
test_apply_guess_neutral        — Neutral word: revealed, turn ends
test_apply_guess_assassin       — Assassin: revealed, game over
test_apply_pass                 — Turn ends, switch team
test_guess_limit                — Can't exceed clue_number + 1
test_is_over_all_found          — Team finds all words
test_is_over_assassin           — Assassin hit ends game
test_get_result_red_wins        — Red finds all words
test_get_result_assassin        — Correct team loses
test_get_active_agent           — Correct sequence: spy→guess→spy→guess
```

### State Filtering Tests

```
test_filter_spymaster_sees_key  — Spymaster gets full answer_key
test_filter_guesser_masked      — Guesser gets "unknown" for unrevealed
test_filter_revealed_visible    — Both roles see revealed categories
test_filter_other_team_masked   — Opponent guesser also gets masked key
```

### Architecture Tests

```
test_team_config_parsing        — match_config with teams field parsed correctly
test_backward_compat            — Chess match_config without teams still works
test_custom_turn_order          — get_active_agent_id overrides default rotation
```

---

## 10. Model Medicine Data Value

Codenames generates unique data not available from any other LxM game:

**Language abstraction ability:** The core mechanic — "find one word that connects BEACH, WAVE, and OCEAN but not BANK or NET" — directly measures semantic association quality. Different models will show dramatically different clue quality. This is the first game that tests what LLMs are BEST at.

**Theory of mind (spymaster):** The spymaster must model what the guesser will think. "Will Haiku associate 'WATER' with 'BANK'?" This is implicit theory of mind — predicting another agent's associations. Measurable by clue success rate.

**Instruction following under constraint (guesser):** The guesser receives a one-word clue and must make constrained decisions. This tests how well a model follows minimal, ambiguous instructions.

**Team cooperation across different Cores:** Opus spymaster + Haiku guesser — does the smarter model adapt its clue complexity to the guesser's level? This is a new dimension of Sociality.

**Risk calibration:** Multi-word clues (number=3) are risky but faster. Single-word clues (number=1) are safe but slow. The spymaster's risk profile is directly measurable.

---

## 11. Implementation Order

```
Step 1: Architecture upgrades
  ├── Add optional `teams` field to match_config parsing
  ├── Add `get_active_agent_id` to LxMGame (optional method, default None)
  ├── Update LxMState to support engine-driven turn order
  ├── Update orchestrator to pass game_state to get_active_agent
  ├── Tests: backward compatibility (Chess, Trust Game still pass)
  
Step 2: Game engine
  ├── games/codenames/wordlist.py (400 words)
  ├── games/codenames/engine.py (full implementation)
  ├── games/codenames/rules.md
  ├── Engine unit tests (all from Section 9)
  
Step 3: Viewer renderer
  ├── viewer/static/renderers/codenames.js
  ├── 5x5 board with color-coded reveals
  ├── Team panels, clue history
  ├── Spymaster view toggle (for replay analysis)
  
Step 4: Integration test
  ├── 4 Claude Code instances play a full Codenames game
  ├── Verify: spymaster sees key, guesser doesn't
  ├── Verify: turn order (spy→guess→spy→guess)
  ├── Verify: viewer shows board correctly
  ├── Try: Opus spymaster + Haiku guesser vs Sonnet + Haiku

Step 5: ELO for team games
  ├── Extend ELO system for 2v2 (team average)
  ├── Update leaderboard to show team game stats
```

**Success criteria for Step 4:** Four agents complete a full Codenames game. Spymasters give multi-word clues. Guessers correctly interpret at least some clues. The answer key is properly hidden from guessers (verify by checking that guessers never reference hidden categories in their reasoning). Viewer shows the board with correct color reveals.

---

## 12. Open Questions

**Word list language:** Start with English. Korean word list would open a whole new dimension (do models give better Korean or English clues?). Defer to v2.

**Clue validation strictness:** Should "WATERY" be allowed as a clue for WATER-related words? Standard Codenames allows it but it's a gray area. For v1, allow any single word that's not on the board. Let the post-game evaluation judge clue quality.

**Guesser multi-guess flow:** In the current orchestrator, each guess is a separate turn (separate CLI invocation). This means the guesser is re-invoked for each guess within a clue. This is correct but expensive — a 3-word clue could mean 4 CLI invocations for the guesser. Acceptable for v1, but consider batched guesses for v2.

**Spymaster temptation:** The spymaster reads state.json which includes the answer key. In a real game, the spymaster is supposed to use this information ONLY for giving clues. But a clever model might encode specific information in the clue ("BEACH-3" where the first letter of each target word spells something). This is hard to prevent and arguably part of the game's skill. Monitor but don't restrict for v1.

---

*LxM Codenames Spec v0.1*
*"One word. Three connections. Can your AI find them all?"*
