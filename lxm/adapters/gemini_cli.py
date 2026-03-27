"""Gemini CLI adapter for LxM."""

import json
import os
import subprocess

from lxm.adapters.base import AgentAdapter


class GeminiCLIAdapter(AgentAdapter):
    """Adapter for calling Gemini CLI as a game agent.

    Requires: `gemini` CLI installed (https://github.com/google-gemini/gemini-cli)
    Uses stdin for prompt delivery to avoid OS command-line length limits.
    --yolo for auto-approve file writes.
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        self._model = agent_config.get("model", "gemini-3.1-pro-preview")

    def invoke(self, match_dir: str, prompt: str) -> dict:
        # Use gemini.cmd on Windows for subprocess compatibility
        gemini_bin = "gemini.cmd" if os.name == "nt" else "gemini"
        # Pass prompt via stdin to avoid OS command-line length limits
        # (Windows cmd.exe ~8KB, macOS ~256KB). stdin has no such limit.
        # -p "" triggers non-interactive mode; actual prompt arrives via stdin.
        cmd = [
            gemini_bin,
            "--model", self._model,
            "-p", "",
            "--yolo",
            "--sandbox", "false",
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=match_dir,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
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
