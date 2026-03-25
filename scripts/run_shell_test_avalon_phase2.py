"""Avalon Phase 2: Parameter Sweep — first_sabotage_quest

Deep Cover shell, sweep sabotage timing: Q1, Q2, Q3, Q4, Q5
5 values × 5 games = 25 games
Opponent: all-Sonnet, no-shell Good team
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.client import LxMClient
from lxm.config import MatchConfig, AgentConfig, TimeModel, InvocationConfig
from lxm.shell.manager import ShellManager
from lxm.shell.tester import MatchResult

manager = ShellManager()
deep_cover = manager.create_shell("avalon", template="deep_cover")

N_GAMES = 5
AGENTS = ["a", "b", "c", "d", "e"]
SWEEP_VALUES = ["1", "2", "3", "4", "5"]


def make_shell_variant(base_content: str, first_sabotage_quest: str) -> str:
    """Modify Deep Cover shell to set first sabotage quest."""
    content = base_content

    # Update parameter
    content = re.sub(
        r'(trust_building_quests:)\s*\d+',
        f'\\1 {int(first_sabotage_quest) - 1}',
        content,
    )

    # Update strategy text
    quest_n = int(first_sabotage_quest)
    if quest_n == 1:
        strategy_line = "Quest 1: Sabotage immediately. No trust building."
    elif quest_n == 2:
        strategy_line = "Quest 1: Play Success to build minimal trust.\nQuest 2+: Begin sabotage."
    elif quest_n == 3:
        strategy_line = "Quests 1-2: Play Success to build trust.\nQuest 3+: Begin sabotage."
    elif quest_n == 4:
        strategy_line = "Quests 1-3: Play Success to build strong trust.\nQuest 4+: Sabotage late."
    else:
        strategy_line = "Quests 1-4: Play Success throughout.\nQuest 5: Sabotage only on the last quest."

    # Replace the strategy section's quest instructions
    content = re.sub(
        r'Quests? \d.*?(?=\nVoting:)',
        strategy_line + "\n",
        content,
        flags=re.DOTALL,
    )

    # Update version
    content = re.sub(r'v\d+\.\d+', f'v1.0_Q{first_sabotage_quest}', content)

    return content


def run_batch(shell_content, label, n_games):
    """Run N avalon games with given evil shell."""
    results = []
    for i in range(n_games):
        match_id = f"avalon_sweep_Q{label}_r{i+1:02d}"
        agents = [
            AgentConfig(agent_id=f"agent-{a}", adapter="claude", model="sonnet", seat=j)
            for j, a in enumerate(AGENTS)
        ]
        role_shells = {"evil": shell_content} if shell_content else {}
        config = MatchConfig(
            game="avalon", agents=agents, match_id=match_id,
            time_model=TimeModel(max_turns=200, timeout_seconds=120, max_retries=2),
            invocation=InvocationConfig(mode="inline", discovery_turns=0),
            recent_moves_count=30, role_shells=role_shells, skip_eval=True,
        )
        try:
            client = LxMClient(config)
            result = client.run()
            results.append(MatchResult(
                match_id=match_id, winner=result.get("winner"),
                outcome=result.get("outcome", ""),
                duration_seconds=client.duration_seconds,
            ))
            print(f"    {match_id}: {result.get('winner')} ({result.get('outcome')})")
        except Exception as e:
            print(f"    {match_id}: ERROR - {e}")
    return results


print("=" * 60)
print("  AVALON PHASE 2: Parameter Sweep — first_sabotage_quest")
print(f"  {len(SWEEP_VALUES)} values × {N_GAMES} games = {len(SWEEP_VALUES)*N_GAMES} games")
print("=" * 60)

points = []
for q in SWEEP_VALUES:
    print(f"\n  first_sabotage_quest = Q{q}:")
    shell_content = make_shell_variant(deep_cover.content, q)
    results = run_batch(shell_content, q, N_GAMES)
    evil_wins = sum(1 for r in results if r.winner == "evil")
    win_rate = evil_wins / len(results) if results else 0
    points.append({
        "quest": int(q), "evil_win_rate": win_rate, "evil_wins": evil_wins,
        "n_games": len(results),
        "results": [{"match_id": r.match_id, "winner": r.winner, "outcome": r.outcome,
                     "duration": r.duration_seconds} for r in results],
    })

# Find best
best = max(points, key=lambda p: p["evil_win_rate"])

report = {
    "type": "avalon_parameter_sweep",
    "param": "first_sabotage_quest",
    "points": points,
    "best_quest": best["quest"],
    "best_evil_win_rate": best["evil_win_rate"],
}
Path("reports/shell_engineering_avalon_phase2.json").write_text(json.dumps(report, indent=2))

print("\n" + "=" * 60)
print("  PHASE 2 RESULTS")
print("=" * 60)
for p in points:
    marker = " ← BEST" if p["quest"] == best["quest"] else ""
    print(f"  Q{p['quest']}: Evil {p['evil_win_rate']:.0%} ({p['evil_wins']}/{p['n_games']}){marker}")
print(f"\nBest: Q{best['quest']} (Evil {best['evil_win_rate']:.0%})")
print(f"Report: reports/shell_engineering_avalon_phase2.json")
