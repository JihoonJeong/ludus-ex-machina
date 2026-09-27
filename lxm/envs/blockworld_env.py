"""A thin reset/step wrapper over the Blockworld engine for non-LLM agents.

Built for the connectome comparison Yeoul asked about (hub-ops/from-ludex-
village/149, LxM 093): a rule baseline, a connectome controller and an LLM
should see the SAME local observation and send the SAME actions, and nothing
outside that interface — no map, no target coordinates — should reach the
agent. The engine is used as is; this module only wraps its state envelope,
turns its absolute-coordinate view into an agent-relative one, and keeps the
environment-side record (trajectory, shortest path, metrics) out of the
observation.

    env = BlockworldEnv("hidden_target_nav_01", view_radius=5)
    obs = env.reset(seed=3)
    while True:
        obs, info, done = env.step("north")      # or {"verb": "wait"}
        if done:
            break
    env.metrics()

Observation (relative=True, the default):
    {"turn": int,
     "agent": {"facing", "inventory", "above", "below"},          # no position
     "view": {"radius": R,
              "terrain": {block: count},                          # natural floor census
              "cells": [{"dx", "dy", "dz", "block", "placed"}],   # features/obstacles
              "items": [{"type", "dx", "dy", "dz", "count"}],     # e.g. the beacon
              "agents": [{"id", "dx", "dy", "dz"}]}}
dx/dy are offsets from the agent in world axes; DIRECTION_DELTAS says which
move changes which (north = dy -1: rules.md). Engine event texts are dropped —
they carry absolute coordinates. What the agent may feel after a step comes
in `info`: `no_op` (it did not move), `invalid` (the action was outside the
allowed verbs, or malformed, and was taken as a wait).
"""

from __future__ import annotations

import copy
import json
import random
from collections import deque
from pathlib import Path

from games.blockworld import world as W
from games.blockworld.engine import BlockworldGame

DIRECTION_DELTAS = {d: W.DIRECTIONS[d][:2] for d in ("north", "south", "east", "west")}
WALK_Z = 1


def walkable(world: dict, x: int, y: int, z: int = WALK_Z) -> bool:
    """The engine's move rule on the walking layer: passable cell, ground below."""
    if not W.in_bounds(world, x, y, z):
        return False
    if W.get_block(world, x, y, z) not in W.PASSABLE:
        return False
    return z == 0 or W.get_block(world, x, y, z - 1) != "air"


def shortest_path_len(world: dict, start: tuple, goal: tuple) -> int | None:
    """Environment-side BFS over the walking layer (4-neighbour moves)."""
    if start == goal:
        return 0
    seen, q = {start}, deque([(start, 0)])
    while q:
        (x, y), d = q.popleft()
        for dx, dy in DIRECTION_DELTAS.values():
            n = (x + dx, y + dy)
            if n in seen or not walkable(world, *n):
                continue
            if n == goal:
                return d + 1
            seen.add(n)
            q.append((n, d + 1))
    return None


def layout_for_seed(scenario: dict, seed: int, *, min_distance: int = 12, walls: int = 3,
                    tries: int = 200) -> dict:
    """A seeded variant of a hidden_target_nav scenario: terrain seed, start,
    beacon and stone wall segments drawn from `seed`. The beacon starts out of
    sight (Chebyshev distance > the default view radius), at least
    `min_distance` steps away, and reachable (BFS). Deterministic in `seed`."""
    rng = random.Random(seed)
    dims = scenario["dimensions"]
    for _ in range(tries):
        sc = copy.deepcopy(scenario)
        sc["seed"] = seed
        sc["obstacles"] = []
        for _w in range(walls):
            horizontal = rng.random() < 0.5
            length = rng.randint(5, 10)
            x0, y0 = rng.randint(2, dims["x"] - 3), rng.randint(2, dims["y"] - 3)
            for i in range(length):
                x, y = (x0 + i, y0) if horizontal else (x0, y0 + i)
                if 1 <= x < dims["x"] - 1 and 1 <= y < dims["y"] - 1:
                    sc["obstacles"].append({"x": x, "y": y, "z": WALK_Z, "block": "stone"})
        world = W.generate_world(dimensions=dims, seed=seed, terrain_profile=sc["terrain_profile"])
        for ob in sc["obstacles"]:
            W.set_block(world, ob["x"], ob["y"], ob["z"], ob["block"], placed_by_agent=False)
        cells = [(x, y) for y in range(dims["y"]) for x in range(dims["x"]) if walkable(world, x, y)]
        start, goal = rng.choice(cells), rng.choice(cells)
        if max(abs(start[0] - goal[0]), abs(start[1] - goal[1])) <= 5:
            continue
        d = shortest_path_len(world, start, goal)
        if d is None or d < min_distance:
            continue
        sc["agent_starts"] = [{"agent_id": "a", "x": start[0], "y": start[1], "z": WALK_Z, "facing": "north"}]
        sc["target_cell"] = {"x": goal[0], "y": goal[1], "z": WALK_Z}
        return sc
    raise RuntimeError(f"no valid layout for seed {seed} in {tries} tries")


class BlockworldEnv:
    def __init__(self, scenario_id: str = "hidden_target_nav_01", *, view_radius: int | None = None,
                 verbs: tuple = ("move", "wait"), relative: bool = True, agent_id: str = "a"):
        self.scenario_id = scenario_id
        self.view_radius = view_radius
        self.verbs = tuple(verbs)
        self.relative = relative
        self.agent_id = agent_id
        self.game: BlockworldGame | None = None
        self.state: dict | None = None
        self.trajectory: list[dict] = []

    # --- lifecycle -----------------------------------------------------------
    def reset(self, seed: int | None = None) -> dict:
        game = BlockworldGame(self.scenario_id)
        if seed is not None:
            game._scenario = layout_for_seed(game._scenario, seed)
        self.game, self.seed = game, seed
        self.state = {"game": game.initial_state([{"agent_id": self.agent_id}])}
        self.trajectory = []
        self._visits: dict[tuple, int] = {}
        self._first_seen: int | None = None
        self._steps = self._no_ops = self._invalid = self._revisits = 0
        self._start = self._pos()
        self._visits[self._start] = 1
        obs = self._obs()
        self._note_seen(obs, 0)
        self.trajectory.append({"t": 0, "pos": list(self._start), "action": None})
        return obs

    def step(self, action) -> tuple[dict, dict, bool]:
        assert self.state is not None, "reset() first"
        move, invalid = self._to_move(action)
        before = self._pos()
        game_state = self.game.apply_move(move, self.agent_id, self.state)
        self.state["game"] = game_state
        done = self.game.is_over(self.state)
        after = self._pos()
        no_op = move["verb"] == "move" and after == before
        revisit = move["verb"] == "move" and not no_op and after in self._visits
        self._visits[after] = self._visits.get(after, 0) + 1
        self._steps += 1
        self._no_ops += int(no_op)
        self._invalid += int(invalid)
        self._revisits += int(revisit)
        obs = self._obs()
        self._note_seen(obs, self._steps)
        info = {"no_op": no_op, "invalid": invalid, "revisit": revisit,
                "reached": self._reached(), "turn": self._current()["turn"]}
        self.trajectory.append({"t": self._steps, "pos": list(after), "action": move,
                                "no_op": no_op, "invalid": invalid, "reached": info["reached"]})
        return obs, info, done

    # --- environment-side record (never in the observation) --------------------
    def metrics(self) -> dict:
        cur = self._current()
        world = cur["world"]
        tgt = (cur.get("navigate") or {}).get("target_cell") or {}
        goal = (tgt.get("x"), tgt.get("y")) if tgt else None
        shortest = shortest_path_len(world, self._start, goal) if goal else None
        reached = self._reached()
        return {
            "scenario": self.scenario_id, "seed": self.seed, "view_radius": self.view_radius,
            "reached": reached, "steps": self._steps, "shortest": shortest,
            "path_efficiency": (round(shortest / self._steps, 3) if reached and self._steps else None),
            "no_op_rate": round(self._no_ops / self._steps, 3) if self._steps else None,
            "invalid": self._invalid, "revisit_rate": round(self._revisits / self._steps, 3) if self._steps else None,
            "first_seen_step": self._first_seen,
            "search_steps": self._first_seen,
            "approach_steps": (self._steps - self._first_seen) if (reached and self._first_seen is not None) else None,
        }

    def save_trajectory(self, path) -> None:
        with Path(path).open("w", encoding="utf-8") as f:
            for row in self.trajectory:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # --- internals ---------------------------------------------------------------
    def _current(self) -> dict:
        return self.state["game"]["current"]

    def _pos(self) -> tuple:
        a = self._current()["agents"][self.agent_id]
        return (a["x"], a["y"])

    def _reached(self) -> bool:
        return bool((self._current().get("navigate") or {}).get("reached"))

    def _note_seen(self, obs: dict, step: int) -> None:
        if self._first_seen is None and any(i["type"] == "beacon" for i in obs["view"]["items"]):
            self._first_seen = step

    def _to_move(self, action) -> tuple[dict, bool]:
        if isinstance(action, str):
            action = {"verb": "wait"} if action == "wait" else {"verb": "move", "direction": action}
        verb = (action or {}).get("verb")
        move = {"type": "action", **{k: v for k, v in action.items() if k != "type"}}
        if verb not in self.verbs:
            return {"type": "action", "verb": "wait"}, True
        v = self.game.validate_move(move, self.agent_id, self.state)
        if not v.get("valid"):
            return {"type": "action", "verb": "wait"}, True
        return move, False

    def _obs(self) -> dict:
        sem = self.game.build_semantic_state(self.agent_id, self.state, radius=self.view_radius)
        if not self.relative:
            return sem
        a = sem["agent"]
        ax, ay, az = a["x"], a["y"], a["z"]
        v = sem["view"]
        rel = lambda o: {"dx": o["x"] - ax, "dy": o["y"] - ay, "dz": o["z"] - az}  # noqa: E731
        return {
            "turn": sem["turn"],
            "agent": {k: a[k] for k in ("facing", "inventory", "above", "below")},
            "view": {
                "radius": v["radius"],
                "terrain": dict(v["terrain"]),
                "cells": [{**rel(c), "block": c["block"], "placed": c["placed"]} for c in v["cells"]],
                "items": [{"type": i["type"], **rel(i), "count": i["count"]} for i in v["items"]],
                "agents": [{"id": o["id"], **rel(o)} for o in v["agents"]],
            },
        }
