"""Tests for lxm/envelope.py"""

import json
import tempfile
from pathlib import Path

from lxm.envelope import parse_from_file, parse_from_stdout, validate_envelope


SAMPLE_ENVELOPE = {
    "protocol": "lxm-v0.2",
    "match_id": "match_001",
    "agent_id": "claude-alpha",
    "turn": 1,
    "move": {"type": "place", "position": [1, 1]},
}

MATCH_CONFIG = {
    "protocol_version": "lxm-v0.2",
    "match_id": "match_001",
}


class TestParseFromFile:
    def test_valid_json_file(self, tmp_path):
        f = tmp_path / "move.json"
        f.write_text(json.dumps(SAMPLE_ENVELOPE))
        result = parse_from_file(str(f))
        assert result == SAMPLE_ENVELOPE

    def test_nonexistent_file(self):
        result = parse_from_file("/nonexistent/path.json")
        assert result is None

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json {{{")
        result = parse_from_file(str(f))
        assert result is None


class TestParseFromStdout:
    def test_clean_json(self):
        output = json.dumps(SAMPLE_ENVELOPE)
        result = parse_from_stdout(output)
        assert result == SAMPLE_ENVELOPE

    def test_json_in_markdown_fence(self):
        output = f"Here is my move:\n```json\n{json.dumps(SAMPLE_ENVELOPE)}\n```\nDone!"
        result = parse_from_stdout(output)
        assert result == SAMPLE_ENVELOPE

    def test_noisy_stdout(self):
        output = (
            "Let me think about this...\n"
            "I'll play center.\n"
            f"{json.dumps(SAMPLE_ENVELOPE)}\n"
            "That's my move."
        )
        result = parse_from_stdout(output)
        assert result == SAMPLE_ENVELOPE

    def test_no_json(self):
        output = "I don't know what to do. No JSON here."
        result = parse_from_stdout(output)
        assert result is None

    def test_json_without_protocol(self):
        output = json.dumps({"some": "object"})
        result = parse_from_stdout(output)
        assert result is None

    def test_multiple_json_picks_first_with_protocol(self):
        other = json.dumps({"not": "envelope"})
        envelope = json.dumps(SAMPLE_ENVELOPE)
        output = f"First: {other}\nSecond: {envelope}"
        result = parse_from_stdout(output)
        assert result == SAMPLE_ENVELOPE

    def test_codex_thread_started_not_wrapped(self):
        """Regression: codex CLI 0.125+ emits {"type":"thread.started",...}
        metadata in its stdout stream. The Strategy-3 fallback used to wrap
        the FIRST `{type: ...}` it saw as a move envelope, mis-classifying
        the stream metadata as the agent's move. Fallback is now restricted
        to LxM move types ('action' / 'say')."""
        thread_meta = json.dumps({"type": "thread.started", "thread_id": "abc-123"})
        action_json = json.dumps({"type": "action", "verb": "move", "direction": "north"})
        # Stream order: codex emits thread.started before the agent_message.
        output = f"{thread_meta}\n{action_json}"
        result = parse_from_stdout(output)
        assert result is not None
        assert result["move"]["type"] == "action"
        assert result["move"]["verb"] == "move"

    def test_fallback_skips_non_move_type_objects(self):
        """`type: thread.started` and other CLI metadata must NOT be wrapped
        as a move when no protocol envelope is found."""
        output = json.dumps({"type": "thread.started", "thread_id": "abc"})
        result = parse_from_stdout(output)
        assert result is None


class TestValidateEnvelope:
    def test_valid(self):
        result = validate_envelope(SAMPLE_ENVELOPE, MATCH_CONFIG, "claude-alpha", 1)
        assert result == {"valid": True, "message": None}

    def test_wrong_protocol(self):
        env = {**SAMPLE_ENVELOPE, "protocol": "lxm-v0.1"}
        result = validate_envelope(env, MATCH_CONFIG, "claude-alpha", 1)
        assert not result["valid"]
        assert "protocol" in result["message"].lower()

    def test_wrong_match_id(self):
        env = {**SAMPLE_ENVELOPE, "match_id": "wrong"}
        result = validate_envelope(env, MATCH_CONFIG, "claude-alpha", 1)
        assert not result["valid"]

    def test_wrong_agent_id(self):
        result = validate_envelope(SAMPLE_ENVELOPE, MATCH_CONFIG, "claude-beta", 1)
        assert not result["valid"]

    def test_wrong_turn(self):
        result = validate_envelope(SAMPLE_ENVELOPE, MATCH_CONFIG, "claude-alpha", 5)
        assert not result["valid"]
        assert "turn" in result["message"].lower()

    def test_missing_move(self):
        env = {k: v for k, v in SAMPLE_ENVELOPE.items() if k != "move"}
        result = validate_envelope(env, MATCH_CONFIG, "claude-alpha", 1)
        assert not result["valid"]

    def test_move_not_dict(self):
        env = {**SAMPLE_ENVELOPE, "move": "not a dict"}
        result = validate_envelope(env, MATCH_CONFIG, "claude-alpha", 1)
        assert not result["valid"]
