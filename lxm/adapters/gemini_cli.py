"""Gemini CLI adapter for LxM."""

import json
import os
import subprocess

from lxm.adapters.base import AgentAdapter


class GeminiCLIAdapter(AgentAdapter):
    """Adapter for calling Gemini CLI as a game agent.

    Requires: `gemini` CLI installed (https://github.com/google-gemini/gemini-cli)
    Uses -p flag for non-interactive mode, --yolo for auto-approve file writes.
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        self._model = agent_config.get("model", "gemini-2.5-flash")

    def invoke(self, match_dir: str, prompt: str) -> dict:
        cmd = [
            "gemini",
            "-p", prompt,
            "--yolo",
            "--sandbox", "false",
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=match_dir,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            stdout = self._clean_output(result.stdout)
            return {
                "stdout": stdout,
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

    @staticmethod
    def _clean_output(stdout: str) -> str:
        """Remove Gemini CLI status messages from output."""
        lines = []
        for line in stdout.splitlines():
            # Skip loading/status lines
            if line.startswith("Loaded cached") or line.startswith("Using "):
                continue
            lines.append(line)
        return "\n".join(lines)
