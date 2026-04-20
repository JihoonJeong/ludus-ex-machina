"""Interpreter base class for natural-language → move extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Interpretation:
    """Result of extracting a move from a player's free-text response.

    `move` is the game-specific move dict (same shape as the `move` field
    of an LxM envelope). `confidence` is a float 0..1 — interpreters may
    leave it at a neutral value when they can't meaningfully estimate it.
    `path` is a short label used for post-match analysis (rule-based
    interpreters should use `"rule"`, AI interpreters `"ai"`). `evidence`
    is optional structured explanation (e.g. which keywords matched) —
    written into the envelope meta so the log shows WHY the interpreter
    chose this move.
    """

    move: dict
    confidence: float = 0.7
    path: str = "rule"
    evidence: dict = field(default_factory=dict)


class Interpreter(ABC):
    """Extract a move from a player's free-form response.

    Subclasses are per-game. They receive the full response text (already
    stripped of fenced JSON by the caller, but may still contain prose)
    plus a minimal `context` dict built by the orchestrator. They return
    an `Interpretation` when they can, or `None` when the response is
    truly ambiguous — at which point the orchestrator may hand off to a
    CLI-based AI interpreter, or declare the turn a no-op.
    """

    game: str = ""  # set by subclass; matches orchestrator's game name

    @abstractmethod
    def interpret(self, response: str, context: dict[str, Any]) -> Interpretation | None:
        """Return an Interpretation, or None if the text is too ambiguous."""
        ...
