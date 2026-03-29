"""Deduction Cross-Model Test — 3 scenarios × 3 models = 9 matches.

Models: haiku, sonnet, opus
Scenarios: mystery_001, mystery_002, mystery_003
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from games.deduction.engine import DeductionGame
from lxm.orchestrator import Orchestrator

MODELS = ["haiku", "sonnet", "opus"]
SCENARIOS = ["mystery_001", "mystery_002", "mystery_003"]


def run_one(scenario_id, model):
    match_id = f"deduction_cm_{scenario_id}_{model}"

    game = DeductionGame(scenario_id=scenario_id)
    agent_config = {"agent_id": f"det-{model}", "display_name": f"det-{model}", "seat": 0}
    match_config = {
        "protocol_version": "lxm-v0.2",
        "match_id": match_id,
        "game": {"name": "deduction", "version": "1.0"},
        "time_model": {"type": "turn_based", "turn_order": "sequential",
                       "max_turns": 30, "timeout_seconds": 120,
                       "timeout_action": "no_op", "max_retries": 3},
        "agents": [agent_config],
        "history": {"recent_moves_count": 10},
        "invocation": {"mode": "inline", "discovery_turns": 0},
    }

    from lxm.adapters.claude_code import ClaudeCodeAdapter
    adapter = ClaudeCodeAdapter({"agent_id": f"det-{model}", "model": model, "timeout_seconds": 120})
    adapters = {f"det-{model}": adapter}

    orch = Orchestrator(game, match_config, adapters)
    orch.run_evaluation = lambda match_dir: None
    match_dir = orch.setup_match()

    try:
        result = orch.run()
        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


print("=" * 70)
print("  DEDUCTION CROSS-MODEL: 3 scenarios × 3 models = 9 matches")
print("=" * 70)

all_results = {}

for scenario in SCENARIOS:
    print(f"\n--- {scenario} ---")
    for model in MODELS:
        print(f"\n  {model}:")
        result = run_one(scenario, model)
        key = f"{scenario}_{model}"

        if result and "details" in result:
            det_key = f"det-{model}"
            d = result["details"].get(det_key, {})
            c = "✅" if d.get("culprit_correct") else "❌"
            m = "✅" if d.get("motive_correct") == 1 else "❌"
            h = "✅" if d.get("method_correct") == 1 else "❌"
            print(f"    {c} culprit | {m} motive | {h} method | {d.get('files_read',0)}/{d.get('total_evidence',0)} files | score {d.get('final_score',0)}")
            all_results[key] = d
        else:
            print(f"    FAILED")
            all_results[key] = None

# Summary table
print("\n" + "=" * 70)
print("  SUMMARY")
print("=" * 70)
print(f"\n{'Scenario':<15} {'Model':<8} {'Culprit':<9} {'Motive':<8} {'Method':<8} {'Files':<8} {'Score':<6}")
print("-" * 62)

for scenario in SCENARIOS:
    for model in MODELS:
        key = f"{scenario}_{model}"
        d = all_results.get(key)
        if d:
            c = "✅" if d.get("culprit_correct") else "❌"
            m = "✅" if d.get("motive_correct") == 1 else "❌"
            h = "✅" if d.get("method_correct") == 1 else "❌"
            files = f"{d.get('files_read',0)}/{d.get('total_evidence',0)}"
            print(f"{scenario:<15} {model:<8} {c:<9} {m:<8} {h:<8} {files:<8} {d.get('final_score',0):.2f}")
        else:
            print(f"{scenario:<15} {model:<8} FAILED")

# Save JSON
Path("reports").mkdir(exist_ok=True)
Path("reports/deduction_crossmodel.json").write_text(json.dumps(all_results, indent=2, default=str))
print(f"\nReport: reports/deduction_crossmodel.json")
