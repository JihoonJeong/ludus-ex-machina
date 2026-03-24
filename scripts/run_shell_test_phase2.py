"""Phase 2: Parameter Sweep — Poker pre_flop_threshold

6 values × 5 games = 30 games
Opponent: no-shell Sonnet (fixed)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.shell.manager import ShellManager
from lxm.shell.tester import ShellTester

manager = ShellManager()
tester = ShellTester(opponent_adapter="claude", opponent_model="sonnet")

# Create TAG shell
tag_shell = manager.create_shell("poker", template="tight_aggressive")

print("=" * 60)
print("  PHASE 2: Parameter Sweep — pre_flop_threshold")
print("  6 values × 5 games = 30 games")
print("  Opponent: no-shell Sonnet (fixed)")
print("=" * 60)

result = tester.parameter_sweep(
    shell=tag_shell,
    param_name="pre_flop_threshold",
    values=["top 10%", "top 15%", "top 20%", "top 30%", "top 40%", "top 50%"],
    game="poker",
    n_games=5,
    agent_id="sweep-agent",
    adapter="claude",
    model="sonnet",
    opponent_id="baseline",
    verbose=True,
)

tester.save_report(result, "reports/phase2_sweep_pre_flop_threshold.json")

print("\n" + "=" * 60)
print("  PHASE 2 SUMMARY")
print("=" * 60)
print(f"\nBest: {result.best_value} (win rate: {result.best_win_rate:.0%})")
print(f"\nAll results:")
for p in result.points:
    marker = " ← BEST" if p.param_value == result.best_value else ""
    beh = ""
    if p.behavior.metrics:
        fold = p.behavior.metrics.get("fold", 0)
        raise_ = p.behavior.metrics.get("raise", 0)
        beh = f" | fold={fold:.0%} raise={raise_:.0%}"
    print(f"  {p.param_value}: {p.win_rate:.0%} ({p.n_games} games){beh}{marker}")
