"""Shell Tester — A/B testing, parameter sweep, and delta extraction.

Usage:
    tester = ShellTester()
    result = tester.ab_test(
        shell_a=shell_v1, shell_b=None,  # None = no shell
        game="poker", n_games=5,
        agent_id="test-agent", adapter="claude", model="sonnet",
    )
    print(result.delta.summary())
    tester.save_report(result, "reports/ab_tag_vs_none.json")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from lxm.config import MatchConfig, AgentConfig, ShellConfig, TimeModel, InvocationConfig, GAME_MAX_TURNS


@dataclass
class MatchResult:
    """Summary of a single match."""
    match_id: str
    winner: Optional[str]
    outcome: str
    scores: dict = field(default_factory=dict)
    duration_seconds: float = 0.0
    turn_count: int = 0


@dataclass
class CostMetrics:
    """Cost metrics for a set of matches."""
    avg_response_time: float = 0.0
    avg_tokens_per_turn: float = 0.0
    shell_length: int = 0  # characters


@dataclass
class BehaviorMetrics:
    """Aggregated behavior metrics from game logs."""
    metrics: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        if not self.metrics:
            return "(no behavior data)"
        return ", ".join(f"{k}: {v:.0%}" for k, v in sorted(self.metrics.items()))


@dataclass
class Delta:
    """Difference in outcomes between two conditions."""
    win_rate_a: float = 0.0
    win_rate_b: float = 0.0
    win_rate_change: float = 0.0
    behavior_a: BehaviorMetrics = field(default_factory=BehaviorMetrics)
    behavior_b: BehaviorMetrics = field(default_factory=BehaviorMetrics)
    behavior_changes: dict[str, float] = field(default_factory=dict)
    cost_a: CostMetrics = field(default_factory=CostMetrics)
    cost_b: CostMetrics = field(default_factory=CostMetrics)

    def summary(self) -> str:
        lines = [
            f"Win rate: {self.win_rate_a:.0%} → {self.win_rate_b:.0%} ({self.win_rate_change:+.0%})",
        ]
        if self.behavior_a.metrics:
            lines.append(f"Behavior A: {self.behavior_a.summary()}")
        if self.behavior_b.metrics:
            lines.append(f"Behavior B: {self.behavior_b.summary()}")
        if self.behavior_changes:
            lines.append("Behavior delta:")
            for k, v in sorted(self.behavior_changes.items()):
                a_val = self.behavior_a.metrics.get(k, 0)
                b_val = self.behavior_b.metrics.get(k, 0)
                lines.append(f"  {k}: {a_val:.0%} → {b_val:.0%} ({v:+.1%})")
        if self.cost_a.avg_response_time or self.cost_b.avg_response_time:
            lines.append(f"Avg response time: {self.cost_a.avg_response_time:.1f}s → {self.cost_b.avg_response_time:.1f}s")
        if self.cost_a.shell_length or self.cost_b.shell_length:
            lines.append(f"Shell length: {self.cost_a.shell_length} → {self.cost_b.shell_length} chars")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "win_rate_a": self.win_rate_a,
            "win_rate_b": self.win_rate_b,
            "win_rate_change": self.win_rate_change,
            "behavior_a": self.behavior_a.metrics,
            "behavior_b": self.behavior_b.metrics,
            "behavior_changes": self.behavior_changes,
            "cost_a": asdict(self.cost_a),
            "cost_b": asdict(self.cost_b),
        }


@dataclass
class ABResult:
    """Result of an A/B test between two shells."""
    shell_a_version: str
    shell_b_version: str
    game: str
    n_games: int
    results_a: list[MatchResult] = field(default_factory=list)
    results_b: list[MatchResult] = field(default_factory=list)
    delta: Delta = field(default_factory=Delta)

    def to_dict(self) -> dict:
        return {
            "type": "ab_test",
            "shell_a": self.shell_a_version,
            "shell_b": self.shell_b_version,
            "game": self.game,
            "n_games": self.n_games,
            "results_a": [asdict(r) for r in self.results_a],
            "results_b": [asdict(r) for r in self.results_b],
            "delta": self.delta.to_dict(),
        }


@dataclass
class SweepPoint:
    """One point in a parameter sweep."""
    param_value: str
    win_rate: float
    n_games: int
    results: list[MatchResult] = field(default_factory=list)
    behavior: BehaviorMetrics = field(default_factory=BehaviorMetrics)


@dataclass
class SweepResult:
    """Result of a parameter sweep."""
    param_name: str
    game: str
    points: list[SweepPoint] = field(default_factory=list)
    best_value: str = ""
    best_win_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "type": "parameter_sweep",
            "param_name": self.param_name,
            "game": self.game,
            "best_value": self.best_value,
            "best_win_rate": self.best_win_rate,
            "points": [
                {"value": p.param_value, "win_rate": p.win_rate, "n_games": p.n_games,
                 "behavior": p.behavior.metrics}
                for p in self.points
            ],
        }


# ── Behavior Extraction ──

def extract_poker_behavior(match_id: str, agent_id: str,
                           matches_dir: str = "matches") -> dict[str, float]:
    """Extract poker behavior metrics from a match log."""
    log_path = Path(matches_dir) / match_id / "log.json"
    if not log_path.exists():
        return {}

    try:
        log = json.loads(log_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    actions = {"fold": 0, "call": 0, "check": 0, "raise": 0, "all_in": 0}
    total = 0

    for entry in log:
        if entry.get("result") != "accepted":
            continue
        if entry.get("agent_id") != agent_id:
            continue
        move = entry.get("envelope", {}).get("move", {})
        action = move.get("action", "")
        if action in actions:
            actions[action] += 1
            total += 1

    if total == 0:
        return {}

    return {k: v / total for k, v in actions.items()}


def extract_behavior(game: str, match_id: str, agent_id: str,
                     matches_dir: str = "matches") -> dict[str, float]:
    """Extract game-specific behavior metrics."""
    if game == "poker":
        return extract_poker_behavior(match_id, agent_id, matches_dir)
    # Future: chess, avalon, codenames extractors
    return {}


def aggregate_behavior(behaviors: list[dict[str, float]]) -> BehaviorMetrics:
    """Average behavior metrics across multiple matches."""
    if not behaviors:
        return BehaviorMetrics()

    all_keys = set()
    for b in behaviors:
        all_keys.update(b.keys())

    avg = {}
    for k in all_keys:
        vals = [b[k] for b in behaviors if k in b]
        if vals:
            avg[k] = sum(vals) / len(vals)

    return BehaviorMetrics(metrics=avg)


class ShellTester:
    """Run A/B tests and parameter sweeps on shells."""

    def __init__(self, matches_dir: str = "matches", opponent_adapter: str = "claude",
                 opponent_model: str = "sonnet"):
        self._matches_dir = matches_dir
        self._opponent_adapter = opponent_adapter
        self._opponent_model = opponent_model

    def ab_test(self, shell_a: Optional[ShellConfig], shell_b: Optional[ShellConfig],
                game: str, n_games: int,
                agent_id: str = "test-agent",
                adapter: str = "claude", model: str = "sonnet",
                opponent_id: str = "opponent",
                verbose: bool = True) -> ABResult:
        """Run N games with each shell, compare results.

        shell_a/shell_b can be None for no-shell baseline.
        """
        label_a = shell_a.version if shell_a else "no-shell"
        label_b = shell_b.version if shell_b else "no-shell"

        if verbose:
            print(f"=== Shell A/B Test: {game} ({n_games} games each) ===")
            print(f"  Shell A: {label_a}")
            print(f"  Shell B: {label_b}")
            print()

        results_a = self._run_batch(
            shell=shell_a, game=game, n_games=n_games,
            agent_id=agent_id, adapter=adapter, model=model,
            opponent_id=opponent_id, label="A", verbose=verbose,
        )

        results_b = self._run_batch(
            shell=shell_b, game=game, n_games=n_games,
            agent_id=agent_id, adapter=adapter, model=model,
            opponent_id=opponent_id, label="B", verbose=verbose,
        )

        delta = self._extract_delta(
            results_a, results_b, agent_id, game,
            shell_a, shell_b,
        )

        result = ABResult(
            shell_a_version=label_a,
            shell_b_version=label_b,
            game=game,
            n_games=n_games,
            results_a=results_a,
            results_b=results_b,
            delta=delta,
        )

        if verbose:
            print()
            print("=== Delta ===")
            print(delta.summary())

        return result

    def parameter_sweep(self, shell: ShellConfig, param_name: str,
                        values: list[str], game: str, n_games: int,
                        agent_id: str = "test-agent",
                        adapter: str = "claude", model: str = "sonnet",
                        opponent_id: str = "opponent",
                        verbose: bool = True) -> SweepResult:
        """Sweep a single parameter across values."""

        if param_name not in shell.parameters:
            raise ValueError(f"Parameter '{param_name}' not found in shell. "
                           f"Available: {list(shell.parameters.keys())}")

        if verbose:
            print(f"=== Parameter Sweep: {param_name} ({len(values)} values × {n_games} games) ===")

        points = []
        for val in values:
            # Create modified shell with updated content
            modified = self._modify_shell_param(shell, param_name, val)

            if verbose:
                print(f"\n  {param_name}={val}:")

            results = self._run_batch(
                shell=modified, game=game, n_games=n_games,
                agent_id=agent_id, adapter=adapter, model=model,
                opponent_id=opponent_id, label=val, verbose=verbose,
            )

            wins = sum(1 for r in results if r.winner == agent_id)
            win_rate = wins / len(results) if results else 0

            # Extract behavior
            behaviors = [
                extract_behavior(game, r.match_id, agent_id, self._matches_dir)
                for r in results
            ]
            behavior = aggregate_behavior(behaviors)

            points.append(SweepPoint(
                param_value=val,
                win_rate=win_rate,
                n_games=len(results),
                results=results,
                behavior=behavior,
            ))

        best = max(points, key=lambda p: p.win_rate) if points else None

        result = SweepResult(
            param_name=param_name,
            game=game,
            points=points,
            best_value=best.param_value if best else "",
            best_win_rate=best.win_rate if best else 0,
        )

        if verbose:
            print(f"\n=== Sweep Results ===")
            for p in points:
                marker = " ← best" if p.param_value == result.best_value else ""
                beh = f" | {p.behavior.summary()}" if p.behavior.metrics else ""
                print(f"  {param_name}={p.param_value}: {p.win_rate:.0%} ({p.n_games} games){beh}{marker}")

        return result

    def save_report(self, result: ABResult | SweepResult, path: str):
        """Save test result as JSON report."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result.to_dict(), indent=2))
        print(f"Report saved: {p}")

    # ── Internal ──

    def _run_batch(self, shell: Optional[ShellConfig], game: str, n_games: int,
                   agent_id: str, adapter: str, model: str,
                   opponent_id: str, label: str,
                   verbose: bool) -> list[MatchResult]:
        """Run N games with a given shell (None = no shell)."""
        from lxm.client import LxMClient

        results = []
        shell_content = None
        if shell and shell.content:
            shell_content = shell.content
        elif shell and (shell.strategy_text or shell.parameters):
            # Render from parsed data
            from lxm.shell.manager import ShellManager
            shell_content = ShellManager()._render(shell)

        for i in range(n_games):
            match_id = f"shell_test_{label}_{game}_r{i+1:02d}"

            agents = [
                AgentConfig(
                    agent_id=agent_id,
                    adapter=adapter,
                    model=model,
                    seat=0,
                    hard_shell=shell_content,
                ),
                AgentConfig(
                    agent_id=opponent_id,
                    adapter=self._opponent_adapter,
                    model=self._opponent_model,
                    seat=1,
                ),
            ]

            # Alternate seats for fairness
            if i % 2 == 1:
                agents = [agents[1], agents[0]]
                agents[0].seat = 0
                agents[1].seat = 1

            config = MatchConfig(
                game=game,
                agents=agents,
                match_id=match_id,
                time_model=TimeModel(max_turns=GAME_MAX_TURNS.get(game, 100)),
                invocation=InvocationConfig(mode="inline", discovery_turns=0),
                skip_eval=True,
            )

            try:
                client = LxMClient(config)
                result = client.run()
                results.append(MatchResult(
                    match_id=match_id,
                    winner=result.get("winner"),
                    outcome=result.get("outcome", ""),
                    scores=result.get("scores", {}),
                    duration_seconds=client.duration_seconds,
                ))
                if verbose:
                    w = result.get("winner", "draw")
                    print(f"    {match_id}: {w}")
            except Exception as e:
                if verbose:
                    print(f"    {match_id}: ERROR - {e}")

        return results

    def _extract_delta(self, results_a: list[MatchResult],
                       results_b: list[MatchResult],
                       agent_id: str, game: str,
                       shell_a: Optional[ShellConfig],
                       shell_b: Optional[ShellConfig]) -> Delta:
        """Extract delta with behavior metrics."""
        wins_a = sum(1 for r in results_a if r.winner == agent_id)
        wins_b = sum(1 for r in results_b if r.winner == agent_id)
        n_a = len(results_a) or 1
        n_b = len(results_b) or 1
        wr_a = wins_a / n_a
        wr_b = wins_b / n_b

        avg_time_a = sum(r.duration_seconds for r in results_a) / n_a if results_a else 0
        avg_time_b = sum(r.duration_seconds for r in results_b) / n_b if results_b else 0

        # Extract behavior metrics
        beh_a = aggregate_behavior([
            extract_behavior(game, r.match_id, agent_id, self._matches_dir)
            for r in results_a
        ])
        beh_b = aggregate_behavior([
            extract_behavior(game, r.match_id, agent_id, self._matches_dir)
            for r in results_b
        ])

        # Behavior changes
        beh_changes = {}
        all_keys = set(beh_a.metrics.keys()) | set(beh_b.metrics.keys())
        for k in all_keys:
            a_val = beh_a.metrics.get(k, 0)
            b_val = beh_b.metrics.get(k, 0)
            if abs(b_val - a_val) > 0.001:
                beh_changes[k] = b_val - a_val

        shell_len_a = len(shell_a.content or "") if shell_a else 0
        shell_len_b = len(shell_b.content or "") if shell_b else 0

        return Delta(
            win_rate_a=wr_a,
            win_rate_b=wr_b,
            win_rate_change=wr_b - wr_a,
            behavior_a=beh_a,
            behavior_b=beh_b,
            behavior_changes=beh_changes,
            cost_a=CostMetrics(avg_response_time=avg_time_a, shell_length=shell_len_a),
            cost_b=CostMetrics(avg_response_time=avg_time_b, shell_length=shell_len_b),
        )

    def _modify_shell_param(self, shell: ShellConfig, param_name: str, new_value: str) -> ShellConfig:
        """Create a new shell with one parameter changed, updating the raw content too."""
        new_params = {**shell.parameters, param_name: new_value}

        # Update raw content if available
        new_content = shell.content
        if new_content and param_name in shell.parameters:
            old_line = f"- {param_name}: {shell.parameters[param_name]}"
            new_line = f"- {param_name}: {new_value}"
            new_content = new_content.replace(old_line, new_line)

        return ShellConfig(
            content=new_content,
            parameters=new_params,
            strategy_text=shell.strategy_text,
            rules=list(shell.rules),
            version=f"{shell.version}_{param_name}={new_value}",
        )
