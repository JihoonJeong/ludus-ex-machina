"""Avalon Phase 3: LLM-Guided Training

Start: Aggressive Evil (0% win rate from Phase 1 Test C)
Goal: See how many generations it takes to improve
5 generations × 5 games
Opponent: all-Sonnet, no-shell Good team

Baselines:
- no-shell: Evil 80% (Phase 1)
- Deep Cover: Evil 40% (Phase 1)
- Aggressive: Evil 0% (Phase 1 Test C, vs Deep Cover) / 60% (vs no-shell)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.client import LxMClient
from lxm.config import MatchConfig, AgentConfig, ShellConfig, TimeModel, InvocationConfig
from lxm.shell.manager import ShellManager
from lxm.shell.tester import MatchResult

manager = ShellManager()
aggressive = manager.create_shell("avalon", template="aggressive_evil")

N_GAMES = 5
GENERATIONS = 5
AGENTS = ["a", "b", "c", "d", "e"]


def run_batch(shell_content, label, n_games):
    """Run N avalon games. Returns list of MatchResult."""
    results = []
    for i in range(n_games):
        match_id = f"avalon_train_gen{label}_r{i+1:02d}"
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


def analyze_and_modify(shell: ShellConfig, results: list[MatchResult], gen: int) -> ShellConfig:
    """Ask LLM to analyze losses and modify shell."""
    import subprocess

    losses = [r for r in results if r.winner != "evil"]
    if not losses:
        return shell  # All wins, no modification needed

    # Read game logs for losses
    log_summaries = []
    for loss in losses[:3]:
        log_path = Path("matches") / loss.match_id / "log.json"
        if log_path.exists():
            try:
                log = json.loads(log_path.read_text())
                # Get quest outcomes
                quest_data = []
                for e in log:
                    if e.get("result") == "accepted" and "quest" in str(e.get("envelope", {}).get("move", {})):
                        quest_data.append(e["envelope"]["move"])
                log_summaries.append({
                    "match_id": loss.match_id,
                    "outcome": loss.outcome,
                    "quest_moves": quest_data[-10:],
                })
            except (json.JSONDecodeError, OSError):
                pass

    prompt = f"""You are an Avalon strategy optimizer for the Evil team. Analyze this Evil shell and improve it.

CURRENT SHELL (for Evil agents):
```markdown
{shell.content}
```

RESULTS: {len(results)} games, Evil won {len(results) - len(losses)}/{len(results)}

LOSSES ({len(losses)} games):
{json.dumps(log_summaries, indent=2)[:2000]}

The shell is given to Evil players (Morgana + Assassin) at the start. Good players have no shell.

TASK: Modify the shell to improve Evil's win rate. Keep Structured Markdown format.
- Change at most 2-3 things
- Bump version to v{gen + 1}.0
- Focus on: sabotage timing, voting strategy, discussion tactics

Output ONLY the new shell in Structured Markdown. No other text."""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "text"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            # Extract markdown
            if "```markdown" in output:
                start = output.index("```markdown") + len("```markdown")
                end = output.index("```", start)
                output = output[start:end].strip()
            elif "```" in output:
                start = output.index("```") + 3
                newline = output.index("\n", start)
                end = output.index("```", newline)
                output = output[newline:end].strip()

            new_shell = ShellConfig.from_text(output)
            new_shell.content = output
            new_shell.version = f"v{gen + 1}.0"
            new_shell.parent_version = shell.version
            return new_shell
    except Exception as e:
        print(f"  [Trainer] LLM call failed: {e}")

    return shell


print("=" * 60)
print("  AVALON PHASE 3: LLM-Guided Training")
print(f"  Start: Aggressive Evil v1.0")
print(f"  {GENERATIONS} generations × {N_GAMES} games")
print("=" * 60)

current_shell = aggressive
generations = []

for gen in range(1, GENERATIONS + 1):
    print(f"\n=== Generation {gen}/{GENERATIONS}: {current_shell.version} ===\n")

    results = run_batch(current_shell.content, gen, N_GAMES)
    evil_wins = sum(1 for r in results if r.winner == "evil")
    win_rate = evil_wins / len(results) if results else 0

    gen_data = {
        "generation": gen,
        "version": current_shell.version,
        "evil_win_rate": win_rate,
        "evil_wins": evil_wins,
        "n_games": len(results),
        "modification_note": "",
        "shell_length": len(current_shell.content or ""),
    }

    # Check convergence (gen 2+)
    if gen > 1 and generations:
        prev_wr = generations[-1]["evil_win_rate"]
        if abs(win_rate - prev_wr) < 0.05:
            gen_data["modification_note"] = "converged"
            generations.append(gen_data)
            print(f"  Evil {win_rate:.0%} — converged")
            break

    if gen < GENERATIONS:
        if evil_wins < len(results):  # Has losses
            new_shell = analyze_and_modify(current_shell, results, gen)
            if new_shell.version != current_shell.version:
                gen_data["modification_note"] = f"LLM modified → {new_shell.version}"
                current_shell = new_shell
            else:
                gen_data["modification_note"] = "no change"
        else:
            gen_data["modification_note"] = "all wins"

    generations.append(gen_data)
    print(f"  Evil {win_rate:.0%} | {gen_data['modification_note']}")

# Save shells
shells_dir = Path("reports/phase3_avalon_shells")
shells_dir.mkdir(parents=True, exist_ok=True)
(shells_dir / f"final_{current_shell.version}.md").write_text(current_shell.content or "")

# Find best
best = max(generations, key=lambda g: g["evil_win_rate"])

report = {
    "type": "avalon_llm_guided_training",
    "start_shell": "Aggressive Evil v1.0",
    "baselines": {"no_shell": 0.80, "deep_cover": 0.40, "aggressive_vs_noshell": 0.60},
    "generations": generations,
    "best_generation": best["generation"],
    "best_evil_win_rate": best["evil_win_rate"],
    "best_version": best["version"],
}
Path("reports/shell_engineering_avalon_phase3.json").write_text(json.dumps(report, indent=2))

print("\n" + "=" * 60)
print("  PHASE 3 SUMMARY")
print("=" * 60)
for g in generations:
    marker = " ← BEST" if g["generation"] == best["generation"] else ""
    print(f"  Gen {g['generation']}: {g['version']} — Evil {g['evil_win_rate']:.0%} ({g['modification_note']}){marker}")
print(f"\nBest: Gen {best['generation']}, {best['version']} (Evil {best['evil_win_rate']:.0%})")
print(f"\nvs Baselines:")
print(f"  no-shell:     80%")
print(f"  Deep Cover:   40%")
print(f"  Aggressive:   60% (vs no-shell)")
print(f"  LLM-Guided:   {best['evil_win_rate']:.0%}")
print(f"\nReports: reports/shell_engineering_avalon_phase3.json")
