"""Agent Memory Experiment — Poker HU

Condition A: Stateless (current) — recent_moves=20
Condition B: Memory Shell + recent_moves=20 (memory as supplement)
Condition C: Memory Shell + recent_moves=3 (memory replaces history)

5 games per condition. Opponent: no-shell/no-memory Sonnet (fixed).
"""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.client import LxMClient
from lxm.config import MatchConfig, AgentConfig, TimeModel, InvocationConfig
from lxm.shell.manager import ShellManager
from lxm.shell.tester import MatchResult, extract_poker_behavior, aggregate_behavior

manager = ShellManager()
memory_shell = manager.create_shell("poker", template="memory_balanced")

N_GAMES = 5


def run_condition(label: str, shell_content: str | None, recent_moves: int,
                  verbose: bool = True) -> list[MatchResult]:
    """Run N poker games under one condition."""
    results = []

    for i in range(N_GAMES):
        match_id = f"memory_exp_{label}_r{i+1:02d}"

        agents = [
            AgentConfig(
                agent_id="mem-agent", adapter="claude", model="sonnet", seat=0,
                hard_shell=shell_content,
            ),
            AgentConfig(
                agent_id="baseline", adapter="claude", model="sonnet", seat=1,
            ),
        ]

        # Alternate seats
        if i % 2 == 1:
            agents = [agents[1], agents[0]]
            agents[0].seat = 0
            agents[1].seat = 1

        config = MatchConfig(
            game="poker", agents=agents, match_id=match_id,
            time_model=TimeModel(max_turns=2000, timeout_seconds=120, max_retries=2),
            invocation=InvocationConfig(mode="inline", discovery_turns=0),
            recent_moves_count=recent_moves,
            skip_eval=True,
        )

        try:
            client = LxMClient(config)
            result = client.run()
            results.append(MatchResult(
                match_id=match_id,
                winner=result.get("winner"),
                outcome=result.get("outcome", ""),
                scores=result.get("scores", {}),
                duration_seconds=client.duration_seconds,
            ))
            if verbose:
                w = result.get("winner", "draw")
                print(f"    {match_id}: {w} ({client.duration_seconds:.0f}s)")

            # Save memory file if it exists
            mem_path = Path("matches") / match_id / "memory_mem-agent.md"
            if mem_path.exists():
                mem_content = mem_path.read_text()
                mem_save = Path("reports/memory_experiment") / label
                mem_save.mkdir(parents=True, exist_ok=True)
                (mem_save / f"{match_id}_memory.md").write_text(mem_content)
                print(f"      memory.md: {len(mem_content)} chars")
        except Exception as e:
            if verbose:
                print(f"    {match_id}: ERROR - {e}")

    return results


def summarize(results: list[MatchResult], label: str) -> dict:
    agent_id = "mem-agent"
    wins = sum(1 for r in results if r.winner == agent_id)
    n = len(results) or 1
    win_rate = wins / n
    avg_time = sum(r.duration_seconds for r in results) / n

    behaviors = [extract_poker_behavior(r.match_id, agent_id) for r in results]
    beh = aggregate_behavior(behaviors)

    print(f"  {label}: {wins}/{len(results)} ({win_rate:.0%}), avg {avg_time:.0f}s")
    if beh.metrics:
        fold = beh.metrics.get("fold", 0)
        raise_ = beh.metrics.get("raise", 0)
        print(f"    fold={fold:.0%}, raise={raise_:.0%}")

    return {
        "label": label, "win_rate": win_rate, "wins": wins, "n": len(results),
        "avg_time": avg_time, "behavior": beh.metrics,
    }


print("=" * 60)
print("  AGENT MEMORY EXPERIMENT — Poker HU")
print("  Opponent: no-shell/no-memory Sonnet")
print("=" * 60)

# Condition A: Stateless
print("\n>>> Condition A: Stateless (recent_moves=20) <<<\n")
results_a = run_condition("stateless", shell_content=None, recent_moves=20)

# Condition B: Memory + full history
print("\n>>> Condition B: Memory Shell (recent_moves=20) <<<\n")
results_b = run_condition("memory_full", shell_content=memory_shell.content, recent_moves=20)

# Condition C: Memory + reduced history
print("\n>>> Condition C: Memory Shell (recent_moves=3) <<<\n")
results_c = run_condition("memory_compressed", shell_content=memory_shell.content, recent_moves=3)

# Summary
print("\n" + "=" * 60)
print("  RESULTS")
print("=" * 60)
sa = summarize(results_a, "A: Stateless (rm=20)")
sb = summarize(results_b, "B: Memory + rm=20")
sc = summarize(results_c, "C: Memory + rm=3")

# Save report
report = {
    "experiment": "agent_memory_poker",
    "conditions": {
        "A_stateless": sa,
        "B_memory_full": sb,
        "C_memory_compressed": sc,
    },
}
Path("reports/memory_experiment").mkdir(parents=True, exist_ok=True)
Path("reports/memory_experiment/results.json").write_text(json.dumps(report, indent=2))
print(f"\nReport: reports/memory_experiment/results.json")
print(f"Memory files: reports/memory_experiment/*/")
