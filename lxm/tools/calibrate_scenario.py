"""Scenario Difficulty Index (SDI) calibration tool.

Runs cross-model matches and computes SDI for Deduction scenarios.

Usage:
    # Single scenario (9+ matches: opus/sonnet/haiku × 3 runs)
    python -m lxm.tools.calibrate_scenario games/deduction/scenarios/mystery_001/

    # All scenarios
    python -m lxm.tools.calibrate_scenario games/deduction/scenarios/

SDI = 1 - weighted_solve_rate
    weights: opus=0.15, sonnet=0.25, haiku=0.30, slm_best=0.30
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# SDI weights per model tier
WEIGHTS = {
    "opus": 0.15,
    "sonnet": 0.25,
    "haiku": 0.30,
    "slm_best": 0.30,
}

SDI_GRADES = [
    (0.20, "easy", 1),
    (0.50, "medium", 2),
    (0.80, "hard", 3),
    (1.01, "extreme", 4),
]

RUNS_PER_MODEL = 3
CLOUD_MODELS = ["opus", "sonnet", "haiku"]


def run_match(scenario_id: str, model: str, run_idx: int) -> dict | None:
    """Run a single deduction match and return result dict."""
    match_id = f"sdi_{scenario_id}_{model}_{run_idx}"
    cmd = [
        sys.executable, "scripts/run_match.py",
        "--game", "deduction",
        "--scenario", scenario_id,
        "--agents", model,
        "--adapters", "claude",
        "--models", model,
        "--invocation-mode", "inline",
        "--discovery-turns", "0",
        "--no-shell",
        "--skip-eval",
        "--match-id", match_id,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        print(f"  ⏱ {model} run {run_idx}: timeout")
        return None

    # Parse result from match folder
    result_path = Path("matches") / match_id / "result.json"
    if not result_path.exists():
        print(f"  ✗ {model} run {run_idx}: no result file")
        return None

    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ✗ {model} run {run_idx}: {e}")
        return None


def compute_sdi(model_results: dict[str, list[dict]]) -> dict:
    """Compute SDI and auxiliary metrics from model results."""
    model_stats = {}

    for model in CLOUD_MODELS:
        results = model_results.get(model, [])
        if not results:
            model_stats[model] = {
                "runs": 0, "culprit_correct": 0,
                "avg_score": 0, "avg_files": 0,
                "motive_correct": 0, "method_correct": 0,
            }
            continue

        n = len(results)
        culprit_correct = 0
        motive_correct = 0
        method_correct = 0
        total_files = 0
        total_score = 0

        for r in results:
            details = r.get("details", {})
            for agent_id, d in details.items():
                if d.get("culprit_correct"):
                    culprit_correct += 1
                motive_correct += d.get("motive_correct", 0)
                method_correct += d.get("method_correct", 0)
                total_files += d.get("files_read", 0)
                total_score += d.get("final_score", 0)

        model_stats[model] = {
            "runs": n,
            "culprit_correct": culprit_correct,
            "solve_rate": culprit_correct / n if n > 0 else 0,
            "avg_score": round(total_score / n, 2) if n > 0 else 0,
            "avg_files": round(total_files / n, 1) if n > 0 else 0,
            "motive_correct_rate": round(motive_correct / n, 2) if n > 0 else 0,
            "method_correct_rate": round(method_correct / n, 2) if n > 0 else 0,
        }

    # SLM: use existing data if available, else assume 0
    slm_stats = model_results.get("slm_best", [])
    if slm_stats:
        slm_n = len(slm_stats)
        slm_correct = sum(
            1 for r in slm_stats
            for d in r.get("details", {}).values()
            if d.get("culprit_correct")
        )
        slm_solve_rate = slm_correct / slm_n
        model_stats["slm_best"] = {
            "runs": slm_n, "culprit_correct": slm_correct,
            "solve_rate": slm_solve_rate,
        }
    else:
        slm_solve_rate = 0
        model_stats["slm_best"] = {"runs": 0, "culprit_correct": 0, "solve_rate": 0}

    # Weighted solve rate
    weighted = (
        WEIGHTS["opus"] * model_stats["opus"].get("solve_rate", 0)
        + WEIGHTS["sonnet"] * model_stats["sonnet"].get("solve_rate", 0)
        + WEIGHTS["haiku"] * model_stats["haiku"].get("solve_rate", 0)
        + WEIGHTS["slm_best"] * slm_solve_rate
    )

    sdi = round(1 - weighted, 3)

    # Grade
    grade = "extreme"
    stars = 4
    for threshold, g, s in SDI_GRADES:
        if sdi < threshold:
            grade = g
            stars = s
            break

    # Exploration depth
    all_avg_files = [
        model_stats[m].get("avg_files", 0)
        for m in CLOUD_MODELS if model_stats[m].get("runs", 0) > 0
    ]
    total_evidence = None  # will be filled from first result
    for model in CLOUD_MODELS:
        for r in model_results.get(model, []):
            for d in r.get("details", {}).values():
                total_evidence = d.get("total_evidence")
                break
            if total_evidence:
                break
        if total_evidence:
            break

    exploration_depth = 0
    if total_evidence and all_avg_files:
        exploration_depth = round(
            sum(all_avg_files) / len(all_avg_files) / total_evidence, 2
        )

    # Component difficulty
    motive_rates = [
        model_stats[m].get("motive_correct_rate", 0)
        for m in CLOUD_MODELS if model_stats[m].get("runs", 0) > 0
    ]
    method_rates = [
        model_stats[m].get("method_correct_rate", 0)
        for m in CLOUD_MODELS if model_stats[m].get("runs", 0) > 0
    ]
    avg_motive = sum(motive_rates) / len(motive_rates) if motive_rates else 0
    avg_method = sum(method_rates) / len(method_rates) if method_rates else 0
    component_difficulty = round(1 - (avg_motive + avg_method) / 2, 3)

    return {
        "sdi": sdi,
        "grade": grade,
        "stars": stars,
        "exploration_depth": exploration_depth,
        "component_difficulty": component_difficulty,
        "tested_models": model_stats,
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "calibration_version": "v1",
    }


def calibrate_scenario(scenario_dir: Path, skip_existing: bool = False) -> dict | None:
    """Run calibration matches and generate difficulty_card.json."""
    scenario_json = scenario_dir / "scenario.json"
    if not scenario_json.exists():
        print(f"✗ {scenario_dir.name}: scenario.json not found")
        return None

    scenario = json.loads(scenario_json.read_text(encoding="utf-8"))
    scenario_id = scenario["scenario_id"]
    print(f"\n{'='*50}")
    print(f"Calibrating: {scenario_id} ({scenario.get('title', '?')})")
    print(f"{'='*50}")

    # Check for existing difficulty_card
    card_path = scenario_dir / "difficulty_card.json"
    if skip_existing and card_path.exists():
        existing = json.loads(card_path.read_text(encoding="utf-8"))
        print(f"  ⏭ Already calibrated (SDI={existing.get('sdi')}). Skipping.")
        return existing

    # Run matches
    model_results: dict[str, list[dict]] = {}

    for model in CLOUD_MODELS:
        model_results[model] = []
        for run_idx in range(1, RUNS_PER_MODEL + 1):
            print(f"  Running {model} #{run_idx}...", end=" ", flush=True)
            result = run_match(scenario_id, model, run_idx)
            if result:
                model_results[model].append(result)
                # Quick summary
                details = result.get("details", {})
                for aid, d in details.items():
                    score = d.get("accuracy", 0)
                    files = d.get("files_read", 0)
                    print(f"{score}/3 ({files} files)")
            else:
                print("FAILED")

    # Compute SDI
    card = compute_sdi(model_results)

    # Save difficulty_card.json
    card_path.write_text(
        json.dumps(card, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Print summary
    print(f"\n  SDI: {card['sdi']} → {card['grade'].upper()} {'★' * card['stars']}{'☆' * (4 - card['stars'])}")
    print(f"  Exploration depth: {card['exploration_depth']}")
    for model in CLOUD_MODELS:
        stats = card["tested_models"][model]
        print(f"  {model}: {stats['culprit_correct']}/{stats['runs']} correct, avg {stats.get('avg_files', '?')} files")

    return card


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m lxm.tools.calibrate_scenario <path> [--skip-existing]")
        sys.exit(1)

    target = Path(sys.argv[1])
    skip_existing = "--skip-existing" in sys.argv

    # Determine scenarios
    if (target / "scenario.json").exists():
        scenarios = [target]
    else:
        scenarios = sorted([
            d for d in target.iterdir()
            if d.is_dir() and d.name != "TEMPLATE" and (d / "scenario.json").exists()
            and not d.name.endswith("_ko")  # Skip KO versions (same scenario)
        ])

    if not scenarios:
        print(f"No scenarios found in {target}")
        sys.exit(1)

    results = {}
    for scenario_dir in scenarios:
        card = calibrate_scenario(scenario_dir, skip_existing)
        if card:
            results[scenario_dir.name] = card

    # Final summary
    if len(results) > 1:
        print(f"\n{'='*50}")
        print("CALIBRATION SUMMARY")
        print(f"{'='*50}")
        for name, card in sorted(results.items()):
            print(f"  {name}: SDI={card['sdi']} → {card['grade'].upper()} {'★' * card['stars']}{'☆' * (4 - card['stars'])}")


if __name__ == "__main__":
    main()
