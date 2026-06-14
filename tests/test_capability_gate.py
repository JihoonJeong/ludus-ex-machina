"""Tests for D-072 brain capability gate (LxM-side ship 2026-04-30)."""

import unittest

from lxm.adapters.base import BrainCapabilityError, check_capability_compat
from lxm.adapters.claude_code import ClaudeCodeAdapter
from lxm.adapters.codex_cli import CodexCLIAdapter
from lxm.adapters.gemini_cli import GeminiCLIAdapter
from lxm.adapters.ollama import OllamaAdapter
from lxm.adapters.rule_bot import RuleBotAdapter
from games.avalon.engine import AvalonGame
from games.chess.engine import ChessGame


class TestAdapterCapabilities(unittest.TestCase):
    """Each bare-CLI adapter declares its brain_capabilities at construction."""

    def test_claude_code_emits_json(self):
        a = ClaudeCodeAdapter({"agent_id": "x", "model": "sonnet"})
        self.assertEqual(a.brain_capabilities, ["json_emit"])

    def test_codex_cli_emits_json(self):
        a = CodexCLIAdapter({"agent_id": "x", "model": "gpt-5.4-mini"})
        self.assertEqual(a.brain_capabilities, ["json_emit"])

    def test_gemini_cli_emits_json(self):
        # gemini-cli v0.39+ emits clean JSON for LxM-shape prompts; the earlier
        # v<0.39 "narrative only" verdict is retired (see gemini_cli.py). A
        # genuinely narrative-only brain is exercised via an unknown ollama
        # model below.
        a = GeminiCLIAdapter({"agent_id": "x", "model": "gemini-2.5-flash"})
        self.assertEqual(a.brain_capabilities, ["json_emit"])

    def test_rule_bot_emits_json(self):
        a = RuleBotAdapter({"agent_id": "x", "model": "medium"})
        self.assertEqual(a.brain_capabilities, ["json_emit"])

    def test_ollama_known_model_has_both(self):
        a = OllamaAdapter({"agent_id": "x", "model": "qwen-coder:7b"})
        self.assertIn("json_emit", a.brain_capabilities)
        self.assertIn("narrative", a.brain_capabilities)

    def test_ollama_unknown_model_narrative_default(self):
        a = OllamaAdapter({"agent_id": "x", "model": "some-future-model:99b"})
        self.assertEqual(a.brain_capabilities, ["narrative"])


class TestCapabilityGate(unittest.TestCase):
    """check_capability_compat raises when (brain × field) sets don't overlap."""

    def test_json_brain_passes_json_field(self):
        adapter = ClaudeCodeAdapter({"agent_id": "x", "model": "sonnet"})
        check_capability_compat(adapter, AvalonGame())  # no raise

    def test_narrative_brain_rejected_on_json_field(self):
        # Chess still inherits the default ["json_emit"] from LxMGame.
        # A narrative-only brain (unknown ollama model -> ["narrative"]) has
        # no overlap with chess's json_emit field, so the gate rejects it.
        adapter = OllamaAdapter({"agent_id": "wick", "model": "some-future-model:99b"})
        with self.assertRaises(BrainCapabilityError) as ctx:
            check_capability_compat(adapter, ChessGame())
        msg = str(ctx.exception)
        self.assertIn("wick", msg)
        self.assertIn("narrative", msg)
        self.assertIn("json_emit", msg)

    def test_narrative_brain_passes_avalon_after_extractor(self):
        # Once the AvalonRuleInterpreter landed, narrative-only brains
        # can play Avalon — the extractor pulls the JSON move from prose.
        adapter = OllamaAdapter({"agent_id": "wick", "model": "some-future-model:99b"})
        check_capability_compat(adapter, AvalonGame())  # no raise

    def test_default_field_accepts_json_emit(self):
        # A game without explicit accepts_capabilities falls back to base
        # default ["json_emit"] inherited from LxMGame.
        from lxm.engine import LxMGame
        self.assertEqual(LxMGame.accepts_capabilities, ["json_emit"])

    def test_error_carries_diagnostic_fields(self):
        adapter = OllamaAdapter({"agent_id": "wick", "model": "some-future-model:99b"})
        with self.assertRaises(BrainCapabilityError) as ctx:
            check_capability_compat(adapter, ChessGame())
        e = ctx.exception
        self.assertEqual(e.adapter, "OllamaAdapter")
        self.assertEqual(e.agent_id, "wick")
        self.assertEqual(e.brain_capabilities, ["narrative"])
        self.assertEqual(e.game, "ChessGame")
        self.assertEqual(e.accepts_capabilities, ["json_emit"])


if __name__ == "__main__":
    unittest.main()
