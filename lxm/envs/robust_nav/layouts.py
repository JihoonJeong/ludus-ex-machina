"""Seeded layouts for robust_nav — the environment RNG.

Every layout is a function of (rng namespace, family, seed) alone: the terrain
seed, the start, the start heading, the beacon and the obstacles all come from
one RNG derived from that string, separate from the sensor RNG and from any
controller RNG. The beacon starts out of sight (Chebyshev distance beyond the
full grid radius), at least `min_shortest` steps away, and reachable (BFS).

Families
    walls_v0   the development distribution: a meadow with a few straight
               stone wall segments (the hidden_target_nav_01 world, reseeded).
"""

from __future__ import annotations

import hashlib
import random
from collections import deque

from games.blockworld import world as W

WALK_Z = 1
DELTAS4 = ((0, -1), (1, 0), (0, 1), (-1, 0))


def derive_int(*parts) -> int:
    """A 31-bit integer derived from the parts (stable across runs/platforms)."""
    h = hashlib.sha256("/".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF


def walkable(world: dict, x: int, y: int, z: int = WALK_Z) -> bool:
    """The engine's move rule on the walking layer: passable cell, ground below."""
    if not W.in_bounds(world, x, y, z):
        return False
    if W.get_block(world, x, y, z) not in W.PASSABLE:
        return False
    return z == 0 or W.get_block(world, x, y, z - 1) != "air"


def distance_map(world: dict, source: tuple) -> dict:
    """BFS geodesic distance from `source` to every reachable walking cell."""
    dist, q = {source: 0}, deque([source])
    while q:
        x, y = q.popleft()
        for dx, dy in DELTAS4:
            n = (x + dx, y + dy)
            if n not in dist and walkable(world, *n):
                dist[n] = dist[(x, y)] + 1
                q.append(n)
    return dist


def build_world(layout: dict) -> dict:
    """The world a layout describes (terrain + obstacles), without agents."""
    dims = layout["dimensions"]
    world = W.generate_world(dimensions=dims, seed=layout["terrain_seed"],
                             terrain_profile=layout["terrain_profile"])
    for ob in layout["obstacles"]:
        W.set_block(world, ob["x"], ob["y"], ob["z"], ob["block"], placed_by_agent=False)
    return world


def _walls_v0(rng: random.Random, dims: dict, spec: dict) -> list[dict]:
    obstacles = []
    for _ in range(spec.get("walls", 3)):
        horizontal = rng.random() < 0.5
        length = rng.randint(5, 10)
        x0, y0 = rng.randint(2, dims["x"] - 3), rng.randint(2, dims["y"] - 3)
        for i in range(length):
            x, y = (x0 + i, y0) if horizontal else (x0, y0 + i)
            if 1 <= x < dims["x"] - 1 and 1 <= y < dims["y"] - 1:
                obstacles.append({"x": x, "y": y, "z": WALK_Z, "block": "stone"})
    return obstacles


FAMILIES = {"walls_v0": _walls_v0}


def make_layout(namespace: str, seed: int, spec: dict, *, grid_radius: int, tries: int = 200) -> dict:
    """The layout for `seed` under the config's layout `spec`."""
    family = spec["family"]
    rng = random.Random(f"{namespace}/layout/{family}/{seed}")
    dims = dict(zip("xyz", spec["dimensions"]))
    for _ in range(tries):
        layout = {
            "family": family, "seed": seed, "dimensions": dims,
            "terrain_profile": spec["terrain_profile"],
            "terrain_seed": rng.randrange(2**31),
            "obstacles": FAMILIES[family](rng, dims, spec),
        }
        world = build_world(layout)
        cells = [(x, y) for y in range(dims["y"]) for x in range(dims["x"]) if walkable(world, x, y)]
        start, goal = rng.choice(cells), rng.choice(cells)
        heading = rng.choice(("north", "east", "south", "west"))
        if max(abs(start[0] - goal[0]), abs(start[1] - goal[1])) <= grid_radius:
            continue
        d = distance_map(world, goal).get(start)
        if d is None or d < spec.get("min_shortest", 12):
            continue
        layout.update({"start": list(start), "heading": heading, "goal": list(goal), "shortest": d})
        return layout
    raise RuntimeError(f"no valid {family} layout for seed {seed} in {tries} tries")


def scenario_for(layout: dict, base: dict, budget: int) -> dict:
    """An engine scenario (hidden_target_nav mode) for the layout."""
    sc = dict(base)
    sc.update({
        "mode": "hidden_target_nav",
        "dimensions": dict(layout["dimensions"]),
        "seed": layout["terrain_seed"],
        "terrain_profile": layout["terrain_profile"],
        "obstacles": [dict(o) for o in layout["obstacles"]],
        "agent_starts": [{"agent_id": "a", "x": layout["start"][0], "y": layout["start"][1],
                          "z": WALK_Z, "facing": layout["heading"]}],
        "target_cell": {"x": layout["goal"][0], "y": layout["goal"][1], "z": WALK_Z},
        "turn_limit": budget + 10,          # the env ends the episode; the engine never does first
    })
    return sc
