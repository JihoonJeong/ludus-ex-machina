"""Blockworld — world generation, manipulation, rendering.

2.5D layered voxel world. Each cell carries a block-type int AND a
`placed` bit distinguishing agent-placed blocks from natural terrain
(scenario evaluations — e.g. the shelter validity check — require
structures built from placed blocks only).

The world dict is serializable as JSON; all fields use plain ints/lists
so it can travel through LxM's envelope / log / state plumbing without
extra schema.
"""

from __future__ import annotations

import random
from typing import Any

# Block type name <-> id. IDs are stable; renaming would require a
# scenario migration so keep them locked once used.
BLOCK_TYPES = {
    0: "air",
    1: "stone",
    2: "dirt",
    3: "grass",
    4: "wood",
    5: "water",
    6: "sand",
    7: "iron_ore",
    8: "glass",
    # Gen 3 (open-world) additions:
    9: "ladder",
}
BLOCK_IDS = {name: id_ for id_, name in BLOCK_TYPES.items()}

AIR = 0

# Break hardness (turns to break by hand). None = unbreakable.
HARDNESS = {
    "air": 0, "stone": 3, "dirt": 1, "grass": 1, "wood": 1,
    "water": None, "sand": 1, "iron_ore": 3, "glass": 2,
    "ladder": 1,
}

# What breaking a natural block gives you in inventory. None = nothing.
DROP_ON_BREAK = {
    "air": None, "stone": "stone", "dirt": "dirt", "grass": "dirt",
    "wood": "wood", "water": None, "sand": "sand",
    "iron_ore": "iron_ore", "glass": "glass",
    "ladder": "ladder",
}

# Blocks that an agent can move *through* (treated like air for traversal
# even though they're solid for terrain purposes). Currently just ladders.
PASSABLE = {"air", "ladder"}

DIRECTIONS = {
    "north": (0, -1, 0),
    "south": (0, 1, 0),
    "east":  (1, 0, 0),
    "west":  (-1, 0, 0),
    "up":    (0, 0, 1),
    "down":  (0, 0, -1),
}


# ── generation ────────────────────────────────────────────────────────────

def generate_world(
    dimensions: dict,
    seed: int,
    terrain_profile: str = "shelter_default",
) -> dict:
    """Create a starting world. Deterministic given seed.

    Profiles encode the kind of starting terrain:
    - "shelter_default": open grass field, tree cluster in SW, stone in NE.
    - (future profiles here as scenarios expand.)
    """
    dx, dy, dz = dimensions["x"], dimensions["y"], dimensions["z"]
    rng = random.Random(seed)

    # Allocate: layers[z][y][x] = block_id; placed[z][y][x] = 0/1.
    layers = [[[AIR for _ in range(dx)] for _ in range(dy)] for _ in range(dz)]
    placed = [[[0 for _ in range(dx)] for _ in range(dy)] for _ in range(dz)]

    if terrain_profile == "shelter_default":
        _gen_shelter_default(layers, placed, dx, dy, dz, rng)
    elif terrain_profile == "open_default":
        _gen_open_default(layers, placed, dx, dy, dz, rng)
    else:
        raise ValueError(f"unknown terrain_profile: {terrain_profile}")

    return {
        "dimensions": dimensions,
        "layers": layers,
        "placed": placed,
        "seed": seed,
        "terrain_profile": terrain_profile,
    }


def _gen_shelter_default(layers, placed, dx, dy, dz, rng: random.Random):
    """Layer 0: grass floor, tree cluster SW, stone outcrop NE, dirt rim."""
    grass = BLOCK_IDS["grass"]
    dirt = BLOCK_IDS["dirt"]
    stone = BLOCK_IDS["stone"]
    wood = BLOCK_IDS["wood"]

    # Layer 0: grass field, dirt rim on edges.
    for y in range(dy):
        for x in range(dx):
            edge = (x < 2 or x >= dx - 2 or y < 2 or y >= dy - 2)
            layers[0][y][x] = dirt if edge else grass

    # Tree cluster in SW corner (x: 2-7, y: dy-8..dy-3). Each tree = wood pillar,
    # 2-3 blocks tall. Trees are vertical wood columns above the grass cell.
    # We represent the ground cell as wood (so breaking it gives wood) AND
    # put wood on layers 1 and 2 above selected cells.
    tree_positions = []
    for _ in range(8):
        tx = rng.randint(2, 7)
        ty = rng.randint(dy - 8, dy - 3)
        if (tx, ty) not in tree_positions:
            tree_positions.append((tx, ty))
    for (tx, ty) in tree_positions:
        layers[0][ty][tx] = wood
        if dz > 1:
            layers[1][ty][tx] = wood
        if dz > 2 and rng.random() < 0.6:
            layers[2][ty][tx] = wood

    # Stone outcrop in NE corner (x: dx-8..dx-3, y: 2-7). A single patch of
    # stone blocks on layer 0. About 12-16 stone cells.
    stone_positions = set()
    cx, cy = dx - 5, 4
    stone_positions.add((cx, cy))
    for _ in range(40):
        # Grow cluster by random walk.
        px, py = rng.choice(list(stone_positions))
        nx, ny = px + rng.randint(-1, 1), py + rng.randint(-1, 1)
        if (dx - 8 <= nx <= dx - 3) and (2 <= ny <= 7):
            stone_positions.add((nx, ny))
        if len(stone_positions) >= 14:
            break
    for (sx, sy) in stone_positions:
        layers[0][sy][sx] = stone

    # Layers above are air (already initialized).


def _gen_open_default(layers, placed, dx, dy, dz, rng: random.Random):
    """Open-world terrain for Gen 3: 64×64×4 sized. Layer 0 is the
    surface, layer 1 is mid-air (mostly), layer 2 is upper-air, layer 3
    is sky. Surface features:

      - Grass field with a dirt rim (2-cell wide along edges).
      - Multiple small tree clusters scattered across the map.
      - Two stone outcrops (one NE + one rocky hill that climbs into z=1).
      - Sand patches near water.
      - One small lake of water on the surface.
      - A few iron-ore deposits embedded in stone.

    Designed to give a creature a 200-turn budget enough room to walk
    a few minutes between landmarks without running out of world.
    """
    grass = BLOCK_IDS["grass"]
    dirt = BLOCK_IDS["dirt"]
    stone = BLOCK_IDS["stone"]
    wood = BLOCK_IDS["wood"]
    water = BLOCK_IDS["water"]
    sand = BLOCK_IDS["sand"]
    iron = BLOCK_IDS["iron_ore"]

    # Layer 0 base: grass everywhere, dirt rim.
    for y in range(dy):
        for x in range(dx):
            edge = (x < 2 or x >= dx - 2 or y < 2 or y >= dy - 2)
            layers[0][y][x] = dirt if edge else grass

    # Lake near center-south. ~6×4 oval of water, rimmed with sand.
    lake_cx, lake_cy = dx // 2 + 4, dy // 2 + 8
    for dy_ in range(-3, 4):
        for dx_ in range(-4, 5):
            x, y = lake_cx + dx_, lake_cy + dy_
            if not (0 <= x < dx and 0 <= y < dy):
                continue
            d2 = (dx_ / 4.5) ** 2 + (dy_ / 3.5) ** 2
            if d2 < 0.7:
                layers[0][y][x] = water
            elif d2 < 1.05:
                layers[0][y][x] = sand

    # Tree clusters — 4 clusters of 5-9 trees each at varied locations.
    cluster_centers = [
        (dx // 4, dy // 4),
        (dx * 3 // 4, dy // 5),
        (dx // 5, dy * 3 // 4),
        (dx // 2 - 6, dy // 2 - 4),
    ]
    for (cx, cy) in cluster_centers:
        n_trees = rng.randint(5, 9)
        positions = set()
        while len(positions) < n_trees:
            tx = cx + rng.randint(-4, 4)
            ty = cy + rng.randint(-4, 4)
            if 2 <= tx < dx - 2 and 2 <= ty < dy - 2:
                # Don't put trees in lake.
                if layers[0][ty][tx] in (water, sand):
                    continue
                positions.add((tx, ty))
        for (tx, ty) in positions:
            layers[0][ty][tx] = wood
            if dz > 1:
                layers[1][ty][tx] = wood
            if dz > 2 and rng.random() < 0.7:
                layers[2][ty][tx] = wood

    # Big stone outcrop / hill in NE — climbs into z=1 for a few cells,
    # so the agent has a reason to use ladders (or break a path).
    hill_cx, hill_cy = dx - 8, 8
    hill_positions = {(hill_cx, hill_cy)}
    for _ in range(80):
        px, py = rng.choice(list(hill_positions))
        nx, ny = px + rng.randint(-1, 1), py + rng.randint(-1, 1)
        if (dx - 14 <= nx <= dx - 4) and (3 <= ny <= 14):
            hill_positions.add((nx, ny))
        if len(hill_positions) >= 28:
            break
    for (sx, sy) in hill_positions:
        layers[0][sy][sx] = stone
    # Hill peak — a few stone blocks raised on z=1.
    peak_positions = list(hill_positions)
    rng.shuffle(peak_positions)
    if dz > 1:
        for (sx, sy) in peak_positions[:6]:
            layers[1][sy][sx] = stone

    # Iron-ore deposits — sprinkle 4-6 ore cells inside stone clusters.
    stone_cells = [(sx, sy) for (sx, sy) in hill_positions]
    rng.shuffle(stone_cells)
    for (sx, sy) in stone_cells[:5]:
        layers[0][sy][sx] = iron

    # Small secondary stone patch SW — gives an agent two distinct
    # mining sites if they choose to build.
    patch_cx, patch_cy = 6, dy - 10
    for dy_ in range(-2, 3):
        for dx_ in range(-2, 3):
            x, y = patch_cx + dx_, patch_cy + dy_
            if not (0 <= x < dx and 0 <= y < dy):
                continue
            if rng.random() < 0.55 and layers[0][y][x] == grass:
                layers[0][y][x] = stone


# ── access helpers ────────────────────────────────────────────────────────

def in_bounds(world: dict, x: int, y: int, z: int) -> bool:
    d = world["dimensions"]
    return 0 <= x < d["x"] and 0 <= y < d["y"] and 0 <= z < d["z"]


def get_block(world: dict, x: int, y: int, z: int) -> str:
    """Return block type name. Out-of-bounds returns 'air' (treated as open)."""
    if not in_bounds(world, x, y, z):
        return "air"
    return BLOCK_TYPES[world["layers"][z][y][x]]


def get_block_id(world: dict, x: int, y: int, z: int) -> int:
    if not in_bounds(world, x, y, z):
        return AIR
    return world["layers"][z][y][x]


def is_placed(world: dict, x: int, y: int, z: int) -> bool:
    if not in_bounds(world, x, y, z):
        return False
    return bool(world["placed"][z][y][x])


def set_block(world: dict, x: int, y: int, z: int, block: str, placed_by_agent: bool):
    """Mutate world in place."""
    if not in_bounds(world, x, y, z):
        raise ValueError(f"out of bounds: ({x},{y},{z})")
    world["layers"][z][y][x] = BLOCK_IDS[block]
    world["placed"][z][y][x] = 1 if placed_by_agent else 0


# ── rendering ─────────────────────────────────────────────────────────────

# One-char tile glyphs for ASCII dump.
GLYPHS = {
    "air": ".",
    "stone": "#",
    "dirt": ",",
    "grass": "\"",
    "wood": "T",
    "water": "~",
    "sand": ":",
    "iron_ore": "I",
    "glass": "G",
    "ladder": "H",
}


def render_local_view(
    world: dict,
    center: dict,
    radius: int = 5,
    others: list[dict] | None = None,
) -> str:
    """Return multi-line ASCII view around (cx, cy, cz).

    Always shows agent's layer (where movement happens). Additionally
    shows the ground layer beneath when the agent is standing in air
    above solid ground — that's where terrain features (trees, stone
    outcrops, dirt) live, and is essential for navigation.

    `others` (optional) is a list of {agent_id, x, y, z} entries for
    other agents in the world. Each is drawn as its first-letter
    uppercase glyph (overriding the terrain block) when visible within
    radius on the relevant layer.
    """
    cx, cy, cz = center["x"], center["y"], center["z"]
    lines = []

    def _other_glyph_at(x: int, y: int, z: int) -> str | None:
        if not others:
            return None
        for o in others:
            if o["x"] == x and o["y"] == y and o["z"] == z:
                aid = o.get("agent_id", "?")
                return (aid[:1] or "?").upper()
        return None

    # Agent's layer (where your body is).
    lines.append(f"Layer {cz} (your layer — what you can walk through):")
    lines.append("     N")
    for dy in range(-radius, radius + 1):
        row = []
        for dx in range(-radius, radius + 1):
            x, y = cx + dx, cy + dy
            if dx == 0 and dy == 0:
                row.append("@")
            elif (og := _other_glyph_at(x, y, cz)) is not None:
                row.append(og)
            else:
                row.append(GLYPHS.get(get_block(world, x, y, cz), "?"))
        lines.append("   " + " ".join(row))
    lines.append("     S")

    # Ground layer (z-1) if agent is in air above something solid — this is
    # where terrain landmarks live (trees, stone, dirt, water).
    if cz > 0 and get_block(world, cx, cy, cz) == "air":
        lines.append("")
        lines.append(f"Layer {cz-1} (ground beneath — terrain / landmarks):")
        lines.append("     N")
        for dy in range(-radius, radius + 1):
            row = []
            for dx in range(-radius, radius + 1):
                x, y = cx + dx, cy + dy
                if dx == 0 and dy == 0:
                    row.append("*")  # directly below you
                elif (og := _other_glyph_at(x, y, cz - 1)) is not None:
                    row.append(og)
                else:
                    row.append(GLYPHS.get(get_block(world, x, y, cz - 1), "?"))
            lines.append("   " + " ".join(row))
        lines.append("     S")

    lines.append("(@ = you  * = below-you  uppercase = other agent  # stone  T wood  , dirt  \" grass  . air  ~ water  : sand  I iron_ore  G glass  H ladder)")

    # Vertical context at your exact column.
    above = get_block(world, cx, cy, cz + 1)
    below = get_block(world, cx, cy, cz - 1) if cz > 0 else "(world bottom)"
    lines.append(f"Above you (layer {cz+1}): {above}   Below you (layer {cz-1}): {below}")
    return "\n".join(lines)


# ── shelter validity check (scenario logic; lives here for reuse) ────────

def _enclosed_air_cells(world: dict, start: tuple[int, int, int], cap: int = 400):
    """BFS through air cells starting at `start`, bounded by non-air walls.

    World edges: z<0 is bedrock (sealed). z≥max, x/y out-of-bounds are
    open (sky + horizontal). A pit-dweller shelter — dig down 1 cell, wall
    sides, roof above — is therefore valid.

    Returns a set of (x,y,z) air cells inside the enclosure, OR None if the
    enclosure is open to the world edge (which means "not enclosed").
    """
    d = world["dimensions"]
    if get_block(world, *start) != "air":
        return None
    seen: set[tuple[int, int, int]] = {start}
    frontier = [start]
    while frontier:
        if len(seen) > cap:
            return None
        x, y, z = frontier.pop()
        for dx, dy, dz in DIRECTIONS.values():
            nx, ny, nz = x + dx, y + dy, z + dz
            if nz < 0:
                # Below-world is sealed bedrock: this direction is a wall.
                continue
            if not in_bounds(world, nx, ny, nz):
                # Reached sky (z≥max) or horizontal edge through air: open.
                return None
            if get_block(world, nx, ny, nz) == "air" and (nx, ny, nz) not in seen:
                seen.add((nx, ny, nz))
                frontier.append((nx, ny, nz))
    return seen


def check_valid_shelter(
    world: dict,
    agent_pos: dict,
    min_floor: int = 9,
    strict_placed: bool = True,
    min_placed_boundary: int | None = None,
) -> dict:
    """Shelter validity check with two modes.

    Always required:
      (1) Agent stands in an enclosed air volume (sealed by blocks, not
          open to world edge).
      (2) Every boundary cell is non-air (no gaps).
      (3) Lowest z-layer of volume has ≥ `min_floor` floor cells beneath.

    Mode A — **strict placed** (default, scenario shelter_01):
      (4a) Every boundary cell is placed=True. No natural terrain allowed
           anywhere on the shelter's boundary. Tight budget hurts.

    Mode B — **count-based placed** (scenario shelter_02 and variants):
      (4b) At least `min_placed_boundary` cells of the boundary are
           placed=True. Natural cover allowed for the rest. Creature can
           build onto existing trees / outcrops as structural cover.

    Returns: {"valid": bool, "reason": str, "volume": int,
              "floor_area": int, "boundary_total": int,
              "boundary_placed": int}.
    """
    start = (agent_pos["x"], agent_pos["y"], agent_pos["z"])
    volume = _enclosed_air_cells(world, start)
    if volume is None:
        return {
            "valid": False,
            "reason": "not enclosed (open to world edge or agent not in air)",
            "volume": 0, "floor_area": 0,
            "boundary_total": 0, "boundary_placed": 0,
        }

    # Boundary = all 6-neighbors of volume cells not themselves in volume.
    # Bedrock (z<0) cells are implicit walls — skip, don't require a block.
    boundary: set[tuple[int, int, int]] = set()
    for (x, y, z) in volume:
        for dx, dy, dz in DIRECTIONS.values():
            nx, ny, nz = x + dx, y + dy, z + dz
            if nz < 0:
                continue
            if (nx, ny, nz) not in volume:
                boundary.add((nx, ny, nz))

    # No gap allowed in either mode.
    for (x, y, z) in boundary:
        if not in_bounds(world, x, y, z):
            return {
                "valid": False,
                "reason": f"boundary extends out of world at ({x},{y},{z})",
                "volume": len(volume), "floor_area": 0,
                "boundary_total": len(boundary), "boundary_placed": 0,
            }
        if get_block(world, x, y, z) == "air":
            return {
                "valid": False,
                "reason": f"boundary open at ({x},{y},{z})",
                "volume": len(volume), "floor_area": 0,
                "boundary_total": len(boundary), "boundary_placed": 0,
            }

    boundary_placed = sum(1 for (x, y, z) in boundary if is_placed(world, x, y, z))

    # Mode-specific check on placed-ness.
    if strict_placed:
        for (x, y, z) in boundary:
            if not is_placed(world, x, y, z):
                return {
                    "valid": False,
                    "reason": f"strict mode: uses natural terrain at ({x},{y},{z})",
                    "volume": len(volume), "floor_area": 0,
                    "boundary_total": len(boundary), "boundary_placed": boundary_placed,
                }
    else:
        threshold = min_placed_boundary or 0
        if boundary_placed < threshold:
            return {
                "valid": False,
                "reason": f"placed-boundary count {boundary_placed} < {threshold}",
                "volume": len(volume), "floor_area": 0,
                "boundary_total": len(boundary), "boundary_placed": boundary_placed,
            }

    # Floor area: cells one layer below the lowest volume layer.
    # When min_z == 0, bedrock is the implicit floor (1 cell per volume
    # footprint at the bottom layer).
    min_z = min(z for (_, _, z) in volume)
    if min_z == 0:
        floor_cells = [(x, y, z) for (x, y, z) in volume if z == 0]
    else:
        floor_cells = [(x, y, z) for (x, y, z) in boundary if z == min_z - 1]
    if len(floor_cells) < min_floor:
        return {
            "valid": False,
            "reason": f"floor area {len(floor_cells)} < {min_floor}",
            "volume": len(volume), "floor_area": len(floor_cells),
            "boundary_total": len(boundary), "boundary_placed": boundary_placed,
        }

    return {
        "valid": True, "reason": "ok",
        "volume": len(volume), "floor_area": len(floor_cells),
        "boundary_total": len(boundary), "boundary_placed": boundary_placed,
    }
