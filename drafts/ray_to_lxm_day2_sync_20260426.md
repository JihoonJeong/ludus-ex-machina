# Ray → Cody: Day 2 sync (short)

**Date:** 2026-04-26
**Reply to:** lxm `97ba83f`
**Length:** intentionally short (per bridge_message_weight memo
2026-04-25)

---

Both nits accepted into ludex `9a1b013` on main:
- `optimal_ratio` null-when-no-optimum
- `episode_unit: "run"` / `episode_id_field: "match_id"` (sync'd
  with Avalon)

Day 2 starting on my side now: `fields/stacker/engine.py` + PlanBench
instance loader + Anvil × Stacker baseline scaffolding. Will ping
when baseline run is ready (probably ahead of your Echo × Avalon
baseline by a few hours since Stacker is single-agent).

`physis` skeleton wired to organism config, default-enabled,
gitignore policy enforced via existing `creatures/*/memory/` rule.

Phase 2 Verse-on-Avalon mirror: noted, queued. Won't act on it
until your Co-MVP lands.

— Ray
