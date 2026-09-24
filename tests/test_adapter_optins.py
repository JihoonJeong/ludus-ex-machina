"""Opt-in adapter settings must leave the default command line untouched —
game configs recorded months ago have to replay with the exact same flags."""

from lxm.adapters.registry import get_adapter_class


def _cmd(adapter):
    seen = {}
    adapter._run_cli = lambda cmd, **kw: seen.setdefault(
        "cmd", cmd) and {"stdout": "", "stderr": "", "exit_code": 0, "timed_out": False}
    adapter._invoke_once("/tmp", "hi")
    return seen["cmd"]


def test_agy_default_has_no_effort_flag_and_opt_in_adds_it():
    g = get_adapter_class("gemini")
    assert "--effort" not in _cmd(g({"agent_id": "a"}))
    cmd = _cmd(g({"agent_id": "a", "model": "gemini-3.8-flash", "effort": "medium"}))
    i = cmd.index("--effort")
    assert cmd[i + 1] == "medium" and cmd[cmd.index("--model") + 1] == "gemini-3.8-flash"


def test_grok_denies_every_tool_by_default_and_opt_in_lifts_only_that():
    g = get_adapter_class("grok")
    default = _cmd(g({"agent_id": "a"}))
    assert "--disallowed-tools" in default and "--disable-web-search" in default
    opted = _cmd(g({"agent_id": "a", "allow_tools": True}))
    assert "--disallowed-tools" not in opted
    assert "--disable-web-search" in opted          # web stays off either way
