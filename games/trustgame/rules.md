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
