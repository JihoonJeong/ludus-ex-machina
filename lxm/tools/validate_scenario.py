"""Deduction scenario validator.

Usage:
    python -m lxm.tools.validate_scenario games/deduction/scenarios/mystery_001/
    python -m lxm.tools.validate_scenario games/deduction/scenarios/  # validate all
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_JSON_FIELDS = [
    "scenario_id", "title", "difficulty", "suspects", "suspect_names",
    "evidence_files", "critical_evidence", "max_reads", "answer",
]
REQUIRED_ANSWER_FIELDS = ["culprit", "motive", "method"]
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
OPTIONAL_WARN_FIELDS = {
    "red_herrings": "red_herrings is empty or missing",
    "answer_ko": "Korean answer not provided (한글 미지원)",
    "motive_options_ko": "Korean motive options not provided (한글 미지원)",
    "method_options_ko": "Korean method options not provided (한글 미지원)",
}


def validate_scenario(path: Path) -> tuple[bool, list[str], list[str]]:
    """Validate a single scenario directory.

    Returns (valid, errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Structure checks ---
    scenario_json = path / "scenario.json"
    if not scenario_json.exists():
        errors.append("scenario.json not found")
        return False, errors, warnings

    case_brief = path / "case_brief.md"
    if not case_brief.exists():
        errors.append("case_brief.md not found")

    evidence_dir = path / "evidence"
    if not evidence_dir.is_dir():
        errors.append("evidence/ directory not found")

    # --- Parse JSON ---
    try:
        with open(scenario_json) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"scenario.json is invalid JSON: {e}")
        return False, errors, warnings

    # --- Required fields ---
    for field in REQUIRED_JSON_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    if errors:
        return False, errors, warnings

    # --- Field validation ---
    difficulty = data.get("difficulty", "")
    if difficulty not in VALID_DIFFICULTIES:
        errors.append(f"invalid difficulty '{difficulty}' (must be {VALID_DIFFICULTIES})")

    suspects = data.get("suspects", [])
    suspect_names = data.get("suspect_names", {})
    evidence_files = data.get("evidence_files", [])
    critical_evidence = data.get("critical_evidence", [])
    answer = data.get("answer", {})

    # Answer sub-fields
    for field in REQUIRED_ANSWER_FIELDS:
        if field not in answer:
            errors.append(f"answer missing required field: {field}")

    # culprit in suspects
    if answer.get("culprit") and answer["culprit"] not in suspects:
        errors.append(f"answer.culprit '{answer['culprit']}' not in suspects {suspects}")

    # motive/method in options
    motive_options = data.get("motive_options", [])
    method_options = data.get("method_options", [])

    if not motive_options:
        errors.append("motive_options is missing or empty")
    elif answer.get("motive") and answer["motive"] not in motive_options:
        errors.append(f"answer.motive '{answer['motive']}' not in motive_options")

    if not method_options:
        errors.append("method_options is missing or empty")
    elif answer.get("method") and answer["method"] not in method_options:
        errors.append(f"answer.method '{answer['method']}' not in method_options")

    # suspect_names covers all suspects
    for s in suspects:
        if s not in suspect_names:
            errors.append(f"suspect '{s}' missing from suspect_names")

    # critical_evidence subset of evidence_files
    for ce in critical_evidence:
        if ce not in evidence_files:
            errors.append(f"critical_evidence '{ce}' not in evidence_files")

    # Evidence files exist on disk
    if evidence_dir.is_dir():
        for ef in evidence_files:
            if not (evidence_dir / ef).exists():
                errors.append(f"evidence file '{ef}' not found in evidence/")

    # --- Warnings ---
    red_herrings = data.get("red_herrings")
    if not red_herrings:
        warnings.append("red_herrings is empty or missing")

    for field, msg in OPTIONAL_WARN_FIELDS.items():
        if field == "red_herrings":
            continue  # already handled
        if field not in data:
            warnings.append(msg)

    n_evidence = len(evidence_files)
    if n_evidence < 5:
        warnings.append(f"only {n_evidence} evidence files (recommend 5-20)")
    elif n_evidence > 20:
        warnings.append(f"{n_evidence} evidence files (recommend 5-20)")

    max_reads = data.get("max_reads", 0)
    if not isinstance(max_reads, int) or max_reads < 1:
        errors.append(f"max_reads must be a positive integer, got {max_reads}")

    valid = len(errors) == 0
    return valid, errors, warnings


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m lxm.tools.validate_scenario <path>")
        print("  <path> can be a single scenario dir or parent dir containing multiple scenarios")
        sys.exit(1)

    target = Path(sys.argv[1])

    # Determine if single scenario or parent directory
    if (target / "scenario.json").exists():
        scenarios = [target]
    else:
        scenarios = sorted([
            d for d in target.iterdir()
            if d.is_dir() and d.name != "TEMPLATE" and (d / "scenario.json").exists()
        ])

    if not scenarios:
        print(f"No scenarios found in {target}")
        sys.exit(1)

    all_valid = True
    for scenario_dir in scenarios:
        sid = scenario_dir.name
        valid, errors, warnings = validate_scenario(scenario_dir)

        if valid and not warnings:
            n_ev = len(json.loads((scenario_dir / "scenario.json").read_text()).get("evidence_files", []))
            diff = json.loads((scenario_dir / "scenario.json").read_text()).get("difficulty", "?")
            print(f"✅ {sid}: Valid ({n_ev} evidence files, difficulty={diff})")
        elif valid and warnings:
            print(f"⚠️  {sid}: Valid with warnings")
            for w in warnings:
                print(f"    - {w}")
        else:
            all_valid = False
            print(f"❌ {sid}: INVALID")
            for e in errors:
                print(f"    - {e}")
            if warnings:
                for w in warnings:
                    print(f"    - ⚠️  {w}")

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
