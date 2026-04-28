"""Distill — D-067 Phase B v3 prompt assembly + output parser.

The brain receives `prior_model_md + recent_match_summaries`, returns a
fresh world-model markdown body plus a structured YAML hint block.
This module:

  - Composes the prompt from a per-game template.
  - Parses the brain's output into (markdown body, action_hints,
    rhetorical_hints).
  - Post-processes confidence labels so brain-emitted aspirational
    levels match evidence counts (Ludex Phase B v3 found this
    necessary even on function-calling brains).

Brain calling itself stays out of this module — orchestrated
upstream by the match runner. Distill operates on text only, which
keeps it testable without API calls.

Per drafts/lxm_to_ray_d067_v3_avalon_replan_20260428.md (Q4):
Avalon emits one YAML block with two top-level keys
(action_hints / rhetorical_hints), then the writer splits to
two sidecar files at save time.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = Path(__file__).parent / "distill_prompts"

# Confidence tier rules (Ludex 8c3f02d post-processing convention).
# A tier is invalid if evidence.confirmed < lower bound for that tier.
# disconfirmed crowds the tier downward — 2+ disconfirmations forces
# tentative regardless of confirmed count.
_TIER_MIN_CONFIRMED = {
    "tentative": 1,
    "confirmed": 3,
    "well-supported": 10,
}
_TIER_ORDER = ["tentative", "confirmed", "well-supported"]


@dataclass
class DistillOutput:
    """Parsed brain output — body markdown plus typed hint lists."""
    body_md: str
    action_hints: list[dict] = field(default_factory=list)
    rhetorical_hints: list[dict] = field(default_factory=list)


# ── prompt composition ────────────────────────────────────────────────────


def load_prompt_template(field_or_game: str) -> str:
    """Load `lxm/distill_prompts/<game>.md`. Raises if missing."""
    name = field_or_game.split("/")[-1]  # "lxm/avalon" -> "avalon"
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"no distill prompt template at {path}")
    return path.read_text(encoding="utf-8")


def compose_distill_prompt(
    *,
    field_or_game: str,
    creature: str,
    prior_model_md: str,
    recent_match_summaries: str,
) -> str:
    """Render the per-game template with creature identity + priors +
    trace summaries. The template contains `{creature}`,
    `{prior_model_md}`, `{recent_match_summaries}` placeholders.
    """
    template = load_prompt_template(field_or_game)
    # Use %-substitution-style replacement so curly-braces inside the
    # template body (e.g. YAML examples) don't trip str.format.
    out = template
    out = out.replace("{creature}", creature)
    out = out.replace("{prior_model_md}", prior_model_md or "_(none yet — this is your first reflection.)_")
    out = out.replace("{recent_match_summaries}", recent_match_summaries or "_(no matches in scope.)_")
    return out


# ── output parsing ────────────────────────────────────────────────────────


_FENCED_BLOCK_RE = re.compile(
    r"```(?:yaml|yml)?\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)


def parse_distill_output(output: str) -> DistillOutput:
    """Split the brain's response into a markdown body and the YAML
    hint block. Last fenced YAML block in the response is treated as
    the canonical hints block (in case the brain quotes the schema
    earlier as an example).
    """
    matches = list(_FENCED_BLOCK_RE.finditer(output))
    if not matches:
        # No fenced block — body is the whole output, hints empty.
        return DistillOutput(body_md=output.strip(), action_hints=[], rhetorical_hints=[])

    last = matches[-1]
    body_md = output[: last.start()].rstrip()
    yaml_text = last.group(1)

    import yaml as _yaml
    try:
        parsed = _yaml.safe_load(yaml_text) or {}
    except _yaml.YAMLError:
        # Brain emitted invalid YAML — preserve body, drop hints.
        return DistillOutput(body_md=body_md, action_hints=[], rhetorical_hints=[])

    action = parsed.get("action_hints") or []
    rhet = parsed.get("rhetorical_hints") or []
    if not isinstance(action, list):
        action = []
    if not isinstance(rhet, list):
        rhet = []
    return DistillOutput(
        body_md=body_md,
        action_hints=[h for h in action if isinstance(h, dict)],
        rhetorical_hints=[h for h in rhet if isinstance(h, dict)],
    )


# ── confidence post-processing ────────────────────────────────────────────


def _post_process_one_hint(hint: dict) -> dict:
    """Downgrade `confidence` to match `evidence.confirmed` /
    `evidence.disconfirmed` per Phase B v3 calibration discipline.
    Returns the hint with `confidence` rewritten. Original tier
    preserved at `_calibration_demoted_from` if a demotion occurred.
    """
    out = dict(hint)
    evidence = out.get("evidence") or {}
    confirmed = int(evidence.get("confirmed", 0) or 0)
    disconfirmed = int(evidence.get("disconfirmed", 0) or 0)
    declared = (out.get("confidence") or "tentative").strip().lower()
    if declared not in _TIER_ORDER:
        declared = "tentative"

    # Hard rule: 2+ disconfirmations forces tentative.
    if disconfirmed >= 2:
        max_allowed = "tentative"
    else:
        # Highest tier whose minimum-confirmed bar is met.
        max_allowed = "tentative"
        for tier in _TIER_ORDER:
            if confirmed >= _TIER_MIN_CONFIRMED[tier]:
                max_allowed = tier

    declared_idx = _TIER_ORDER.index(declared)
    max_idx = _TIER_ORDER.index(max_allowed)
    if declared_idx > max_idx:
        out["_calibration_demoted_from"] = declared
        out["confidence"] = max_allowed
    else:
        out["confidence"] = declared

    return out


def post_process_hints(hints: list[dict]) -> list[dict]:
    """Apply confidence calibration to every hint. No-op for hints
    that already match their evidence."""
    return [_post_process_one_hint(h) for h in hints]


def post_process_distill(out: DistillOutput) -> DistillOutput:
    """Apply post-processing to both hint types in a parsed output."""
    return DistillOutput(
        body_md=out.body_md,
        action_hints=post_process_hints(out.action_hints),
        rhetorical_hints=post_process_hints(out.rhetorical_hints),
    )


# ── trace summarization ────────────────────────────────────────────────────


def summarize_trace_for_distill(trace_path: Path, *, agent_id: str | None = None) -> str:
    """Produce a compact text summary of one match trace, oriented
    around the named agent (or all agents if not specified). The
    summary is what the distill prompt feeds back into the brain
    so it can identify patterns without re-reading the full jsonl.

    Format (one match):

      MATCH <id>: outcome=<...>, my_faction=<...>, my_role=<...>, scores=<...>
        Quest 1 (round 1, team_size N): <action_summary>
        Quest 2 ...
        Final: ...
    """
    lines = []
    with trace_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lines.append(json.loads(line))
    if not lines:
        return "(empty trace)"

    meta_first = next((l for l in lines if l.get("kind") == "meta_first"), {})
    meta_last = next((l for l in lines if l.get("kind") == "meta_last"), {})
    turns = [l for l in lines if l.get("kind") == "turn"]

    match_id = meta_first.get("match_id", "?")
    outcome = meta_last.get("outcome", "?")
    scores = meta_last.get("scores") or {}
    my_score = scores.get(agent_id) if agent_id else None
    my_role = None
    if agent_id and turns:
        first_state = turns[0].get("ground_truth_state") or {}
        players = first_state.get("players") or {}
        me = players.get(agent_id) or {}
        my_role = me.get("role")
    my_faction_won = (my_score is not None and my_score >= 1.0)

    out = [
        f"MATCH {match_id}: outcome={outcome}, my_role={my_role}, "
        f"my_score={my_score}, my_faction_won={my_faction_won}"
    ]

    # Per-quest summaries — group by quest_round transitions.
    last_round = None
    for t in turns:
        sig = t.get("state_signature") or {}
        rnd = sig.get("quest_round")
        if rnd != last_round and rnd is not None:
            out.append(f"  Quest {rnd}:")
            last_round = rnd
        # Brief per-turn line
        action = t.get("action") or {}
        if t.get("active_agent_id") == agent_id:
            atype = action.get("type", "?")
            out.append(f"    [me] {atype} {_brief_action(action)}")
        # peer turns omitted from summary by default — the trace itself
        # is available to the brain for fine-grained reads.

    if my_score is not None:
        out.append(f"  Final reward (my): {my_score}")
    return "\n".join(out)


def _brief_action(action: dict) -> str:
    """Compact per-action string for summaries."""
    t = action.get("type", "?")
    if t == "proposal":
        team = action.get("team") or []
        return f"team={team}"
    if t == "vote":
        return f"choice={action.get('choice')}"
    if t == "quest_action":
        return f"choice={action.get('choice')}"
    return ""


# ── sidecar I/O ────────────────────────────────────────────────────────────


def write_world_model(
    creature_dir: Path,
    field_or_game: str,
    body_md: str,
    action_hints: list[dict],
    rhetorical_hints: list[dict],
) -> dict:
    """Write the body + 2 sidecar yaml files into the creature's
    habitat at `creatures/<C>/memory/world_models/<namespace>/<field>.md`
    and `.action.yaml` / `.rhetorical.yaml`. Returns a dict of the
    written paths.
    """
    import yaml as _yaml
    if "/" in field_or_game:
        ns, name = field_or_game.split("/", 1)
    else:
        ns, name = "lxm", field_or_game
    base_dir = creature_dir / "memory" / "world_models" / ns
    base_dir.mkdir(parents=True, exist_ok=True)
    body_path = base_dir / f"{name}.md"
    action_path = base_dir / f"{name}.action.yaml"
    rhet_path = base_dir / f"{name}.rhetorical.yaml"

    body_path.write_text(body_md or "", encoding="utf-8")
    action_path.write_text(
        _yaml.safe_dump({"action_hints": action_hints}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    rhet_path.write_text(
        _yaml.safe_dump({"rhetorical_hints": rhetorical_hints}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {
        "body": body_path,
        "action_hints": action_path,
        "rhetorical_hints": rhet_path,
    }
