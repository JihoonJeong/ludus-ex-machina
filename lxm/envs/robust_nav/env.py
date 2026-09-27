"""RobustNavEnv — task A (hidden search) under single-change sensor conditions.

Built for Yeoul's connectome comparison (hub-ops/from-ludex-village/152,
LxM 096). It runs the Blockworld engine as is — same move rule, same world —
and adds a sensor layer, the policy/evaluator split and the metrics.

    env = RobustNavEnv()                          # the packaged v0 config
    obs = env.reset(seed=dev_seed, condition="hemi_left_transient")
    while True:
        obs, info, done = env.step(policy.act(obs, info))
        if done:
            break
    env.metrics()

What the policy gets — nothing else:
    obs  {"t", "heading", "last": {"action", "outcome", "bump_side"},
          "local": {"frame", "grid_radius", "occlusion", "blocked", "beacon", "valid"}}
    info {"t", "outcome", "reward", "done"} (+ "end" when done)
Everything else — position, map, goal, shortest path, visits, seed, layout,
the true grids, the condition's name — stays in the evaluator record
(`trajectory`, `layout`, `metrics()`).
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path

from games.blockworld.engine import BlockworldGame
from lxm.envs.robust_nav import layouts as L
from lxm.envs.robust_nav import sensors as S

CONFIG_V0 = Path(__file__).with_name("conditions_v0.json")
OBS_KEYS = ("t", "heading", "last", "local")
INFO_KEYS = ("t", "outcome", "reward", "done", "end")
OUTCOMES = ("moved", "collided", "waited", "invalid")
MOVES = ("north", "south", "east", "west")


def load_config(config=None) -> tuple[dict, str]:
    """(config dict, sha256 of its bytes). Accepts None (v0), a path or a dict."""
    if isinstance(config, dict):
        raw = json.dumps(config, sort_keys=True).encode()
        return copy.deepcopy(config), hashlib.sha256(raw).hexdigest()
    raw = Path(config or CONFIG_V0).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def controller_seed(episode_seed: int, rep: int = 0) -> int:
    """The controller RNG seed for an episode: derived, never the episode seed
    itself, and the same across conditions so paired runs share it."""
    return L.derive_int("robust_nav", "controller", episode_seed, rep)


class RobustNavEnv:
    def __init__(self, config=None, *, frame: str = "world", base_scenario: str = "hidden_target_nav_01"):
        if frame not in ("world", "body"):
            raise ValueError(f"frame must be 'world' or 'body', not {frame!r}")
        self.config, self.config_sha256 = load_config(config)
        self.version = self.config["version"]
        self.rng_ns = self.config["rng_namespace"]
        self.frame = frame
        self.R = self.config["grid_radius"]
        self.budget = self.config["budget"]
        self.reward = self.config["reward"]
        self.base_scenario = base_scenario
        self.game = None
        self.trajectory: list[dict] = []

    # --- public spec ------------------------------------------------------------
    def spec(self) -> dict:
        """What any controller may know up front."""
        return {
            "version": self.version, "task": self.config["task"],
            "actions": list(self.config["actions"]), "budget": self.budget,
            "grid": {"radius": self.R, "size": 2 * self.R + 1, "frame": self.frame,
                     "occlusion": self.config["occlusion"],
                     "channels": ["blocked", "beacon", "valid"]},
            "outcomes": list(OUTCOMES), "reward": dict(self.reward),
            "obs_keys": list(OBS_KEYS), "info_keys": list(INFO_KEYS),
        }

    # --- lifecycle --------------------------------------------------------------
    def reset(self, seed: int, condition: str = "nominal") -> dict:
        if condition not in self.config["conditions"]:
            raise KeyError(f"unknown condition {condition!r}")
        self.seed, self.condition_id = seed, condition
        self.condition = self.config["conditions"][condition]
        self.layout = L.make_layout(self.rng_ns, seed, self.config["layout"], grid_radius=self.R)
        game = BlockworldGame(self.base_scenario)
        game._scenario = L.scenario_for(self.layout, game._scenario, self.budget)
        self.game = game
        self.state = {"game": game.initial_state([{"agent_id": "a"}])}
        self._world = self._current()["world"]
        self._goal = tuple(self.layout["goal"])
        self._geo = L.distance_map(self._world, self._goal)
        self.t = 0
        self.done = False
        self._last = {"action": None, "outcome": None, "bump_side": None}
        obs = self._observe()
        self.trajectory = [self._row(obs, reward=None, meta=None)]
        return copy.deepcopy(obs)

    def step(self, action, meta: dict | None = None) -> tuple[dict, dict, bool]:
        """One action. `meta` is the harness's evaluator annotation (e.g.
        infra_fail, act_ms); it never reaches the policy."""
        assert self.game is not None, "reset() first"
        assert not self.done, "episode is over"
        direction, outcome = self._normalize(action)
        heading_before = self._agent()["facing"]
        before = self._pos()
        move = ({"type": "action", "verb": "move", "direction": direction} if direction
                else {"type": "action", "verb": "wait"})
        self.state["game"] = self.game.apply_move(move, "a", self.state)
        bump = None
        if direction:
            if self._pos() == before:
                outcome, bump = "collided", S.side_of(direction, heading_before)
            else:
                outcome = "moved"
        self.t += 1
        reached = self._reached()
        self.done = reached or self.t >= self.budget
        reward = self.reward["step"] + (self.reward["collision"] if outcome == "collided" else 0.0)
        if reached:
            reward += self.reward["success"]
        self._last = {"action": direction or "wait", "outcome": outcome, "bump_side": bump}
        obs = self._observe()
        info = {"t": self.t, "outcome": outcome, "reward": round(reward, 6), "done": self.done}
        if self.done:
            info["end"] = "reached" if reached else "budget"
        assert tuple(info) == INFO_KEYS[:len(info)], info
        self.trajectory.append(self._row(obs, reward=info["reward"], meta=meta))
        return copy.deepcopy(obs), copy.deepcopy(info), self.done

    # --- evaluator side ---------------------------------------------------------
    def metrics(self) -> dict:
        from lxm.envs.robust_nav.metrics import episode_metrics
        return episode_metrics(self.trajectory, self.layout, self.condition, self.config,
                               header=self.header())

    def header(self) -> dict:
        return {"kind": "header", "version": self.version, "config_sha256": self.config_sha256,
                "seed": self.seed, "condition": self.condition_id, "frame": self.frame,
                "condition_spec": copy.deepcopy(self.condition), "layout": copy.deepcopy(self.layout)}

    def save_trajectory(self, path) -> None:
        path = Path(path)
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "wt", encoding="utf-8") as f:
            f.write(json.dumps(self.header(), ensure_ascii=False) + "\n")
            for row in self.trajectory:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # --- internals --------------------------------------------------------------
    def _current(self) -> dict:
        return self.state["game"]["current"]

    def _agent(self) -> dict:
        return self._current()["agents"]["a"]

    def _pos(self) -> tuple:
        a = self._agent()
        return (a["x"], a["y"])

    def _reached(self) -> bool:
        return bool((self._current().get("navigate") or {}).get("reached"))

    def _normalize(self, action) -> tuple[str | None, str]:
        """(direction or None, outcome if already decided). Anything outside
        the four cardinal moves and wait is invalid and taken as a wait."""
        if isinstance(action, str):
            if action in MOVES:
                return action, "moved"
            return None, "waited" if action == "wait" else "invalid"
        if isinstance(action, dict):
            verb = action.get("verb")
            if verb == "wait" and set(action) <= {"verb", "type"}:
                return None, "waited"
            if verb == "move" and action.get("direction") in MOVES and set(action) <= {"verb", "type", "direction"}:
                return action["direction"], "moved"
        return None, "invalid"

    def _truth(self, offsets) -> tuple[list, list]:
        x0, y0 = self._pos()
        blocked = [[0 if (dx, dy) == (0, 0) else int(not L.walkable(self._world, x0 + dx, y0 + dy))
                    for dx, dy in row] for row in offsets]
        beacon = [[int((x0 + dx, y0 + dy) == self._goal) for dx, dy in row] for row in offsets]
        return blocked, beacon

    def _observe(self) -> dict:
        heading = self._agent()["facing"]
        offsets = S.grid_offsets(self.R, self.frame, heading)
        tb, tg = self._truth(offsets)
        grids = S.sense(tb, tg, offsets, heading=heading, condition=self.condition,
                        condition_id=self.condition_id, t=self.t, namespace=self.rng_ns, seed=self.seed)
        self._true = (tb, tg)
        return {
            "t": self.t,
            "heading": heading,
            "last": dict(self._last),
            "local": {"frame": self.frame, "grid_radius": self.R, "occlusion": self.config["occlusion"],
                      **grids},
        }

    def _row(self, obs: dict, *, reward, meta) -> dict:
        x, y = self._pos()
        loc = obs["local"]
        pack = lambda g: ["".join(map(str, r)) for r in g]  # noqa: E731
        return {
            "t": self.t, "pos": [x, y], "heading": obs["heading"],
            "action": obs["last"]["action"], "outcome": obs["last"]["outcome"],
            "bump_side": obs["last"]["bump_side"], "reward": reward, "reached": self._reached(),
            "impaired": S.active(self.condition, self.t), "geo": self._geo.get((x, y)),
            "obs": {"blocked": pack(loc["blocked"]), "beacon": pack(loc["beacon"]), "valid": pack(loc["valid"])},
            "true": {"blocked": pack(self._true[0]), "beacon": pack(self._true[1])},
            "meta": meta or {},
        }
