"""Tests for lxm/distill.py — D-067 Phase B v3 prompt + parser.

Coverage:
- prompt template loads + substitutes {creature}, {prior_model_md},
  {recent_match_summaries}
- parser handles brain output with one fenced YAML block at end,
  multiple blocks, no block, malformed YAML
- post-processing demotes confidence per evidence count
- trace summarization produces a compact match digest
- write_world_model lays out body + 2 sidecar YAMLs in the right
  habitat path
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from lxm import distill


# ── prompt template ────────────────────────────────────────────────────────


def test_load_prompt_template_avalon():
    text = distill.load_prompt_template("lxm/avalon")
    assert "Avalon" in text
    assert "{creature}" in text
    assert "{prior_model_md}" in text
    assert "{recent_match_summaries}" in text


def test_load_prompt_template_missing():
    with pytest.raises(FileNotFoundError):
        distill.load_prompt_template("lxm/nonexistent")


def test_compose_substitutes_placeholders():
    out = distill.compose_distill_prompt(
        field_or_game="lxm/avalon",
        creature="Echo",
        prior_model_md="(empty prior)",
        recent_match_summaries="(no matches)",
    )
    assert "Echo" in out
    assert "(empty prior)" in out
    assert "(no matches)" in out
    # Placeholders must all be filled.
    assert "{creature}" not in out
    assert "{prior_model_md}" not in out
    assert "{recent_match_summaries}" not in out


def test_compose_default_when_priors_empty():
    out = distill.compose_distill_prompt(
        field_or_game="lxm/avalon",
        creature="X",
        prior_model_md="",
        recent_match_summaries="",
    )
    assert "first reflection" in out
    assert "no matches" in out


# ── output parser ──────────────────────────────────────────────────────────


VALID_BRAIN_OUTPUT = """\
### Reward correlates
Won as good 3 of 5 times when I voted reject on quest 1.

### Policy hints
- (tentative) early-quest reject if leader proposed an evil-revealed peer

### Open uncertainty
- Does this hold for evil-side play?

```yaml
action_hints:
  - id: reject-q1-with-evil-revealed
    rule: "vote reject on quest 1 if leader proposed an evil-revealed peer"
    precondition:
      phase: vote
      my_role: good
      quest_round: 1
    action:
      type: vote
      choice: reject
    confidence: tentative
    evidence:
      confirmed: 2
      disconfirmed: 0
    last_episode: avalon_smoke_001

rhetorical_hints:
  - id: peer-says-careful
    pattern: "uses 'we should be careful here'"
    role_correlation:
      evil: 4
      good: 2
    precondition:
      phase: propose
    confidence: confirmed
    evidence:
      confirmed: 4
      disconfirmed: 1
    last_episode: avalon_smoke_002
```
"""


def test_parser_extracts_body_and_hints():
    out = distill.parse_distill_output(VALID_BRAIN_OUTPUT)
    assert "Reward correlates" in out.body_md
    assert "```yaml" not in out.body_md
    assert len(out.action_hints) == 1
    assert out.action_hints[0]["id"] == "reject-q1-with-evil-revealed"
    assert len(out.rhetorical_hints) == 1
    assert out.rhetorical_hints[0]["id"] == "peer-says-careful"


def test_parser_uses_last_yaml_block_when_multiple():
    """If the brain quotes the schema as an example and then emits
    its real hints, use the LAST fenced YAML block."""
    text = (
        "Some narrative\n\n"
        "Schema example:\n"
        "```yaml\naction_hints:\n  - id: example-only\n```\n\n"
        "My actual hints:\n"
        "```yaml\naction_hints:\n  - id: real-one\n    confidence: tentative\n    evidence:\n      confirmed: 1\n      disconfirmed: 0\nrhetorical_hints: []\n```\n"
    )
    out = distill.parse_distill_output(text)
    assert len(out.action_hints) == 1
    assert out.action_hints[0]["id"] == "real-one"


def test_parser_no_yaml_block_returns_empty_hints():
    text = "Just narrative, no hints emitted."
    out = distill.parse_distill_output(text)
    assert out.body_md == "Just narrative, no hints emitted."
    assert out.action_hints == []
    assert out.rhetorical_hints == []


def test_parser_malformed_yaml_drops_hints_keeps_body():
    text = "Body content.\n\n```yaml\n{ this: is: not: yaml }\n```\n"
    out = distill.parse_distill_output(text)
    assert "Body content" in out.body_md
    assert out.action_hints == []
    assert out.rhetorical_hints == []


# ── confidence post-processing ─────────────────────────────────────────────


def test_post_process_demotes_unsupported_confirmed():
    h = {
        "id": "x", "confidence": "confirmed",
        "evidence": {"confirmed": 1, "disconfirmed": 0},
    }
    out = distill._post_process_one_hint(h)
    assert out["confidence"] == "tentative"
    assert out["_calibration_demoted_from"] == "confirmed"


def test_post_process_keeps_well_supported_when_evidence_strong():
    h = {
        "id": "x", "confidence": "well-supported",
        "evidence": {"confirmed": 12, "disconfirmed": 0},
    }
    out = distill._post_process_one_hint(h)
    assert out["confidence"] == "well-supported"
    assert "_calibration_demoted_from" not in out


def test_post_process_disconfirmation_forces_tentative():
    """2+ disconfirmations forces tentative regardless of confirmed
    count (Phase B v3 hard rule)."""
    h = {
        "id": "x", "confidence": "well-supported",
        "evidence": {"confirmed": 15, "disconfirmed": 2},
    }
    out = distill._post_process_one_hint(h)
    assert out["confidence"] == "tentative"


def test_post_process_uses_implicit_tentative_for_unknown_label():
    h = {
        "id": "x", "confidence": "absolutely-certain",  # not a valid tier
        "evidence": {"confirmed": 4, "disconfirmed": 0},
    }
    out = distill._post_process_one_hint(h)
    # 4 confirmed, 0 disconfirmed => max-allowed = confirmed; declared
    # was bogus -> normalized to tentative; tentative_idx (0) <= 1, no
    # demotion. Result: tentative.
    assert out["confidence"] == "tentative"


def test_post_process_distill_applies_to_both_hint_types():
    out = distill.parse_distill_output(VALID_BRAIN_OUTPUT)
    processed = distill.post_process_distill(out)
    # action_hints: confirmed=2 declared tentative -> stays tentative
    assert processed.action_hints[0]["confidence"] == "tentative"
    # rhetorical_hints: confirmed=4, disconfirmed=1, declared confirmed
    # -> 4 confirmed meets confirmed tier; 1 disconfirmed below 2 hard
    # rule -> stays confirmed
    assert processed.rhetorical_hints[0]["confidence"] == "confirmed"


# ── trace summarization ────────────────────────────────────────────────────


def test_summarize_trace(tmp_path: Path):
    # Synth a tiny trace
    trace_path = tmp_path / "trace.jsonl"
    lines = [
        {"kind": "meta_first", "match_id": "tiny", "field": "lxm/avalon"},
        {
            "kind": "turn",
            "turn": 1,
            "active_agent_id": "agent-a",
            "phase": "propose",
            "ground_truth_state": {
                "players": {"agent-a": {"role": "good"}, "agent-b": {"role": "evil"}},
                "phase": "propose",
            },
            "state_signature": {"quest_round": 1, "phase": "propose"},
            "action": {"type": "proposal", "team": ["agent-a", "agent-b"]},
        },
        {
            "kind": "turn",
            "turn": 2,
            "active_agent_id": "agent-b",
            "phase": "vote",
            "ground_truth_state": {"phase": "vote"},
            "state_signature": {"quest_round": 1, "phase": "vote"},
            "action": {"type": "vote", "choice": "approve"},
        },
        {"kind": "meta_last", "outcome": "good_wins", "scores": {"agent-a": 1.0, "agent-b": 0.0}},
    ]
    with trace_path.open("w") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")

    summary = distill.summarize_trace_for_distill(trace_path, agent_id="agent-a")
    assert "MATCH tiny" in summary
    assert "good_wins" in summary
    assert "my_role=good" in summary
    assert "Quest 1" in summary
    assert "[me] proposal" in summary  # active turn for agent-a captured


# ── write_world_model ──────────────────────────────────────────────────────


# ── retrieval (Day 3 AM) ───────────────────────────────────────────────────


def test_precondition_matches_subset_semantics():
    sig = {"phase": "vote", "my_role": "good", "quest_round": 1, "is_leader": True}
    # Empty precondition matches anything
    assert distill._precondition_matches({}, sig) is True
    # Single key match
    assert distill._precondition_matches({"phase": "vote"}, sig) is True
    # Multi-key match
    assert distill._precondition_matches(
        {"phase": "vote", "my_role": "good"}, sig
    ) is True
    # Mismatch on one key
    assert distill._precondition_matches({"phase": "propose"}, sig) is False
    # Key in precondition not in signature -> no match
    assert distill._precondition_matches(
        {"phase": "vote", "evil_revealed_count": 2}, sig
    ) is False


def test_get_relevant_hints_filters_and_sorts():
    sig = {"phase": "vote", "my_role": "good", "quest_round": 1}
    hints = [
        {
            "id": "off-phase",
            "confidence": "well-supported",
            "evidence": {"confirmed": 12, "disconfirmed": 0},
            "precondition": {"phase": "propose"},
        },
        {
            "id": "weak-but-applies",
            "confidence": "tentative",
            "evidence": {"confirmed": 1, "disconfirmed": 0},
            "precondition": {"phase": "vote"},
        },
        {
            "id": "strong-applies",
            "confidence": "confirmed",
            "evidence": {"confirmed": 5, "disconfirmed": 0},
            "precondition": {"phase": "vote", "my_role": "good"},
        },
        {
            "id": "well-supported-applies",
            "confidence": "well-supported",
            "evidence": {"confirmed": 15, "disconfirmed": 0},
            "precondition": {"phase": "vote"},
        },
    ]
    out = distill.get_relevant_hints(hints, sig, max_hints=4)
    ids = [h["id"] for h in out]
    # off-phase filtered out, others sorted by tier desc then evidence desc
    assert "off-phase" not in ids
    assert ids[0] == "well-supported-applies"
    assert ids[1] == "strong-applies"
    assert ids[2] == "weak-but-applies"


def test_get_relevant_hints_respects_max_cap():
    sig = {"phase": "vote"}
    hints = [
        {
            "id": f"h{i}",
            "confidence": "tentative",
            "evidence": {"confirmed": 1, "disconfirmed": 0},
            "precondition": {"phase": "vote"},
        }
        for i in range(10)
    ]
    out = distill.get_relevant_hints(hints, sig, max_hints=3)
    assert len(out) == 3


def test_get_relevant_hints_empty_when_no_match():
    sig = {"phase": "quest"}
    hints = [{"id": "x", "precondition": {"phase": "vote"}}]
    assert distill.get_relevant_hints(hints, sig) == []


def test_load_creature_hints_reads_both_sidecars(tmp_path: Path):
    creature_dir = tmp_path / "creatures" / "Echo"
    base = creature_dir / "memory" / "world_models" / "lxm"
    base.mkdir(parents=True)
    (base / "avalon.action.yaml").write_text(
        "action_hints:\n"
        "  - id: a1\n"
        "    confidence: tentative\n"
        "    precondition: {phase: vote}\n",
        encoding="utf-8",
    )
    (base / "avalon.rhetorical.yaml").write_text(
        "rhetorical_hints:\n"
        "  - id: r1\n"
        "    confidence: tentative\n"
        "    precondition: {phase: propose}\n",
        encoding="utf-8",
    )
    all_hints = distill.load_creature_hints(creature_dir, "lxm/avalon")
    assert {h["id"] for h in all_hints} == {"a1", "r1"}
    assert next(h for h in all_hints if h["id"] == "a1")["_hint_type"] == "action"

    only_action = distill.load_creature_hints(creature_dir, "lxm/avalon", hint_type="action")
    assert {h["id"] for h in only_action} == {"a1"}


def test_load_creature_hints_missing_sidecar_returns_empty(tmp_path: Path):
    creature_dir = tmp_path / "creatures" / "X"
    creature_dir.mkdir(parents=True)
    assert distill.load_creature_hints(creature_dir, "lxm/avalon") == []


def test_write_world_model_lays_out_three_files(tmp_path: Path):
    creature_dir = tmp_path / "creatures" / "Echo"
    creature_dir.mkdir(parents=True)
    paths = distill.write_world_model(
        creature_dir,
        "lxm/avalon",
        body_md="# Avalon body\n\nHello.",
        action_hints=[{"id": "a1", "confidence": "tentative"}],
        rhetorical_hints=[{"id": "r1", "confidence": "tentative"}],
    )
    assert paths["body"].name == "avalon.md"
    assert paths["action_hints"].name == "avalon.action.yaml"
    assert paths["rhetorical_hints"].name == "avalon.rhetorical.yaml"
    assert paths["body"].parent.name == "lxm"
    assert paths["body"].parent.parent.name == "world_models"
    # Body content faithful
    assert "Avalon body" in paths["body"].read_text()
    # Yaml structure
    import yaml as _yaml
    a = _yaml.safe_load(paths["action_hints"].read_text())
    assert a["action_hints"][0]["id"] == "a1"
    r = _yaml.safe_load(paths["rhetorical_hints"].read_text())
    assert r["rhetorical_hints"][0]["id"] == "r1"
