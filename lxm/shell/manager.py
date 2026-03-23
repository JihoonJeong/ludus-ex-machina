"""Shell Manager — create, version, diff, and manage shell documents.

Shells are stored as Structured Markdown files:
    shells/{agent_id}/{game}/shell_v{version}.md

Usage:
    manager = ShellManager()
    shell = manager.create_shell("poker", template="tight_aggressive")
    manager.save(shell, agent_id="jj-sonnet", game="poker")
    diff = manager.diff(shell_v1, shell_v2)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from lxm.config import ShellConfig


@dataclass
class ShellDiff:
    """Difference between two shells."""
    param_changes: dict[str, tuple[str, str]] = field(default_factory=dict)  # key → (old, new)
    param_added: dict[str, str] = field(default_factory=dict)
    param_removed: dict[str, str] = field(default_factory=dict)
    strategy_changed: bool = False
    rules_added: list[str] = field(default_factory=list)
    rules_removed: list[str] = field(default_factory=list)
    version_from: str = ""
    version_to: str = ""

    def summary(self) -> str:
        parts = []
        if self.param_changes:
            for k, (old, new) in self.param_changes.items():
                parts.append(f"  {k}: {old} → {new}")
        if self.param_added:
            for k, v in self.param_added.items():
                parts.append(f"  +{k}: {v}")
        if self.param_removed:
            for k, v in self.param_removed.items():
                parts.append(f"  -{k}: {v}")
        if self.strategy_changed:
            parts.append("  [Strategy text changed]")
        if self.rules_added:
            for r in self.rules_added:
                parts.append(f"  +Rule: {r}")
        if self.rules_removed:
            for r in self.rules_removed:
                parts.append(f"  -Rule: {r}")

        header = f"Shell diff: {self.version_from} → {self.version_to}"
        if not parts:
            return f"{header}\n  (no changes)"
        return f"{header}\n" + "\n".join(parts)


@dataclass
class ShellVersion:
    """A point in shell version history."""
    version: str
    path: str
    timestamp: float
    parent_version: Optional[str] = None
    note: str = ""


# Built-in templates
TEMPLATES: dict[str, dict[str, str]] = {
    "poker": {
        "tight_aggressive": """\
# Poker Strategy: Tight-Aggressive v1.0

## Parameters
- pre_flop_threshold: top 20%
- bluff_frequency: 1 per 5 hands
- position_bluff_only: true
- continuation_bet: 70%

## Strategy
Pre-flop: Play only the top 20% of hands. Fold everything else without hesitation.
Post-flop: If you hit the flop, bet aggressively. If you miss, fold to any bet.
Position: Use late position to steal blinds with wider range.

## Situational Rules
- Stack below 20BB: switch to push-or-fold mode
- Opponent folded 3+ times in a row: increase bluff frequency
- Heads-up with strong draw: semi-bluff with a raise
""",
        "loose_passive": """\
# Poker Strategy: Loose-Passive v1.0

## Parameters
- pre_flop_threshold: top 50%
- bluff_frequency: 1 per 20 hands
- check_call_preference: 80%

## Strategy
Pre-flop: Play a wide range of hands. See many flops cheaply.
Post-flop: Check and call with decent hands. Only raise with the nuts.
Avoid confrontation unless you have a very strong hand.

## Situational Rules
- Strong hand (two pair+): switch to aggressive betting
- Opponent raises big: fold unless holding top pair or better
""",
        "bluff_heavy": """\
# Poker Strategy: Bluff-Heavy v1.0

## Parameters
- pre_flop_threshold: top 30%
- bluff_frequency: 1 per 3 hands
- overbet_bluff: true
- represent_strength: always

## Strategy
Pre-flop: Open with a moderate range but always raise (never limp).
Post-flop: Bet regardless of hand strength. Represent strong hands.
Use large bet sizes to pressure opponents into folding.

## Situational Rules
- Opponent is tight: increase bluff frequency
- Caught bluffing recently: tighten up for 3 hands, then resume
- River with missed draw: large overbet bluff
""",
    },
    "avalon": {
        "deep_cover": """\
# Avalon Strategy: Deep Cover v1.0

## Parameters
- early_sabotage: false
- trust_building_quests: 2
- framing_aggression: low

## Strategy
Quests 1-2: Play Success to build trust. Appear as a loyal Good player.
Quest 3+: Begin subtle sabotage. Only sabotage when you have cover.
Voting: Vote approve on quests you're on, reject quests without Evil presence.
Discussion: Support Good players' arguments. Never accuse other Evil players.

## Situational Rules
- If accused early: defend calmly, point to your Success record
- If partner is accused: do not defend too strongly (suspicious)
- Quest 5 (if reached): sabotage regardless — last chance
""",
        "aggressive_evil": """\
# Avalon Strategy: Aggressive Evil v1.0

## Parameters
- early_sabotage: true
- accusation_frequency: high
- misdirection: active

## Strategy
Sabotage from Quest 1. Be aggressive in discussion — accuse Good players.
Create chaos and confusion. Make it hard for Good to identify Evil.
Vote reject on quests without Evil. Vote approve when Evil is present.

## Situational Rules
- If multiple Evil on quest: only one sabotages (coordination)
- If suspicion falls on you: double down on accusing others
""",
    },
}


class ShellManager:
    """Shell creation, storage, versioning, and diff."""

    def __init__(self, shells_dir: str = "shells"):
        self._shells_dir = Path(shells_dir)

    def create_shell(self, game: str, template: str | None = None,
                     content: str | None = None) -> ShellConfig:
        """Create a new shell from template or raw content."""
        if template:
            game_templates = TEMPLATES.get(game, {})
            if template not in game_templates:
                available = ", ".join(game_templates.keys()) or "(none)"
                raise ValueError(f"Unknown template '{template}' for {game}. Available: {available}")
            content = game_templates[template]

        if not content:
            raise ValueError("Must provide either template or content")

        return ShellConfig.from_text(content)

    def list_templates(self, game: str | None = None) -> dict[str, list[str]]:
        """List available templates, optionally filtered by game."""
        if game:
            return {game: list(TEMPLATES.get(game, {}).keys())}
        return {g: list(t.keys()) for g, t in TEMPLATES.items()}

    def save(self, shell: ShellConfig, agent_id: str, game: str,
             note: str = "") -> Path:
        """Save shell to agent's shell directory."""
        shell_dir = self._shells_dir / agent_id / game
        shell_dir.mkdir(parents=True, exist_ok=True)

        filename = f"shell_{shell.version}.md"
        path = shell_dir / filename
        content = shell.content or self._render(shell)
        path.write_text(content)
        return path

    def load(self, agent_id: str, game: str,
             version: str | None = None) -> ShellConfig | None:
        """Load shell for an agent/game. Latest version if not specified."""
        shell_dir = self._shells_dir / agent_id / game
        if not shell_dir.exists():
            return None

        if version:
            path = shell_dir / f"shell_{version}.md"
            if path.exists():
                return ShellConfig.from_file(str(path))
            return None

        # Find latest version
        versions = self.get_history(agent_id, game)
        if not versions:
            return None
        latest = versions[-1]
        return ShellConfig.from_file(latest.path)

    def get_history(self, agent_id: str, game: str) -> list[ShellVersion]:
        """Get shell version history for an agent/game."""
        shell_dir = self._shells_dir / agent_id / game
        if not shell_dir.exists():
            return []

        versions = []
        for p in sorted(shell_dir.glob("shell_v*.md")):
            # Extract version from filename
            match = re.search(r"shell_(v[\d.]+)\.md", p.name)
            if match:
                ver = match.group(1)
                versions.append(ShellVersion(
                    version=ver,
                    path=str(p),
                    timestamp=p.stat().st_mtime,
                ))

        return versions

    def diff(self, shell_a: ShellConfig, shell_b: ShellConfig) -> ShellDiff:
        """Compare two shells and extract differences."""
        result = ShellDiff(
            version_from=shell_a.version,
            version_to=shell_b.version,
        )

        # Parameter changes
        all_keys = set(shell_a.parameters.keys()) | set(shell_b.parameters.keys())
        for k in all_keys:
            a_val = shell_a.parameters.get(k)
            b_val = shell_b.parameters.get(k)
            if a_val is None:
                result.param_added[k] = b_val
            elif b_val is None:
                result.param_removed[k] = a_val
            elif a_val != b_val:
                result.param_changes[k] = (a_val, b_val)

        # Strategy change
        result.strategy_changed = shell_a.strategy_text != shell_b.strategy_text

        # Rules changes
        rules_a = set(shell_a.rules)
        rules_b = set(shell_b.rules)
        result.rules_added = sorted(rules_b - rules_a)
        result.rules_removed = sorted(rules_a - rules_b)

        return result

    def _render(self, shell: ShellConfig) -> str:
        """Render ShellConfig back to Structured Markdown."""
        lines = [f"# Shell {shell.version}", ""]

        if shell.parameters:
            lines.append("## Parameters")
            for k, v in shell.parameters.items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        if shell.strategy_text:
            lines.append("## Strategy")
            lines.append(shell.strategy_text)
            lines.append("")

        if shell.rules:
            lines.append("## Situational Rules")
            for r in shell.rules:
                lines.append(f"- {r}")
            lines.append("")

        return "\n".join(lines)
