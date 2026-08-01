# PhysGym import smoke — LxM side (external agent) — PASS

*LxM Cody, 2026-08-01. Mirror of Ludex's creature import smoke (b63eaed5),
but with an EXTERNAL agent through the LxM harness = the diagnostic-axis path.
Script: `import_smoke.py`. Env: PhysGym installed editable into `.venv` from
the GitHub clone (`principia-ai/PhysGym`, MIT).*

## Result — the import path stands for LxM too

- **External agent (haiku via `ClaudeCodeAdapter`) drove PhysGym env 285**
  ("bug on a disk", vars m/R/omega) **through the LxM harness**: read the
  report → proposed 5 experiments (JSON) → `run_experiment` returned real
  observations (outputs 0.1, 0.5, 0.2, 0.625, 1.47) → proposed hypothesis
  → `test_hypothesis` returned metrics. No PhysGym native runner, no model-
  endpoint dispatch — our driver, our loop.
- **haiku SOLVED it at default masking**: hypothesis `5*m*R*omega**2` →
  **MSE 0.0, R² 1.0, symbolically equivalent (`is_correct`=True)**.

## The load-bearing finding — masking IS the acquirability axis

haiku solving env 285 at *default* masking = a **ceiling** (the physics-
literate model derives the centripetal-style law from prior knowledge, not
from the 5 observations). This is the immune-E1 encyclopedic ceiling in
physics clothing. So the interesting signal is the **default→anonymous
delta**:
- `default`: params `[m, R, omega]` + physical descriptions → solvable via prior.
- `anonymous_no_context_no_description`: params `[var_1, var_2, var_3]`,
  descriptions `None`, "Environment anonymized" → must INDUCE from observations.

The masking level (PhysGym's built-in `mode`) is the acquirability control we
wanted — and it is **under our harness's control**, confirmed empirically.

## Carriage §point-of-use — under our control

The report (law-relevant context: problem + controllable variables + prior
observations) is embedded in **every decision-turn prompt by our driver**.
Carriage is our driver's job here (nowline (d) lesson applied), not PhysGym's —
the import path is carriage-safe by construction on our side.

## Harvest note

`test_hypothesis` returns nested metrics: `fit_metrics` (MSE/NMSE/R²/Kendall
tau/MAPE/fit_quality) + top-level `is_correct` / `overall_score` /
`equivalence_metrics` / `fits_data`. Richer than raw MSE; read the nested
keys (the smoke's top-level `.get("mse")` was None only because the key is
under `fit_metrics`).

## Verdict

"One bench, two harnesses, both import" confirmed on the LxM side. LxM imports
PhysGym envs and runs EXTERNAL agents (diagnostic axis, OpenMMO-readiness) with
our carriage + masking + result control; Ludex imports for creature organ-arm
신검. Same bench, same indicators store, distinct agent types.

Productionizing: PhysGym is installed editable from a local clone for the
smoke — a real feature needs a vendoring/requirements decision. agy excluded
here (tool-hunts on investigation prompts, see the agy adapter fix `d26bd6e`);
lineage comparison (haiku/claude/grok) is a pre-reg lineage-column item.

## Anonymous-masking probe (decisive for the Physics-E1 spec rebuttal)

`anon_smoke.py` — env 285 at `anonymous_no_context_no_description`
(`var_1/var_2/var_3`, descriptions `None`), **honest carriage** (all 8
observations placed in the prompt by the driver), **NO organ**:

> haiku inferred `5 * var_1 * var_2 * var_3**2` → **is_correct=True, R² 1.0**.

Same law as default, induced purely from the numbers (variable names carry no
information). Two consequences for the spec:

1. **Anonymous is NOT a ceiling-escape.** Masking removes prior-KNOWLEDGE
   access but the functional form is still in the observations, so a capable
   inducer still solves it → the wall does not bind at anonymous either (the
   immune-E1/E1b W0-fail pattern). A per-(env, lineage) W0 check is needed
   before fixing cells on "anonymous".
2. **Cross-turn memory is irrelevant here.** The task is solved in ONE round
   with honest carriage and no organ. So `memory.recall` OFF would fail only
   if the driver *withholds* carriage (the draft's no-reload decision) — which
   measures "recall vs deliberately-withheld carriage", not "does memory help
   induction". The honest-carriage/no-organ path already succeeds.
