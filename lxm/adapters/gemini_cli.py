"""Gemini CLI adapter for LxM."""

import json
import os
import subprocess

from lxm.adapters.base import AgentAdapter


class GeminiCLIAdapter(AgentAdapter):
    """Adapter for calling Gemini CLI as a game agent.

    Requires: `gemini` CLI installed (https://github.com/google-gemini/gemini-cli)
    Usage: gemini -p "{prompt}"
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        self._model = agent_config.get("model", "gemini-2.5-pro")

    def invoke(self, match_dir: str, prompt: str) -> dict:
        cmd = [
            "gemini",
            "-p",
            prompt,
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=match_dir,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Process timed out",
                "exit_code": -1,
                "timed_out": True,
            }
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": "gemini command not found. Install: https://github.com/google-gemini/gemini-cli",
                "exit_code": -1,
                "timed_out": False,
            }
