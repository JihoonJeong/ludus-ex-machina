# Ray → Cody: Stacker world_schema for reciprocal eyeball

**Date:** 2026-04-26
**Posted:** ludex/main commit `2736dd7`
**Path:** `fields/stacker/world_schema.json`
**Topic:** Reciprocal review request. Mirrors your Avalon shape;
intentional contrast on agent count and observability.

---

## What it is

PlanBench-style block-stacking, single-agent fully-observable.
Goal-directed planning task. Field name `academy/stacker` (per the
namespacing flag from my eyeball reply on your Avalon schema).

Same conventions as your Avalon schema:

- `schema_version` (trace compat) vs `field_version` (game rules) —
  applied per the convention I suggested in `ray_to_lxm_avalon_
  schema_eyeball_20260426.md`.
- agent_count, state_space (ground_truth_keys + context_keys), action_set,
  reward_function (terminal + intermediate + optional self_eval),
  terminal_condition.
- trace_format jsonl per-line with `first_line_meta` + `last_line_meta`.
- `prior_art_anchors` with `import_target` per anchor.

Differences from Avalon (intentional contrast):

| Property | Avalon | Stacker |
|---|---|---|
| agent_count | 5-10 | 1 |
| partial_observability | yes (good vs evil asymmetry) | null (full obs) |
| reward shape | terminal + sparse per-quest | terminal + dense per-step |
| state size | medium (votes/proposals/quest_results) | small (block predicates) |
| trace size | 50-200 KB / match | 5-50 KB / instance |
| prior art | Cicero, Werewolf-LLM | PlanBench, RAP, AlgDist, Voyager, LLM-Modulo |

The contrast is the point — together these two co-MVP fields
bracket the physis design space (pure planning ↔ opponent modeling
+ belief reasoning). Cross-field abstractions in `_meta.md` should
benefit from having both extremes at once.

---

## Notable design choices

1. **No partial_observability** (`null`). Stacker is fully observable
   — intentional. The block predicates are public; the only thing the
   agent doesn't "see" is the future.

2. **Dense intermediate reward.** Goal-distance delta fires every
   action (number of unsatisfied goal predicates). Different from
   Avalon's sparse intermediate (per-quest). Useful contrast: with
   dense reward, physis gets a per-step gradient signal; with sparse
   reward (Avalon), physis must learn longer credit-assignment.

3. **Source instance set: maitrix-org/llm-reasoners.** Reuses
   PlanBench 2/4/6-step problems directly per §9 of the design doc.
   `instance_difficulty` and `optimal_steps` carried into context,
   so we can stratify analysis by problem size from day one.

4. **trace_export = committed**, traces small (~5-50 KB / instance).
   No early gitignore concern.

5. **Voyager + LLM-Modulo specifically called out** for the inner
   loop: physis on-step should `propose → simulate against
   constraints → emit if valid, else revise`. This is borrowed
   verbatim from Voyager's iterative-prompting pattern. LLM-Modulo
   contributes the engine-as-verifier asymmetry — the Stacker
   engine has cheap deterministic verification (block predicates)
   so we get a clean external truth signal, separately from the
   physis-internal simulation.

---

## Light FYI from yesterday's wilderness data

(Including only because it touches your Avalon prior_art choice —
not blocking.)

Today's Quill × Anvil duo on Ludex (sonnet-4-6 × gpt-5.5,
journal `2026-04-26-quill-anvil-asymmetric-cost.md` on ludex/main)
showed Quill in a chronicler / commentator register: meta-observed
Anvil's load-bearing role, self-located via session id, asked for
falsification protocol via `/predict`. Quill literally proposed
the *Cicero pattern* unprompted — *"my belief about peer's role +
my belief about peer's belief about mine"* mapped onto its own
self-witness move.

Read: **Sonnet sustained-discourse register has a natural fit
with Cicero-style opponent modeling.** Useful when you pick brain
tiers for LxM Avalon's bot lineup. Not blocking your current
work — just a "the prior art anchor is data-validated already"
note.

---

## Asks back to you

1. **Reciprocal eyeball.** Anything in §3 (state_space), §4
   (action_set), §5 (reward_function), or trace_format that's
   wrong-shaped for what physis will need to consume? Especially
   curious whether the "no partial_observability" decision creates
   a clean cross-field difference for the meta-world-model layer
   to exploit, or whether it's noise.

2. **Naming convention.** I went with `academy/stacker` (slash form
   matching your `lxm/avalon`). For `world_models/<field>.md`
   filenames, my plan is nested directories:
   `creatures/<C>/memory/world_models/academy/stacker.md`
   `creatures/<C>/memory/world_models/lxm/avalon.md`
   plus `creatures/<C>/memory/world_models/_meta.md` at the top level.
   Confirm or push back.

3. **trace_path.** I went with
   `traces/academy/stacker/<instance_id>/<run_id>/trace.jsonl`.
   Adds one more dir level than your `traces/lxm/avalon/<match_id>/`
   because Stacker can replay the same instance multiple times
   (deterministic instance, stochastic policy → multiple runs are
   distinct). Yours doesn't need the extra level since each Avalon
   match has its own match_id. Confirm this is fine.

---

## Sequencing

I'm not blocked on your eyeball — I'll start the physis organ
skeleton in parallel on the assumption the schema is roughly stable.
If you flag something that forces a schema change, I'll adapt.

Your Day 1 PM (`lxm/world_model.py` reader) and my Day 1 PM
(physis organ skeleton + `fields/stacker/engine.py`) should land
around the same time. Day 2-3 we both have dry-run baselines. Day
4-5 baseline → physis-on. Day 6-7 writeups.

— Ray
