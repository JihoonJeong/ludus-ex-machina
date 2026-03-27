# Shell Engineering — Avalon 3-Phase Results

## Overview

| Phase | Method | Matches | Best Evil Win% | Key Finding |
|-------|--------|---------|----------------|-------------|
| 1 | A/B Test | 30 | no-shell 80% | Shell compliance ≠ winning |
| 2 | Parameter Sweep | 25 | Q1-Q3 → 60% | Monotonic decrease, no inverted-U |
| 3 | LLM-Guided | 25 + LLM×4 | Gen 4 → 60% | Non-monotonic, unstable |

Opponent: all-Sonnet, no-shell Good team (fixed).

---

## Phase 1: A/B Test

| Condition | Evil Win% |
|-----------|-----------|
| Deep Cover | 40% |
| no-shell | **80%** |
| Aggressive | 60% |
| Aggressive (vs Deep Cover) | 0% |

- Shell compliance ≠ winning (reproduced from poker)
- no-shell Evil strongest — LLM's own judgment > template strategies
- Aggressive 0% vs Deep Cover matches previous Cross-Shell data

## Phase 2: Parameter Sweep (first_sabotage_quest)

| Quest | Evil Win% |
|-------|-----------|
| Q1 | 60% |
| Q2 | 60% |
| Q3 | 60% |
| Q4 | 20% |
| Q5 | 40% |

- Monotonic decrease (not inverted-U like poker)
- Q1-Q3 identical at 60% — early sabotage timing doesn't differentiate
- Optimal Shell (60%) < no-shell (80%)

## Phase 3: LLM-Guided Training

| Gen | Version | Evil Win% | Note |
|-----|---------|-----------|------|
| 1 | v1.0 | 0% | LLM → v2.0 |
| 2 | v2.0 | 20% | LLM → v3.0 |
| 3 | v3.0 | 0% | LLM → v4.0 |
| 4 | v4.0 | **60%** | LLM → v5.0 |
| 5 | v5.0 | 40% | |

- Aggressive(0%) → 60% improvement, but non-monotonic (0→20→0→60→40)
- Cannot exceed no-shell (80%)

## Key Finding

**Shell optimization has limits in complex social games.** Avalon's multi-agent social deduction resists parameterization — Shell constrains the LLM's natural social reasoning.

## Data Files
- `shell_engineering_avalon_phase1.json`
- `shell_engineering_avalon_phase2.json`
- `shell_engineering_avalon_phase3.json`
