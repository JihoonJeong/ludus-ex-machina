# Blockworld Action Schema (world-model contract v1)

Stable action contract for the Blockworld world-model integration. Both sides
(LxM engine, Ludex creature) rely on this. Authoritative source:
`games/blockworld/engine.py` (`VALID_VERBS`, `validate_move`, `apply_move`) +
`games/blockworld/world.py` (`DIRECTIONS`, `BLOCK_TYPES`). Bump the version on
any change.

## Envelope

```json
{"type": "action", "verb": "<verb>", ...verb-specific fields...}
```

- `type` — MUST be `"action"`.
- `verb` — one of the 10 verbs below.
- Optional on ANY verb:
  - `message`: string — free-text utterance (echoed as an event).
  - `intent`: string — sandbox-mode intent capture (stored in `context.intent_log`).

## Directions

`DIRECTIONS = {north, south, east, west, up, down}` with deltas
north=(0,−1,0) south=(0,+1,0) east=(+1,0,0) west=(−1,0,0) up=(0,0,+1) down=(0,0,−1).

## Verbs

| verb | required | optional | effect | no-op when |
|------|----------|----------|--------|-----------|
| `move` | `direction` | `message` | agent moves 1 cell in `direction` | target blocked / out of bounds |
| `break` | `direction` | `message` | target cell → air; `inventory += DROP_ON_BREAK[block]` | target air / unbreakable (water) / inventory full |
| `place` | `direction`, `block` | `message` | target cell ← `block` (placed=true); `inventory[block] -= 1` | block not in inventory / target not air |
| `pick` | — | `message` | ground item at agent cell → `inventory` | no item at cell / inventory full |
| `drop` | `item` | `message` | `inventory[item] -= 1` → ground item at agent cell | item not in inventory |
| `craft` | `recipe` | `message` | consume inputs, add outputs per recipe | inputs insufficient |
| `interact` | `direction` (`up`/`down`) | `message` | ladder vertical traversal (MVP) | not a ladder / no ladder |
| `look` | — | `message` | wider view (radius 10); no state change | — |
| `say` | `message` (string) | — | utterance event; no state change | — |
| `wait` | — | `message` | no-op turn | — |

**Authority rule (for world-model prediction):** invalid actions and blocked
preconditions resolve to a **no-op** (state unchanged except turn advance). The
engine `validate_move` rejects malformed moves before `apply_move`; preconditions
(wall, empty hand, full inventory) yield no effect inside `apply_move`. A correct
world model predicts unchanged state for these.

## Placeable blocks (`place`)

Any `BLOCK_TYPES` name except `air`:
`stone, dirt, grass, wood, water, sand, iron_ore, glass, ladder, planks, stone_brick`.

## Break drops

`DROP_ON_BREAK`: stone→stone, dirt→dirt, **grass→dirt**, wood→wood, sand→sand,
iron_ore→iron_ore, glass→glass, ladder→ladder, planks→planks,
stone_brick→stone_brick. `air`/`water` → nothing (water is unbreakable).

## Craft recipes

`recipe` ids come from `games/blockworld/recipes.py` (`recipe_ids()`); each maps
declared inputs (inventory item counts) → outputs. Query the live list rather
than hard-coding.

## Notes for the predict-before-act hook

- One verb = one turn. After apply, `current.turn += 1`, `active_index` rotates,
  `current.last_events` holds this turn's event strings.
- `say_attached_only` scenarios (e.g. some pure_coord) disable the standalone
  `say` verb — attach `message` to a `move`/`look`/`wait` instead.
- Inventory cap = `INVENTORY_CAP` (20). Picks/breaks that would exceed it no-op.

— v1, 2026-06-28 (paired with `build_semantic_state` contract_version 1)
