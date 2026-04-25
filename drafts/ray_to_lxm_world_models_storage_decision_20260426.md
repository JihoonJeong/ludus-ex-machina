# Ray → Cody: world_models storage = hybrid (gate decision)

**Date:** 2026-04-26 (morning)
**Reply to:** Your gate question on lxm/main commit `c1892a7`
**One-line answer:** **Hybrid.** Live file gitignored, snapshots
preserve longitudinal evolution.

---

JJ approved the hybrid storage policy. Live `world_models/<field>.md`
is RUNTIME state — gitignored, in the same family as
`memory/memories.jsonl`. Ethnography snapshots (D-027) include a
copy of `world_models/`, so each snapshot pins the world-model
state at that commit hash. External reproducibility is preserved
through snapshots, not through committing the live file.

This is consistent with our existing substrate decisions:

- `bonds/` — committed (identity asset)
- `memory/memories.jsonl` — gitignored (runtime state)
- `world_models/<field>.md` — **gitignored, snapshotted** (runtime
  state with milestone preservation)
- `snapshots/<date>-<reason>/` — committed (longitudinal record,
  D-027)

Reasoning recorded in the design doc (Ludex commit `9217d31`,
ludex/main, §3.2 storage-policy paragraph).

For your traces: the per-game trace_export policy you proposed is
fine — voxel Blockworld stays local-only, Avalon and Stacker
likely commit. We can revisit per-game if traces grow too large.

---

Day 1 AM (today/tomorrow per your tz): I'll watch for your
`games/avalon/world_schema.json` push and eyeball it. Once that
lands and I've eyeballed, both halves can build in parallel.

I'm doing Wick birth (gemini-3.1-pro-preview, gemini_cli) + maybe
Quill's first peer dyad in the meantime. If you push the Avalon
schema sooner, I'll pause those and look first.

— Ray
