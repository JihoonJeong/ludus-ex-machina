"""Tests for D-067 bond-memory leak mitigation in LudexCreatureAdapter.

Ray's smoke_021 + handle_recall probe (2026-04-30) showed that
EngineBlock's auto-recall surfaces cross-field biographical memory
into per-turn prompts via TF-IDF vocabulary match. Fix: bypass auto-
recall, do manual lxm-tag-filtered recall in the adapter, and
exclude `deprecated:`-prefix tags so quarantined leak records stay
out of the prompt.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from lxm.adapters.ludex_creature import LudexCreatureAdapter


def _mk_recall(content: str, tags: list[str], score: float):
    """Build a minimal RecallResult-shaped object."""
    mem = MagicMock()
    mem.content = content
    mem.tags = tags
    rec = MagicMock()
    rec.memory = mem
    rec.relevance = score
    return rec


class _FakeMemoryBlock:
    """Minimal stand-in for ludex.blocks.memory.MemoryBlock."""

    def __init__(self, results):
        self._results = results
        self.last_call_kwargs = None

    def handle_recall(self, query, memory_type=None, tags=None, limit=5):
        self.last_call_kwargs = {
            "query": query,
            "memory_type": memory_type,
            "tags": tags,
            "limit": limit,
        }
        return self._results


def _build_adapter_with_memory(memory_block):
    """Construct a bare LudexCreatureAdapter shell with self._memory set
    to memory_block. We bypass __init__ because it requires a live
    Ludex creature path; we only need _maybe_inject_lxm_recalled_memory.
    """
    adapter = LudexCreatureAdapter.__new__(LudexCreatureAdapter)
    adapter._memory = memory_block
    return adapter


class TestLxmRecallFilter(unittest.TestCase):
    def test_recall_called_with_lxm_tag(self):
        mem = _FakeMemoryBlock([])
        a = _build_adapter_with_memory(mem)
        a._maybe_inject_lxm_recalled_memory("prompt")
        self.assertEqual(mem.last_call_kwargs["tags"], ["lxm"])
        self.assertEqual(mem.last_call_kwargs["limit"], 5)

    def test_no_memory_block_returns_prompt_unchanged(self):
        a = _build_adapter_with_memory(None)
        out = a._maybe_inject_lxm_recalled_memory("hello")
        self.assertEqual(out, "hello")

    def test_empty_recall_returns_prompt_unchanged(self):
        mem = _FakeMemoryBlock([])
        a = _build_adapter_with_memory(mem)
        out = a._maybe_inject_lxm_recalled_memory("hello")
        self.assertEqual(out, "hello")

    def test_recall_failure_returns_prompt_unchanged(self):
        mem = _FakeMemoryBlock([])
        # Replace handle_recall with one that raises.
        mem.handle_recall = MagicMock(side_effect=RuntimeError("backend down"))
        a = _build_adapter_with_memory(mem)
        out = a._maybe_inject_lxm_recalled_memory("hello")
        self.assertEqual(out, "hello")  # best-effort, no raise

    def test_deprecated_tag_excluded(self):
        # The smoke_013 [hearth, flint] leak case: tagged ['lxm',
        # 'physis_smoke_013', 'deprecated:lxm_leak']. Should be filtered
        # out even though it passes the lxm-tag retrieval filter.
        results = [
            _mk_recall(
                "I'll think briefly: as Evil leader on Quest 1...",
                tags=["lxm", "physis_smoke_015"],
                score=0.42,
            ),
            _mk_recall(
                "Move submitted: {team: [hearth, flint]} ... bond context",
                tags=["lxm", "physis_smoke_013", "deprecated:lxm_leak"],
                score=0.40,
            ),
        ]
        mem = _FakeMemoryBlock(results)
        a = _build_adapter_with_memory(mem)
        out = a._maybe_inject_lxm_recalled_memory("Q1 propose")
        self.assertIn("[Recalled Memory]", out)
        self.assertIn("Evil leader on Quest 1", out)
        self.assertNotIn("flint", out)  # deprecated leak excluded

    def test_format_block_shape(self):
        results = [
            _mk_recall("hello world", tags=["lxm", "physis_smoke_015"], score=0.5),
        ]
        mem = _FakeMemoryBlock(results)
        a = _build_adapter_with_memory(mem)
        out = a._maybe_inject_lxm_recalled_memory("prompt body")
        self.assertTrue(out.startswith("[Recalled Memory]"))
        self.assertIn("score=0.500", out)
        self.assertIn("hello world", out)
        # The original prompt is preserved after the block.
        self.assertTrue(out.endswith("prompt body"))


if __name__ == "__main__":
    unittest.main()
