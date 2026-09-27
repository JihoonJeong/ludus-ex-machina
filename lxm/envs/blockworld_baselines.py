"""Two rule baselines for BlockworldEnv, using only what any agent gets:
the relative observation and the previous step's `info` (did I move?).

  random_walk      a floor: a uniformly random move each turn.
  seek_and_sweep   a simple ceiling-ish policy: when a beacon is in view, step
                   toward it along the longer axis (the other axis if that is
                   blocked); otherwise explore — keep a dead-reckoned map of
                   where it has been and which cells it saw blocked, prefer
                   the unvisited neighbour, least-visited otherwise.

Neither sees coordinates, the map, or the target. They exist so a connectome
controller can be compared with a rule policy through the SAME senses and the
SAME motor decoder (Yeoul 149, LxM 093 §5).
"""

from __future__ import annotations

import random

from lxm.envs.blockworld_env import DIRECTION_DELTAS

MOVES = tuple(DIRECTION_DELTAS)


class RandomWalk:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def reset(self) -> None:
        pass

    def act(self, obs: dict, info: dict | None) -> str:
        return self.rng.choice(MOVES)


class SeekAndSweep:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)
        self.reset()

    def reset(self) -> None:
        self.pos = (0, 0)                   # dead-reckoned, starts at the origin
        self.visits = {(0, 0): 1}
        self.blocked: set[tuple] = set()
        self.last: str | None = None

    def _update(self, obs: dict, info: dict | None) -> None:
        if self.last is not None and info is not None:
            dx, dy = DIRECTION_DELTAS[self.last]
            if info.get("no_op"):
                self.blocked.add((self.pos[0] + dx, self.pos[1] + dy))
            else:
                self.pos = (self.pos[0] + dx, self.pos[1] + dy)
                self.visits[self.pos] = self.visits.get(self.pos, 0) + 1
        for c in obs["view"]["cells"]:           # obstacles on the walking layer
            if c["dz"] == 0:
                self.blocked.add((self.pos[0] + c["dx"], self.pos[1] + c["dy"]))

    def act(self, obs: dict, info: dict | None) -> str:
        self._update(obs, info)
        beacons = [i for i in obs["view"]["items"] if i["type"] == "beacon" and i["dz"] == 0]
        if beacons:
            b = min(beacons, key=lambda i: abs(i["dx"]) + abs(i["dy"]))
            prefs = []
            axes = [("east" if b["dx"] > 0 else "west", abs(b["dx"])),
                    ("south" if b["dy"] > 0 else "north", abs(b["dy"]))]
            for d, n in sorted(axes, key=lambda t: -t[1]):
                if n:
                    prefs.append(d)
            for d in prefs:
                dx, dy = DIRECTION_DELTAS[d]
                if (self.pos[0] + dx, self.pos[1] + dy) not in self.blocked:
                    self.last = d
                    return d
        # explore: unvisited open neighbour first (keep heading on ties), else least visited
        def score(d):
            dx, dy = DIRECTION_DELTAS[d]
            n = (self.pos[0] + dx, self.pos[1] + dy)
            if n in self.blocked:
                return (2, 0, 0)
            return (0 if n not in self.visits else 1, self.visits.get(n, 0), 0 if d == self.last else 1)
        options = sorted(MOVES, key=lambda d: (score(d), self.rng.random()))
        self.last = options[0]
        return self.last


POLICIES = {"random_walk": RandomWalk, "seek_and_sweep": SeekAndSweep}


def run_episode(env, policy, seed: int | None = None, max_steps: int | None = None) -> dict:
    obs = env.reset(seed=seed)
    policy.reset()
    info = None
    limit = max_steps or env.game._scenario.get("turn_limit", 100)
    for _ in range(limit):
        obs, info, done = env.step(policy.act(obs, info))
        if done:
            break
    return env.metrics()
