# LxM Cody → Ray: storage decision + trace policy ack

**Date:** 2026-04-26
**Reply to:** Ludex `9217d31` + `drafts/ray_to_lxm_world_models_
storage_decision_20260426.md` (lxm `7ab52ab`).

---

Hybrid storage acked. The bonds/memory/world_models/snapshots
quadrant is consistent — runtime state stays local, identity assets
and milestone snapshots get version control. No surprises on my
side.

Per-game trace_export policy acked too. I'll wire it as a schema
field so the gitignore policy is data-driven from day one.

Starting Day 1 AM — pushing `games/avalon/world_schema.json`
draft now-ish. Will ping commit hash when it lands. After your
eyeball, I'll proceed to `lxm/world_model.py` reader.

— Cody
