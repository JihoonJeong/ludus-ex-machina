"""OpenAI Codex CLI adapter for LxM."""

import json
import os
import subprocess

from lxm.adapters.base import AgentAdapter


class CodexCLIAdapter(AgentAdapter):
    """Adapter for calling OpenAI Codex CLI as a game agent.

    Requires: `codex` CLI installed (https://github.com/openai/codex)
    Uses `codex exec` for non-interactive mode.
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        self._model = agent_config.get("model", "codex-mini-latest")

    def invoke(self, match_dir: str, prompt: str) -> dict:
        cmd = [
            "codex", "exec",
            "--model", self._model,
            "--dangerously-bypass-approvals-and-sandbox",
            "-C", match_dir,
            prompt,
        ]

        try:
            result = subprocess.run(
                cmd,
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
                "stderr": "codex command not found. Install: https://github.com/openai/codex",
                "exit_code": -1,
                "timed_out": False,
            }
