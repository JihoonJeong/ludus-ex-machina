"""Gemini adapter for LxM — via the `agy` CLI.

google-gemini/gemini-cli support ended (observed 2026-07); `agy` is its
successor and serves Gemini 3.x models through the same account login.
The adapter keeps the "gemini" key so existing configs/replays stay valid.
"""

import json
import os
import subprocess

from lxm.adapters.base import AgentAdapter



def default_effort(model: str | None) -> str | None:
    """The effort agy needs when the config names none. Pro models offer
    low/high only; everything else in the 3.x line offers medium."""
    if not model:
        return None
    return "high" if "-pro" in model else "medium"

class GeminiCLIAdapter(AgentAdapter):
    hands_mechanism = {"none": "no --dangerously-skip-permissions (headless auto-denies permissioned tools)"}

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
        # The flash line is the fast JSON-reliable tier on agy (3.5 until
        # 2026-09-24, when agy 1.2.10 dropped it; 3.8 shipped 2026-09-02);
        # use gemini-3.1-pro for frontier runs (conquest board etc.).
        self._model = agent_config.get("model", "gemini-3.8-flash")
        # agy 1.2.x makes --effort mandatory for every Gemini 3.x model, and
        # the allowed values differ by model (probed 2026-09-24): 3.8 Flash
        # takes low/medium/high, 3.1 Pro only low/high. An explicit config
        # value wins; otherwise the middle of whatever the model offers.
        self._effort = agent_config.get("effort") or default_effort(self._model)
        # hands "none": no permission bypass. Headless agy auto-denies any tool
        # that needs permission — the exact state Naru's agy speech seats hit.
        self._hands = agent_config.get("hands")

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
            *(["--effort", self._effort] if self._effort else []),
            *([] if self._hands == "none" else ["--dangerously-skip-permissions"]),
            "--print-timeout", f"{self._timeout}s",
        ]

        try:
            result = self._run_cli(cmd, cwd=match_dir, input_text="")
            # agy can return exit 0 with EMPTY stdout and the real reason only
            # on stderr (e.g. it tried to call a tool and headless auto-denied
            # it — the failure mode surfaces on investigation-flavoured prompts
            # like a physics-lab report). base._is_transient_error() short-
            # circuits on exit 0, so an empty-stdout/stderr-reason run would
            # read as a silent empty brain. Surface it as a diagnosed error.
            # (Joint finding with Ludex, 2026-08-01.)
            if not (result.get("stdout") or "").strip() \
                    and (result.get("stderr") or "").strip() \
                    and not result.get("timed_out"):
                result["exit_code"] = result.get("exit_code") or -2
            return result
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": "agy command not found. Install the agy CLI and "
                          "log in once interactively (gemini-cli is EOL).",
                "exit_code": -1,
                "timed_out": False,
            }
