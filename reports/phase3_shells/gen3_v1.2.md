<!--
Changes v1.1 → v1.2:
1. Further loosened pre-flop threshold (30%→40%) to win more pots before hand limit
2. Added hand-limit awareness rule: when >60 hands played, loosen to top 50% to maximize chip accumulation
3. Reduced fold-to-miss default — check back more often to see cheap showdowns
-->

# Poker Strategy: Tight-Aggressive v1.2

## Parameters
- pre_flop_threshold: top 40%
- bluff_frequency: 1 per 5 hands
- position_bluff_only: true
- continuation_bet: 80%

## Strategy
Pre-flop: Play only the top 40% of hands. Fold everything else without hesitation.
Post-flop: If you hit the flop, bet aggressively. If you miss, check back when in position rather than auto-folding; fold to large bets only.
Position: Use late position to steal blinds with wider range.

## Situational Rules
- Stack below 15BB: switch to push-or-fold mode with top 35% of hands
- Stack below 20BB: switch to push-or-fold mode
- Hand count > 60: loosen pre-flop to top 50% to maximize chip accumulation before limit
- Opponent folded 3+ times in a row: increase bluff frequency
- Heads-up with strong draw: semi-bluff with a raise