"""Claude Code CLI adapter for LxM."""

import json
import os
import subprocess
from pathlib import Path

from lxm.adapters.base import AgentAdapter


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter for calling Claude Code CLI as a game agent."""

    def __init__(self, agent_config: dict, shell_path: str | None = None):
        super().__init__(agent_config)
        self._model = agent_config.get("model", "sonnet")

    def invoke(self, match_dir: str, prompt: str) -> dict:
        """Invoke Claude Code CLI to make a move."""
        full_prompt = self._build_full_prompt(prompt)

        # Use claude.cmd on Windows for subprocess compatibility
        claude_bin = "claude.cmd" if os.name == "nt" else "claude"
        cmd = [
            claude_bin,
            "-p",
            "--model", self._model,
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]

        # Remove CLAUDECODE env var to allow nested invocation
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        try:
            result = subprocess.run(
                cmd,
                cwd=match_dir,
                input=full_prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout,
                env=env,
            )
            stdout = self._extract_text(result.stdout)
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
                "stderr": "claude command not found",
                "exit_code": -1,
                "timed_out": False,
            }

    def _build_full_prompt(self, prompt: str) -> str:
        """Pass through prompt. Shells are injected by the orchestrator."""
        return prompt

    @staticmethod
    def _extract_text(stdout: str) -> str:
        """Extract text from Claude Code's JSON output format."""
        if not stdout.strip():
            return ""
        try:
            data = json.loads(stdout)
            if isinstance(data, dict) and "result" in data:
                return data["result"]
            # Might be a list of content blocks
            if isinstance(data, list):
                texts = []
                for block in data:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                if texts:
                    return "\n".join(texts)
            return stdout
        except json.JSONDecodeError:
            return stdout
