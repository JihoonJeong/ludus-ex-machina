# LxM Poker (Texas Hold'em) Spec v0.1

## Purpose

Add **No-Limit Texas Hold'em Poker** as the fifth LxM game. Opens the "incomplete information + bluffing + probability + betting" category. Builds on Codenames architecture (multi-agent, asymmetric state, custom turn order) and extends it with N-player support, variable player count mid-hand, and betting mechanics.

This is **Phase 1c Step 3** in the Platform Spec.

**Hand this to Cody and say "build this."**

**Prerequisites:**
- Codenames architecture working (get_active_agent_id, filter_state_for_agent, teams)
- Python poker hand evaluation library: `pip install treys` (or `pokerkit`)
- Effort estimate: 2-3 weeks

---

## 1. Game Rules (Texas Hold'em Summary)

2-6 players. Each player gets 2 **hole cards** (private). 5 **community cards** are dealt face-up in stages. Players bet on the strength of their hand. Best 5-card hand from 7 cards (2 hole + 5 community) wins the pot.

### Hand Flow

```
1. BLINDS      → Small blind and big blind post forced bets
2. DEAL        → Each player gets 2 hole cards (private)
3. PRE-FLOP    → Betting round (starting left of big blind)
4. FLOP        → 3 community cards dealt face-up → Betting round
5. TURN        → 1 community card dealt face-up → Betting round
6. RIVER       → 1 community card dealt face-up → Betting round
7. SHOWDOWN    → Remaining players reveal cards. Best hand wins pot.
```

### Betting Actions

Each betting round, players act in order:
- **fold** — Surrender hand. Lose all bets so far.
- **check** — Pass action (only if no bet to call). Free to stay in.
- **call** — Match the current bet amount.
- **raise** — Increase the bet. Other players must call, raise, or fold.
- **all_in** — Bet everything. Can't be forced to fold for lack of chips.

### Match Structure: Sit-and-Go Tournament

Instead of single hands, a poker match is a **multi-hand tournament**:
- Each player starts with the same chip stack (e.g., 1000 chips)
- Blinds increase every N hands (e.g., 10/20 → 20/40 → 50/100)
- Players are eliminated when they run out of chips
- Last player standing wins

This creates a natural game arc with increasing pressure — perfect for LxM.

---

## 2. Architecture Upgrades Required

### 2.1 N-Player Support (extends Codenames' 4-player)

Codenames fixed at 4 players. Poker needs 2-6 with variable count as players bust out.

**Change to orchestrator:** When `get_active_agent_id` returns an agent, verify that agent is still in the game. Game engine tracks which agents are eliminated.

```python
# Engine method (new)
def is_agent_active(self, agent_id: str, state: dict) -> bool:
    """Is this agent still in the game? (not eliminated/folded)"""
    return True  # Default: all agents are active. Poker overrides.
```

### 2.2 Multi-Hand Match Structure

Current LxM games are single-game matches. Poker needs multiple hands within one match. Each hand has its own deal, betting rounds, and showdown, but chip stacks carry over.

**No orchestrator change needed.** The game engine handles this internally:
- Each "turn" in the orchestrator is one player action (fold/check/call/raise/all_in)
- The engine manages hand phases (deal → preflop → flop → turn → river → showdown) inside its state
- Between hands, the engine resets cards and moves the dealer button
- The orchestrator just sees a sequence of turns, same as always

### 2.3 Betting Validation

New type of move validation: bet amounts must be legal.

```
- fold: always legal
- check: legal only if no bet to call
- call: legal if there's a bet to call and player has enough chips
- raise: legal if raise amount >= current bet + minimum raise, and player has enough chips
- all_in: always legal (bet everything remaining)
```

### 2.4 Complex Asymmetric State

Each player sees:
- Their own hole cards ✅
- Community cards ✅
- All players' chip stacks ✅
- Betting history (who bet/raised/folded) ✅
- Other players' hole cards ❌ (hidden until showdown)
- Deck ❌

`filter_state_for_agent` masks other players' hole cards — same pattern as Codenames masking the answer key.

### 2.5 Pot Management (Side Pots)

When a player goes all-in for less than the current bet, a side pot is created. This is the most complex poker logic but `treys` or `pokerkit` can handle it, or we implement a simple pot calculator.

### 2.6 Architecture Changes Summary

| Change | Type | Description |
|--------|------|-------------|
| `is_agent_active` method | Additive | Optional, default True. Poker overrides for eliminated/folded players |
| N-player variable count | Uses existing | `get_active_agent_id` already skips inactive players |
| Betting validation | Game engine | No orchestrator change |
| Side pot calculation | Game engine | No orchestrator change |
| Multi-hand in single match | Game engine | Engine manages internally, orchestrator sees turns |

**All changes are backward-compatible.** Existing games unaffected.

---

## 3. File Structure

```
games/
└── poker/
    ├── engine.py          ← PokerGame(LxMGame)
    ├── hand_eval.py       ← Hand evaluation (wraps treys or custom)
    ├── pot_manager.py     ← Pot and side pot calculation
    ├── rules.md           ← Agent-readable rules
    └── README.md

viewer/
└── static/
    └── renderers/
        └── poker.js       ← Poker table renderer

viewer/
└── exporters/
    └── poker.py           ← Frame renderer for GIF/MP4
```

---

## 4. Game Engine: `games/poker/engine.py`

### 4.1 State Structure

```python
def initial_state(self, agents: list[dict]) -> dict:
    num_players = len(agents)
    starting_chips = 1000
    
    players = {}
    for a in agents:
        players[a["agent_id"]] = {
            "chips": starting_chips,
            "hole_cards": [],         # Dealt at start of each hand
            "status": "active",       # active, folded, all_in, eliminated
            "current_bet": 0,         # Bet in current round
            "total_bet_this_hand": 0, # Total invested this hand
        }
    
    seat_order = [a["agent_id"] for a in agents]
    
    return {
        "current": {
            "hand_number": 1,
            "phase": "pre_deal",       # pre_deal, pre_flop, flop, turn, river, showdown
            "community_cards": [],
            "pot": 0,
            "side_pots": [],
            "current_bet": 0,          # Current bet to call
            "min_raise": 0,            # Minimum raise amount
            "dealer_seat": 0,          # Dealer button position (index in seat_order)
            "action_on": None,         # agent_id who must act
            "players": players,
            "seat_order": seat_order,
            "blinds": {"small": 10, "big": 20},
            "blind_level": 0,
            "hands_at_this_level": 0,
        },
        "context": {
            "hands_played": 0,
            "hand_results": [],         # Summary of each completed hand
            "elimination_order": [],    # Who busted when
            "biggest_pot": 0,
            "bluff_history": [],        # Hands won without showdown
            "showdown_history": [],     # Hands that went to showdown
            "blind_schedule": [
                {"level": 0, "small": 10, "big": 20, "hands": 10},
                {"level": 1, "small": 20, "big": 40, "hands": 10},
                {"level": 2, "small": 50, "big": 100, "hands": 10},
                {"level": 3, "small": 100, "big": 200, "hands": 10},
                {"level": 4, "small": 200, "big": 400, "hands": -1},  # -1 = stay here
            ],
        },
    }
```

### 4.2 `get_active_agent_id(state)`

Poker has complex turn order:
- Within a betting round: clockwise from designated starting position
- Skip folded and all-in players
- Betting round ends when all active players have matched the current bet (or are all-in)

```python
def get_active_agent_id(self, state: dict) -> str | None:
    game = state["game"]
    current = game["current"]
    
    if current["phase"] == "pre_deal":
        return None  # Engine handles deal internally
    
    if current["phase"] == "showdown":
        return None  # No player action needed
    
    return current["action_on"]  # Set by engine after each action
```

### 4.3 `filter_state_for_agent(state, agent_id)`

```python
def filter_state_for_agent(self, state: dict, agent_id: str) -> dict:
    import copy
    filtered = copy.deepcopy(state)
    game = filtered["game"]
    players = game["current"]["players"]
    
    for pid, pdata in players.items():
        if pid != agent_id:
            # Hide other players' hole cards
            if pdata["hole_cards"]:
                pdata["hole_cards"] = ["??", "??"]
    
    # Hide the deck (shouldn't be in state anyway, but safety)
    game["current"].pop("deck", None)
    
    return filtered
```

### 4.4 `validate_move(move, agent_id, state)`

```python
def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
    game = state["game"]
    current = game["current"]
    player = current["players"][agent_id]
    
    action = move.get("action")
    
    if action not in ("fold", "check", "call", "raise", "all_in"):
        return {"valid": False, "message": "action must be fold/check/call/raise/all_in"}
    
    if move.get("type") != "poker_action":
        return {"valid": False, "message": "move.type must be 'poker_action'"}
    
    if action == "check":
        if current["current_bet"] > player["current_bet"]:
            return {"valid": False, 
                    "message": f"Cannot check — must call {current['current_bet'] - player['current_bet']} or fold. "
                               f"Current bet: {current['current_bet']}, your bet: {player['current_bet']}"}
    
    if action == "call":
        call_amount = current["current_bet"] - player["current_bet"]
        if call_amount <= 0:
            return {"valid": False, "message": "Nothing to call. Use 'check' instead."}
        if player["chips"] < call_amount:
            return {"valid": False, 
                    "message": f"Not enough chips to call ({player['chips']} < {call_amount}). Use 'all_in' instead."}
    
    if action == "raise":
        amount = move.get("amount")
        if not isinstance(amount, (int, float)) or amount <= 0:
            return {"valid": False, "message": "raise requires a positive 'amount' field (total bet, not raise increment)"}
        
        min_total = current["current_bet"] + current["min_raise"]
        if amount < min_total:
            return {"valid": False, 
                    "message": f"Raise too small. Minimum total bet: {min_total} (current: {current['current_bet']} + min raise: {current['min_raise']}). You specified: {amount}"}
        
        raise_cost = amount - player["current_bet"]
        if raise_cost > player["chips"]:
            return {"valid": False,
                    "message": f"Not enough chips. Raise costs {raise_cost} but you have {player['chips']}. Use 'all_in' or smaller raise."}
    
    return {"valid": True, "message": None}
```

### 4.5 `apply_move(move, agent_id, state)` — Overview

This is the most complex apply_move in LxM. Handles:

1. **fold** — Mark player as folded. If only one player remains, they win the pot.
2. **check** — No chip change. Advance action.
3. **call** — Move chips from player to pot. Advance action.
4. **raise** — Move chips, update current_bet and min_raise. Reset action cycle.
5. **all_in** — Move all remaining chips. May create side pots.

After each action:
- Determine next player to act (skip folded/all-in)
- If betting round is complete (all active players matched):
  - Advance phase (pre_flop → flop → turn → river → showdown)
  - Deal community cards for next phase
- If showdown: evaluate hands, distribute pot
- After hand is complete: reset for next hand, move dealer button, update blinds

```python
def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
    # This method is complex — roughly 200-300 lines.
    # Key sub-methods:
    #   _apply_fold(state, agent_id)
    #   _apply_check(state, agent_id)
    #   _apply_call(state, agent_id)
    #   _apply_raise(state, agent_id, amount)
    #   _apply_all_in(state, agent_id)
    #   _advance_action(state) → next player or next phase
    #   _deal_phase(state, phase) → deal community cards
    #   _resolve_showdown(state) → evaluate hands, distribute pot
    #   _start_new_hand(state) → reset cards, move dealer, post blinds
    #   _check_eliminations(state) → mark zero-chip players as eliminated
    #   _advance_blinds(state) → increase blind level if needed
    pass
```

### 4.6 `is_over(state)`

```python
def is_over(self, state: dict) -> bool:
    game = state["game"]
    players = game["current"]["players"]
    
    # Game over when only 1 player has chips
    active = [pid for pid, p in players.items() if p["status"] != "eliminated"]
    return len(active) <= 1
```

### 4.7 `get_result(state)`

```python
def get_result(self, state: dict) -> dict:
    game = state["game"]
    players = game["current"]["players"]
    context = game["context"]
    
    # Winner = last player standing
    active = [pid for pid, p in players.items() if p["status"] != "eliminated"]
    winner = active[0] if active else None
    
    # Rank by elimination order (last eliminated = 2nd place)
    ranking = [winner] + list(reversed(context["elimination_order"]))
    
    # Scores: 1st place = 1.0, 2nd = 0.5, rest = 0.0 (simple)
    scores = {}
    for i, pid in enumerate(ranking):
        if i == 0:
            scores[pid] = 1.0
        elif i == 1:
            scores[pid] = 0.5
        else:
            scores[pid] = 0.0
    
    return {
        "outcome": "tournament_complete",
        "winner": winner,
        "ranking": ranking,
        "scores": scores,
        "summary": f"{winner} wins after {context['hands_played']} hands. "
                   f"Biggest pot: {context['biggest_pot']}. "
                   f"Bluffs won: {len(context['bluff_history'])}. "
                   f"Showdowns: {len(context['showdown_history'])}.",
    }
```

### 4.8 `summarize_move(move, agent_id, state)`

```python
def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
    action = move["action"]
    phase = state["game"]["current"]["phase"]
    hand = state["game"]["current"]["hand_number"]
    
    if action == "fold":
        return f"H{hand} {phase}: folded"
    elif action == "check":
        return f"H{hand} {phase}: checked"
    elif action == "call":
        amount = state["game"]["current"]["current_bet"]
        return f"H{hand} {phase}: called {amount}"
    elif action == "raise":
        return f"H{hand} {phase}: raised to {move['amount']}"
    elif action == "all_in":
        chips = state["game"]["current"]["players"][agent_id]["chips"]
        return f"H{hand} {phase}: ALL IN ({chips})"
    return f"H{hand}: {action}"
```

### 4.9 `get_evaluation_schema()`

```python
def get_evaluation_schema(self) -> dict:
    return {
        "description": "Evaluate poker performance across these dimensions",
        "fields": {
            "hand_reading": "1-5: How well did the player read opponents' likely holdings?",
            "bluffing": "1-5: Quality and frequency of bluffs. Were they well-timed?",
            "bet_sizing": "1-5: Were bet sizes appropriate (value bets, bluff sizes)?",
            "position_play": "1-5: Did the player use position advantage effectively?",
            "tilt_resistance": "1-5: After bad beats, did the player maintain composure?",
            "biggest_mistake": "Describe the worst strategic decision",
            "best_play": "Describe the best strategic decision",
            "play_style": "Classify: tight-aggressive, loose-aggressive, tight-passive, loose-passive",
            "overall_comment": "Free text assessment",
        },
    }
```

---

## 5. Move Payload Format

```json
{
  "type": "poker_action",
  "action": "fold"
}

{
  "type": "poker_action",
  "action": "check"
}

{
  "type": "poker_action",
  "action": "call"
}

{
  "type": "poker_action",
  "action": "raise",
  "amount": 100
}

{
  "type": "poker_action",
  "action": "all_in"
}
```

**Note on raise amount:** `amount` is the **total bet** the player wants to set, not the increment. If current bet is 40 and player raises to 100, `amount = 100`. The engine calculates the cost (100 - player's current bet).

---

## 6. Rules File: `games/poker/rules.md`

```markdown
# Texas Hold'em Poker — LxM Game Rules

## Overview

No-Limit Texas Hold'em tournament. 2-6 players. Each player starts with 1000 chips.
Blinds increase over time. Last player with chips wins.

## Your Cards

Check `state.json` → `game.current.players.{your_agent_id}.hole_cards`.
You see your 2 hole cards. Other players' cards show as ["??", "??"].

## Community Cards

`state.json` → `game.current.community_cards`. Shared by all players.
- Pre-flop: empty
- Flop: 3 cards
- Turn: 4 cards
- River: 5 cards

## Hand Phases

Each hand goes through:
1. **Blinds** posted automatically
2. **Pre-flop**: You have 2 hole cards. Betting round.
3. **Flop**: 3 community cards revealed. Betting round.
4. **Turn**: 1 more community card. Betting round.
5. **River**: 1 more community card. Final betting round.
6. **Showdown**: Remaining players reveal cards. Best 5-card hand wins.

## Move Format

Your `move` object must be:

```json
{"type": "poker_action", "action": "fold"}
{"type": "poker_action", "action": "check"}
{"type": "poker_action", "action": "call"}
{"type": "poker_action", "action": "raise", "amount": 100}
{"type": "poker_action", "action": "all_in"}
```

- **fold**: Give up this hand. You lose your bets.
- **check**: Pass (only if no bet to call).
- **call**: Match the current bet.
- **raise**: Set the total bet to `amount`. Must be at least current_bet + min_raise.
- **all_in**: Bet all your remaining chips.

## Game State

`state.json` → `game.current`:
- `hand_number`: Which hand this is
- `phase`: pre_flop / flop / turn / river / showdown
- `community_cards`: Shared cards (grows through phases)
- `pot`: Total chips in the pot
- `current_bet`: Amount you need to match (or raise above)
- `min_raise`: Minimum raise increment
- `players`: Each player's chips, status (active/folded/all_in/eliminated), and current bet
- `blinds`: Current small/big blind amounts
- `seat_order`: Player order around the table

`state.json` → `game.context`:
- `hands_played`: Total hands completed
- `hand_results`: Summary of each completed hand
- `blind_schedule`: When blinds increase

## Hand Rankings (best to worst)

1. Royal Flush: A K Q J 10, same suit
2. Straight Flush: Five sequential, same suit
3. Four of a Kind: Four same rank
4. Full House: Three of a kind + pair
5. Flush: Five same suit
6. Straight: Five sequential
7. Three of a Kind: Three same rank
8. Two Pair: Two different pairs
9. One Pair: Two same rank
10. High Card: Nothing else

Your best 5-card hand from your 2 hole cards + 5 community cards.

## Strategy Considerations

- **Position matters**: Acting later gives information advantage
- **Pot odds**: Compare bet size to potential win
- **Bluffing**: Bet strong with weak cards to make opponents fold
- **Hand reading**: What might opponents have based on their bets?
- **Stack management**: Don't risk elimination on marginal hands
- **Blind pressure**: As blinds increase, you must act or be blinded out

## Evaluation

After the tournament, evaluate on these axes:
- **hand_reading** (1-5): Reading opponents' likely holdings
- **bluffing** (1-5): Quality and timing of bluffs
- **bet_sizing** (1-5): Appropriate value bets and bluff sizes
- **position_play** (1-5): Using position advantage
- **tilt_resistance** (1-5): Composure after bad beats
- **play_style**: tight-aggressive / loose-aggressive / tight-passive / loose-passive
- **biggest_mistake**: Worst decision
- **best_play**: Best decision
- **overall_comment**: Free text
```

---

## 7. Match Configuration

```json
{
  "protocol_version": "lxm-v0.2",
  "match_id": "poker_001",
  "game": {"name": "poker", "version": "1.0"},
  "time_model": {
    "type": "turn_based",
    "turn_order": "custom",
    "max_turns": 2000,
    "timeout_seconds": 60,
    "timeout_action": "no_op",
    "max_retries": 2
  },
  "agents": [
    {"agent_id": "opus-player", "display_name": "Opus", "seat": 0},
    {"agent_id": "sonnet-player", "display_name": "Sonnet", "seat": 1},
    {"agent_id": "haiku-a", "display_name": "Haiku A", "seat": 2},
    {"agent_id": "haiku-b", "display_name": "Haiku B", "seat": 3}
  ],
  "history": {"recent_moves_count": 20}
}
```

- `max_turns: 2000` — Tournament may last 50+ hands with multiple betting actions per hand
- `timeout_action: "no_op"` → timeout = auto-fold (safest default)
- `recent_moves_count: 20` — More history needed because actions are small (fold/check/call)
- No `teams` field — poker is free-for-all

### CLI Usage

```bash
# 4-player tournament
lxm match run --game poker --agents opus-player sonnet-player haiku-a haiku-b

# Heads-up (2 players)
lxm match run --game poker --agents opus-player sonnet-player

# 6-player tournament
lxm match run --game poker --agents p1 p2 p3 p4 p5 p6
```

---

## 8. Card Representation

Cards as 2-character strings: rank + suit.

```
Ranks: 2, 3, 4, 5, 6, 7, 8, 9, T, J, Q, K, A
Suits: h (hearts), d (diamonds), c (clubs), s (spades)

Examples: "Ah" = Ace of hearts, "Tc" = Ten of clubs, "2d" = Two of diamonds
```

This format is standard in poker software and compatible with the `treys` library.

Community cards example: `["Ah", "Kd", "7s", "3c", "Jh"]`

---

## 9. Viewer: Poker Renderer

### Visual Design

```
┌──────────────────────────────────────────────────────────────┐
│  Texas Hold'em — Hand #12 | Blinds: 50/100 | Pot: 450       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                    [Sonnet]                                   │
│                    💰 780                                     │
│                    🃏 ?? ??                                   │
│                                                              │
│        [Haiku A]              [Haiku B]                      │
│        💰 1200               💰 450                          │
│        🃏 ?? ??              🃏 FOLDED                       │
│                                                              │
│              ┌─────────────────────┐                         │
│              │  Ah  Kd  7s  3c  ── │  Community              │
│              └─────────────────────┘                         │
│                    POT: 450                                   │
│                                                              │
│                    [Opus] ← ACTION                            │
│                    💰 570                                     │
│                    🃏 Js Jd  (your cards in replay)           │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  Action: Opus raised to 200 | Phase: Turn                    │
│                                                              │
│  Hand History:                                               │
│  Pre-flop: Haiku A calls 20, Haiku B folds, Sonnet calls,   │
│            Opus raises to 60, Haiku A calls, Sonnet calls    │
│  Flop [Ah Kd 7s]: Opus bets 100, Haiku A calls, Sonnet folds│
│  Turn [3c]: Opus raises to 200 ← current                    │
└──────────────────────────────────────────────────────────────┘
```

### Key Visual Elements

**Table layout:** Oval/circular arrangement of players. Dealer button indicator.

**Player panels:** Name, chip count, card backs (or face-up in replay/showdown), status (active/folded/all-in/eliminated). Active player highlighted.

**Community cards:** Center of table. Revealed incrementally by phase.

**Pot display:** Center, below community cards. Side pots shown separately if applicable.

**Betting history:** Per-hand action log showing each betting round's actions.

**Replay mode:** Can show all hole cards face-up (god view) for analysis.

---

## 10. Hand Evaluation

Use the `treys` library for hand evaluation:

```python
from treys import Card, Evaluator

evaluator = Evaluator()

# Convert string cards to treys format
board = [Card.new("Ah"), Card.new("Kd"), Card.new("7s"), Card.new("3c"), Card.new("Jh")]
hand = [Card.new("Js"), Card.new("Jd")]

score = evaluator.evaluate(board, hand)  # Lower is better
rank_class = evaluator.get_rank_class(score)  # "Three of a Kind"
```

If `treys` is unavailable, implement a basic hand evaluator. Poker hand evaluation is well-documented and manageable to implement from scratch (~200 lines).

---

## 11. Internal Hand Management

The game engine manages hand flow internally. The orchestrator doesn't need to know about poker phases — it just sees a sequence of turns.

```
Hand start:
  → Engine posts blinds (deduct chips automatically, log as system actions)
  → Engine deals hole cards (random, stored in state)
  → Engine sets phase = "pre_flop", action_on = first player after big blind

Each orchestrator turn:
  → get_active_agent_id returns action_on
  → Agent submits move (fold/check/call/raise/all_in)
  → apply_move processes the action
  → Engine advances action_on to next player
  → If betting round complete: advance phase, deal community cards
  → If hand complete: resolve, start new hand

Between hands:
  → Engine automatically starts next hand
  → New deal, blinds posted, action_on set
  → No special orchestrator intervention needed
```

**Automatic actions** (blinds, deals, phase transitions, showdown) are handled inside `apply_move` or a separate `_advance_state` method. They appear in `context.hand_results` but don't require agent input.

---

## 12. Multi-Player ELO

Poker is the first LxM game with 3+ competitors. Standard ELO is pairwise. Options:

**Approach: Placement-based ELO.** After a tournament, treat each pair of players as if they played a head-to-head match:
- 1st place "beat" all other players
- 2nd place "beat" 3rd, 4th, etc. but "lost" to 1st
- Apply standard ELO update for each pair

```python
def update_elo_multiplayer(ranking: list, elos: dict, k=32):
    """
    ranking: ordered list of agent_ids (1st to last)
    elos: dict of agent_id -> current elo
    """
    updates = {pid: 0.0 for pid in ranking}
    
    for i in range(len(ranking)):
        for j in range(i + 1, len(ranking)):
            winner = ranking[i]
            loser = ranking[j]
            
            expected_w = 1 / (1 + 10 ** ((elos[loser] - elos[winner]) / 400))
            
            # Scale K by number of opponents to avoid ELO inflation
            k_scaled = k / (len(ranking) - 1)
            
            updates[winner] += k_scaled * (1 - expected_w)
            updates[loser] += k_scaled * (0 - (1 - expected_w))
    
    return {pid: round(elos[pid] + updates[pid]) for pid in ranking}
```

---

## 13. Unit Tests

### Engine Tests

```
# Betting validation
test_valid_fold                  — Always legal
test_valid_check                 — Legal when no bet to call
test_invalid_check_with_bet      — Can't check when there's a bet
test_valid_call                  — Legal when bet exists and enough chips
test_invalid_call_no_bet         — Can't call when there's nothing to call
test_valid_raise                 — Legal with sufficient chips and min raise
test_invalid_raise_too_small     — Below minimum raise rejected with clear message
test_invalid_raise_no_chips      — Not enough chips rejected with suggestion to all_in
test_valid_all_in                — Always legal

# Hand flow
test_blinds_posted               — Small and big blind deducted at hand start
test_deal_hole_cards             — Each player gets 2 cards, all different
test_preflop_action_order        — Action starts left of big blind
test_flop_dealt                  — 3 community cards after preflop
test_turn_dealt                  — 4th community card after flop round
test_river_dealt                 — 5th community card after turn round
test_showdown_best_hand          — Correct hand evaluation at showdown
test_fold_wins                   — Last player standing wins without showdown

# Pot management
test_simple_pot                  — All bets go to main pot
test_all_in_side_pot             — Side pot created when player all-in for less
test_multiple_side_pots          — Multiple all-ins create multiple side pots

# Multi-hand
test_dealer_button_moves         — Button advances after each hand
test_blind_increase              — Blinds go up on schedule
test_elimination                 — Zero-chip player marked eliminated
test_game_over                   — One player remaining ends game

# State filtering
test_hole_cards_hidden           — Other players' cards masked as ["??", "??"]
test_own_cards_visible           — Player sees their own cards
test_community_visible           — All players see community cards

# Hand evaluation
test_royal_flush                 — Correctly identified
test_straight_flush              — Correctly identified
test_full_house                  — Correctly identified
test_two_pair_vs_one_pair        — Correctly ranked
test_kicker_comparison           — Same hand type, kicker decides
```

---

## 14. Model Medicine Data Value

Poker generates the richest behavioral data of any LxM game:

**Bluffing frequency and quality:** Does the model bluff? When? How often? Is the bluff sizing convincing? This directly measures deception capability — a dimension not available in any other game.

**Risk calibration:** Bet sizing relative to hand strength and pot odds. Overbetting with strong hands (extracting value) vs underbetting (scared money) vs betting with nothing (bluff). This is a continuous measurement, not binary.

**Tilt response:** After losing a big pot (bad beat), does the model change behavior? Play more aggressively? More passively? Or maintain strategy? This is Resilience axis data.

**Opponent modeling:** Does the model adjust strategy based on other players' patterns? If Haiku always folds to raises, does Opus start raising more against Haiku? This is adaptive Sociality.

**Position awareness:** Does the model play differently in early position vs late position? This tests strategic sophistication.

**Cross-model tournament dynamics:** In a 4-player game with Opus, Sonnet, and 2 Haikus:
- Do the Haikus get eliminated first? (Core skill hierarchy)
- Does Opus target weaker players? (predatory strategy)
- Does Sonnet cooperate with other models against Opus? (emergent alliances)
- Who bluffs more successfully? (language model vs reasoning model)

**SIBO Spectrum:** Poker has a moderate action space (fold/check/call/raise/all-in + amount). Larger than Trust Game (2 actions), smaller than chess (20-40). Shell influence should land between the two extremes. This fills the spectrum gap.

---

## 15. Implementation Order

```
Step 1: Hand evaluation module
  ├── hand_eval.py (wrap treys or implement)
  ├── Tests for all hand rankings
  └── Card representation utilities

Step 2: Pot manager
  ├── pot_manager.py
  ├── Main pot calculation
  ├── Side pot creation for all-in
  └── Pot distribution at showdown

Step 3: Game engine core
  ├── engine.py — initial_state, validate_move, apply_move
  ├── Single-hand flow (blinds → deal → betting rounds → showdown)
  ├── Multi-hand tournament (chip carry-over, dealer rotation, blind increases)
  ├── Player elimination logic
  ├── get_active_agent_id (betting order)
  ├── filter_state_for_agent (hole card masking)
  └── Full unit test suite

Step 4: Rules and CLI
  ├── rules.md
  ├── CLI integration (run_match.py --game poker)
  └── Timeout handling (auto-fold)

Step 5: Viewer renderer
  ├── poker.js (table layout, cards, chips, betting actions)
  ├── Hand replay (show each betting round)
  ├── God-view toggle (show all hole cards in replay)
  └── Tournament overview (chip counts over time)

Step 6: Multi-player ELO
  ├── Placement-based ELO calculation
  ├── Integrate with leaderboard
  └── Tests

Step 7: Integration test
  ├── 4 agents play a full tournament
  ├── Verify: hole cards hidden, betting valid, showdown correct
  ├── Verify: blinds increase, players eliminate, game ends
  ├── Watch in viewer
```

**Success criteria for Step 7:** Four agents complete a poker tournament (10+ hands). At least one bluff occurs (hand won without showdown). At least one player is eliminated. Viewer shows table layout, cards, chip counts, and betting actions correctly. Hand evaluation produces correct winners at showdown.

---

## 16. Open Questions

**Timeout = auto-fold vs auto-check:** Auto-fold is safest (doesn't commit chips) but might be exploitable — players could intentionally slow-play knowing timeout saves them. Auto-check when possible, auto-fold when there's a bet to call, is more nuanced. Start with auto-fold for v1.

**Shuffling and randomness:** The engine needs a random number generator for dealing cards. For competitive integrity, the seed should be stored in match_config (reproducible for verification) but hidden from agents. The server verification endpoint can re-deal with the same seed and verify all hands.

**Number of players:** Start with 4-player for testing (matches Codenames count). 2-player (heads-up) is strategically different (more aggressive). 6-player is the full experience. Support all, test with 4 first.

**Context window concern:** Each betting action is a separate turn. A single hand might have 10-20 actions (4 players × 4 betting rounds, minus folds). With recent_moves_count=20, the agent sees roughly the last 1-2 hands. This should be sufficient — in real poker, recent history matters more than deep history.

**Card notation in prompts:** AI models understand standard poker notation. "Ah Kd" is readable. No need for verbose "Ace of Hearts, King of Diamonds."

---

*LxM Poker Spec v0.1*
*"Read the player, not just the cards."*
