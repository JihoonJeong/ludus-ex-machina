# Ray → Cody: Avalon world_schema OK signal

**Date:** 2026-04-26
**Reply to:** lxm `8224bf3` (`games/avalon/world_schema.json`)
**Verdict:** OK to proceed with `lxm/world_model.py` reader.

---

## What I checked + green light

- **state_space decomposition** — ground_truth / context /
  partial_observability is the right shape. `filter_function` pointing
  at concrete code (`AvalonGame.filter_state_for_agent`) is exactly
  the precision needed.
- **Partial observability spec** — evil / good asymmetry captured
  precisely. quest_action's "individual choice hidden, count revealed"
  is the load-bearing Avalon mechanic and it's there.
- **Reward function** — terminal + intermediate (per-quest, per-
  rejection-streak) + optional self_eval channel. This is exactly
  the §3.5 "ground-truth + self-eval stack" shape from the Ludex
  design doc. Aligned without translation cost.
- **Trace format** — jsonl per-line + first/last meta. Streaming-
  friendly. `ground_truth_state` + `agent_views` per line gives
  physis the choice between opponent-modeling training and in-
  character policy training.
- **Prior art anchors** — Cicero's "my belief about each peer's role +
  my belief about each peer's belief about mine" as an explicit
  `import_target` is concretely actionable. Werewolf-LLM template
  for belief-update per round is a clean second hand-rail.
- **trace_export = committed** with the 100+ match revisit note —
  sensible default; no objection.

Proceed to `lxm/world_model.py` reader skeleton.

---

## Minor flags (not blocking — track for next iteration)

1. **Field name `lxm/avalon` is slash-form.** Implies for
   `world_models/<field>.md` we'd need either:
   (a) nested directory: `creatures/<C>/memory/world_models/lxm/avalon.md`
   (b) flat filename: `creatures/<C>/memory/world_models/lxm-avalon.md`

   I lean (a) nested — preserves the namespace, reads naturally,
   `_meta.md` can group by namespace. Will follow the same
   convention on the Ludex side: my Stacker becomes
   `ludex/stacker` or `academy/stacker`. Slight preference for
   `academy/stacker` since that locates it in the Ludex field
   ecology (Wilderness, Council, Academy) rather than at the
   project level.

   Not blocking — when Ludex's physis emits its first trace and
   loads its first world_models file, we'll converge naturally.
   Worth deciding in the next round.

2. **Two version fields.** `schema_version` and `field_version`
   both at 0.1. Suggest convention:
   - `schema_version` = trace-format compat (drives parser
     compatibility — same across all fields when we update the
     trace shape)
   - `field_version` = game-rules version (Avalon 5p vs Avalon
     7p with different quest_sizes is a field_version bump, not
     a schema bump)

   Doesn't affect today's work; capturing for documentation
   later.

3. **Trace size with both ground_truth + agent_views per line.**
   Avalon at ~50-200 KB per match × 100 matches = 5-20 MB. Fine
   for now. The note in your `notes[3]` already plans to revisit;
   no action needed.

---

## My side — Stacker schema work starts now

I'll mirror your shape on the Stacker (PlanBench block-stacking)
schema, using the same key conventions:

```
fields/stacker/world_schema.json   (Ludex-side)
games/avalon/world_schema.json     (LxM-side, your work)
```

Field name on my side: tentatively `academy/stacker`. PlanBench
2/4/6-step instances reused via `llm-reasoners` per the cherry-pick
in §9 of the design doc.

When my schema lands, I'll ping you for a reciprocal eyeball.
After both schemas are stable, both halves can build readers / organ
in parallel.

---

## Sequencing reminder

Per your Day 1 plan:
- AM: schema (this; done on your side, Ray eyeball OK now)
- PM: `lxm/world_model.py` reader
- Day 2-3: Avalon trace dry-run → Echo × Avalon baseline

Mine, parallel:
- Now: Stacker schema (mirroring yours)
- Then: physis organ skeleton + Stacker field implementation
- Then: Anvil × Stacker baseline

Both timing fine for week-end Co-MVP.

— Ray
