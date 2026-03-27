# Shell Engineering — Cross-Game Comparison

## The Big Picture

Three games, three phases each. 195+ matches total.

| Game | SIBO | Shell > no-shell? | Best Method | Optimal Win% | no-shell Win% |
|------|------|-------------------|-------------|--------------|---------------|
| **Poker** | 0.65 | **Yes** | Sweep/LLM-Guided (tied) | 80% | 60% |
| **Avalon** | 0.58 | **No** | — | 60% | 80% |
| **Codenames** | 0.35 | **Yes** | Parameter Sweep | 100% | 80% |

---

## Pattern 1: "Shell Compliance ≠ Winning"

In all three games, the default shell template performed worse than or equal to no-shell:

| Game | Default Shell | Win% | no-shell Win% |
|------|--------------|------|---------------|
| Poker | TAG (fold 52%) | 20% | 60% |
| Avalon | Deep Cover | 40% | 80% |
| Codenames | Aggressive (max 4) | 20% | 80% |

**Following instructions faithfully does not mean winning.** This is the foundational finding of Shell Engineering.

## Pattern 2: Inverted-U Curve

Poker and Codenames both show inverted-U curves when sweeping parameters:

### Poker: pre_flop_threshold
```
top 10% → 0%  |  top 20% → 20%  |  top 30% → 80%  |  top 50% → 40%
```

### Codenames: clue_number_max
```
max=1 → 20%  |  max=2 → 80%  |  max=3 → 100%  |  max=4 → 40%
```

**There exists an optimal parameter value.** Too little and too much both hurt.

### Avalon: first_sabotage_quest
```
Q1 → 60%  |  Q2 → 60%  |  Q3 → 60%  |  Q4 → 20%  |  Q5 → 40%
```

Avalon shows monotonic decrease, not inverted-U. The parameter doesn't map cleanly to outcome.

## Pattern 3: SIBO Doesn't Predict Optimization Success

Original hypothesis: Higher SIBO → better Shell optimization.

| Game | SIBO | Shell > no-shell? | Prediction |
|------|------|-------------------|------------|
| Poker | 0.65 | Yes | ✅ Correct |
| Avalon | 0.58 | No | ✅ Correct |
| Codenames | 0.35 | **Yes** | ❌ Wrong |

**SIBO measures behavioral override, not optimization potential.** Codenames has low SIBO (shell doesn't change behavior much) but high optimization potential because:
- The game has a **single dominant parameter** (clue number) that directly maps to outcomes
- Small behavioral change (avg clue 2.5 → 2.1) creates large outcome change (20% → 100%)
- "Signal-to-noise ratio" of the parameter is high

### New Hypothesis: Parameter Directness

What predicts Shell optimization success:

| Factor | Poker | Avalon | Codenames |
|--------|-------|--------|-----------|
| Clear tunable parameter | ✅ pre_flop_threshold | ❌ sabotage timing is fuzzy | ✅ clue_number_max |
| Parameter → behavior mapping | ✅ direct (fold%) | ❌ indirect (social dynamics) | ✅ direct (clue size) |
| Small change → large effect | ✅ 20%→30% → +60% win | ❌ Q1-Q3 identical | ✅ max 2→3 → +20% win |
| Shell optimization works | ✅ | ❌ | ✅ |

**Parameter Directness > SIBO** for predicting optimization success.

## Pattern 4: LLM-Guided Efficiency

| Game | Sweep Cost | LLM-Guided Cost | Same Result? |
|------|-----------|-----------------|-------------|
| Poker | 30 matches | 10 + LLM×2 | **Yes** (both 80%) |
| Avalon | 25 matches | 25 + LLM×4 | **Yes** (both 60%) |
| Codenames | 20 matches | 25 + LLM×3 | **No** (80% < 100%) |

- Poker: LLM-Guided is strictly more efficient (1/3 cost, same result)
- Avalon: LLM-Guided matches sweep but is unstable (non-monotonic)
- Codenames: LLM-Guided underperforms sweep (80% vs 100%)

**LLM-Guided is best when the key parameter is identifiable from loss analysis.** Poker losses clearly show "fold too much" → adjust threshold. Codenames losses don't clearly show "clue number too high" → LLM makes wrong adjustments.

## Pattern 5: Shell Can Hurt

In 2/3 games, the wrong shell is worse than no shell:

| Game | Worst Shell | Win% | no-shell | Delta |
|------|------------|------|----------|-------|
| Poker | TAG (default) | 20% | 60% | **-40%** |
| Avalon | Deep Cover | 40% | 80% | **-40%** |
| Codenames | Aggressive | 20% | 80% | **-60%** |

**Untested shells are dangerous.** This is a warning for the entire prompt engineering field: adding instructions without measurement can actively degrade performance.

---

## Summary Table

| Metric | Poker | Avalon | Codenames |
|--------|-------|--------|-----------|
| SIBO Index | 0.65 | 0.58 | 0.35 |
| Default Shell win% | 20% | 40% | 20% |
| no-shell win% | 60% | 80% | 80% |
| Sweep optimal win% | **80%** | 60% | **100%** |
| LLM-Guided best win% | **80%** | 60% | 80% |
| Shell > no-shell? | **Yes** | No | **Yes** |
| Inverted-U curve? | Yes | No (monotonic) | Yes |
| Key parameter | pre_flop_threshold | — | clue_number_max |
| Parameter directness | High | Low | High |

---

## Implications for Paper

1. **"Prompt Engineering Without Measurement is Dangerous"** — Default shells hurt in 2/3 games
2. **"Inverted-U Exists When Parameters Are Direct"** — Optimal point exists, can be found
3. **"SIBO ≠ Optimization Potential"** — Need new metric: Parameter Directness
4. **"LLM-Guided Works for Diagnosable Problems"** — When losses have clear causes
5. **"Shell Engineering Framework Generalizes"** — Same methodology works across game types

## Data Files
- `shell_engineering_poker_summary.md` + phase 1/2/3 JSONs
- `shell_engineering_avalon_summary.md` + phase 1/2/3 JSONs
- `shell_engineering_codenames_summary.md` + full JSON
