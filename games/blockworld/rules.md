# Blockworld — Rules

A MUD-style text-based Minecraft for AI agents. You inhabit a 2.5D layered voxel world, gather materials, and build structures to complete scenario objectives.

---

## World

The world is divided into layers (z=0 bottom, higher z = up). Each layer is a 2D grid of cells. Each cell contains exactly one block type:

| ID | Name | Breakable by hand | Notes |
|---|---|---|---|
| 0 | air | (nothing to break) | you can walk through |
| 1 | stone | hard (3 turns if no tool) | durable wall material |
| 2 | dirt | easy (1 turn) | weak but abundant |
| 3 | grass | easy (1 turn) | gives dirt when broken |
| 4 | wood | easy (1 turn) | from trees, fast to build with |
| 5 | water | (can't break) | passable (slows movement) |
| 6 | sand | easy (1 turn) | weak; may collapse near edges |
| 7 | iron_ore | hard (3 turns if no tool) | for advanced recipes |
| 8 | glass | medium (2 turns) | transparent, placed material |

Natural terrain: stone, dirt, grass, water, sand, iron_ore appear in the generated world. Wood is found in **trees** (pillars of wood blocks). Glass must be crafted.

---

## Agent

- Position: (x, y, z), facing one of {north, south, east, west}.
- Inventory: max 20 items total. Each block type is a stackable item.
- Movement: one cell per turn, in any cardinal direction. `up`/`down` moves to an adjacent layer **only if** a ladder-like path exists (step-up: block adjacent at your level, open air at head level; step-down: mirror).

---

## Actions

Each turn, output exactly one JSON action object.

| Verb | Required fields | Effect |
|---|---|---|
| `move` | `direction` | Move one cell in that direction. |
| `break` | `direction` | Break the block adjacent in that direction. Item goes to inventory. Break time (1/2/3 turns) depends on block hardness and tool. |
| `place` | `direction`, `block` | Consume one of `block` from inventory and place it in the adjacent cell. Target must be `air`. |
| `craft` | `recipe` | Consume inventory per recipe; produce output. (See recipes below.) |
| `pick` | *(none)* | Pick up any item lying at your current cell. |
| `drop` | `item` | Drop one from inventory onto your current cell. |
| `look` | *(none)* | Get a wider view (radius 10 instead of default 5). Costs one turn. |
| `say` | `message` | Broadcast to agents on the same layer within radius 8. Does not advance game state. |
| `wait` | *(none)* | Do nothing for this turn. |

### Recipes (minimal MVP)

- `glass_pane`: 2 sand + 1 wood (for fuel) → 1 glass

(More recipes may be added per scenario.)

---

## Turn flow

1. Read your prompt (local view, inventory, status, goal, recent actions).
2. Decide one action.
3. Emit JSON envelope ending in e.g. `{"verb":"move","direction":"north"}`.
4. Engine resolves, world updates, next turn begins.

Multi-agent scenarios: turns rotate by seat order, one agent per turn.

---

## Placed vs. natural blocks

Each cell carries a **placed** flag. A block placed by an agent is marked placed=true; natural terrain is placed=false.

Scenarios that check "built structures" count only placed=true blocks (so you cannot cheat by standing in a natural cave and claiming it as a shelter).

---

## Scenarios

Each scenario declares:
- Initial world layout (from seed)
- Turn limit
- Victory condition
- Evaluation breakdown

See `games/blockworld/scenarios/<id>/scenario.json` for the specification of each scenario.
