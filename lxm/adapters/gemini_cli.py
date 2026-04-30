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

    def _populate_capabilities(self, agent_config: dict) -> None:
        # gemini-cli is structurally agentic across all model families on
        # LxM-shape prompts (Ray's smoke_014b 6h diagnostic 2026-04-30).
        # `-e ""` / `--approval-mode plan|yolo` / `GEMINI_SYSTEM_MD` strict
        # override all produce narrative tool-plans, not structured JSON
        # for the LxM move schema. Future @google/genai SDK adapter can
        # reclaim json_emit; until then the verdict is operational.
        self.brain_capabilities = ["narrative"]

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        # Use gemini.cmd on Windows for subprocess compatibility
        gemini_bin = "gemini.cmd" if os.name == "nt" else "gemini"
        # Pass prompt via stdin pipe (NOT -p headless mode).
        # stdin pipe uses the interactive API path which has better capacity
        # for preview models. -o text for plain text output (json mode hangs).
        cmd = [
            gemini_bin,
            "--model", self._model,
            "--yolo",
            "--sandbox", "false",
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
        """Extract response from Gemini CLI output.

        Handles two formats:
        1. JSON output (-o json): extract "response" field
        2. Plain text: strip status lines
        """
        # Plain text cleanup
        lines = []
        for line in stdout.splitlines():
            if line.startswith("Loaded cached") or line.startswith("Using "):
                continue
            if line.startswith("YOLO mode"):
                continue
            lines.append(line)
        return "\n".join(lines)
