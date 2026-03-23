"""Shell Trainer — automated shell optimization via evolutionary strategies.

Strategies:
- parameter_sweep: grid search over Parameter values
- llm_guided: LLM analyzes losses and suggests modifications
- genetic: population-based evolution (future)

Usage:
    trainer = ShellTrainer()
    best_shell = trainer.train(
        shell=initial_shell, game="poker",
        agent_id="jj-sonnet", adapter="claude", model="sonnet",
        strategy="llm_guided", generations=5, games_per_gen=5,
    )
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lxm.config import ShellConfig
from lxm.shell.manager import ShellManager
from lxm.shell.tester import ShellTester, MatchResult, Delta


@dataclass
class GenerationResult:
    """Result of one generation in training."""
    generation: int
    shell: ShellConfig
    win_rate: float
    n_games: int
    results: list[MatchResult] = field(default_factory=list)
    delta_from_prev: Optional[Delta] = None
    modification_note: str = ""


@dataclass
class LossAnalysis:
    """Analysis of why matches were lost."""
    total_games: int = 0
    losses: int = 0
    loss_patterns: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    raw_analysis: str = ""


@dataclass
class TrainResult:
    """Full training run result."""
    game: str
    strategy: str
    generations: list[GenerationResult] = field(default_factory=list)
    best_shell: Optional[ShellConfig] = None
    best_win_rate: float = 0.0
    best_generation: int = 0

    def summary(self) -> str:
        lines = [
            f"=== Training Summary: {self.game} ({self.strategy}) ===",
            f"Generations: {len(self.generations)}",
        ]
        for g in self.generations:
            marker = " ← best" if g.generation == self.best_generation else ""
            note = f" ({g.modification_note})" if g.modification_note else ""
            lines.append(
                f"  Gen {g.generation}: {g.shell.version} — "
                f"Win {g.win_rate:.0%} ({g.n_games} games){note}{marker}"
            )
        lines.append(f"Best: {self.best_shell.version} ({self.best_win_rate:.0%})")
        return "\n".join(lines)


class ShellTrainer:
    """Automated shell optimization."""

    def __init__(self, matches_dir: str = "matches",
                 opponent_adapter: str = "claude",
                 opponent_model: str = "sonnet",
                 shells_dir: str = "shells"):
        self._tester = ShellTester(
            matches_dir=matches_dir,
            opponent_adapter=opponent_adapter,
            opponent_model=opponent_model,
        )
        self._manager = ShellManager(shells_dir=shells_dir)

    def train(self, shell: ShellConfig, game: str,
              agent_id: str = "train-agent",
              adapter: str = "claude", model: str = "sonnet",
              opponent_id: str = "opponent",
              strategy: str = "llm_guided",
              generations: int = 5,
              games_per_gen: int = 5,
              cost_weight: float = 0.1,
              convergence_threshold: float = 0.05,
              verbose: bool = True) -> TrainResult:
        """Train a shell over multiple generations.

        Args:
            shell: Initial shell to optimize
            game: Game to train on
            strategy: "parameter_sweep" | "llm_guided"
            generations: Max generations
            games_per_gen: Games per generation for evaluation
            cost_weight: Weight for cost in score (0=ignore, 1=prioritize)
            convergence_threshold: Stop if win rate change < this
        """
        if strategy == "parameter_sweep":
            return self._train_sweep(
                shell, game, agent_id, adapter, model, opponent_id,
                generations, games_per_gen, verbose,
            )
        elif strategy == "llm_guided":
            return self._train_llm_guided(
                shell, game, agent_id, adapter, model, opponent_id,
                generations, games_per_gen, cost_weight,
                convergence_threshold, verbose,
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy}. Use 'parameter_sweep' or 'llm_guided'.")

    def analyze_losses(self, results: list[MatchResult],
                       agent_id: str, game: str,
                       match_dir: str = "matches") -> LossAnalysis:
        """Analyze lost games to identify patterns."""
        losses = [r for r in results if r.winner and r.winner != agent_id]
        analysis = LossAnalysis(
            total_games=len(results),
            losses=len(losses),
        )

        # Read game logs for lost matches
        log_summaries = []
        for loss in losses[:5]:  # Cap at 5 for LLM context
            log_path = Path(match_dir) / loss.match_id / "log.json"
            if log_path.exists():
                try:
                    log = json.loads(log_path.read_text())
                    # Extract agent's moves only
                    agent_moves = [
                        e for e in log
                        if e.get("agent_id") == agent_id and e.get("result") == "accepted"
                    ]
                    moves_summary = [e.get("move", "") for e in agent_moves[-10:]]
                    log_summaries.append({
                        "match_id": loss.match_id,
                        "outcome": loss.outcome,
                        "last_moves": moves_summary,
                    })
                except (json.JSONDecodeError, OSError):
                    pass

        if log_summaries:
            analysis.loss_patterns = [
                f"Lost {loss.match_id}: {loss.outcome}" for loss in losses
            ]

        analysis.raw_analysis = json.dumps(log_summaries, indent=2)
        return analysis

    def suggest_modification(self, shell: ShellConfig,
                             analysis: LossAnalysis,
                             adapter: str = "claude",
                             model: str = "sonnet") -> ShellConfig:
        """Ask an LLM to suggest shell modifications based on loss analysis.

        Uses the same CLI adapter infrastructure to call the LLM.
        """
        prompt = self._build_modification_prompt(shell, analysis)

        # Call LLM via CLI adapter
        try:
            new_content = self._call_llm_for_shell(prompt, adapter, model)
            if new_content:
                new_shell = ShellConfig.from_text(new_content)
                # Bump version
                new_shell.parent_version = shell.version
                new_shell.version = self._bump_version(shell.version)
                new_shell.content = new_content
                return new_shell
        except Exception as e:
            print(f"  [Trainer] LLM suggestion failed: {e}")

        # Fallback: return shell unchanged
        return shell

    # ── Strategy: Parameter Sweep ──

    def _train_sweep(self, shell, game, agent_id, adapter, model,
                     opponent_id, generations, games_per_gen,
                     verbose) -> TrainResult:
        """Sweep each parameter one at a time (coordinate descent)."""
        result = TrainResult(game=game, strategy="parameter_sweep")
        current_shell = shell
        gen = 0

        for param_name in list(shell.parameters.keys()):
            if gen >= generations:
                break

            # Generate sweep values for this parameter
            values = self._generate_sweep_values(param_name, shell.parameters[param_name])
            if len(values) <= 1:
                continue

            sweep = self._tester.parameter_sweep(
                shell=current_shell, param_name=param_name,
                values=values, game=game, n_games=games_per_gen,
                agent_id=agent_id, adapter=adapter, model=model,
                opponent_id=opponent_id, verbose=verbose,
            )

            if sweep.best_value != current_shell.parameters.get(param_name):
                # Update shell with best value
                new_params = {**current_shell.parameters, param_name: sweep.best_value}
                current_shell = ShellConfig(
                    content=current_shell.content,
                    parameters=new_params,
                    strategy_text=current_shell.strategy_text,
                    rules=list(current_shell.rules),
                    version=self._bump_version(current_shell.version),
                    parent_version=current_shell.version,
                )

            gen += 1
            result.generations.append(GenerationResult(
                generation=gen,
                shell=current_shell,
                win_rate=sweep.best_win_rate,
                n_games=games_per_gen,
                modification_note=f"{param_name}={sweep.best_value}",
            ))

        # Find best
        if result.generations:
            best = max(result.generations, key=lambda g: g.win_rate)
            result.best_shell = best.shell
            result.best_win_rate = best.win_rate
            result.best_generation = best.generation

        return result

    # ── Strategy: LLM-Guided Evolution ──

    def _train_llm_guided(self, shell, game, agent_id, adapter, model,
                          opponent_id, generations, games_per_gen,
                          cost_weight, convergence_threshold,
                          verbose) -> TrainResult:
        """LLM analyzes losses and suggests shell modifications."""
        result = TrainResult(game=game, strategy="llm_guided")
        current_shell = shell
        prev_win_rate = 0.0

        for gen in range(1, generations + 1):
            if verbose:
                print(f"\n=== Generation {gen}/{generations}: {current_shell.version} ===")

            # Evaluate current shell
            from lxm.client import LxMClient
            from lxm.config import MatchConfig, AgentConfig, TimeModel, InvocationConfig, GAME_MAX_TURNS

            eval_results = self._tester._run_batch(
                shell=current_shell, game=game, n_games=games_per_gen,
                agent_id=agent_id, adapter=adapter, model=model,
                opponent_id=opponent_id,
                label=f"gen{gen}", verbose=verbose,
            )

            wins = sum(1 for r in eval_results if r.winner == agent_id)
            win_rate = wins / len(eval_results) if eval_results else 0

            gen_result = GenerationResult(
                generation=gen,
                shell=current_shell,
                win_rate=win_rate,
                n_games=len(eval_results),
                results=eval_results,
            )

            # Check convergence
            if gen > 1 and abs(win_rate - prev_win_rate) < convergence_threshold:
                gen_result.modification_note = "converged"
                result.generations.append(gen_result)
                if verbose:
                    print(f"  Converged (delta {abs(win_rate - prev_win_rate):.1%} < {convergence_threshold:.1%})")
                break

            result.generations.append(gen_result)

            # If not last generation, evolve
            if gen < generations:
                analysis = self.analyze_losses(eval_results, agent_id, game)
                if analysis.losses > 0:
                    new_shell = self.suggest_modification(
                        current_shell, analysis, adapter, model,
                    )
                    if new_shell.version != current_shell.version:
                        gen_result.modification_note = f"LLM modified → {new_shell.version}"
                        current_shell = new_shell
                    else:
                        gen_result.modification_note = "no change suggested"
                else:
                    gen_result.modification_note = "all wins"

            prev_win_rate = win_rate

        # Find best generation
        if result.generations:
            best = max(result.generations, key=lambda g: g.win_rate)
            result.best_shell = best.shell
            result.best_win_rate = best.win_rate
            result.best_generation = best.generation

        if verbose:
            print()
            print(result.summary())

        return result

    # ── Helpers ──

    def _build_modification_prompt(self, shell: ShellConfig,
                                   analysis: LossAnalysis) -> str:
        """Build prompt asking LLM to modify a shell."""
        return f"""You are a game strategy optimizer. Analyze the following shell (strategy document) and its performance, then produce an improved version.

CURRENT SHELL:
```markdown
{shell.content or self._manager._render(shell)}
```

PERFORMANCE:
- {analysis.total_games} games played, {analysis.losses} losses
- Loss patterns: {json.dumps(analysis.loss_patterns, indent=2)}

GAME LOGS (last moves from lost games):
{analysis.raw_analysis}

TASK:
Modify the shell to address the weaknesses shown in the losses. Keep the same Structured Markdown format with ## Parameters, ## Strategy, and ## Situational Rules sections.

Rules:
- Change at most 2-3 things (incremental improvement)
- Bump the version number
- Explain your changes briefly in a comment at the top

Output ONLY the new shell document in Structured Markdown format. No other text."""

    def _call_llm_for_shell(self, prompt: str,
                            adapter: str, model: str) -> Optional[str]:
        """Call an LLM to generate a shell modification.

        Uses subprocess to call the CLI directly — same approach as adapters.
        """
        if adapter == "claude":
            cmd = [
                "claude", "-p", prompt,
                "--model", model,
                "--output-format", "text",
            ]
        elif adapter == "gemini":
            cmd = ["gemini", "-p", prompt]
        else:
            return None

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
                # Extract markdown if wrapped in code fences
                if "```markdown" in output:
                    start = output.index("```markdown") + len("```markdown")
                    end = output.index("```", start)
                    return output[start:end].strip()
                elif "```" in output:
                    start = output.index("```") + 3
                    # Skip language identifier if present
                    newline = output.index("\n", start)
                    end = output.index("```", newline)
                    return output[newline:end].strip()
                return output
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"  [Trainer] LLM call failed: {e}")

        return None

    def _bump_version(self, version: str) -> str:
        """Bump version: v1.0 → v1.1, v2.3 → v2.4."""
        import re
        match = re.match(r"v(\d+)\.(\d+)", version)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            return f"v{major}.{minor + 1}"
        match = re.match(r"v(\d+)", version)
        if match:
            return f"v{int(match.group(1))}.1"
        return f"{version}.1"

    def _generate_sweep_values(self, param_name: str, current_value: str) -> list[str]:
        """Generate reasonable sweep values for a parameter."""
        # Try to parse as fraction (e.g., "1 per 5 hands")
        import re
        frac_match = re.search(r"(\d+)\s*per\s*(\d+)", current_value)
        if frac_match:
            num, denom = int(frac_match.group(1)), int(frac_match.group(2))
            variants = [denom // 2, denom, denom * 2]
            return [f"{num} per {d} hands" for d in variants if d > 0]

        # Try to parse as percentage (e.g., "top 20%")
        pct_match = re.search(r"(\d+)%", current_value)
        if pct_match:
            pct = int(pct_match.group(1))
            prefix = current_value[:current_value.index(str(pct))]
            variants = [max(5, pct - 10), pct, min(95, pct + 10)]
            return [f"{prefix}{v}%" for v in variants]

        # Boolean
        if current_value.lower() in ("true", "false"):
            return ["true", "false"]

        return [current_value]
