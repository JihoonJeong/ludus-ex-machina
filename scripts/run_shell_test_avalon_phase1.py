"""Avalon Shell A/B Testing — Phase 1

Test A: Deep Cover Evil vs no-shell, 5 games
Test B: Aggressive Evil vs no-shell, 5 games
Test C: Deep Cover vs Aggressive, 5 games

All agents: Sonnet, no-shell Good team (3), Evil team (2) gets the shell.
Role assignment is random by engine.
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
deep_cover = manager.create_shell("avalon", template="deep_cover")
aggressive = manager.create_shell("avalon", template="aggressive_evil")

N_GAMES = 5
AGENTS_TEMPLATE = ["a", "b", "c", "d", "e"]


def run_avalon_batch(evil_shell_content, label, n_games, verbose=True):
    """Run N avalon games with given evil shell via role_shells."""
    results = []
    for i in range(n_games):
        match_id = f"avalon_shell_{label}_r{i+1:02d}"

        agents = [
            AgentConfig(agent_id=f"agent-{a}", adapter="claude", model="sonnet", seat=j)
            for j, a in enumerate(AGENTS_TEMPLATE)
        ]

        role_shells = {}
        if evil_shell_content:
            role_shells["evil"] = evil_shell_content

        config = MatchConfig(
            game="avalon",
            agents=agents,
            match_id=match_id,
            time_model=TimeModel(max_turns=200, timeout_seconds=120, max_retries=2),
            invocation=InvocationConfig(mode="inline", discovery_turns=0),
            recent_moves_count=30,
            role_shells=role_shells,
            skip_eval=True,
        )

        try:
            client = LxMClient(config)
            result = client.run()
            winner = result.get("winner", "")
            outcome = result.get("outcome", "")
            # In Avalon, winner is "good" or "evil"
            results.append(MatchResult(
                match_id=match_id,
                winner=winner,
                outcome=outcome,
                scores=result.get("scores", {}),
                duration_seconds=client.duration_seconds,
            ))
            if verbose:
                print(f"    {match_id}: {winner} wins ({outcome})")
        except Exception as e:
            if verbose:
                print(f"    {match_id}: ERROR - {e}")

    return results


def summarize(results, label):
    evil_wins = sum(1 for r in results if r.winner == "evil")
    good_wins = sum(1 for r in results if r.winner == "good")
    n = len(results)
    avg_time = sum(r.duration_seconds for r in results) / n if n else 0
    print(f"  {label}: Evil {evil_wins}/{n} ({evil_wins/n:.0%}), Good {good_wins}/{n} ({good_wins/n:.0%}), avg {avg_time:.0f}s")
    return {"evil_wins": evil_wins, "good_wins": good_wins, "n": n, "evil_rate": evil_wins/n if n else 0}


print("=" * 60)
print("  AVALON SHELL A/B TESTING — Phase 1")
print("  All Sonnet, Good = no-shell, Evil = test shell")
print("=" * 60)

# Test A: Deep Cover vs no-shell
print("\n>>> TEST A: Deep Cover Evil vs no-shell Evil <<<\n")
results_a_shell = run_avalon_batch(deep_cover.content, "dc", N_GAMES)
results_a_none = run_avalon_batch(None, "noshell_a", N_GAMES)

# Test B: Aggressive vs no-shell
print("\n>>> TEST B: Aggressive Evil vs no-shell Evil <<<\n")
results_b_shell = run_avalon_batch(aggressive.content, "agg", N_GAMES)
results_b_none = run_avalon_batch(None, "noshell_b", N_GAMES)

# Test C: Deep Cover vs Aggressive
print("\n>>> TEST C: Deep Cover vs Aggressive <<<")
print("  (Both applied as evil shell in separate batches)\n")
results_c_dc = run_avalon_batch(deep_cover.content, "dc_vs_agg_dc", N_GAMES)
results_c_agg = run_avalon_batch(aggressive.content, "dc_vs_agg_agg", N_GAMES)

# Summary
print("\n" + "=" * 60)
print("  PHASE 1 SUMMARY")
print("=" * 60)

print("\nTest A: Deep Cover vs no-shell")
sa_shell = summarize(results_a_shell, "Deep Cover")
sa_none = summarize(results_a_none, "no-shell")

print("\nTest B: Aggressive vs no-shell")
sb_shell = summarize(results_b_shell, "Aggressive")
sb_none = summarize(results_b_none, "no-shell")

print("\nTest C: Deep Cover vs Aggressive")
sc_dc = summarize(results_c_dc, "Deep Cover")
sc_agg = summarize(results_c_agg, "Aggressive")

# Save report
report = {
    "type": "avalon_ab_test",
    "game": "avalon",
    "n_games_per_condition": N_GAMES,
    "test_a": {
        "label": "Deep Cover vs no-shell",
        "deep_cover": sa_shell,
        "no_shell": sa_none,
        "results_shell": [{"match_id": r.match_id, "winner": r.winner, "outcome": r.outcome, "duration": r.duration_seconds} for r in results_a_shell],
        "results_none": [{"match_id": r.match_id, "winner": r.winner, "outcome": r.outcome, "duration": r.duration_seconds} for r in results_a_none],
    },
    "test_b": {
        "label": "Aggressive vs no-shell",
        "aggressive": sb_shell,
        "no_shell": sb_none,
        "results_shell": [{"match_id": r.match_id, "winner": r.winner, "outcome": r.outcome, "duration": r.duration_seconds} for r in results_b_shell],
        "results_none": [{"match_id": r.match_id, "winner": r.winner, "outcome": r.outcome, "duration": r.duration_seconds} for r in results_b_none],
    },
    "test_c": {
        "label": "Deep Cover vs Aggressive",
        "deep_cover": sc_dc,
        "aggressive": sc_agg,
        "results_dc": [{"match_id": r.match_id, "winner": r.winner, "outcome": r.outcome, "duration": r.duration_seconds} for r in results_c_dc],
        "results_agg": [{"match_id": r.match_id, "winner": r.winner, "outcome": r.outcome, "duration": r.duration_seconds} for r in results_c_agg],
    },
}

Path("reports").mkdir(exist_ok=True)
Path("reports/shell_engineering_avalon_phase1.json").write_text(json.dumps(report, indent=2))
print(f"\nReport saved: reports/shell_engineering_avalon_phase1.json")
