"""Agent Memory Experiment — Avalon

Condition A: Evil no-memory, Good no-shell — 5 games (baseline)
Condition B: Evil memory Shell, Good no-shell — 5 games

5-player all-Sonnet. Evil team gets memory Shell via role_shells.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.client import LxMClient
from lxm.config import MatchConfig, AgentConfig, TimeModel, InvocationConfig
from lxm.shell.manager import ShellManager
from lxm.shell.tester import MatchResult

manager = ShellManager()
memory_evil = manager.create_shell("avalon", template="memory_evil")

N_GAMES = 5
AGENTS = ["a", "b", "c", "d", "e"]


def run_batch(evil_shell_content, label, n_games):
    results = []
    for i in range(n_games):
        match_id = f"memory_avalon_{label}_r{i+1:02d}"
        agents = [
            AgentConfig(agent_id=f"agent-{a}", adapter="claude", model="sonnet", seat=j)
            for j, a in enumerate(AGENTS)
        ]
        role_shells = {"evil": evil_shell_content} if evil_shell_content else {}
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

            # Save memory files for all agents
            match_dir = Path("matches") / match_id
            mem_save = Path("reports/memory_avalon") / label
            mem_save.mkdir(parents=True, exist_ok=True)
            for a in AGENTS:
                mem_path = match_dir / f"memory_agent-{a}.md"
                if mem_path.exists():
                    content = mem_path.read_text()
                    (mem_save / f"{match_id}_agent-{a}_memory.md").write_text(content)
                    print(f"      agent-{a} memory: {len(content)} chars")
        except Exception as e:
            print(f"    {match_id}: ERROR - {e}")
    return results


print("=" * 60)
print("  AGENT MEMORY — Avalon")
print("  Evil gets memory Shell, Good has no shell")
print("=" * 60)

# Condition A: baseline
print("\n>>> A: Evil no-memory, Good no-shell <<<\n")
results_a = run_batch(None, "baseline", N_GAMES)

# Condition B: Evil memory
print("\n>>> B: Evil memory Shell, Good no-shell <<<\n")
results_b = run_batch(memory_evil.content, "memory", N_GAMES)

# Summary
print("\n" + "=" * 60)
print("  RESULTS")
print("=" * 60)

def summarize(results, label):
    evil_wins = sum(1 for r in results if r.winner == "evil")
    n = len(results) or 1
    avg_t = sum(r.duration_seconds for r in results) / n
    print(f"  {label}: Evil {evil_wins}/{len(results)} ({evil_wins/n:.0%}), avg {avg_t:.0f}s")
    return {"evil_wins": evil_wins, "n": len(results), "evil_rate": evil_wins/n, "avg_time": avg_t}

sa = summarize(results_a, "A: Baseline (no memory)")
sb = summarize(results_b, "B: Evil Memory Shell")

# Count memory files
mem_count = len(list(Path("reports/memory_avalon/memory").glob("*.md"))) if Path("reports/memory_avalon/memory").exists() else 0
print(f"\n  Memory files saved: {mem_count}")

report = {
    "experiment": "agent_memory_avalon",
    "conditions": {"A_baseline": sa, "B_memory": sb},
    "memory_files_count": mem_count,
}
Path("reports/memory_avalon").mkdir(parents=True, exist_ok=True)
Path("reports/memory_avalon/results.json").write_text(json.dumps(report, indent=2))
print(f"\nReport: reports/memory_avalon/results.json")
