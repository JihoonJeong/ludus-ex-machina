"""LxM Client — manages the full lifecycle of running matches.

Responsibilities:
- Resolve config (CLI args, dict, or future server payload)
- Create game engine and adapters via registry
- Delegate match execution to Orchestrator
- Handle result submission
- Future: connect to matchmaking server

Usage:
    config = MatchConfig.from_cli_args(args)
    client = LxMClient(config)
    result = client.run()
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from lxm.adapters.base import AgentAdapter
from lxm.adapters.registry import get_adapter_class, get_game_class
from lxm.config import MatchConfig
from lxm.orchestrator import Orchestrator


class LxMClient:
    """Manages match lifecycle: prepare → run → submit."""

    def __init__(self, config: MatchConfig):
        self._config = config
        self._game = None
        self._adapters: dict[str, AgentAdapter] = {}
        self._orchestrator: Optional[Orchestrator] = None
        self._result: Optional[dict] = None
        self._match_dir: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None

    @property
    def config(self) -> MatchConfig:
        return self._config

    @property
    def result(self) -> Optional[dict]:
        return self._result

    @property
    def match_dir(self) -> Optional[str]:
        return self._match_dir

    @property
    def duration_seconds(self) -> float:
        if self._start_time and self._end_time:
            return (self._end_time - self._start_time).total_seconds()
        return 0.0

    # ── Setup ──

    def prepare(self) -> str:
        """Initialize game, adapters, match directory. Returns match_dir."""
        self._game = get_game_class(self._config.game)()
        self._adapters = self._create_adapters()
        match_config_dict = self._config.to_dict()
        self._orchestrator = Orchestrator(self._game, match_config_dict, self._adapters)
        if self._config.skip_eval:
            self._orchestrator.run_evaluation = lambda match_dir: None
        self._match_dir = self._orchestrator.setup_match()
        return self._match_dir

    def _create_adapters(self) -> dict[str, AgentAdapter]:
        adapters = {}
        for agent_cfg in self._config.agents:
            AdapterClass = get_adapter_class(agent_cfg.adapter)
            adapters[agent_cfg.agent_id] = AdapterClass(agent_cfg.to_adapter_dict())
        return adapters

    # ── Execution ──

    def run(self) -> dict:
        """Run the match end-to-end. Returns result dict."""
        if not self._orchestrator:
            self.prepare()

        self._print_header()
        self._start_time = datetime.now(timezone.utc)
        self._result = self._orchestrator.run()
        self._end_time = datetime.now(timezone.utc)
        self._print_result()

        if self._config.submit:
            self.submit_result()

        return self._result

    # ── Result Submission ──

    def submit_result(self) -> Optional[dict]:
        """Submit result to API server."""
        if not self._result:
            return None

        agents = []
        for agent_cfg in self._config.agents:
            agents.append({
                "agent_id": agent_cfg.agent_id,
                "user_id": "local",
                "adapter": agent_cfg.adapter,
                "model": agent_cfg.model,
            })

        payload = {
            "match_id": self._config.match_id,
            "game": self._config.game,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(self.duration_seconds),
            "agents": agents,
            "result": {
                "outcome": self._result.get("outcome", ""),
                "winner": self._result.get("winner"),
                "scores": self._result.get("scores", {}),
                "summary": self._result.get("summary", ""),
            },
            "shell_hashes": {},
            "invocation_mode": self._config.invocation.mode,
        }

        url = f"{self._config.api_url}/api/matches/result"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read())
                elo_changes = resp_data.get("elo_changes", {})
                print()
                print("=== Submitted to API ===")
                if elo_changes:
                    for aid, change in elo_changes.items():
                        sign = "+" if change >= 0 else ""
                        print(f"  {aid}: ELO {sign}{change}")
                else:
                    print("  Result recorded (no ELO agents registered)")
                return resp_data
        except urllib.error.URLError as e:
            print(f"\n[Submit] Failed to reach API server: {e}")
        except Exception as e:
            print(f"\n[Submit] Error: {e}")
        return None

    # ── Future Server Mode ──

    def connect(self, server_url: str, token: str):
        """Connect to matchmaking server (future)."""
        raise NotImplementedError("Server mode not yet implemented")

    def wait_for_match(self) -> MatchConfig:
        """Block until server assigns a match (future)."""
        raise NotImplementedError("Server mode not yet implemented")

    # ── Output ──

    def _print_header(self):
        print(f"=== LxM Match: {self._config.match_id} ===")
        print(f"Game: {self._config.game}")
        agent_strs = [f"{a.agent_id} ({a.model})" for a in self._config.agents]
        print(f"Agents: {', '.join(agent_strs)}")
        print()
        print(f"Match folder: {self._match_dir}")
        print()

    def _print_result(self):
        print()
        print("=== Match Complete ===")
        print(f"Outcome: {self._result['outcome']}")
        if self._result.get("winner"):
            print(f"Winner: {self._result['winner']}")
        print(f"Summary: {self._result['summary']}")
        print(f"Duration: {self.duration_seconds:.0f}s")
        print(f"Files: {self._match_dir}")
