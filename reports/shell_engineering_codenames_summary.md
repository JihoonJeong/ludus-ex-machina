# Shell Engineering — Codenames 3-Phase Results

## Overview

| Phase | Method | Matches | Best Shell Win% | Key Finding |
|-------|--------|---------|-----------------|-------------|
| 1 | A/B Test | 30 | Conservative 80% | Aggressive hurts (20%) |
| 2 | Parameter Sweep | 20 | max=3 → 100% | Inverted-U confirmed |
| 3 | LLM-Guided | 25 + LLM×3 | Gen 1 → 80% | Modification often hurts |

Opponent: no-shell Sonnet spy + Haiku guessers (both teams).

---

## Phase 1: A/B Test

| Test | Condition | Shell Spy Win% |
|------|-----------|---------------|
| A | Conservative | 80% |
| A | no-shell | 80% |
| B | Aggressive | 20% |
| B | no-shell | 40% |
| C | Conservative | 40% |
| C | Aggressive | 40% |

- Conservative (safe 2-word clues) matches no-shell
- Aggressive (4-word clues) actively hurts — 20% win rate
- Confirms Cross-Company finding: Claude's aggressive clues → assassin risk

## Phase 2: Parameter Sweep (clue_number_max)

| clue_number_max | Win% | Avg Clue Number |
|-----------------|------|-----------------|
| 1 | 20% | 1.1 |
| 2 | 80% | 1.9 |
| **3** | **100%** | **2.1** |
| 4 | 40% | 2.2 |

- **Inverted-U curve confirmed!** Too conservative (1) and too aggressive (4) both lose.
- **Optimal: max=3 with actual avg 2.1.** The constraint guides toward 2-word clues with occasional 3-word stretches.
- **Shell(100%) > no-shell(80%)** — optimization succeeds!

## Phase 3: LLM-Guided Training

| Gen | Version | Win% | Note |
|-----|---------|------|------|
| 1 | v1.0 | **80%** | LLM → v2.0 |
| 2 | v2.0 | 20% | LLM → v3.0 |
| 3 | v3.0 | 80% | LLM → v4.0 |
| 4 | v4.0 | 80% | converged |

- Started from Aggressive (should be weak), but Gen 1 already 80%
- LLM modification to v2.0 hurt performance (20%)
- Recovered by Gen 3, converged at 80%
- **Did not reach sweep optimal (100%)** — LLM-Guided less effective than grid search here

## Key Finding

**SIBO prediction was WRONG for Codenames.** SIBO 0.35 predicted Shell < no-shell, but Shell(100%) > no-shell(80%). The key factor isn't SIBO — it's whether the game has a **directly tunable parameter** (clue_number_max) that maps to behavior.

## Data Files
- `shell_engineering_codenames_full.json`
