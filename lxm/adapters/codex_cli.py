"""OpenAI Codex CLI adapter for LxM."""

import json
import os
import subprocess

from lxm.adapters.base import AgentAdapter


class CodexCLIAdapter(AgentAdapter):
    hands_mechanism = {"none": "--sandbox read-only (reads allowed, writes fail in the sandbox)"}

    """Adapter for calling OpenAI Codex CLI as a game agent.

    Requires: `codex` CLI installed (https://github.com/openai/codex)
    Uses `codex exec --json` for non-interactive JSONL output.
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        # Light tier. gpt-5.4-mini was the default until 2026-09-24, when a
        # ChatGPT-account codex began rejecting it (400 "not supported when
        # using Codex with a ChatGPT account"). GPT-6 = Astra / Sol / Luna
        # (Sol and Luna shipped 2026-09-22; there is no GPT-6 Terra — it 400s).
        # Luna is the light successor and was probed live before this change.
        self._model = agent_config.get("model", "gpt-6-luna")
        # hands "none": the read-only sandbox instead of the full bypass, so a
        # write attempt fails inside the tool the way a denied session fails.
        self._hands = agent_config.get("hands")

    def _populate_capabilities(self, agent_config: dict) -> None:
        # codex_cli emits structured JSON; Echo smoke_004-009 schema-drift
        # was caught by Hermes but never narrative-only.
        self.brain_capabilities = ["json_emit"]

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        cmd = [
            "codex", "exec",
            "--model", self._model,
            *(["--sandbox", "read-only"] if self._hands == "none"
              else ["--dangerously-bypass-approvals-and-sandbox"]),
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
        """Extract agent messages from Codex JSONL output.

        Supports both stream schemas: the current CLI emits
        {"type":"item.completed","item":{"type":"agent_message","text":...}}
        (observed 2026-07-21); older builds emitted
        {"msg":{"type":"agent_message","message":...}} — the 07-12 sweeps ran
        on that shape. Keep both: the CLI self-updates, the schema drifts.
        """
        messages = []
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = obj.get("item") or {}
            if obj.get("type") == "item.completed" and item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
                continue
            msg = obj.get("msg", {})
            if msg.get("type") == "agent_message":
                messages.append(msg.get("message", ""))
        return "\n".join(messages) if messages else stdout
