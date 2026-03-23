"""Shell Tester — A/B testing, parameter sweep, and delta extraction.

Usage:
    tester = ShellTester()
    result = tester.ab_test(
        shell_a=shell_v1, shell_b=shell_v2,
        game="poker", n_games=10,
        agent_id="jj-sonnet", adapter="claude", model="sonnet",
    )
    print(result.delta.summary())
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
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
        if self.behavior_changes:
            lines.append("Behavior changes:")
            for k, v in sorted(self.behavior_changes.items()):
                lines.append(f"  {k}: {v:+.1%}")
        if self.cost_a.avg_response_time or self.cost_b.avg_response_time:
            lines.append(f"Avg response time: {self.cost_a.avg_response_time:.1f}s → {self.cost_b.avg_response_time:.1f}s")
        return "\n".join(lines)


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


class ShellTester:
    """Run A/B tests and parameter sweeps on shells."""

    def __init__(self, matches_dir: str = "matches", opponent_adapter: str = "claude",
                 opponent_model: str = "sonnet"):
        self._matches_dir = matches_dir
        self._opponent_adapter = opponent_adapter
        self._opponent_model = opponent_model

    def ab_test(self, shell_a: ShellConfig, shell_b: ShellConfig,
                game: str, n_games: int,
                agent_id: str = "test-agent",
                adapter: str = "claude", model: str = "sonnet",
                opponent_id: str = "opponent",
                verbose: bool = True) -> ABResult:
        """Run N games with each shell, compare results."""

        if verbose:
            print(f"=== Shell A/B Test: {game} ({n_games} games each) ===")
            print(f"  Shell A: {shell_a.version}")
            print(f"  Shell B: {shell_b.version}")
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

        delta = self._extract_delta(results_a, results_b, agent_id, shell_a, shell_b)

        result = ABResult(
            shell_a_version=shell_a.version,
            shell_b_version=shell_b.version,
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
            # Create modified shell
            modified = ShellConfig(
                content=shell.content,
                parameters={**shell.parameters, param_name: val},
                strategy_text=shell.strategy_text,
                rules=list(shell.rules),
                version=f"{shell.version}_{param_name}={val}",
            )

            if verbose:
                print(f"\n  {param_name}={val}:")

            results = self._run_batch(
                shell=modified, game=game, n_games=n_games,
                agent_id=agent_id, adapter=adapter, model=model,
                opponent_id=opponent_id, label=val, verbose=verbose,
            )

            wins = sum(1 for r in results if r.winner == agent_id)
            win_rate = wins / len(results) if results else 0

            points.append(SweepPoint(
                param_value=val,
                win_rate=win_rate,
                n_games=len(results),
                results=results,
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
                print(f"  {param_name}={p.param_value}: {p.win_rate:.0%} ({p.n_games} games){marker}")

        return result

    def _run_batch(self, shell: ShellConfig, game: str, n_games: int,
                   agent_id: str, adapter: str, model: str,
                   opponent_id: str, label: str,
                   verbose: bool) -> list[MatchResult]:
        """Run N games with a given shell. Returns list of results."""
        from lxm.client import LxMClient

        results = []
        shell_content = shell.content or ""

        for i in range(n_games):
            match_id = f"shell_test_{label}_{game}_r{i+1:02d}"

            agents = [
                AgentConfig(
                    agent_id=agent_id,
                    adapter=adapter,
                    model=model,
                    seat=0,
                    hard_shell=shell_content if shell_content else None,
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
                       agent_id: str,
                       shell_a: ShellConfig,
                       shell_b: ShellConfig) -> Delta:
        """Extract delta between two sets of results."""
        wins_a = sum(1 for r in results_a if r.winner == agent_id)
        wins_b = sum(1 for r in results_b if r.winner == agent_id)
        n_a = len(results_a) or 1
        n_b = len(results_b) or 1
        wr_a = wins_a / n_a
        wr_b = wins_b / n_b

        avg_time_a = sum(r.duration_seconds for r in results_a) / n_a if results_a else 0
        avg_time_b = sum(r.duration_seconds for r in results_b) / n_b if results_b else 0

        return Delta(
            win_rate_a=wr_a,
            win_rate_b=wr_b,
            win_rate_change=wr_b - wr_a,
            cost_a=CostMetrics(
                avg_response_time=avg_time_a,
                shell_length=len(shell_a.content or ""),
            ),
            cost_b=CostMetrics(
                avg_response_time=avg_time_b,
                shell_length=len(shell_b.content or ""),
            ),
        )
