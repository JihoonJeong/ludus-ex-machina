"""Gemini adapter for LxM — via the `agy` CLI.

google-gemini/gemini-cli support ended (observed 2026-07); `agy` is its
successor and serves Gemini 3.x models through the same account login.
The adapter keeps the "gemini" key so existing configs/replays stay valid.
"""

import json
import os
import subprocess

from lxm.adapters.base import AgentAdapter


class GeminiCLIAdapter(AgentAdapter):
    """Adapter for calling Gemini models through the `agy` CLI.

    Requires: `agy` CLI installed and logged in (`agy install`, then run
    `agy` once interactively to authenticate).

    Invocation notes (verified on agy 1.0.16, 2026-07-04):
    - `-p <prompt>` runs one prompt non-interactively; the prompt must be
      an argument (stdin-only is rejected with "flag needs an argument").
      argv is fine for LxM inline prompts (macOS ARG_MAX is 1 MB).
    - stdout is exactly the model response — no banner/status lines,
      no files dropped into cwd (unlike gemini-cli v0.39's YOLO chatter).
    - `--print-timeout` defaults to 5m; we pin it to the adapter timeout
      so agy never gives up before (or long after) the orchestrator does.
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        # gemini-3.5-flash is the fast JSON-reliable tier on agy;
        # use gemini-3.1-pro for frontier runs (conquest board etc.).
        self._model = agent_config.get("model", "gemini-3.5-flash")

    def _populate_capabilities(self, agent_config: dict) -> None:
        # agy print mode returns clean JSON for LxM-shape prompts
        # (smoke-verified 2026-07-04 on 3.5-flash and 3.1-pro).
        self.brain_capabilities = ["json_emit"]

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        agy_bin = "agy.exe" if os.name == "nt" else "agy"
        cmd = [
            agy_bin,
            "-p", prompt,
            "--model", self._model,
            "--dangerously-skip-permissions",
            "--print-timeout", f"{self._timeout}s",
        ]

        try:
            return self._run_cli(cmd, cwd=match_dir, input_text="")
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": "agy command not found. Install the agy CLI and "
                          "log in once interactively (gemini-cli is EOL).",
                "exit_code": -1,
                "timed_out": False,
            }
