# LxM Trust Game Spec v0.1

## Purpose

Add the **Iterated Prisoner's Dilemma** (Trust Game) as the third LxM game. Opens the "game theory / cooperation-betrayal" category. Requires **zero architecture changes** — works with current 2-player sequential turn orchestrator.

**Hand this to Cody and say "build this."**

**Effort estimate:** 1 day.

---

## 1. Game Rules

Two agents play N rounds of the Prisoner's Dilemma. Each round, both agents simultaneously choose **cooperate** or **defect**. Payoffs follow the classic matrix:

```
                Agent B
              Cooperate  Defect
Agent A  
  Cooperate    3, 3      0, 5
  Defect       5, 0      1, 1
```

- Mutual cooperation: both get 3 points
- Mutual defection: both get 1 point
- One defects, one cooperates: defector gets 5, cooperator gets 0

**"Simultaneously"** in LxM's sequential turn system: both agents submit their choice in the same round. The orchestrator collects both moves before revealing the outcome. Each agent sees the OTHER agent's previous choices in state.json, but NOT the current round's choice until both have submitted.

### Implementation of Simultaneous Moves

Since LxM is sequential (Agent A moves, then Agent B moves), we handle simultaneous choice via a **two-phase round**:

```
Round N:
  Phase 1: Agent A submits choice (doesn't see B's current choice)
  Phase 2: Agent B submits choice (doesn't see A's current choice)
  → Orchestrator reveals both choices, updates scores
```

Agent B's state.json during Phase 2 shows A's move as "submitted" but NOT the actual choice. This prevents second-mover advantage. After both submit, the round resolves and both choices become visible in the next round's state.

**Game length:** Configurable. Default 20 rounds. Agents do NOT know the exact number of rounds (to prevent end-game defection). State shows "round X" but not "of Y".

---

## 2. File Structure

```
games/
└── trustgame/
    ├── engine.py          ← TrustGame(LxMGame)
    ├── rules.md           ← Agent-readable rules
    └── README.md

viewer/
└── static/
    └── renderers/
        └── trustgame.js   ← Trust Game renderer

viewer/
└── exporters/
    └── trustgame.py       ← Frame renderer for GIF/MP4
```

---

## 3. Game Engine: `games/trustgame/engine.py`

```python
from pathlib import Path
from lxm.engine import LxMGame

class TrustGame(LxMGame):
    
    DEFAULT_ROUNDS = 20
    
    PAYOFF_MATRIX = {
        ("cooperate", "cooperate"): (3, 3),
        ("cooperate", "defect"):    (0, 5),
        ("defect",    "cooperate"): (5, 0),
        ("defect",    "defect"):    (1, 1),
    }
```

### 3.1 `initial_state(agents)`

```python
def initial_state(self, agents: list[dict]) -> dict:
    return {
        "current": {
            "round": 1,
            "phase": "choose",       # "choose" or "resolved"
            "pending_move": None,     # Agent A's choice, hidden from B
            "scores": {
                agents[0]["agent_id"]: 0,
                agents[1]["agent_id"]: 0,
            },
        },
        "context": {
            "total_rounds": "unknown",  # Agents don't know the exact count
            "rounds_played": 0,
            "history": [],              # List of resolved rounds
            "cooperation_rate": {
                agents[0]["agent_id"]: 0.0,
                agents[1]["agent_id"]: 0.0,
            },
            "patterns": {
                "mutual_cooperate": 0,
                "mutual_defect": 0,
                "betrayals": 0,         # One cooperated, other defected
            },
        },
    }
```

### 3.2 `validate_move(move, agent_id, state)`

```python
def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
    """
    Checks:
    - move["type"] == "choice"
    - move["action"] is "cooperate" or "defect"
    """
    if move.get("type") != "choice":
        return {"valid": False, "message": "move.type must be 'choice'"}
    
    action = move.get("action")
    if action not in ("cooperate", "defect"):
        return {"valid": False, "message": "move.action must be 'cooperate' or 'defect'"}
    
    return {"valid": True, "message": None}
```

### 3.3 `apply_move(move, agent_id, state)`

This is the key logic. Two cases:

**First agent in round (Phase 1):**
- Store choice in `pending_move` (hidden from second agent)
- Don't update scores yet
- Don't advance round

**Second agent in round (Phase 2):**
- Retrieve first agent's pending_move
- Resolve payoffs
- Append to history
- Update scores, cooperation rates, patterns
- Advance to next round

```python
def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
    game = state["game"]
    current = game["current"]
    context = game["context"]
    agents = list(current["scores"].keys())
    
    action = move["action"]
    
    if current["pending_move"] is None:
        # Phase 1: first agent submits
        new_current = {
            **current,
            "pending_move": {
                "agent_id": agent_id,
                "action": action,
            },
        }
        return {"current": new_current, "context": context}
    
    else:
        # Phase 2: second agent submits, resolve round
        first = current["pending_move"]
        first_action = first["action"]
        first_agent = first["agent_id"]
        second_action = action
        second_agent = agent_id
        
        # Calculate payoffs
        p1, p2 = self.PAYOFF_MATRIX[(first_action, second_action)]
        
        # Update scores
        new_scores = dict(current["scores"])
        new_scores[first_agent] += p1
        new_scores[second_agent] += p2
        
        # Round result
        round_result = {
            "round": current["round"],
            first_agent: first_action,
            second_agent: second_action,
            "payoffs": {first_agent: p1, second_agent: p2},
        }
        
        new_history = context["history"] + [round_result]
        rounds_played = context["rounds_played"] + 1
        
        # Update cooperation rates
        new_coop_rate = {}
        for aid in agents:
            coop_count = sum(1 for r in new_history if r[aid] == "cooperate")
            new_coop_rate[aid] = round(coop_count / rounds_played, 3)
        
        # Update patterns
        new_patterns = dict(context["patterns"])
        if first_action == "cooperate" and second_action == "cooperate":
            new_patterns["mutual_cooperate"] += 1
        elif first_action == "defect" and second_action == "defect":
            new_patterns["mutual_defect"] += 1
        else:
            new_patterns["betrayals"] += 1
        
        new_current = {
            "round": current["round"] + 1,
            "phase": "choose",
            "pending_move": None,
            "scores": new_scores,
        }
        
        new_context = {
            "total_rounds": "unknown",
            "rounds_played": rounds_played,
            "history": new_history,
            "cooperation_rate": new_coop_rate,
            "patterns": new_patterns,
        }
        
        return {"current": new_current, "context": new_context}
```

### 3.4 `is_over(state)`

```python
def is_over(self, state: dict) -> bool:
    rounds_played = state["game"]["context"]["rounds_played"]
    # Default 20 rounds. Can be overridden via match_config.
    max_rounds = state.get("lxm", {}).get("max_rounds", self.DEFAULT_ROUNDS)
    return rounds_played >= max_rounds
```

Note: `max_rounds` needs to be passed through. Options:
- Add to match_config.time_model (as max_turns — already exists, use max_turns / 2 since each round = 2 turns)
- Or add game-specific config. Simplest: `max_turns = rounds * 2`.

**Use existing max_turns:** If max_turns = 40, that's 20 rounds (2 turns per round).

```python
def is_over(self, state: dict) -> bool:
    rounds_played = state["game"]["context"]["rounds_played"]
    max_turns = state["lxm"].get("max_turns", self.DEFAULT_ROUNDS * 2)
    max_rounds = max_turns // 2
    return rounds_played >= max_rounds
```

### 3.5 `get_result(state)`

```python
def get_result(self, state: dict) -> dict:
    scores = state["game"]["current"]["scores"]
    agents = list(scores.keys())
    s0, s1 = scores[agents[0]], scores[agents[1]]
    
    if s0 > s1:
        outcome, winner = "win", agents[0]
    elif s1 > s0:
        outcome, winner = "win", agents[1]
    else:
        outcome, winner = "draw", None
    
    patterns = state["game"]["context"]["patterns"]
    coop_rate = state["game"]["context"]["cooperation_rate"]
    rounds = state["game"]["context"]["rounds_played"]
    
    summary = f"{scores[agents[0]]}-{scores[agents[1]]} after {rounds} rounds. "
    summary += f"Mutual cooperation: {patterns['mutual_cooperate']}, "
    summary += f"Mutual defection: {patterns['mutual_defect']}, "
    summary += f"Betrayals: {patterns['betrayals']}"
    
    return {
        "outcome": outcome,
        "winner": winner,
        "scores": {a: float(s) for a, s in scores.items()},
        "summary": summary,
        "analysis": {
            "cooperation_rates": coop_rate,
            "patterns": patterns,
        },
    }
```

### 3.6 `summarize_move(move, agent_id, state)`

```python
def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
    action = move["action"]
    round_num = state["game"]["current"]["round"]
    
    if state["game"]["current"]["pending_move"] is None:
        return f"Round {round_num}: chose to {action}"
    else:
        # This is the resolving move
        first = state["game"]["current"]["pending_move"]
        p1, p2 = self.PAYOFF_MATRIX[(first["action"], action)]
        return f"Round {round_num}: chose to {action} (resolved: {first['action']}/{action} → {p1}/{p2})"
```

### 3.7 `get_evaluation_schema()`

```python
def get_evaluation_schema(self) -> dict:
    return {
        "description": "Evaluate strategic and social behavior in the Trust Game",
        "fields": {
            "strategy_type": "Classify the overall strategy: tit-for-tat, always-cooperate, always-defect, random, grudger, pavlov, or other. Explain.",
            "adaptability": "1-5: Did the agent adapt its strategy based on the opponent's behavior?",
            "exploitation": "Did the agent exploit cooperative behavior? How?",
            "retaliation": "How did the agent respond to defection?",
            "forgiveness": "After mutual defection, did the agent attempt to restore cooperation?",
            "consistency": "1-5: How consistent was the agent's strategy across rounds?",
            "overall_comment": "Free text assessment of the agent's social behavior.",
        },
    }
```

---

## 4. Rules File: `games/trustgame/rules.md`

```markdown
# Trust Game — LxM Game Rules

## Overview

You and your opponent play multiple rounds of a trust game. Each round, you both simultaneously choose to **cooperate** or **defect**. Your goal is to maximize your total score.

## Payoff Matrix

```
                Opponent
              Cooperate  Defect
You
  Cooperate    3, 3      0, 5
  Defect       5, 0      1, 1
```

- Both cooperate: you each get 3 points
- Both defect: you each get 1 point
- You defect, they cooperate: you get 5, they get 0
- You cooperate, they defect: you get 0, they get 5

## How It Works

Each round has two phases:
1. You submit your choice (you don't see the opponent's current choice)
2. After both agents have chosen, the round resolves and both choices are revealed

You can see all previous rounds' choices in `state.json` → `game.context.history`.

## Move Format

Your `move` object must be:

```json
{
  "type": "choice",
  "action": "cooperate"
}
```

or

```json
{
  "type": "choice",
  "action": "defect"
}
```

Only two valid actions: `"cooperate"` or `"defect"`.

## Game State

`state.json` → `game.current`:
- `round`: Current round number
- `scores`: Running total for each agent

`state.json` → `game.context`:
- `history`: Array of all resolved rounds with both agents' choices and payoffs
- `cooperation_rate`: Each agent's cooperation percentage so far
- `patterns`: Count of mutual cooperations, mutual defections, and betrayals

## Strategy Considerations

- Mutual cooperation (3+3=6) produces more total value than mutual defection (1+1=2)
- But defecting against a cooperator gives the highest individual payoff (5)
- The game lasts multiple rounds — your opponent will see your past choices
- Building trust can lead to sustained mutual cooperation (3 per round)
- Betrayal may give short-term gain but can trigger retaliation

## Game Length

The number of rounds is not revealed to you. Play as if the game could end at any time.

## Evaluation

After the game, evaluate on these axes:
- **strategy_type**: Classify the strategy (tit-for-tat, always-cooperate, always-defect, etc.)
- **adaptability** (1-5): Did the agent adapt to the opponent?
- **exploitation**: Did the agent exploit cooperative behavior?
- **retaliation**: How did the agent respond to defection?
- **forgiveness**: Did the agent try to restore cooperation after conflict?
- **consistency** (1-5): How consistent was the strategy?
- **overall_comment**: Free text assessment
```

---

## 5. Viewer Renderer: `viewer/static/renderers/trustgame.js`

### Visual Design

The Trust Game viewer shows the strategic interaction visually:

```
┌─────────────────────────────────────────────────┐
│  Round 12                                        │
│                                                  │
│  ┌──────────────┐    ┌──────────────┐           │
│  │ claude-alpha  │    │ claude-beta   │           │
│  │   Score: 28   │    │   Score: 31   │           │
│  │              │    │              │           │
│  │  COOPERATE   │    │   DEFECT     │           │
│  │   🤝         │    │   🗡️         │           │
│  └──────────────┘    └──────────────┘           │
│                                                  │
│  Payoff: 0 ←──────────────────→ 5               │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │ History:  C C D C C C C D C C C D       │    │
│  │           C C C C D C C C C D C D       │    │
│  │           ✓ ✓ ✗ · ✗ ✓ ✓ ✗ · ✗ ✓ ✗      │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  Cooperation: α 67%  β 58%                      │
│  Mutual coop: 7 | Mutual defect: 2 | Betrayals: 3│
└─────────────────────────────────────────────────┘
```

### Key Visual Elements

**Agent cards:** Each agent's name, running score, and current round choice. Choice displayed with color and icon:
- Cooperate: green background, handshake icon 🤝
- Defect: red background, dagger icon 🗡️

**History strip:** A compact row per agent showing all past choices:
- C = cooperate (green dot), D = defect (red dot)
- Third row: ✓ = mutual cooperate, ✗ = any defection, middle dot = asymmetric

**Statistics bar:** Cooperation rates, pattern counts.

**Payoff animation:** When a round resolves, briefly flash the payoff numbers (+3, +5, +0, +1) near each agent.

### State Reconstruction

```javascript
class TrustGameRenderer {
    initialState(matchConfig) {
        const agents = matchConfig.agents.map(a => a.agent_id);
        return {
            round: 1,
            scores: { [agents[0]]: 0, [agents[1]]: 0 },
            history: [],
            pendingMove: null,
        };
    }

    applyMove(state, logEntry) {
        // Use post_move_state from log entry
        const gameState = logEntry.post_move_state;
        return {
            round: gameState.current.round,
            scores: gameState.current.scores,
            history: gameState.context.history,
            pendingMove: gameState.current.pending_move,
        };
    }

    render(state, turnNumber, lastMove) {
        // Draw agent cards, history strip, stats
    }

    formatMoveSummary(logEntry) {
        const action = logEntry.envelope.move.action;
        return action === "cooperate" ? "🤝 Cooperate" : "🗡️ Defect";
    }
}
```

---

## 6. Video Export: `viewer/exporters/trustgame.py`

### Frame Layout (800×600)

```
┌────────────────────────────────────┐
│  Trust Game — Round 12/??          │
│  claude-alpha vs claude-beta       │
├────────────────────────────────────┤
│                                    │
│  [COOPERATE]      [DEFECT]         │
│   claude-α         claude-β        │
│   Score: 28        Score: 31       │
│   Payoff: +0       Payoff: +5      │
│                                    │
│  History:                          │
│  α: C C D C C C C D C C C D       │
│  β: C C C C D C C C C D C D       │
│                                    │
│  Coop rate: α 67% | β 58%         │
├────────────────────────────────────┤
│  LxM — Ludus Ex Machina           │
└────────────────────────────────────┘
```

Color-coded: cooperate actions in green, defect actions in red.

---

## 7. Match Configuration

```json
{
  "game": {
    "name": "trustgame",
    "version": "1.0"
  },
  "time_model": {
    "type": "turn_based",
    "turn_order": "sequential",
    "max_turns": 40,
    "timeout_seconds": 60,
    "timeout_action": "no_op",
    "max_retries": 2
  },
  "history": {
    "recent_moves_count": 10
  }
}
```

- `max_turns: 40` = 20 rounds (2 turns per round, one per agent)
- `timeout_action: "no_op"` → if an agent times out, it plays "cooperate" by default (generous interpretation)
- Shorter timeout (60s) since the decision is simple

### CLI Usage

```bash
python scripts/run_match.py --game trustgame --agents claude-alpha claude-beta
python scripts/run_match.py --game trustgame --agents claude-alpha claude-beta --model haiku
```

---

## 8. Simultaneous Move — Key Design Detail

The critical implementation detail: **Agent B must NOT see Agent A's current-round choice.**

When it's Agent B's turn (Phase 2 of a round), the state.json that Agent B reads must show:

```json
{
  "game": {
    "current": {
      "round": 12,
      "phase": "choose",
      "pending_move": "submitted",
      "scores": { "claude-alpha": 28, "claude-beta": 31 }
    }
  }
}
```

Note: `pending_move` is `"submitted"` (a string), NOT the actual move object. Agent B knows A has submitted but not what A chose.

**Implementation:** The orchestrator already passes the full state to the engine's methods. The engine needs to provide a `get_agent_state()` or the orchestrator needs to filter `pending_move` before writing state.json for Agent B.

**Simplest approach:** Add a method to the engine or handle in orchestrator:

```python
# In orchestrator, before invoking Agent B:
if state["game"]["current"]["pending_move"] is not None:
    # Replace actual move with "submitted" marker
    filtered_state = deep_copy(state)
    filtered_state["game"]["current"]["pending_move"] = "submitted"
    write_state_json(filtered_state)
```

This is a **minor orchestrator change** — just filtering one field before writing state.json. Not a structural change. The orchestrator already writes state.json before each invocation; it just needs to conditionally mask one field.

**This is the seed of per-agent state filtering that Codenames (Step 2) will fully develop.** Document it as such so Cody knows this is a stepping stone.

---

## 9. Unit Tests

```
test_initial_state              — Scores zero, round 1, no pending move
test_valid_move_cooperate       — "cooperate" accepted
test_valid_move_defect          — "defect" accepted
test_invalid_move_type          — Wrong type rejected
test_invalid_action             — "betray" rejected (must be cooperate/defect)
test_apply_first_move           — Pending move set, scores unchanged
test_apply_second_move_cc       — Both cooperate: 3, 3
test_apply_second_move_cd       — Cooperate vs defect: 0, 5
test_apply_second_move_dc       — Defect vs cooperate: 5, 0
test_apply_second_move_dd       — Both defect: 1, 1
test_round_advances             — After resolution, round increments
test_history_tracking           — History array grows correctly
test_cooperation_rate           — Rates calculated correctly after N rounds
test_pattern_tracking           — mutual_cooperate/defect/betrayals counted
test_is_over_not_yet            — False before max rounds
test_is_over_complete           — True at max rounds
test_get_result_win             — Higher score wins
test_get_result_draw            — Equal scores = draw
test_state_filtering            — pending_move masked to "submitted" for second agent
test_summarize_move             — Correct summary for both phases
```

### Integration Test with MockAdapter

```
test_full_game_tit_for_tat      — Agent A always cooperates first, then copies B's last move.
                                  Agent B always defects.
                                  Expected: A cooperates round 1, defects rounds 2+.
                                  Verify scores match payoff matrix.

test_full_game_mutual_cooperate — Both agents always cooperate.
                                  Verify: 3×N points each after N rounds.
```

---

## 10. Model Medicine Data Value

Trust Game generates unique behavioral data not available from Chess or other games:

**Cooperation propensity:** Does the model default to cooperate or defect? This is a Core-level trait — different models may have different baselines due to RLHF training (cooperative models vs. reward-maximizing models).

**Retaliation pattern:** After being defected against, how quickly does the model defect back? Classic strategies like tit-for-tat, grudger, or generous-tit-for-tat can be directly identified.

**Forgiveness:** After mutual defection, does the model try to restore cooperation? How many rounds of mutual defection before it tries a cooperative signal?

**Strategic adaptation:** Does the model change strategy based on observed opponent patterns? A model that plays the same way regardless of opponent is not adapting (low Reactivity). A model that shifts strategy mid-game shows adaptation.

**These map directly to MTI axes:**
- Cooperation propensity → Sociality
- Retaliation speed → Reactivity
- Strategic consistency → Compliance
- Forgiveness → Resilience

**Cross-model comparison:** Run the same matchups across Haiku/Sonnet/Opus. Hypothesis: RLHF-heavier models may cooperate more (trained to be "nice") while reasoning-heavier models may defect more (calculated utility maximization). This is directly testable.

---

## 11. Implementation Order

```
Step 1: games/trustgame/engine.py + rules.md + tests
        → All engine methods working, unit tests passing.

Step 2: Orchestrator state filtering (pending_move masking)
        → Minor change: mask pending_move to "submitted" for second agent.
        → Document as precursor to full per-agent state (Codenames).

Step 3: viewer/static/renderers/trustgame.js
        → History strip, agent cards, cooperation stats.

Step 4: viewer/exporters/trustgame.py
        → Frame renderer for GIF/MP4.

Step 5: Integration test
        → Two Claude Code instances play 20 rounds.
        → Verify in viewer: history, scores, cooperation rates all visible.
```

**Success criteria:** Two agents complete a 20-round Trust Game. All moves are valid. The viewer shows the history strip with cooperation/defection choices color-coded. Post-game evaluation correctly classifies the strategies used.

---

*LxM Trust Game Spec v0.1*
*"In the long run, trust is the best strategy — but can a machine learn that?"*
