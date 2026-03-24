"""Phase 1: Shell A/B Testing — Poker (3 tests × 5 games each)

Test A: TAG vs no-shell (baseline)
Test B: TAG vs Bluff-Heavy
Test C: Bluff-Heavy vs no-shell

Opponent: no-shell Sonnet (fixed)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.shell.manager import ShellManager
from lxm.shell.tester import ShellTester

manager = ShellManager()
tester = ShellTester(opponent_adapter="claude", opponent_model="sonnet")

# Create shells from templates
tag_shell = manager.create_shell("poker", template="tight_aggressive")
bluff_shell = manager.create_shell("poker", template="bluff_heavy")

N_GAMES = 5

print("=" * 60)
print("  PHASE 1: Shell A/B Testing — Poker")
print("  Opponent: no-shell Sonnet (fixed)")
print("=" * 60)

# Test A: TAG vs no-shell
print("\n\n>>> TEST A: TAG vs no-shell <<<\n")
result_a = tester.ab_test(
    shell_a=tag_shell, shell_b=None,
    game="poker", n_games=N_GAMES,
    agent_id="shell-agent", adapter="claude", model="sonnet",
    opponent_id="baseline",
)
tester.save_report(result_a, "reports/phase1_test_a_tag_vs_none.json")

# Test B: TAG vs Bluff-Heavy
print("\n\n>>> TEST B: TAG vs Bluff-Heavy <<<\n")
result_b = tester.ab_test(
    shell_a=tag_shell, shell_b=bluff_shell,
    game="poker", n_games=N_GAMES,
    agent_id="shell-agent", adapter="claude", model="sonnet",
    opponent_id="baseline",
)
tester.save_report(result_b, "reports/phase1_test_b_tag_vs_bluff.json")

# Test C: Bluff-Heavy vs no-shell
print("\n\n>>> TEST C: Bluff-Heavy vs no-shell <<<\n")
result_c = tester.ab_test(
    shell_a=bluff_shell, shell_b=None,
    game="poker", n_games=N_GAMES,
    agent_id="shell-agent", adapter="claude", model="sonnet",
    opponent_id="baseline",
)
tester.save_report(result_c, "reports/phase1_test_c_bluff_vs_none.json")

# Summary
print("\n" + "=" * 60)
print("  PHASE 1 SUMMARY")
print("=" * 60)
print(f"\nTest A (TAG vs no-shell):")
print(f"  {result_a.delta.summary()}")
print(f"\nTest B (TAG vs Bluff-Heavy):")
print(f"  {result_b.delta.summary()}")
print(f"\nTest C (Bluff-Heavy vs no-shell):")
print(f"  {result_c.delta.summary()}")
