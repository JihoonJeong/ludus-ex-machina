<!--
Changes v1.0 → v1.1:
1. Loosened pre-flop threshold (20%→30%) to build stack faster; hand_limit losses suggest too few chips accumulated
2. Increased continuation bet sizing (70%→80%) for more aggressive pot control
3. Added short-stack aggression rule: push wider range (top 35%) when <15BB to avoid blinding out
-->

# Poker Strategy: Tight-Aggressive v1.1

## Parameters
- pre_flop_threshold: top 30%
- bluff_frequency: 1 per 5 hands
- position_bluff_only: true
- continuation_bet: 80%

## Strategy
Pre-flop: Play only the top 30% of hands. Fold everything else without hesitation.
Post-flop: If you hit the flop, bet aggressively. If you miss, fold to any bet.
Position: Use late position to steal blinds with wider range.

## Situational Rules
- Stack below 15BB: switch to push-or-fold mode with top 35% of hands
- Stack below 20BB: switch to push-or-fold mode
- Opponent folded 3+ times in a row: increase bluff frequency
- Heads-up with strong draw: semi-bluff with a raise