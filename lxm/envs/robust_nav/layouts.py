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


# --- condition 6: out-of-distribution obstacle structure (v0.2) --------------------
#
# An OOD layout keeps the dev layout of the same seed — terrain, start, heading,
# beacon — and replaces only its obstacles with a structure the dev family never
# makes. So condition 6 is paired with nominal on the same start and goal, and
# differs from a mere seed change: the seed is the same, the structure is not.
#
#   corridors_v0  a band of parallel walls, one cell apart, across the start-goal
#                 line, each `length` long with one 1-cell gap set off the line by
#                 `gap_offset` cells, alternating sides: narrow corridors (path
#                 width 1) to thread, or a walk round the band's open ends
#   deadends_v0   one wide U between start and goal, mouth toward the start (a
#                 trap for going straight at the goal), and narrow dead-end alleys
#                 (1 cell wide, 4 deep) scattered around
#   detour_v0     one long barrier (`length`) across the start-goal line, shifted
#                 off-centre, no gap: a way round one of its ends
#
# None of them cuts the map in two: a structure that does turns hidden search
# (task A) into sweeping one's own half first, and every baseline sits at the
# floor.
#
# Each is checked: start and goal stay walkable, the goal stays reachable, and
# the shortest path lies in [min_shortest, max_shortest].


def _stone(x, y):
    return {"x": x, "y": y, "z": WALK_Z, "block": "stone"}


def _axis(start, goal):
    """The major axis between start and goal: 0 = x, 1 = y."""
    return 0 if abs(goal[0] - start[0]) >= abs(goal[1] - start[1]) else 1


def _line(axis: int, at: int, cells_on: range, skip: set) -> list[dict]:
    """A wall across `axis` at coordinate `at` over `cells_on`, except `skip`."""
    return [(_stone(at, c) if axis == 0 else _stone(c, at)) for c in cells_on if c not in skip]


def _band(s, g, ax, span, length, shift):
    """The cross-axis cells of a `length`-long wall centred on the start-goal
    line, moved by `shift`, clipped to the map."""
    centre = (s[1 - ax] + g[1 - ax]) // 2 + shift
    a = max(0, centre - length // 2)
    return range(a, min(span, a + length))


def _off_line(rng, s, g, ax, span, spec, side):
    """A cross-axis coordinate `gap_offset` cells off the start-goal line."""
    cross_mid = (s[1 - ax] + g[1 - ax]) // 2
    lo, hi = spec.get("gap_offset", [3, 6])
    c = cross_mid + side * rng.randint(lo, hi)
    return min(max(c, 1), span - 3)


def _corridors_v0(rng, dims, base, spec):
    s, g = base["start"], base["goal"]
    ax = _axis(s, g)
    lo, hi = sorted((s[ax], g[ax]))
    span = dims["y"] if ax == 0 else dims["x"]
    mid = (lo + hi) // 2
    n = spec.get("walls", 3)
    first = mid - (n - 1)
    cells_on = _band(s, g, ax, span, spec.get("length", 15), rng.randint(-2, 2))
    side = rng.choice((-1, 1))
    out = []
    for k in range(n):
        at = first + 2 * k
        if not lo < at < hi:
            continue
        out += _line(ax, at, cells_on, {_off_line(rng, s, g, ax, span, spec, side)})
        side = -side
    return out


def _cup(cx, cy, mouth, w=5, d=4):
    """A U of stone, `w` wide and `d` deep, open toward `mouth`, centred on (cx, cy)."""
    h = w // 2
    cells = []
    if mouth in ("north", "south"):
        back = cy + (d - 1) if mouth == "north" else cy - (d - 1)
        ys = range(cy, back + 1) if mouth == "north" else range(back, cy + 1)
        for x in range(cx - h, cx + h + 1):
            cells.append((x, back))
        for y in ys:
            cells += [(cx - h, y), (cx + h, y)]
    else:
        back = cx + (d - 1) if mouth == "west" else cx - (d - 1)
        xs = range(cx, back + 1) if mouth == "west" else range(back, cx + 1)
        for y in range(cy - h, cy + h + 1):
            cells.append((back, y))
        for x in xs:
            cells += [(x, cy - h), (x, cy + h)]
    return cells


def _deadends_v0(rng, dims, base, spec):
    s, g = base["start"], base["goal"]
    cells = []
    # the wide U between start and goal, mouth toward the start
    cx, cy = s[0] + (g[0] - s[0]) // 2, s[1] + (g[1] - s[1]) // 2
    ax = _axis(s, g)
    if ax == 0:
        mouth = "west" if g[0] > s[0] else "east"
    else:
        mouth = "north" if g[1] > s[1] else "south"
    cells += _cup(cx, cy, mouth, w=7, d=5)
    for _ in range(spec.get("alleys", 6)):
        cells += _cup(rng.randint(2, dims["x"] - 3), rng.randint(2, dims["y"] - 3),
                      rng.choice(("north", "south", "east", "west")), w=3, d=5)
    seen, out = set(), []
    for x, y in cells:
        if 0 <= x < dims["x"] and 0 <= y < dims["y"] and (x, y) not in seen:
            seen.add((x, y))
            out.append(_stone(x, y))
    return out


def _detour_v0(rng, dims, base, spec):
    s, g = base["start"], base["goal"]
    ax = _axis(s, g)
    lo, hi = sorted((s[ax], g[ax]))
    at = (lo + hi) // 2
    span = dims["y"] if ax == 0 else dims["x"]
    length = spec.get("length", 15)
    shift = rng.choice((-1, 1)) * rng.randint(2, length // 2 - 2)
    return _line(ax, at, _band(s, g, ax, span, length, shift), set())


OOD_FAMILIES = {"corridors_v0": _corridors_v0, "deadends_v0": _deadends_v0, "detour_v0": _detour_v0}


def make_ood_layout(namespace: str, seed: int, base: dict, family: str, spec: dict, tries: int = 200) -> dict:
    """The seed's dev layout with its obstacles replaced by an OOD `family`."""
    rng = random.Random(f"{namespace}/ood/{family}/{seed}")
    dims = base["dimensions"]
    start, goal = tuple(base["start"]), tuple(base["goal"])
    lo, hi = spec.get("min_shortest", 12), spec.get("max_shortest", 70)
    for _ in range(tries):
        obstacles = [o for o in OOD_FAMILIES[family](rng, dims, base, spec)
                     if (o["x"], o["y"]) not in (start, goal)]
        layout = {**base, "family": family, "base_family": base["family"], "obstacles": obstacles,
                  "shortest_base": base["shortest"]}
        world = build_world(layout)
        if not (walkable(world, *start) and walkable(world, *goal)):
            continue
        d = distance_map(world, goal).get(start)
        if d is None or not lo <= d <= hi:
            continue
        layout["shortest"] = d
        return layout
    raise RuntimeError(f"no valid {family} layout for seed {seed} in {tries} tries")


def structure_stats(layout: dict) -> dict:
    """Evaluator-only structure of a layout's walking layer: how open it is,
    how many dead-end and corridor cells it has, how far round the shortest
    path goes. Used to show that an OOD family differs from the dev family."""
    world = build_world(layout)
    dims = layout["dimensions"]
    walk = {(x, y) for y in range(dims["y"]) for x in range(dims["x"]) if walkable(world, x, y)}
    corridor = 0
    for x, y in walk:
        nb = [(dx, dy) for dx, dy in DELTAS4 if (x + dx, y + dy) in walk]
        if len(nb) == 2 and nb[0][0] == -nb[1][0] and nb[0][1] == -nb[1][1]:
            corridor += 1
    # dead-end filling: prune cells with at most one open neighbour until none
    # is left; what goes is the dead-end branches (cul-de-sacs, alleys)
    left, dead = set(walk), 0
    while True:
        leaves = {(x, y) for x, y in left
                  if sum((x + dx, y + dy) in left for dx, dy in DELTAS4) <= 1}
        if not leaves:
            break
        left -= leaves
        dead += len(leaves)
    (sx, sy), (gx, gy) = layout["start"], layout["goal"]
    return {"family": layout["family"], "walkable": len(walk), "dead_end_cells": dead,
            "corridor_cells": corridor, "shortest": layout["shortest"],
            "detour_ratio": round(layout["shortest"] / (abs(sx - gx) + abs(sy - gy)), 3)}
