"""Scenario generator — Mode C: Human Outline + AI Expansion.

Given a brief JSON outline (culprit, suspects, incident, hints) and an archetype,
generates a complete Deduction Game scenario with case_brief and evidence files.

Usage:
    python -m lxm.tools.generate_scenario outline.json
    python -m lxm.tools.generate_scenario outline.json --id mystery_008
    python -m lxm.tools.generate_scenario outline.json --model opus
    python -m lxm.tools.generate_scenario outline.json --lang ko
    python -m lxm.tools.generate_scenario outline.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCENARIOS_DIR = Path("games/deduction/scenarios")
ARCHETYPES_DIR = Path("games/deduction/archetypes")

REQUIRED_OUTLINE_FIELDS = [
    "archetype", "title", "culprit", "suspects",
    "incident", "motive_hint", "method_hint", "difficulty",
]

# Gen 2 design principles (from TEMPLATE/README.md) — embedded in system prompt
GEN2_PRINCIPLES = """
## Deduction Scenario Design Principles (Generation 2)

### case_brief.md Rules (CRITICAL)
The case_brief is the FIRST thing the player reads. If it contains too much info, the player solves without reading evidence.

INCLUDE only:
- Incident facts: when, where, who was harmed/killed
- Suspect names + job title (1 line each, NO detailed role descriptions)
- "Investigation underway" or "Major crimes unit assigned"

EXCLUDE:
- Cause of death hints (toxicology, poison, IV, etc.)
- Method hints (alarm disabled, locked room, access card, etc.)
- Motive suggestions (business dispute, inheritance, rivalry, etc.)
- Role-specific info that gives away involvement (pharmacist, IT admin with server access, etc.)
- Crime scene details (mechanism clues)

TEST: If an AI can solve the case from case_brief alone, you leaked too much info.

### Structural Requirements
1. 4-5 suspects minimum (3 suspects = 33% random guess)
2. Equal suspicion distribution — at least 2 suspects should have plausible evidence pointing to them
3. Culprit's evidence must contain contradiction — evidence both for AND against the culprit must coexist

### Evidence Files
- Each file: 300-500 words, markdown format, snake_case filename
- Self-contained and independently readable
- Include specific timestamps, names, amounts for cross-referencing
- Critical evidence should be discoverable but not obvious
- Red herrings should be plausible but distinguishable with careful analysis
"""

OUTPUT_FORMAT_SPEC = """
## Required Output Format

You must return a SINGLE JSON object with exactly this structure:

```json
{
  "scenario_json": {
    "scenario_id": "<will be set by tool>",
    "title": "<from outline>",
    "difficulty": "<from outline>",
    "generation": 3,
    "archetype": "<from outline>",
    "description": "<1-line case description>",
    "suspects": ["A", "B", "C", "D"],
    "suspect_names": {"A": "Name (Role)", "B": "Name (Role)", ...},
    "evidence_files": ["file1.md", "file2.md", ...],
    "critical_evidence": ["file_x.md", "file_y.md"],
    "red_herrings": ["file_r1.md", "file_r2.md"],
    "max_reads": <integer, typically total_evidence + 5>,
    "answer": {
      "culprit": "<letter>",
      "motive": "<exact string, will be one of motive_options>",
      "method": "<exact string, will be one of method_options>"
    },
    "motive_options": ["<correct>", "<decoy1>", "<decoy2>", "<decoy3>", "<decoy4>"],
    "method_options": ["<correct>", "<decoy1>", "<decoy2>", "<decoy3>", "<decoy4>"],
    "answer_aliases": {
      "motive": ["alias1", "alias2", "alias3"],
      "method": ["alias1", "alias2", "alias3"]
    }
  },
  "case_brief_md": "<full markdown content of case_brief.md>",
  "evidence_files": {
    "filename1.md": "<full markdown content>",
    "filename2.md": "<full markdown content>",
    ...
  }
}
```

IMPORTANT:
- motive_options and method_options must each have EXACTLY 5 items
- answer.motive must be one of the motive_options (exact string match)
- answer.method must be one of the method_options (exact string match)
- critical_evidence must be a subset of evidence_files
- red_herrings must be a subset of evidence_files
- All filenames in evidence_files must have matching entries in the evidence_files object
- Evidence file content should be 300-500 words each
- Return ONLY the JSON object, no other text
"""


def load_outline(path: str) -> dict:
    """Load and validate the outline JSON file."""
    with open(path, encoding="utf-8") as f:
        outline = json.load(f)

    missing = [f for f in REQUIRED_OUTLINE_FIELDS if f not in outline]
    if missing:
        print(f"[Error] Missing required fields in outline: {', '.join(missing)}")
        sys.exit(1)

    if outline["difficulty"] not in ("easy", "medium", "hard"):
        print(f"[Error] Invalid difficulty: {outline['difficulty']}. Must be easy/medium/hard.")
        sys.exit(1)

    if outline["culprit"] not in outline["suspects"]:
        print(f"[Error] Culprit '{outline['culprit']}' not in suspects list.")
        sys.exit(1)

    return outline


def load_archetype(archetype_id: str) -> dict:
    """Load archetype spec from games/deduction/archetypes/."""
    path = ARCHETYPES_DIR / f"{archetype_id}.json"
    if not path.exists():
        available = [f.stem for f in ARCHETYPES_DIR.glob("*.json")]
        print(f"[Error] Archetype '{archetype_id}' not found.")
        print(f"  Available: {', '.join(sorted(available))}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def next_scenario_id() -> str:
    """Auto-increment scenario ID from existing directories."""
    existing = []
    for d in SCENARIOS_DIR.iterdir():
        if d.is_dir() and d.name.startswith("mystery_"):
            try:
                num = int(d.name.split("_")[1])
                existing.append(num)
            except (ValueError, IndexError):
                pass
    next_num = max(existing, default=0) + 1
    return f"mystery_{next_num:03d}"


def build_prompt(outline: dict, archetype: dict, scenario_id: str) -> tuple[str, str]:
    """Build system and user prompts for the LLM.

    Returns (system_prompt, user_prompt).
    """
    difficulty = outline["difficulty"]
    ev_range = archetype.get("evidence_count", {}).get(difficulty, [10, 14])
    crit_range = archetype.get("critical_evidence_count", {}).get(difficulty, [3, 4])
    rh_range = archetype.get("red_herring_count", {}).get(difficulty, [2, 4])

    system = f"""You are a mystery scenario designer for the LxM Deduction Game.

## Archetype: {archetype['archetype_name']}
{archetype['description']}

## Puzzle Mechanic
{archetype['puzzle_mechanic']}

## Answer Emphasis: {archetype.get('answer_emphasis', 'balanced')}

## Archetype-Specific Generation Rules
{archetype['generation_prompt']}

## Difficulty: {difficulty}
{archetype.get('difficulty_scaling', {}).get(difficulty, '')}

Evidence count target: {ev_range[0]}-{ev_range[1]} files
Critical evidence: {crit_range[0]}-{crit_range[1]} files
Red herrings: {rh_range[0]}-{rh_range[1]} files

{GEN2_PRINCIPLES}

{OUTPUT_FORMAT_SPEC}"""

    # Build user prompt from outline
    user_parts = [
        f"Generate a complete {archetype['archetype_name']} scenario with the following outline:",
        f"",
        f"Title: {outline['title']}",
        f"Setting: {outline.get('setting', 'Not specified')}",
        f"Difficulty: {difficulty}",
        f"Scenario ID: {scenario_id}",
        f"",
        f"Culprit: {outline['culprit']}",
        f"",
        "Suspects:",
    ]
    for sid, name in outline["suspects"].items():
        user_parts.append(f"  {sid}: {name}")

    user_parts.extend([
        f"",
        f"Incident: {outline['incident']}",
        f"Motive hint: {outline['motive_hint']}",
        f"Method hint: {outline['method_hint']}",
    ])

    # Archetype-specific hint fields
    for hint_key in ("key_contradiction", "causal_chain", "trick_mechanism",
                     "timeline_key", "behavioral_key", "numerical_anomaly"):
        if hint_key in outline:
            user_parts.append(f"{hint_key.replace('_', ' ').title()}: {outline[hint_key]}")

    if outline.get("extra_constraints"):
        user_parts.append(f"\nAdditional constraints: {outline['extra_constraints']}")

    user_parts.append(f"\nGenerate the complete scenario now. Return ONLY the JSON object.")

    return system, "\n".join(user_parts)


def invoke_claude(system: str, user: str, model: str = "sonnet") -> str:
    """Invoke Claude CLI and return the response text."""
    claude_bin = "claude.cmd" if os.name == "nt" else "claude"
    cmd = [
        claude_bin, "-p",
        "--input-format", "text",
        "--model", model,
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]

    # Combine system + user into a single prompt
    full_prompt = f"{system}\n\n---\n\n{user}"

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    print(f"[Generate] Invoking Claude ({model})...")
    try:
        result = subprocess.run(
            cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            env=env,
        )
    except FileNotFoundError:
        print("[Error] 'claude' CLI not found. Install Claude Code first.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("[Error] Claude CLI timed out (600s). Try a simpler outline or smaller scenario.")
        sys.exit(1)

    if result.returncode != 0:
        print(f"[Error] Claude CLI exited with code {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:500]}")
        sys.exit(1)

    # Extract text from JSON output format
    stdout = result.stdout.strip()
    if not stdout:
        print("[Error] Empty response from Claude CLI.")
        sys.exit(1)

    try:
        cc_output = json.loads(stdout)
        if isinstance(cc_output, dict) and "result" in cc_output:
            return cc_output["result"]
        return stdout
    except json.JSONDecodeError:
        return stdout


def parse_llm_output(raw: str) -> dict:
    """Parse the LLM's JSON output, handling markdown code fences."""
    text = raw.strip()

    # Strip markdown code fence if present
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```\w*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    # Try to find JSON object in the text
    # Look for the outermost { ... }
    brace_start = text.find("{")
    if brace_start == -1:
        raise ValueError("No JSON object found in LLM output")

    # Find matching closing brace
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                json_str = text[brace_start:i + 1]
                return json.loads(json_str)

    raise ValueError("Unmatched braces in LLM output")


def write_scenario(data: dict, scenario_id: str, output_dir: Path) -> None:
    """Write the parsed scenario data to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = output_dir / "evidence"
    evidence_dir.mkdir(exist_ok=True)

    # Fix scenario_id in the JSON
    scenario_json = data["scenario_json"]
    scenario_json["scenario_id"] = scenario_id

    # Write scenario.json
    (output_dir / "scenario.json").write_text(
        json.dumps(scenario_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  scenario.json ✓")

    # Write case_brief.md
    (output_dir / "case_brief.md").write_text(
        data["case_brief_md"],
        encoding="utf-8",
    )
    print(f"  case_brief.md ✓")

    # Write evidence files
    evidence_files = data.get("evidence_files", {})
    for filename, content in evidence_files.items():
        (evidence_dir / filename).write_text(content, encoding="utf-8")
    print(f"  evidence/ ({len(evidence_files)} files) ✓")


def run_validation(scenario_dir: Path) -> bool:
    """Run the existing validator on the generated scenario."""
    try:
        from lxm.tools.validate_scenario import validate_scenario
        valid, errors, warnings = validate_scenario(scenario_dir)

        if errors:
            print(f"\n[Validation] ERRORS:")
            for e in errors:
                print(f"  ✗ {e}")
        if warnings:
            print(f"\n[Validation] Warnings:")
            for w in warnings:
                print(f"  ⚠ {w}")

        if valid:
            print(f"\n[Validation] ✓ Scenario is valid")
        else:
            print(f"\n[Validation] ✗ Scenario has errors (see above)")

        return valid
    except ImportError:
        print("[Validation] Could not import validator (skipped)")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Deduction Game scenario from a brief outline"
    )
    parser.add_argument("outline", help="Path to outline JSON file")
    parser.add_argument("--id", dest="scenario_id", help="Scenario ID (default: auto-increment)")
    parser.add_argument("--model", default="sonnet", help="Claude model (default: sonnet)")
    parser.add_argument("--lang", default="en", help="Language: en or ko (default: en)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt without calling LLM")
    parser.add_argument("--output-dir", help="Custom output directory (default: games/deduction/scenarios/)")
    args = parser.parse_args()

    # Stage 1: Parse and validate
    print(f"[1/5] Loading outline: {args.outline}")
    outline = load_outline(args.outline)

    print(f"[1/5] Loading archetype: {outline['archetype']}")
    archetype = load_archetype(outline["archetype"])

    scenario_id = args.scenario_id or next_scenario_id()
    print(f"[1/5] Scenario ID: {scenario_id}")

    # Stage 2: Build prompt
    print(f"[2/5] Building generation prompt...")
    system_prompt, user_prompt = build_prompt(outline, archetype, scenario_id)

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN — Prompt that would be sent to Claude:")
        print("=" * 60)
        print("\n[SYSTEM]\n")
        print(system_prompt)
        print("\n[USER]\n")
        print(user_prompt)
        print("\n" + "=" * 60)
        return

    # Stage 3: Invoke Claude
    print(f"[3/5] Generating scenario with Claude ({args.model})...")
    raw_response = invoke_claude(system_prompt, user_prompt, args.model)

    # Stage 4: Parse and write
    print(f"[4/5] Parsing and writing files...")
    try:
        data = parse_llm_output(raw_response)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[Error] Failed to parse LLM output: {e}")
        print(f"  Raw output (first 500 chars): {raw_response[:500]}")
        # Save raw output for debugging
        debug_path = Path(f"/tmp/generate_scenario_debug_{scenario_id}.txt")
        debug_path.write_text(raw_response, encoding="utf-8")
        print(f"  Full output saved to: {debug_path}")
        sys.exit(1)

    # Validate required keys in output
    for key in ("scenario_json", "case_brief_md", "evidence_files"):
        if key not in data:
            print(f"[Error] LLM output missing required key: {key}")
            sys.exit(1)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = SCENARIOS_DIR / scenario_id
    write_scenario(data, scenario_id, output_dir)

    # Stage 5: Validate
    print(f"[5/5] Running validation...")
    valid = run_validation(output_dir)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"Scenario generated: {output_dir}")
    print(f"  Archetype: {archetype['archetype_name']}")
    print(f"  Title: {outline['title']}")
    print(f"  Difficulty: {outline['difficulty']}")
    print(f"  Evidence files: {len(data.get('evidence_files', {}))}")
    print(f"  Valid: {'✓' if valid else '✗ (check errors above)'}")

    if valid:
        print(f"\nNext steps:")
        print(f"  1. Review: Read the generated files in {output_dir}")
        print(f"  2. Calibrate: python -m lxm.tools.calibrate_scenario {output_dir}")
        if args.lang == "en":
            print(f"  3. Korean: python -m lxm.tools.generate_scenario {args.outline} --lang ko --id {scenario_id}_ko")

    # Handle Korean generation if requested
    if args.lang == "ko" and valid:
        print(f"\n[KO] Korean generation not yet implemented. Generate EN first, then translate.")
        # TODO: Implement KO translation pass


if __name__ == "__main__":
    main()
