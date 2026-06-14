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
        # 2.5-flash is the most reliable JSON-emitting tier as of v0.39+
        # (3.1-pro-preview server capacity issues observed 2026-03-31).
        self._model = agent_config.get("model", "gemini-2.5-flash")

    def _populate_capabilities(self, agent_config: dict) -> None:
        # gemini-cli v0.39+ emits clean JSON for LxM-shape prompts when
        # invoked with stdin-pipe + --skip-trust. The earlier "narrative
        # only" verdict (Ray 2026-04-30 on v<0.39) is no longer current —
        # 2.5-flash on a real pure_coord_01 prompt returns markdown-fenced
        # JSON via Strategy-1 parse path (verified 2026-05-14).
        self.brain_capabilities = ["json_emit"]

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        # Use gemini.cmd on Windows for subprocess compatibility
        gemini_bin = "gemini.cmd" if os.name == "nt" else "gemini"
        # Pass prompt via stdin pipe (NOT -p headless mode).
        # stdin pipe uses the interactive API path which has better capacity
        # for preview models. -o text for plain text output (json mode hangs).
        # --skip-trust bypasses the "trusted workspace" check (v0.38+).
        cmd = [
            gemini_bin,
            "--model", self._model,
            "--yolo",
            "--sandbox", "false",
            "--skip-trust",
            "-o", "text",
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
        """Strip Gemini CLI status lines from the response body.

        v0.39+ prepends informational lines like 'YOLO mode is enabled.',
        'Approval mode overridden...', 'Loaded cached credentials.', etc.
        Drop them so the envelope parser sees only the model response.
        """
        prefix_drop = (
            "YOLO mode",
            "Approval mode",
            "Loaded cached",
            "Using ",
        )
        lines = [
            line for line in stdout.splitlines()
            if not line.startswith(prefix_drop)
        ]
        return "\n".join(lines)
