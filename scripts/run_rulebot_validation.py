"""Validate rule_bot as Shell test opponent.

Compare: TAG Shell vs rule_bot(medium) vs TAG Shell vs LLM(Sonnet no-shell)
If results are similar, rule_bot can replace LLM for cheaper Shell testing.

3 tests × 5 games = 15 games (instant — no LLM cost for opponent)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.shell.manager import ShellManager
from lxm.shell.tester import ShellTester

manager = ShellManager()
tag_shell = manager.create_shell("poker", template="tight_aggressive")
bluff_shell = manager.create_shell("poker", template="bluff_heavy")

N_GAMES = 5

# Test against rule_bot instead of LLM
tester = ShellTester(opponent_adapter="rule_bot", opponent_model="medium")

print("=" * 60)
print("  RULE BOT VALIDATION — Poker")
print("  Opponent: rule_bot (medium) instead of Sonnet")
print("=" * 60)

# Test 1: TAG vs rule_bot
print("\n>>> TAG vs rule_bot(medium) <<<\n")
result_1 = tester.ab_test(
    shell_a=tag_shell, shell_b=None,
    game="poker", n_games=N_GAMES,
    agent_id="shell-agent", adapter="claude", model="sonnet",
    opponent_id="rule-bot",
)
tester.save_report(result_1, "reports/rulebot_val_tag_vs_bot.json")

# Test 2: Bluff-Heavy vs rule_bot
print("\n>>> Bluff-Heavy vs rule_bot(medium) <<<\n")
result_2 = tester.ab_test(
    shell_a=bluff_shell, shell_b=None,
    game="poker", n_games=N_GAMES,
    agent_id="shell-agent", adapter="claude", model="sonnet",
    opponent_id="rule-bot",
)
tester.save_report(result_2, "reports/rulebot_val_bluff_vs_bot.json")

# Test 3: Optimal (top 30%) vs rule_bot
from lxm.config import ShellConfig
optimal_content = tag_shell.content.replace("top 20%", "top 30%")
optimal_shell = ShellConfig.from_text(optimal_content)
optimal_shell.version = "v1.0_optimal"

print("\n>>> Optimal TAG (top 30%) vs rule_bot(medium) <<<\n")
result_3 = tester.ab_test(
    shell_a=optimal_shell, shell_b=None,
    game="poker", n_games=N_GAMES,
    agent_id="shell-agent", adapter="claude", model="sonnet",
    opponent_id="rule-bot",
)
tester.save_report(result_3, "reports/rulebot_val_optimal_vs_bot.json")

# Summary comparison
print("\n" + "=" * 60)
print("  COMPARISON: LLM opponent vs rule_bot opponent")
print("=" * 60)
print(f"{'Shell':<20} {'vs LLM (Phase 1)':<18} {'vs rule_bot':<18}")
print("-" * 56)
print(f"{'TAG (top 20%)':<20} {'40%':<18} {f'{result_1.delta.win_rate_a:.0%}':<18}")
print(f"{'Bluff-Heavy':<20} {'80%':<18} {f'{result_2.delta.win_rate_a:.0%}':<18}")
print(f"{'Optimal (top 30%)':<20} {'80% (sweep)':<18} {f'{result_3.delta.win_rate_a:.0%}':<18}")
