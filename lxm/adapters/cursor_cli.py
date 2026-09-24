"""Cursor Agent CLI adapter (`cursor-agent`, 2026.09).

Added for the report-fidelity field: two of Naru's real failing cases ran on
Cursor seats (composer-2.5), and a lineage the villages run but LxM cannot call
is a row missing from any comparison. Invocation, probed 2026-09-24:

    cursor-agent -p --output-format json --model <m> --trust --workspace <dir> \
                 [--force | --mode ask] <prompt>

`-p` has every tool including write and shell; `--force` lets commands run
headless. `--mode ask` is Cursor's own read-only mode — the write-less session.
JSON output is one object: {"type":"result","is_error":..,"result":<text>,
"usage":{"inputTokens","outputTokens","cacheReadTokens","cacheWriteTokens"}}.
"""

import json
import os

from lxm.adapters.base import AgentAdapter


class CursorCLIAdapter(AgentAdapter):
    hands_mechanism = {"none": "--mode ask (Cursor's read-only mode; reads allowed)"}

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        # composer-2.5 is Cursor's own current model and the one Naru's cases
        # ran on; `cursor-agent --list-models` shows the rest.
        self._model = agent_config.get("model", "composer-2.5")
        self._hands = agent_config.get("hands")

    def _populate_capabilities(self, agent_config: dict) -> None:
        self.brain_capabilities = ["json_emit"]

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        exe = "cursor-agent.exe" if os.name == "nt" else "cursor-agent"
        cmd = [exe, "-p", "--output-format", "json", "--model", self._model,
               "--trust", "--workspace", match_dir,
               *(["--mode", "ask"] if self._hands == "none" else ["--force"]),
               prompt]
        try:
            result = self._run_cli(cmd, cwd=match_dir, input_text="")
        except FileNotFoundError:
            return {"stdout": "", "stderr": "cursor-agent not found — install the "
                    "Cursor CLI and run `cursor-agent login` once",
                    "exit_code": -1, "timed_out": False}
        result["stdout"] = self._extract_text(result["stdout"])
        return result

    @staticmethod
    def _extract_text(stdout: str) -> str:
        if not stdout.strip():
            return ""
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return stdout
        if isinstance(data, dict):
            if data.get("is_error"):
                return ""
            if isinstance(data.get("result"), str):
                return data["result"]
        return stdout
