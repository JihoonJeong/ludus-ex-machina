# MUD — World & Scenario Design Guide

How to author a MUD world/scenario, and *why*. MUD is a **language world-model
field**: each zone is a solo, fully-deterministic puzzle world, and the point of
a zone is to **stress a specific world-model capability** — not to tell a story.
Scoring falls out of the goal (solved / turns); the value is the capability it
probes.

**The Astronomer's Tower (`astronomer_tower`) is the reference zone / PoC.** It
proved the whole vertical slice end-to-end — engine → WM-eval → viewer → live API
→ real creature play — and hardened the field (item-name strictness → `_norm`;
board jitter → definite height; contract refinements). Keep it as zone #1 of the
library; new worlds generalize from it.

Direction: **single-player solo campaign** — a *library* of authored zones (and,
later, an optional *linked progression* for a long-horizon-memory axis).
Multiplayer shared-world is deferred (`max_players=4` scaffolding kept, not the
focus).

---

## Where MUD lives — directory map (READ THIS FIRST)

MUD spans several locations, each a **distinct role**. `games/mud/` (logic + data)
and `assets/mud/` (room art) are different things — don't conflate them.

| Path | Role | Contains |
|---|---|---|
| `games/mud/engine.py` | **Engine** (code) — theme-agnostic verb interpreter | verbs, resolve/no-op, semantic-state contract |
| `games/mud/zones.py` | **World DATA** — every zone is a dict in `ZONES` | rooms/objects/locks/interactions/npcs/goal |
| `games/mud/DESIGN.md` | **This doc** — authoring guide + roadmap | schema, WM axes, art workflow |
| `games/mud/rules.md` | **Player-facing rules** (shown to the agent) | verb list, how a turn works |
| `games/mud/art_prompts.md` | **Art prompts** per world | style spec + per-room prompts |
| `viewer/static/renderers/mud.js` | **Renderer** (code) — draws any zone | room panel + world-model map |
| `viewer/static/assets/mud/<scenario>/` | **Room ART — SOURCE** | `<room>.png` (local) + `<room>.webp` (committed) |
| `docs/viewer/assets/mud/<scenario>/` | **Room ART — DEPLOY MIRROR** (GitHub Pages) | `<room>.webp` only |
| `lxm/wm_predict.py`, `scripts/mud_wm_eval.py` | **WM eval** (code) | predict-before-act scoring |

Naming: `mud` = the field/game; `<scenario_id>` (e.g. `astronomer_tower`,
`grimhold_keep`) = one world. The **same `<scenario_id>` string** keys the zone
dict, the art dir, and the `--scenario` / `config.scenario_id` argument — keep
them identical or the renderer can't find the art.

### Asset rules (avoid the two-tree tangle)

- **Two trees, mirrored.** `viewer/static/assets/…` is the source you edit;
  `docs/viewer/assets/…` is the deploy copy for GitHub Pages. The renderer loads
  a **relative** path `assets/mud/<scenario>/<room>.webp`, so it resolves against
  whichever tree is being served. **Always update both** (copy webp static→docs).
- **Commit `.webp` only.** Source `.png` (from image-gen, ~2.5 MB each) is
  git-ignored via the single `assets/mud/.gitignore` (also ignores `.DS_Store`).
  Per-zone `.gitignore` files are NOT used — one rule at the `assets/mud/` level
  covers every scenario.
- **One dir per scenario:** `assets/mud/<scenario_id>/`, room files named exactly
  `<room_id>.webp`. Missing art → renderer falls back to a 16-bit gradient (art
  is optional/incremental).

---

## The stack a zone plugs into (all automatic — no code to add a world)

The engine (`engine.py`) is a **theme-agnostic generic verb interpreter**; a zone
is pure data. Add one entry to `ZONES` in `zones.py` and it is picked up by:

- **Local run** — `python scripts/run_match.py --game mud --scenario <id> --agents a --adapter claude ...`
- **Live API / cross-machine plane** — `POST /api/matches {game:"mud", config:{scenario_id:"<id>"}, participants:[{id,kind:"remote"}]}` (Ludex creatures attach here; solo `min_players:1`)
- **Viewer** — `viewer/static/renderers/mud.js` renders any zone from `post_move_state`
- **WM eval** — `lxm/wm_predict.py` (predict-before-act) + `canonicalize_mud` score any zone's contract-v1 semantic state
- **Room art** — drop `assets/mud/<scenario_id>/<room_id>.webp` (gradient fallback if absent)

---

## Zone authoring schema (`games/mud/zones.py`)

A zone is a dict, registered as `ZONES["<scenario_id>"]`.

```
scenario_id : str          # unique id, matches the art dir + --scenario
title       : str          # display name
goal        : str          # one-line goal shown to the agent
goal_object : oid          # taking THIS object into inventory wins
start_room  : rid
turn_limit  : int          # ~2-3x the optimal solve path

rooms   : { rid: { name, desc, exits: { dir: { to: rid, lock?: lid } } } }
          # dir ∈ north/south/east/west/up/down/in/out
objects : { oid: { name,               # human display ('Saturn-ring'); id stays snake_case
                   loc,                 # "room:<rid>" | "inv:<aid>" | "in:<cid>" | null(consumed/unplaced)
                   takeable: bool,
                   visible: bool,       # false = hidden until a search/interaction reveals it
                   examine?: str,       # examine text (put HINTS here)
                   read?: str,          # read text
                   state?: {..},        # mutable per-object facts (scored in WM eval)
                   container?, open?, locked?, key?: oid,   # for containers
                   searchable?: bool } }
locks   : { lid: { locked: bool, key: oid } }
interactions : { (item_oid, target_oid): { set_flags?: {..}, object_state?: {oid:{..}},
                                           reveal?: [oid], consume?: oid, event: str } }
search  : { target_oid: { reveal: [oid], event: str } }
npcs    : { nid: { name, loc: rid, talk: str,
                  give?: { item_oid: { event, set_flags? } } } }
```

Verbs (fixed, in `engine.py`): `go look examine read take drop open close unlock
use talk give search wait`. Invalid/blocked → **no-op** (world unchanged).

---

## Design principles (from the Tower + the Lyra run)

- **Deterministic transitions.** Every (state, action) has one exact next state.
  No RNG in state — this is what makes it a world-model testbed.
- **No-op fidelity.** Blocked/invalid actions leave the world unchanged; the
  headline WM failure mode is a model that hallucinates an effect on a no-op.
- **Forgiving references, honest feedback.** `_resolve_object`/`_resolve_npc`
  normalize case + separators (`_norm`): ids are snake_case, names are human, and
  `saturn ring`/`Saturn-ring`/`saturn_ring` all resolve. On a recognized-but-wrong
  `use` target, say "X has no effect on Y" (not "Nothing happens") so a wrong
  **target** never reads as a wrong **name** (Lyra's dead-end).
- **Hints require inference.** Put clues in `examine`/`read`/`talk` that need a
  step of reasoning (the star-chart's "the ring completes the dance" → the orrery
  = clockwork heavens). Don't spell out the exact object.
- **Symbolic/relational state only.** Object location, container open/locked, lock
  state, hidden-until-searched, flags — the linguistic-WM contrast to Blockworld's
  spatial/voxel state.

---

## What each new zone should test — WM axes

Aim each zone at a **distinct** capability so the suite grows benchmark coverage,
not just content. The Tower already covers *fog exploration + a linear dependency
chain + hint inference*. Open axes:

| Axis | What it probes | Zone hook |
|---|---|---|
| **Deep dependency chain** | long-horizon causal tracking | 6-8 gated steps (A reveals B unlocks C …) |
| **Distractors / relevance** | tracking only what matters (Lyra's globe fixation) | many useless objects among the few that matter |
| **Mutable / reversible state** | dynamic, non-monotonic state (not just reveal) | valves/levers/flooding that toggle; goal needs a *configuration* |
| **Other-entity (NPC) state** | modeling another agent's state | NPCs that move/change based on your actions |
| **Large-map navigation** | spatial+relational memory under exploration | 10+ rooms, revisits, a map-assembly goal |
| **Long-horizon (campaign)** | maintaining a world model across a long arc | linked zones carrying inventory/state (progression mode) |

---

## Scoring / eval

- **Play mode** — `solved` (goal_object in inventory) + `turns` used. That's the
  match result (viewer + leaderboard + creature benchmark).
- **WM-eval mode** — `scripts/mud_wm_eval.py`: score a brain's next-state
  *prediction* per (state, action) via `wm_predict` + `canonicalize_mud`
  (identity-based, prose-insensitive), no-op fidelity weighted. Never fed back
  into play. Distinct from play scoring; both run on the same zone.

---

## Roadmap (proposed worlds — one per open axis)

Genre worlds (typical, crowd-pleasing) — one per WM axis:

- ✅ `astronomer_tower` — fantasy-ish tower; *fog + linear dependency + hints* (PoC).
- ✅ `grimhold_keep` — fantasy dungeon-quest; *deep dependency chain*.
- ✅ `ss_erebus` — sci-fi derelict ship; *mutable/reversible state* (coolant→reactor
  →power ordering via interaction `requires` gate).
- ✅ `critter_cove` — collection island; *relevance* (right bait→right critter) +
  *collect-set goal*. Added the multi-collect win-condition (`goal_objects` set:
  win when ALL held; per-pickup `[n/N collected]` cue).
- *(later)* large-map navigation world; and/or link worlds into a progression for
  the *long-horizon* axis.

Four worlds shipped across three genres (fantasy ×2, sci-fi, collection). Win
conditions: single `goal_object`, OR a `goal_objects` SET (collect-style).

## Art workflow

Per `games/mud/art_prompts.md`: one webp per room at
`assets/mud/<scenario_id>/<room_id>.webp`, shared 16-bit style spec for
cross-room cohesion, dark-gradient overlay for legibility, gradient fallback when
absent. Cody writes prompts → JJ generates → optimize to webp (1280px, q85) →
commit webp (source PNGs git-ignored).
