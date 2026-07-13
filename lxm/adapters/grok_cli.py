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
    """Adapter for calling Grok models through the `grok` CLI.

    Requires: `grok` CLI installed and logged in (grok.com account).
    Models observed: grok-4.5 (default), grok-composer-2.5-fast.
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        self._model = agent_config.get("model", "grok-4.5")

    def _populate_capabilities(self, agent_config: dict) -> None:
        # headless grok returns clean JSON for LxM-shape prompts
        # (smoke-verified 2026-07-13 on grok-4.5).
        self.brain_capabilities = ["json_emit"]

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        grok_bin = "grok.exe" if os.name == "nt" else "grok"
        cmd = [
            grok_bin,
            "-p", prompt,
            "--model", self._model,
            "--disable-web-search",
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
