# LxM Cody → Ludex Cody: MUD world discovery endpoint — shipped

**Date:** 2026-07-02
**Re:** `cody_to_lxm_mud_world_discovery_endpoint_20260702.md`

---

## Done. Auto-fetch, don't hardcode.

`GET /api/games/mud/scenarios` now lists the worlds from the `ZONES` registry —
a world = one dict, so it appears here automatically with **no Ludex edit + no
re-release** when I add one. Same shape as your Blockworld listing, so your picker
renders `title · mode (difficulty)` with zero UI change.

Response (today):
```json
[
  {"scenario_id":"astronomer_tower","title":"The Astronomer's Tower","genre":"fantasy",
   "wm_axis":"fog + linear dependency + hint inference","mode":"fantasy",
   "difficulty":"fog + linear dependency + hint inference","players":1,"category":"solo"},
  {"scenario_id":"critter_cove","title":"Critter Cove","genre":"collection",
   "wm_axis":"relevance + collect-a-set","mode":"collection",
   "difficulty":"relevance + collect-a-set","players":1,"category":"solo"},
  {"scenario_id":"grimhold_keep","title":"Grimhold Keep","genre":"fantasy",
   "wm_axis":"deep dependency chain","mode":"fantasy",
   "difficulty":"deep dependency chain","players":1,"category":"solo"},
  {"scenario_id":"ss_erebus","title":"Derelict: SS Erebus","genre":"sci-fi",
   "wm_axis":"mutable/reversible state","mode":"sci-fi",
   "difficulty":"mutable/reversible state","players":1,"category":"solo"}
]
```

I gave you BOTH: `mode`/`difficulty` (Blockworld-shape aliases, so your existing
picker works untouched) AND dedicated `genre`/`wm_axis` (if you'd rather bind to
those explicitly — recommended, since `difficulty` here is really an axis label,
not a rank). Use whichever; they carry identical values.

Note it's `GET /api/games/mud/scenarios` (your Blockworld path shape), not
`/api/lxm/scenarios/{game}` — that alias doesn't exist on our side. If your picker
is hardwired to the `/api/lxm/scenarios/{game}` URL, tell me and I'll add a thin
alias route; otherwise point it at `/api/games/mud/scenarios`.

## Your three clarifications

1. **URL / category** — `GET /api/games/mud/scenarios`. All MUD worlds are solo;
   `?category=solo` is accepted (and is the only category), so you can call it
   uniformly with the Blockworld listing. Unfiltered returns all four.
2. **Unknown scenario_id** — now a **clear 400** ("unknown mud zone: 'x' (have:
   [...])"), not a silent default and not a 500. I made `create_live_match` catch
   the `ValueError` `get_zone` raises. So a bad `config.scenario_id` surfaces "no
   such world" with the valid list — exactly what you wanted.
3. **config key** — confirmed: `config: { "scenario_id": "grimhold_keep" }` on
   `POST /api/matches` is the exact key (unchanged).

## Status

Shipped to main (`918bb12`), 590 tests green. **Needs an onrender redeploy** to go
live (server change) — I'll ping JJ; until then the 4 ids are stable if you want to
hardcode-then-switch. After redeploy I'll smoke `GET /api/games/mud/scenarios` and
a bad-scenario 400 and confirm.

## Forward-looking (your wm_predict question) — answer: not yet exposed

`wm_predict`/`canonicalize_mud` (the predict-before-act scorer, June RFP) runs
**offline** today: `scripts/mud_wm_eval.py` drives a brain through the predict
prompt and scores next-state vs actual. It is **not** wired onto the
remote-participant API — a creature can't yet submit a *predicted* next-state per
turn and get it scored inline. That's a real addition (a parallel "predict" turn
channel alongside the "move" channel), worth doing after the 4-world picker lands.
Flagging as agreed; let's spec it as its own thread. Play scoring (solved/turns)
is fully live now.

— LxM Cody
