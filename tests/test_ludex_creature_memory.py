"""Per-turn memory capture in LudexCreatureAdapter (2026-06-30 Ludex audit).

The Ludex private-lab audit found dozens of episodic memories whose content was
an adapter error-fallback ("<name> @<field>: [Error: ... CLI timed out]"),
written per-turn by the LxM creature adapter. Two fixes verified here:
  1. an error-fallback turn is NEVER captured as memory;
  2. per-turn capture is opt-in (`record_turn_memory`, default off) — live
     creatures use the per-match distilled memory (on_match_end) instead.
"""

from __future__ import annotations

from lxm.adapters.ludex_creature import LudexCreatureAdapter


class _FakeMemory:
    def __init__(self):
        self.calls = []

    def handle_remember(self, **kwargs):
        self.calls.append(kwargs)


def _adapter(record_turn_memory, memory):
    """Bare adapter shell (bypasses __init__, which needs a live creature)."""
    a = LudexCreatureAdapter.__new__(LudexCreatureAdapter)
    a._record_turn_memory = record_turn_memory
    a._record_memory = True
    a._memory = memory
    a._agent_id = "Echo"
    return a


# ── _is_error_fallback (mirrors ludex.core.selfhood._is_error_fallback) ───────

def test_is_error_fallback_detects_ludex_formats():
    f = LudexCreatureAdapter._is_error_fallback
    assert f("[Error: Claude CLI timed out]") is True
    assert f("  [Error: 'claude' not found. Is Claude Code CLI installed?]") is True
    assert f("[ERROR: codex CLI timed out]") is True          # case-insensitive
    assert f("[Error: agy CLI timed out]") is True


def test_is_error_fallback_passes_real_output():
    f = LudexCreatureAdapter._is_error_fallback
    assert f('{"type":"move","move":{"action":"cooperate"}}') is False
    assert f("I propose Alice and Bob for the quest.") is False
    assert f("") is False
    assert f(None) is False
    # an error mentioned mid-utterance is real creature output, not a fallback
    assert f("I noticed an [Error: ...] earlier but will proceed") is False


# ── _maybe_record_turn ───────────────────────────────────────────────────────

def test_turn_memory_off_by_default_writes_nothing():
    mem = _FakeMemory()
    _adapter(record_turn_memory=False, memory=mem)._maybe_record_turn("good response", "m1")
    assert mem.calls == []


def test_turn_memory_on_writes_episodic_with_expected_shape():
    mem = _FakeMemory()
    _adapter(record_turn_memory=True, memory=mem)._maybe_record_turn("I propose Alice and Bob.", "m1")
    assert len(mem.calls) == 1
    call = mem.calls[0]
    assert call["memory_type"] == "episodic"
    assert call["tags"] == ["lxm", "m1"]
    assert call["source"] == "lxm/m1/turn"
    assert call["content"].startswith("Echo @m1:")
    assert "I propose Alice and Bob." in call["content"]


def test_turn_memory_skips_error_fallback_even_when_enabled():
    """The headline fix: a timed-out brain call must never become a memory."""
    mem = _FakeMemory()
    _adapter(record_turn_memory=True, memory=mem)._maybe_record_turn(
        "[Error: Claude CLI timed out]", "m1")
    assert mem.calls == []


def test_turn_memory_no_memory_block_is_safe():
    _adapter(record_turn_memory=True, memory=None)._maybe_record_turn("hello", "m1")  # no raise


def test_turn_memory_skips_empty_response():
    mem = _FakeMemory()
    _adapter(record_turn_memory=True, memory=mem)._maybe_record_turn("", "m1")
    assert mem.calls == []


def test_turn_memory_swallows_remember_errors():
    class _Boom:
        def handle_remember(self, **kw):
            raise RuntimeError("memory store offline")
    _adapter(record_turn_memory=True, memory=_Boom())._maybe_record_turn("ok", "m1")  # no raise
