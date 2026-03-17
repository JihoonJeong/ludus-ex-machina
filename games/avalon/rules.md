# Avalon — Game Rules

You are playing **The Resistance: Avalon**, a social deduction game.

## Overview

- **5-10 players**, each secretly assigned **Good** or **Evil**
- Evil players know who each other are. Good players don't.
- Play up to **5 Quests**. Each Quest has a team that goes on a mission.
- **Good wins** if 3 Quests succeed. **Evil wins** if 3 Quests fail OR 5 consecutive proposals are rejected.

## Roles

- **Good (Loyal Servants of Arthur)**: You want Quests to succeed. You do NOT know who is Evil.
- **Evil (Minions of Mordred)**: You want Quests to fail. You KNOW who all Evil players are.

### Role Distribution

| Players | Good | Evil |
|---------|------|------|
| 5       | 3    | 2    |
| 6       | 4    | 2    |
| 7       | 4    | 3    |

## Game Flow

Each Quest goes through 4 phases:

### Phase 1: PROPOSE

The current **Leader** proposes a team of players for the Quest.

```json
{"type": "proposal", "team": ["player_a", "player_b"]}
```

Team size depends on the Quest number (see table below).

### Phase 2: VOTE

**All** players simultaneously vote to approve or reject the proposed team.

```json
{"type": "vote", "choice": "approve"}
```
or
```json
{"type": "vote", "choice": "reject"}
```

- **Majority approve**: Team goes on the Quest.
- **Majority reject**: Leadership passes clockwise. New proposal.
- **5 consecutive rejections**: Evil wins automatically!

During voting, you cannot see how others voted until all votes are collected.

### Phase 3: QUEST

Approved team members secretly choose their action:

```json
{"type": "quest_action", "choice": "success"}
```
or (Evil only):
```json
{"type": "quest_action", "choice": "sabotage"}
```

- **Good players MUST play "success"**. They cannot sabotage.
- **Evil players choose**: "success" (to stay hidden) or "sabotage" (to fail the quest).
- If **all** play success → Quest succeeds (Good point).
- If **any** play sabotage → Quest fails (Evil point).

The number of sabotages is revealed, but NOT who sabotaged.

### Phase 4: RESULT

Quest outcome is revealed. If neither side has 3 wins, the next Quest begins with leadership passing clockwise.

## Quest Team Sizes (5 players)

| Quest | Team Size |
|-------|-----------|
| 1     | 2         |
| 2     | 3         |
| 3     | 2         |
| 4     | 3         |
| 5     | 3         |

## Win Conditions

- **Good wins**: 3 Quests succeed
- **Evil wins**: 3 Quests fail OR 5 consecutive proposal rejections

## State Information

In `state.json`, you can see:
- `quest_number`: Current quest (1-5)
- `phase`: Current phase (propose/vote/quest/result)
- `leader`: Who is proposing the team
- `proposed_team`: The proposed team (during vote/quest phases)
- `quest_results`: Array of past quest outcomes (true=success, false=fail)
- `consecutive_rejections`: How many proposals have been rejected in a row
- `players`: All players and their status
  - If you are **Evil**: You see everyone's role
  - If you are **Good**: Other players' roles appear as "unknown"

## Strategy Tips

### As Good:
- Track voting patterns. Evil players tend to approve teams with other Evil on them.
- If a quest fails with 2 people, one of them is Evil.
- Propose teams with players who have been on successful quests.

### As Evil:
- Early game: Vote like a Good player. Build trust.
- Consider playing "success" early to avoid suspicion.
- Sabotage strategically — too early and you'll be caught.
- Watch the rejection counter — sometimes letting proposals through is better than reaching 5 rejections too obviously.

## Move Format

All moves use the standard LxM envelope:

```json
{
  "protocol": "lxm-v0.2",
  "match_id": "...",
  "agent_id": "...",
  "turn": 0,
  "move": {
    "type": "proposal" | "vote" | "quest_action",
    ...
  }
}
```
