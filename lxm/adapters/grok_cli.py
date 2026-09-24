"""Grok (xAI) adapter for LxM — via the `grok` CLI.

The fourth lineage joins the arena (grok CLI 0.2.99+, headless mode).

Invocation notes (verified 2026-07-13):
- `grok -p <prompt>` runs a single turn and prints the bare response to
  stdout (no banners, no cwd artifacts — session state lives in ~/.grok).
- prompt is an ARGUMENT (argv is fine for LxM inline prompts).
- `--disable-web-search` keeps game turns self-contained (no tool use);
  `--output-format plain` pins the headless format.
- ~4s round trip on grok-4.5 with realistic game-size prompts.
"""

import os

from lxm.adapters.base import AgentAdapter


class GrokCLIAdapter(AgentAdapter):
    hands_mechanism = {"none": "--disallowed-tools <all tools> (no reads either)"}

    """Adapter for calling Grok models through the `grok` CLI.

    Requires: `grok` CLI installed and logged in (grok.com account).
    Models observed: grok-4.7 (default since 2026-09-24), grok-4.7-build-fast,
    grok-4.6, grok-4.5; earlier grok-composer-2.5-fast.
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        # grok-4.7 shipped 2026-09-21 and is the CLI default (grok 1.0.40
        # `grok models`); 4.5 is still listed but no longer current.
        # grok-4.7-build-fast is the same model at 2x speed and 2x token rate.
        self._model = agent_config.get("model", "grok-4.7")
        # Games only need a move, so every tool is denied by default (the
        # containment posture). A field that measures agentic work — the
        # report-fidelity tasks write files — must opt in, or grok would be
        # the one lineage measured without the tools the others have. Opting
        # in does not bypass the canary: the gate probes the adapter exactly
        # as configured, so grok-with-tools must pass it on its own.
        # hands: None/"none" keep every tool denied (the game default); "full"
        # is the same as allow_tools. allow_tools stays for existing callers.
        hands = agent_config.get("hands")
        self._allow_tools = bool(agent_config.get("allow_tools", False)) and hands != "none"
        if hands == "full":
            self._allow_tools = True

    def _populate_capabilities(self, agent_config: dict) -> None:
        # headless grok returns clean JSON for LxM-shape prompts
        # (smoke-verified 2026-07-13 on grok-4.5).
        self.brain_capabilities = ["json_emit"]

    # Grok is an agentic coding CLI: run in the match dir with tools enabled, it
    # reads state.json/log.json/rules.md off disk — a FILESYSTEM SIDE-CHANNEL
    # that leaks its own move history (state.json.recent_moves) and the full
    # rules, information the inline prompt deliberately withholds. Left on, that
    # contaminates the measurement (grok answers from files, not the prompt) and
    # manufactured the arena↔plane contradiction (the plane has no match dir).
    # Deny every file/shell/subagent tool so grok must answer from the prompt.
    _DENY_TOOLS = ("read_file,list_dir,grep,run_terminal_command,search_replace,"
                   "write,spawn_subagent,search_tool,use_tool,todo_write,"
                   "get_command_or_subagent_output,kill_command_or_subagent")

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        grok_bin = "grok.exe" if os.name == "nt" else "grok"
        cmd = [
            grok_bin,
            "-p", prompt,
            "--model", self._model,
            "--disable-web-search",
            *([] if self._allow_tools else ["--disallowed-tools", self._DENY_TOOLS]),
            "--output-format", "plain",
        ]
        try:
            return self._run_cli(cmd, cwd=match_dir, input_text="")
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": "grok command not found. Install the grok CLI and "
                          "log in once interactively.",
                "exit_code": -1,
                "timed_out": False,
            }
