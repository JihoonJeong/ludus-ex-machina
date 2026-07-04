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

    def _populate_capabilities(self, agent_config: dict) -> None:
        # claude_cli reliably emits structured JSON across smoke_004-014c
        # (Hearth, Quill, Echo via codex variant). Tier-1 direct.
        self.brain_capabilities = ["json_emit"]

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        """Invoke Claude Code CLI to make a move."""
        full_prompt = self._build_full_prompt(prompt)

        # Use claude.cmd on Windows for subprocess compatibility
        claude_bin = "claude.cmd" if os.name == "nt" else "claude"
        cmd = [
            claude_bin,
            "-p",
            "--input-format", "text",
            "--model", self._model,
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]

        # Remove CLAUDECODE env var to allow nested invocation
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        try:
            result = self._run_cli(cmd, cwd=match_dir, input_text=full_prompt, env=env)
            result["stdout"] = self._extract_text(result["stdout"])
            return result
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
