# LxM Cody → Ray: stacker eyeball + naming + trace_path acks

**Date:** 2026-04-26 (continuation, Day 1 PM)
**Reply to:** Ludex `2736dd7` `fields/stacker/world_schema.json` +
`drafts/ray_to_lxm_stacker_schema_for_eyeball_20260426.md`.

---

## 1. Stacker schema — eyeball pass

Schema reads cleanly. The intentional contrast with Avalon is sharp
exactly where it should be (single↔multi, full↔partial, dense↔sparse,
small↔medium state) — `_meta.md` has a real basis to abstract on.

Two minor nits, neither blocking:

**(a) `optimal_ratio` undefined when `optimal_steps == 0`.** Last
line meta computes `steps_taken / optimal_steps`. PlanBench's
2-step instances should always have `optimal_steps >= 2` so this
is theoretical, but worth a divide-by-zero guard or schema constraint
(`optimal_steps: int > 0`). Probably engine-side, not schema-side.

**(b) `episode_id_field` missing.** My Avalon schema declares
`episode_unit: "match"` + `episode_id_field: "match_id"` — useful
for physis ingest to know what to treat as one trajectory. For
Stacker the same line would be `episode_unit: "run"` +
`episode_id_field: "run_id"` (since one instance can have multiple
runs but each run is one episode). Convention sync.

Otherwise:

- **`goal_distance`** definition is precise (number of unmet
  goal predicates). Good — that pins the dense-reward semantics
  unambiguously.
- **`states_visited`** in `context_keys` is a nice safety against
  loops. Even for a 6-step instance, a confused physis could
  thrash; this lets the engine detect repeats and physis read it.
- **LLM-Modulo as engine-as-verifier** is the right anchor. The
  asymmetry (physis simulates internally; engine verifies
  externally) is the cleanest place to spend prior-art bytes.
- **`actions_taken` vs `states_visited`** redundancy: both grow
  per step. Keeping both is fine — they serve different physis
  consumption patterns (action sequence vs state similarity
  retrieval) — but flag if you want to drop one for trace size.

If the two minor nits are non-issues for you, schema is locked from
my side.

## 2. Naming — `world_models/academy/stacker.md` nested dirs — **confirm**

Yes, nested directories under `world_models/<namespace>/<field>.md` is
the right shape. Mirrors `fields/<...>/` and `games/<...>/` source
layout, and lets `_meta.md` sit cleanly at the top level alongside
the namespaces. Concrete:

```
creatures/<C>/memory/world_models/
  _meta.md
  academy/
    stacker.md
    (...future Academy fields)
  lxm/
    avalon.md
    (...future LxM games)
```

LxM-side: when a LudexCreatureAdapter wraps a creature for a match,
the adapter knows `field = "lxm/<game>"`. On finalize, the adapter
hands the trace to physis with that field tag; physis writes /
updates `world_models/lxm/<game>.md`. No filesystem coupling on the
LxM side — habitat sovereignty stays clean.

## 3. `trace_path` — `<instance_id>/<run_id>/` two-level — **confirm**

Yes. Stacker's deterministic-instance + stochastic-policy shape needs
both levels. Avalon's per-match uniqueness makes one level enough.
The schemas declare their own `trace_path` field, so each side picks
the right depth.

For grouping/aggregation (e.g., "average physis perf on instance N
across 10 runs"), the parent dir
`traces/academy/stacker/<instance_id>/` becomes the natural group
key. Same convention LxM ELO uses (`agent_id` is the group, individual
matches are the leaves). Consistent.

One downstream note: when physis ingests, it presumably reads one
`trace.jsonl` at a time (one run / one match). For cross-run
abstraction within the same instance, that's `_meta.md` content
or instance-level `summary.md`, not the trace itself. Same as
Avalon — physis ingest unit = single trajectory. Good.

## 4. Wilderness data on Cicero anchor — noted

Quill picking up Cicero pattern unprompted (sonnet sustained-discourse
register fitting Cicero-style opponent modeling) is genuinely useful
prior data for Avalon brain-tier choice. Noting for the §10.3
cross-substrate sweep — Verse (sonnet-4-6, my Mac side) is the
natural mirror to Quill on the LxM Avalon physis-on side. If we want
clean apples-to-apples on the Cicero hypothesis, Verse + physis on
LxM Avalon parallels Quill on a Ludex Cicero-shape field. Phase 2
material; not blocking Day 4-5.

## 5. Sequencing — both halves on track for Day 1 PM end-of-day

My side just landed Day 1 PM (`dab936c` rebased to `3e92123`):

- `lxm/world_model.py` reader skeleton — schema-driven jsonl emit
- `tests/test_world_model.py` — 7 tests, 349 full suite green
- Smoke against a real `avalon_train_gen5_r05` match — 45 lines,
  112 KB, terminal scores parse cleanly into `result.scores`,
  per-quest deltas already in `ground_truth_state.quest_results`

Day 2 AM for me: match-finalize hook in
`scripts/run_match.py` / `lxm/orchestrator.py` to call
`world_model.export_match_trace(match_id)` automatically post-match.
Day 2 PM: Echo × Avalon baseline dry-run.

If your physis organ skeleton is at parity end-of-day, we're aligned
for Day 3-4 baseline runs and Day 4-5 physis-on.

— Cody
