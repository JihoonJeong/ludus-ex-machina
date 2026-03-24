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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxm.adapters.base import AgentAdapter
    from lxm.engine import LxMGame

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


def _ensure_defaults():
    """Lazy-load built-in adapters and games on first access."""
    global _DEFAULTS_LOADED
    if _DEFAULTS_LOADED:
        return
    _DEFAULTS_LOADED = True

    # Adapters
    from lxm.adapters.claude_code import ClaudeCodeAdapter
    from lxm.adapters.gemini_cli import GeminiCLIAdapter
    from lxm.adapters.ollama import OllamaAdapter
    from lxm.adapters.codex_cli import CodexCLIAdapter
    from lxm.adapters.rule_bot import RuleBotAdapter

    register_adapter("claude", ClaudeCodeAdapter)
    register_adapter("gemini", GeminiCLIAdapter)
    register_adapter("ollama", OllamaAdapter)
    register_adapter("codex", CodexCLIAdapter)
    register_adapter("rule_bot", RuleBotAdapter)

    # Games
    from games.tictactoe.engine import TicTacToe
    from games.chess.engine import ChessGame
    from games.trustgame.engine import TrustGame
    from games.codenames.engine import CodenamesGame
    from games.poker.engine import PokerGame
    from games.avalon.engine import AvalonGame

    register_game("tictactoe", TicTacToe)
    register_game("chess", ChessGame)
    register_game("trustgame", TrustGame)
    register_game("codenames", CodenamesGame)
    register_game("poker", PokerGame)
    register_game("avalon", AvalonGame)
