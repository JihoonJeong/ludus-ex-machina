"""Adapter and game plugin registry.

Replaces hardcoded dicts in run_match.py. Allows custom adapters/games.

Usage:
    from lxm.adapters.registry import get_adapter_class, get_game_class
    AdapterCls = get_adapter_class("claude")
    GameCls = get_game_class("chess")

Custom registration:
    from lxm.adapters.registry import register_adapter
    register_adapter("my_runtime", MyAdapter)
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxm.adapters.base import AgentAdapter
    from lxm.engine import LxMGame

logger = logging.getLogger(__name__)

_ADAPTERS: dict[str, type[AgentAdapter]] = {}
_GAMES: dict[str, type[LxMGame]] = {}
_DEFAULTS_LOADED = False


def register_adapter(name: str, cls: type[AgentAdapter]):
    """Register an adapter class by name."""
    _ADAPTERS[name] = cls


def register_game(name: str, cls: type[LxMGame]):
    """Register a game engine class by name."""
    _GAMES[name] = cls


def get_adapter_class(name: str) -> type[AgentAdapter]:
    """Get adapter class by name. Loads defaults on first call."""
    _ensure_defaults()
    if name not in _ADAPTERS:
        available = ", ".join(sorted(_ADAPTERS.keys()))
        raise KeyError(f"Unknown adapter '{name}'. Available: {available}")
    return _ADAPTERS[name]


def get_game_class(name: str) -> type[LxMGame]:
    """Get game engine class by name. Loads defaults on first call."""
    _ensure_defaults()
    if name not in _GAMES:
        available = ", ".join(sorted(_GAMES.keys()))
        raise KeyError(f"Unknown game '{name}'. Available: {available}")
    return _GAMES[name]


def list_adapters() -> list[str]:
    """List registered adapter names."""
    _ensure_defaults()
    return sorted(_ADAPTERS.keys())


def list_games() -> list[str]:
    """List registered game names."""
    _ensure_defaults()
    return sorted(_GAMES.keys())


# (registry name, module path, class name) for built-in plugins. Imported
# defensively so a missing optional dependency (the hosted server has no
# treys/chess, or no local ludex engine) drops only that plugin.
_ADAPTER_SPECS = [
    ("claude", "lxm.adapters.claude_code", "ClaudeCodeAdapter"),
    ("gemini", "lxm.adapters.gemini_cli", "GeminiCLIAdapter"),
    ("ollama", "lxm.adapters.ollama", "OllamaAdapter"),
    ("codex", "lxm.adapters.codex_cli", "CodexCLIAdapter"),
    ("rule_bot", "lxm.adapters.rule_bot", "RuleBotAdapter"),
    ("ludex", "lxm.adapters.ludex_creature", "LudexCreatureAdapter"),
]
_GAME_SPECS = [
    ("tictactoe", "games.tictactoe.engine", "TicTacToe"),
    ("chess", "games.chess.engine", "ChessGame"),
    ("trustgame", "games.trustgame.engine", "TrustGame"),
    ("codenames", "games.codenames.engine", "CodenamesGame"),
    ("poker", "games.poker.engine", "PokerGame"),
    ("avalon", "games.avalon.engine", "AvalonGame"),
    ("deduction", "games.deduction.engine", "DeductionGame"),
    ("blockworld", "games.blockworld.engine", "BlockworldGame"),
    ("diplomacy", "games.diplomacy.engine", "DiplomacyGame"),
    ("mud", "games.mud.engine", "MudGame"),
    ("agora12", "games.agora12.engine", "Agora12Game"),
    ("three_kingdoms", "games.three_kingdoms.engine", "ThreeKingdomsGame"),
    ("dugout", "games.dugout.engine", "DugoutGame"),
]


def _ensure_defaults():
    """Lazy-load built-in adapters and games on first access.

    Each plugin is imported independently: one whose optional dependency is
    unavailable (e.g. the hosted server has no `treys`/`chess`, or no local
    ludex engine) is skipped with a warning rather than taking down the whole
    registry — so a remote tictactoe match still works on a host that can't
    import poker or the ludex creature adapter.
    """
    global _DEFAULTS_LOADED
    if _DEFAULTS_LOADED:
        return
    _DEFAULTS_LOADED = True

    for name, module_path, cls_name in _ADAPTER_SPECS:
        try:
            register_adapter(name, getattr(importlib.import_module(module_path), cls_name))
        except Exception as e:
            logger.warning("registry: adapter '%s' unavailable (%s)", name, e)
    for name, module_path, cls_name in _GAME_SPECS:
        try:
            register_game(name, getattr(importlib.import_module(module_path), cls_name))
        except Exception as e:
            logger.warning("registry: game '%s' unavailable (%s)", name, e)
