"""Interpreter registry — pick per-game interpreter by name.

Mirrors `lxm/adapters/registry.py`. Default interpreters are loaded
lazily on first access; custom interpreters may be registered at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxm.interpreters.base import Interpreter

_INTERPRETERS: dict[str, "Interpreter"] = {}
_AI_INTERPRETERS: dict[str, "Interpreter"] = {}
_DEFAULTS_LOADED = False


def register_interpreter(game: str, interpreter: "Interpreter") -> None:
    """Register a rule-based interpreter instance for a game."""
    _INTERPRETERS[game] = interpreter


def register_ai_interpreter(game: str, interpreter: "Interpreter") -> None:
    """Register an AI-CLI interpreter instance for a game (fallback chain)."""
    _AI_INTERPRETERS[game] = interpreter


def get_interpreter(game: str) -> "Interpreter | None":
    """Return the rule-based interpreter for a game, or None."""
    _ensure_defaults()
    return _INTERPRETERS.get(game)


def get_ai_interpreter(game: str) -> "Interpreter | None":
    """Return the AI fallback interpreter for a game, or None.

    Defaults are intentionally NOT auto-registered for AI fallbacks —
    AI interpreters cost subprocess time + tokens and should be opted
    in per match. Wire via `register_ai_interpreter()` from a script
    or per-match setup.
    """
    _ensure_defaults()
    return _AI_INTERPRETERS.get(game)


def _ensure_defaults() -> None:
    global _DEFAULTS_LOADED
    if _DEFAULTS_LOADED:
        return
    _DEFAULTS_LOADED = True

    from lxm.interpreters.rules_trustgame import TrustGameRuleInterpreter

    register_interpreter("trustgame", TrustGameRuleInterpreter())
