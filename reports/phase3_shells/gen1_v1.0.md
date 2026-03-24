# Poker Strategy: Tight-Aggressive v1.0

## Parameters
- pre_flop_threshold: top 20%
- bluff_frequency: 1 per 5 hands
- position_bluff_only: true
- continuation_bet: 70%

## Strategy
Pre-flop: Play only the top 20% of hands. Fold everything else without hesitation.
Post-flop: If you hit the flop, bet aggressively. If you miss, fold to any bet.
Position: Use late position to steal blinds with wider range.

## Situational Rules
- Stack below 20BB: switch to push-or-fold mode
- Opponent folded 3+ times in a row: increase bluff frequency
- Heads-up with strong draw: semi-bluff with a raise
