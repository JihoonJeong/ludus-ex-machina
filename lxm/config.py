"""Typed configuration for LxM matches.

MatchConfig is the contract between all layers:
CLI args, server JSON, YAML files → MatchConfig → Client → Orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ShellConfig:
    """Parsed Shell document (Structured Markdown format).

    Shell format:
        # Strategy Name vX.Y
        ## Parameters
        - key: value
        ## Strategy
        (prose)
        ## Situational Rules
        - condition: action
    """
    path: Optional[str] = None           # source file path
    content: Optional[str] = None        # raw text content
    format: str = "structured_md"        # structured_md | plain_md | json
    parameters: dict = field(default_factory=dict)
    strategy_text: str = ""
    rules: list[str] = field(default_factory=list)
    version: str = "v1.0"
    parent_version: Optional[str] = None

    @classmethod
    def from_file(cls, path: str) -> ShellConfig:
        """Load and parse a Structured Markdown shell file."""
        p = Path(path)
        if not p.exists():
            return cls(path=path)
        content = p.read_text()
        return cls.from_text(content, path=path)

    @classmethod
    def from_text(cls, content: str, path: str | None = None) -> ShellConfig:
        """Parse Structured Markdown shell content."""
        params = {}
        strategy = []
        rules = []
        version = "v1.0"
        current_section = None

        for line in content.splitlines():
            stripped = line.strip()

            # Detect version from title
            if stripped.startswith("# ") and not stripped.startswith("## "):
                # e.g. "# Poker Strategy: Tight-Aggressive v2.3"
                for word in stripped.split():
                    if word.startswith("v") and any(c.isdigit() for c in word):
                        version = word
                continue

            if stripped.lower().startswith("## parameter"):
                current_section = "parameters"
                continue
            elif stripped.lower().startswith("## strateg"):
                current_section = "strategy"
                continue
            elif stripped.lower().startswith("## situational") or stripped.lower().startswith("## rules"):
                current_section = "rules"
                continue
            elif stripped.startswith("## "):
                current_section = "other"
                continue

            if current_section == "parameters" and stripped.startswith("- "):
                # Parse "- key: value"
                kv = stripped[2:]
                if ":" in kv:
                    k, v = kv.split(":", 1)
                    params[k.strip()] = v.strip()
            elif current_section == "strategy":
                strategy.append(line)
            elif current_section == "rules" and stripped.startswith("- "):
                rules.append(stripped[2:])

        return cls(
            path=path,
            content=content,
            parameters=params,
            strategy_text="\n".join(strategy).strip(),
            rules=rules,
            version=version,
        )


@dataclass
class AgentConfig:
    """Configuration for a single agent in a match."""
    agent_id: str
    display_name: str = ""
    seat: int = 0
    adapter: str = "claude"
    model: str = "sonnet"
    timeout_seconds: int = 120
    hard_shell: Optional[str] = None    # path or content
    soft_shell: Optional[str] = None    # coaching text
    # Game-specific role fields
    team: Optional[str] = None
    role: Optional[str] = None

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.agent_id

    def to_dict(self) -> dict:
        """Serialize to the dict format the orchestrator expects."""
        d = {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "seat": self.seat,
        }
        if self.hard_shell:
            d["hard_shell"] = self.hard_shell
        if self.soft_shell:
            d["soft_shell"] = self.soft_shell
        if self.team:
            d["team"] = self.team
        if self.role:
            d["role"] = self.role
        return d

    def to_adapter_dict(self) -> dict:
        """Dict passed to AdapterClass constructor."""
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "seat": self.seat,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class TimeModel:
    type: str = "turn_based"
    turn_order: str = "sequential"
    max_turns: int = 100
    timeout_seconds: int = 120
    timeout_action: str = "no_op"
    max_retries: int = 2


@dataclass
class InvocationConfig:
    mode: str = "inline"
    discovery_turns: int = 1


CODENAMES_ROLES = [
    {"team": "red", "role": "spymaster"},
    {"team": "red", "role": "guesser"},
    {"team": "blue", "role": "spymaster"},
    {"team": "blue", "role": "guesser"},
]

GAME_MAX_TURNS = {
    "tictactoe": 9,
    "chess": 200,
    "trustgame": 100,
    "codenames": 50,
    "poker": 2000,
    "avalon": 200,
}

GAME_TURN_ORDER = {
    "codenames": "custom",
    "poker": "custom",
    "avalon": "custom",
}

GAME_RECENT_MOVES = {
    "avalon": 30,
    "poker": 20,
}


@dataclass
class MatchConfig:
    """The contract. Everything needed to run a match."""
    game: str
    agents: list[AgentConfig]
    match_id: str = ""
    protocol_version: str = "lxm-v0.2"
    time_model: TimeModel = field(default_factory=TimeModel)
    invocation: InvocationConfig = field(default_factory=InvocationConfig)
    recent_moves_count: int = 5
    role_shells: dict[str, str] = field(default_factory=dict)
    teams: Optional[dict] = None
    submit: bool = False
    api_url: str = "http://localhost:8000"
    skip_eval: bool = False

    def __post_init__(self):
        if not self.match_id:
            self.match_id = f"match_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def to_dict(self) -> dict:
        """Serialize to the match_config dict the orchestrator expects."""
        d = {
            "protocol_version": self.protocol_version,
            "match_id": self.match_id,
            "game": {"name": self.game, "version": "1.0"},
            "time_model": {
                "type": self.time_model.type,
                "turn_order": self.time_model.turn_order,
                "max_turns": self.time_model.max_turns,
                "timeout_seconds": self.time_model.timeout_seconds,
                "timeout_action": self.time_model.timeout_action,
                "max_retries": self.time_model.max_retries,
            },
            "agents": [a.to_dict() for a in self.agents],
            "history": {"recent_moves_count": self.recent_moves_count},
            "invocation": {
                "mode": self.invocation.mode,
                "discovery_turns": self.invocation.discovery_turns,
            },
        }
        if self.role_shells:
            d["role_shells"] = self.role_shells
        if self.teams:
            d["teams"] = self.teams
        return d

    @classmethod
    def from_dict(cls, d: dict) -> MatchConfig:
        """Deserialize from server JSON or saved config."""
        game_info = d.get("game", {})
        game_name = game_info.get("name", "unknown") if isinstance(game_info, dict) else str(game_info)
        time_info = d.get("time_model", {})
        inv_info = d.get("invocation", {})

        agents = []
        for a in d.get("agents", []):
            agents.append(AgentConfig(
                agent_id=a.get("agent_id", ""),
                display_name=a.get("display_name", a.get("agent_id", "")),
                seat=a.get("seat", 0),
                adapter=a.get("adapter", "claude"),
                model=a.get("model", "sonnet"),
                timeout_seconds=a.get("timeout_seconds", time_info.get("timeout_seconds", 120)),
                hard_shell=a.get("hard_shell"),
                soft_shell=a.get("soft_shell"),
                team=a.get("team"),
                role=a.get("role"),
            ))

        return cls(
            game=game_name,
            agents=agents,
            match_id=d.get("match_id", ""),
            protocol_version=d.get("protocol_version", "lxm-v0.2"),
            time_model=TimeModel(
                type=time_info.get("type", "turn_based"),
                turn_order=time_info.get("turn_order", "sequential"),
                max_turns=time_info.get("max_turns", 100),
                timeout_seconds=time_info.get("timeout_seconds", 120),
                timeout_action=time_info.get("timeout_action", "no_op"),
                max_retries=time_info.get("max_retries", 2),
            ),
            invocation=InvocationConfig(
                mode=inv_info.get("mode", "inline"),
                discovery_turns=inv_info.get("discovery_turns", 1),
            ),
            recent_moves_count=d.get("history", {}).get("recent_moves_count", 5),
            role_shells=d.get("role_shells", {}),
            teams=d.get("teams"),
        )

    @classmethod
    def from_cli_args(cls, args) -> MatchConfig:
        """Build from argparse namespace. Backward compatible with run_match.py."""
        n_agents = len(args.agents)
        models = args.models or [args.model] * n_agents
        adapter_names = getattr(args, "adapters", None) or [args.adapter] * n_agents

        # Build agent configs
        agents = []
        for i, agent_id in enumerate(args.agents):
            team = None
            role = None
            if args.game == "codenames" and i < len(CODENAMES_ROLES):
                team = CODENAMES_ROLES[i]["team"]
                role = CODENAMES_ROLES[i]["role"]

            hard_shell = None
            if hasattr(args, "shell_paths") and args.shell_paths:
                sp = args.shell_paths[i] if i < len(args.shell_paths) else "none"
                if sp != "none":
                    hard_shell = sp
            elif not getattr(args, "no_shell", False):
                default_path = Path("agents") / agent_id / "shell.md"
                if default_path.exists():
                    hard_shell = str(default_path)

            soft_shell = None
            if hasattr(args, "soft_shells") and args.soft_shells:
                ss = args.soft_shells[i] if i < len(args.soft_shells) else "none"
                if ss != "none":
                    soft_shell = ss
            elif getattr(args, "soft_shell", None):
                soft_shell = args.soft_shell

            agents.append(AgentConfig(
                agent_id=agent_id,
                display_name=agent_id,
                seat=i,
                adapter=adapter_names[i] if i < len(adapter_names) else args.adapter,
                model=models[i] if i < len(models) else args.model,
                timeout_seconds=getattr(args, "timeout", 120),
                hard_shell=hard_shell,
                soft_shell=soft_shell,
                team=team,
                role=role,
            ))

        # Role shells
        role_shells = {}
        if getattr(args, "good_shell", None):
            role_shells["good"] = args.good_shell
        if getattr(args, "evil_shell", None):
            role_shells["evil"] = args.evil_shell

        # Teams
        teams = None
        if args.game == "codenames":
            teams = {
                "red": {"spymaster": args.agents[0], "guesser": args.agents[1]},
                "blue": {"spymaster": args.agents[2], "guesser": args.agents[3]},
            }

        game_name = args.game
        recent = GAME_RECENT_MOVES.get(game_name, getattr(args, "recent_moves", 5))

        return cls(
            game=game_name,
            agents=agents,
            match_id=getattr(args, "match_id", None) or "",
            time_model=TimeModel(
                turn_order=GAME_TURN_ORDER.get(game_name, "sequential"),
                max_turns=GAME_MAX_TURNS.get(game_name, 100),
                timeout_seconds=getattr(args, "timeout", 120),
                max_retries=getattr(args, "max_retries", 2),
            ),
            invocation=InvocationConfig(
                mode=getattr(args, "invocation_mode", None) or "inline",
                discovery_turns=getattr(args, "discovery_turns", 1),
            ),
            recent_moves_count=recent,
            role_shells=role_shells,
            teams=teams,
            submit=getattr(args, "submit", False),
            api_url=getattr(args, "api_url", "http://localhost:8000"),
            skip_eval=getattr(args, "skip_eval", False),
        )
