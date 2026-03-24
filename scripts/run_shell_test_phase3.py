"""Phase 3: LLM-Guided Training — Poker

Start: TAG v1.0 (top 20%, win rate 20%)
Baselines: no-shell (60%), Parameter Sweep optimal (top 30%, 80%)
Goal: See if LLM-Guided evolution reaches/exceeds sweep optimal in 5 generations.

5 generations × 5 games = ~25 games + LLM calls for shell modification
Opponent: no-shell Sonnet (fixed)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.shell.manager import ShellManager
from lxm.shell.trainer import ShellTrainer

manager = ShellManager()
trainer = ShellTrainer(
    opponent_adapter="claude",
    opponent_model="sonnet",
)

# Start from TAG v1.0
tag_shell = manager.create_shell("poker", template="tight_aggressive")

print("=" * 60)
print("  PHASE 3: LLM-Guided Shell Training — Poker")
print("  Start: TAG v1.0 (pre_flop_threshold: top 20%)")
print("  Baselines: no-shell 60%, Sweep optimal 80%")
print("  5 generations × 5 games")
print("  Opponent: no-shell Sonnet (fixed)")
print("=" * 60)

result = trainer.train(
    shell=tag_shell,
    game="poker",
    agent_id="train-agent",
    adapter="claude",
    model="sonnet",
    opponent_id="baseline",
    strategy="llm_guided",
    generations=5,
    games_per_gen=5,
    cost_weight=0.1,
    convergence_threshold=0.05,
    verbose=True,
)

# Save all intermediate shells
shells_dir = Path("reports/phase3_shells")
shells_dir.mkdir(parents=True, exist_ok=True)
for gen in result.generations:
    shell_path = shells_dir / f"gen{gen.generation}_{gen.shell.version}.md"
    content = gen.shell.content or manager._render(gen.shell)
    shell_path.write_text(content)

# Save JSON report
import json
report = {
    "type": "llm_guided_training",
    "game": "poker",
    "strategy": "llm_guided",
    "start_shell": "TAG v1.0 (pre_flop_threshold: top 20%)",
    "baselines": {
        "no_shell": 0.60,
        "sweep_optimal": 0.80,
    },
    "generations": [],
    "best_generation": result.best_generation,
    "best_win_rate": result.best_win_rate,
    "best_shell_version": result.best_shell.version if result.best_shell else None,
}
for gen in result.generations:
    report["generations"].append({
        "generation": gen.generation,
        "version": gen.shell.version,
        "win_rate": gen.win_rate,
        "n_games": gen.n_games,
        "modification_note": gen.modification_note,
        "parameters": gen.shell.parameters,
        "shell_length": len(gen.shell.content or ""),
    })

Path("reports/phase3_llm_guided_training.json").write_text(json.dumps(report, indent=2))
print(f"\nReport saved: reports/phase3_llm_guided_training.json")
print(f"Shells saved: reports/phase3_shells/")

# Final comparison
print("\n" + "=" * 60)
print("  PHASE 3 vs BASELINES")
print("=" * 60)
print(f"  no-shell:        60%")
print(f"  Sweep optimal:   80% (top 30%)")
print(f"  LLM-Guided best: {result.best_win_rate:.0%} (gen {result.best_generation}, {result.best_shell.version if result.best_shell else '?'})")
if result.best_win_rate > 0.80:
    print("  → LLM-Guided EXCEEDED sweep optimal!")
elif result.best_win_rate == 0.80:
    print("  → LLM-Guided MATCHED sweep optimal")
elif result.best_win_rate > 0.60:
    print("  → LLM-Guided beat no-shell but didn't reach sweep optimal")
else:
    print("  → LLM-Guided did NOT beat no-shell")
