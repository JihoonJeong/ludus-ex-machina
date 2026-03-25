"""Codenames Shell Engineering — Phase 1/2/3

Phase 1: A/B Test (Conservative vs Aggressive vs no-shell)
Phase 2: Parameter Sweep (clue_number_max 1/2/3/4)
Phase 3: LLM-Guided Training (start from Aggressive)

4 players: shell-spy (red spy, with shell) + haiku guesser (red)
           vs baseline-spy (blue spy, no shell) + haiku guesser (blue)
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.client import LxMClient
from lxm.config import MatchConfig, AgentConfig, ShellConfig, TimeModel, InvocationConfig
from lxm.shell.manager import ShellManager
from lxm.shell.tester import MatchResult, extract_codenames_behavior, aggregate_behavior

manager = ShellManager()
N_GAMES = 5


def run_codenames_batch(spy_shell_content, label, n_games, verbose=True):
    """Run N codenames games. Red spy gets shell, blue spy = no shell."""
    results = []
    for i in range(n_games):
        match_id = f"cn_shell_{label}_r{i+1:02d}"

        # Alternate which team gets the shell for fairness
        if i % 2 == 0:
            agents = [
                AgentConfig(agent_id="shell-spy", adapter="claude", model="sonnet",
                           seat=0, team="red", role="spymaster",
                           hard_shell=spy_shell_content),
                AgentConfig(agent_id="guess-r", adapter="claude", model="haiku",
                           seat=1, team="red", role="guesser"),
                AgentConfig(agent_id="baseline-spy", adapter="claude", model="sonnet",
                           seat=2, team="blue", role="spymaster"),
                AgentConfig(agent_id="guess-b", adapter="claude", model="haiku",
                           seat=3, team="blue", role="guesser"),
            ]
        else:
            agents = [
                AgentConfig(agent_id="baseline-spy", adapter="claude", model="sonnet",
                           seat=0, team="red", role="spymaster"),
                AgentConfig(agent_id="guess-r", adapter="claude", model="haiku",
                           seat=1, team="red", role="guesser"),
                AgentConfig(agent_id="shell-spy", adapter="claude", model="sonnet",
                           seat=2, team="blue", role="spymaster",
                           hard_shell=spy_shell_content),
                AgentConfig(agent_id="guess-b", adapter="claude", model="haiku",
                           seat=3, team="blue", role="guesser"),
            ]

        teams = {
            "red": {"spymaster": agents[0].agent_id, "guesser": agents[1].agent_id},
            "blue": {"spymaster": agents[2].agent_id, "guesser": agents[3].agent_id},
        }

        config = MatchConfig(
            game="codenames", agents=agents, match_id=match_id,
            time_model=TimeModel(turn_order="custom", max_turns=50, timeout_seconds=120, max_retries=2),
            invocation=InvocationConfig(mode="inline", discovery_turns=0),
            teams=teams, skip_eval=True,
        )

        try:
            client = LxMClient(config)
            result = client.run()
            winner = result.get("winner", "")
            # Determine if shell-spy's team won
            shell_team = "red" if i % 2 == 0 else "blue"
            shell_won = (winner == "shell-spy") or (shell_team in str(winner).lower())
            results.append(MatchResult(
                match_id=match_id,
                winner="shell-spy" if shell_won else "baseline-spy",
                outcome=result.get("outcome", ""),
                scores=result.get("scores", {}),
                duration_seconds=client.duration_seconds,
            ))
            if verbose:
                w = "SHELL wins" if shell_won else "BASELINE wins"
                print(f"    {match_id}: {w} ({result.get('outcome', '')})")
        except Exception as e:
            if verbose:
                print(f"    {match_id}: ERROR - {e}")

    return results


def summarize(results, label):
    shell_wins = sum(1 for r in results if r.winner == "shell-spy")
    n = len(results)
    wr = shell_wins / n if n else 0
    behaviors = [extract_codenames_behavior(r.match_id, "shell-spy") for r in results]
    beh = aggregate_behavior(behaviors)
    print(f"  {label}: Shell spy {shell_wins}/{n} ({wr:.0%})")
    if beh.metrics:
        avg_cn = beh.metrics.get("avg_clue_number", 0)
        print(f"    avg clue number: {avg_cn:.1f}")
    return {"shell_wins": shell_wins, "n": n, "win_rate": wr, "behavior": beh.metrics}


# ════════════════════════════════════════════
# Phase 1: A/B Test
# ════════════════════════════════════════════

conservative = manager.create_shell("codenames", template="conservative")
aggressive = manager.create_shell("codenames", template="aggressive")

print("=" * 60)
print("  CODENAMES PHASE 1: A/B Test")
print("=" * 60)

print("\n>>> Test A: Conservative vs no-shell <<<\n")
r1a = run_codenames_batch(conservative.content, "cons", N_GAMES)
r1a_none = run_codenames_batch(None, "noshell_a", N_GAMES)

print("\n>>> Test B: Aggressive vs no-shell <<<\n")
r1b = run_codenames_batch(aggressive.content, "agg", N_GAMES)
r1b_none = run_codenames_batch(None, "noshell_b", N_GAMES)

print("\n>>> Test C: Conservative vs Aggressive <<<\n")
r1c_cons = run_codenames_batch(conservative.content, "cons_v_agg_c", N_GAMES)
r1c_agg = run_codenames_batch(aggressive.content, "cons_v_agg_a", N_GAMES)

print("\n--- Phase 1 Summary ---")
print("\nTest A: Conservative vs no-shell")
s1a_s = summarize(r1a, "Conservative")
s1a_n = summarize(r1a_none, "no-shell")
print("\nTest B: Aggressive vs no-shell")
s1b_s = summarize(r1b, "Aggressive")
s1b_n = summarize(r1b_none, "no-shell")
print("\nTest C: Conservative vs Aggressive")
s1c_c = summarize(r1c_cons, "Conservative")
s1c_a = summarize(r1c_agg, "Aggressive")


# ════════════════════════════════════════════
# Phase 2: Parameter Sweep — clue_number_max
# ════════════════════════════════════════════

print("\n" + "=" * 60)
print("  CODENAMES PHASE 2: Sweep clue_number_max")
print("=" * 60)

sweep_points = []
for cn_max in [1, 2, 3, 4]:
    # Modify conservative shell's clue_number_max
    content = conservative.content.replace(
        "clue_number_max: 2", f"clue_number_max: {cn_max}"
    )
    if cn_max >= 3:
        content = content.replace("at most 2 words", f"at most {cn_max} words")
    elif cn_max == 1:
        content = content.replace("at most 2 words", "exactly 1 word")

    print(f"\n  clue_number_max = {cn_max}:")
    results = run_codenames_batch(content, f"cn{cn_max}", N_GAMES)
    shell_wins = sum(1 for r in results if r.winner == "shell-spy")
    wr = shell_wins / len(results) if results else 0
    behaviors = [extract_codenames_behavior(r.match_id, "shell-spy") for r in results]
    beh = aggregate_behavior(behaviors)
    avg_cn = beh.metrics.get("avg_clue_number", 0)
    print(f"    Win: {wr:.0%}, avg clue: {avg_cn:.1f}")
    sweep_points.append({
        "clue_number_max": cn_max, "win_rate": wr, "shell_wins": shell_wins,
        "n_games": len(results), "avg_clue_number": avg_cn, "behavior": beh.metrics,
    })

best_sweep = max(sweep_points, key=lambda p: p["win_rate"])


# ════════════════════════════════════════════
# Phase 3: LLM-Guided Training
# ════════════════════════════════════════════

print("\n" + "=" * 60)
print("  CODENAMES PHASE 3: LLM-Guided Training")
print("  Start: Aggressive (clue_number_max: 4)")
print("=" * 60)

current_shell = aggressive
generations = []

for gen in range(1, 6):
    print(f"\n=== Gen {gen}: {current_shell.version} ===\n")
    results = run_codenames_batch(current_shell.content, f"gen{gen}", N_GAMES)
    shell_wins = sum(1 for r in results if r.winner == "shell-spy")
    wr = shell_wins / len(results) if results else 0

    gen_data = {
        "generation": gen, "version": current_shell.version,
        "win_rate": wr, "shell_wins": shell_wins, "n_games": len(results),
        "modification_note": "",
    }

    # Convergence check
    if gen > 1 and generations and abs(wr - generations[-1]["win_rate"]) < 0.05:
        gen_data["modification_note"] = "converged"
        generations.append(gen_data)
        print(f"  Win {wr:.0%} — converged")
        break

    # LLM modification
    if gen < 5 and shell_wins < len(results):
        prompt = f"""You are a Codenames Spymaster strategy optimizer. Improve this shell.

CURRENT SHELL:
```markdown
{current_shell.content}
```

RESULTS: {len(results)} games, won {shell_wins}/{len(results)}

TASK: Modify to improve win rate. Keep Structured Markdown format.
- The spymaster gives clues (word + number). Number = how many board words connect.
- Higher numbers = faster but riskier (might hit assassin or opponent words).
- Change at most 2-3 things. Bump version.

Output ONLY the new shell. No other text."""

        try:
            res = subprocess.run(
                ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "text"],
                capture_output=True, text=True, timeout=120,
            )
            if res.returncode == 0 and res.stdout.strip():
                output = res.stdout.strip()
                if "```markdown" in output:
                    s = output.index("```markdown") + len("```markdown")
                    e = output.index("```", s)
                    output = output[s:e].strip()
                elif "```" in output:
                    s = output.index("```") + 3
                    nl = output.index("\n", s)
                    e = output.index("```", nl)
                    output = output[nl:e].strip()
                new_shell = ShellConfig.from_text(output)
                new_shell.content = output
                new_shell.version = f"v{gen+1}.0"
                gen_data["modification_note"] = f"LLM → {new_shell.version}"
                current_shell = new_shell
            else:
                gen_data["modification_note"] = "LLM failed"
        except Exception as e:
            gen_data["modification_note"] = f"LLM error: {e}"
    elif shell_wins == len(results):
        gen_data["modification_note"] = "all wins"

    generations.append(gen_data)
    print(f"  Win {wr:.0%} | {gen_data['modification_note']}")

best_gen = max(generations, key=lambda g: g["win_rate"]) if generations else {}

# ════════════════════════════════════════════
# Save Reports
# ════════════════════════════════════════════

report = {
    "phase1": {
        "test_a": {"conservative": s1a_s, "no_shell": s1a_n},
        "test_b": {"aggressive": s1b_s, "no_shell": s1b_n},
        "test_c": {"conservative": s1c_c, "aggressive": s1c_a},
    },
    "phase2": {
        "param": "clue_number_max",
        "points": sweep_points,
        "best": best_sweep,
    },
    "phase3": {
        "generations": generations,
        "best_generation": best_gen.get("generation"),
        "best_win_rate": best_gen.get("win_rate"),
        "best_version": best_gen.get("version"),
    },
}
Path("reports/shell_engineering_codenames_full.json").write_text(json.dumps(report, indent=2))

# Final summary
print("\n" + "=" * 60)
print("  CODENAMES FULL SUMMARY")
print("=" * 60)
print("\nPhase 1:")
print(f"  Conservative vs no-shell: {s1a_s['win_rate']:.0%} vs {s1a_n['win_rate']:.0%}")
print(f"  Aggressive vs no-shell: {s1b_s['win_rate']:.0%} vs {s1b_n['win_rate']:.0%}")
print(f"  Conservative vs Aggressive: {s1c_c['win_rate']:.0%} vs {s1c_a['win_rate']:.0%}")
print(f"\nPhase 2 (clue_number_max sweep):")
for p in sweep_points:
    marker = " ← BEST" if p["clue_number_max"] == best_sweep["clue_number_max"] else ""
    print(f"  max={p['clue_number_max']}: {p['win_rate']:.0%} (avg clue {p['avg_clue_number']:.1f}){marker}")
print(f"\nPhase 3 (LLM-Guided):")
for g in generations:
    marker = " ← BEST" if g["generation"] == best_gen.get("generation") else ""
    print(f"  Gen {g['generation']}: {g['version']} — {g['win_rate']:.0%} ({g['modification_note']}){marker}")
print(f"\nSIBO prediction: Shell < no-shell (SIBO 0.35)")
print(f"Report: reports/shell_engineering_codenames_full.json")
