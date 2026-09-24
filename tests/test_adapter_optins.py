"""Adapter defaults and opt-ins. The defaults track what the accounts accept
today (probed 2026-09-24); the opt-ins must not leak into game command lines."""

from lxm.adapters.gemini_cli import default_effort
from lxm.adapters.registry import get_adapter_class


def _cmd(adapter):
    seen = {}
    adapter._run_cli = lambda cmd, **kw: seen.setdefault(
        "cmd", cmd) and {"stdout": "", "stderr": "", "exit_code": 0, "timed_out": False}
    adapter._invoke_once("/tmp", "hi")
    return seen["cmd"]


def _flag(cmd, name):
    return cmd[cmd.index(name) + 1] if name in cmd else None


def test_current_defaults():
    reg = get_adapter_class
    assert reg("codex")({"agent_id": "a"})._model == "gpt-6-luna"
    assert reg("gemini")({"agent_id": "a"})._model == "gemini-3.8-flash"
    assert reg("grok")({"agent_id": "a"})._model == "grok-4.7"


def test_agy_always_sends_an_effort_the_model_accepts():
    g = get_adapter_class("gemini")
    assert _flag(_cmd(g({"agent_id": "a"})), "--effort") == "medium"
    assert _flag(_cmd(g({"agent_id": "a", "model": "gemini-3.1-pro"})), "--effort") == "high"
    assert _flag(_cmd(g({"agent_id": "a", "effort": "low"})), "--effort") == "low"
    assert default_effort("gemini-3.1-pro") == "high"      # pro has no medium
    assert default_effort("gemini-3.8-flash") == "medium"


def test_grok_denies_every_tool_by_default_and_opt_in_lifts_only_that():
    g = get_adapter_class("grok")
    default = _cmd(g({"agent_id": "a"}))
    assert "--disallowed-tools" in default and "--disable-web-search" in default
    opted = _cmd(g({"agent_id": "a", "allow_tools": True}))
    assert "--disallowed-tools" not in opted
    assert "--disable-web-search" in opted          # web stays off either way
