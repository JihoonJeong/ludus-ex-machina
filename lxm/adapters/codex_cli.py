"""OpenAI Codex CLI adapter for LxM."""

import json
import os
import subprocess

from lxm.adapters.base import AgentAdapter


class CodexCLIAdapter(AgentAdapter):
    """Adapter for calling OpenAI Codex CLI as a game agent.

    Requires: `codex` CLI installed (https://github.com/openai/codex)
    Uses `codex exec --json` for non-interactive JSONL output.
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        self._model = agent_config.get("model", "gpt-5.4-mini")

    def _populate_capabilities(self, agent_config: dict) -> None:
        # codex_cli emits structured JSON; Echo smoke_004-009 schema-drift
        # was caught by Hermes but never narrative-only.
        self.brain_capabilities = ["json_emit"]

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        cmd = [
            "codex", "exec",
            "--model", self._model,
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "--json",
            "-C", match_dir,
            prompt,
        ]

        try:
            result = self._run_cli(cmd)
            result["stdout"] = self._extract_text(result["stdout"])
            return result
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": "codex command not found. Install: https://github.com/openai/codex",
                "exit_code": -1,
                "timed_out": False,
            }

    @staticmethod
    def _extract_text(stdout: str) -> str:
        """Extract agent messages from Codex JSONL output."""
        messages = []
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                msg = obj.get("msg", {})
                if msg.get("type") == "agent_message":
                    messages.append(msg.get("message", ""))
            except json.JSONDecodeError:
                continue
        return "\n".join(messages) if messages else stdout
