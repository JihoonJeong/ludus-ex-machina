"""Response interpreters for LxM.

LxM's default parser (`lxm/envelope.py`) requires agents to emit a JSON
envelope. For format-rigid games and structured agents this is fine, but
register-heavy creatures (per spec v0.1 §B.1) routinely drop the JSON
output in favor of natural prose — their task-shell compliance is low
even when the inline prompt requires JSON.

This module provides a **graceful fallback**: when envelope parsing fails,
the orchestrator asks a per-game interpreter to extract the intended move
from natural language. Rule-based interpreters come first (fast, free,
transparent). A CLI-based bare-brain AI interpreter is the designed
fallback for rule-ambiguous cases (see spec v0.1 §G.3 pending thread).

Design principles:
- Strict JSON parse remains the primary path; interpreters never preempt
  a valid envelope.
- Per-game interpreters own their own vocabulary. A Trust Game interpreter
  knows "cooperate/defect" but nothing about chess.
- Every interpretation result carries a confidence signal so the
  orchestrator can log which path (json | rule | ai) produced each move.
- Rule-ambiguous means the rule returns `None`, not a guess. Guessing is
  the AI-fallback's job.
"""

from lxm.interpreters.base import Interpretation, Interpreter
from lxm.interpreters.registry import (
    get_ai_interpreter,
    get_interpreter,
    register_ai_interpreter,
    register_interpreter,
)

__all__ = [
    "Interpretation",
    "Interpreter",
    "get_interpreter",
    "get_ai_interpreter",
    "register_interpreter",
    "register_ai_interpreter",
]
