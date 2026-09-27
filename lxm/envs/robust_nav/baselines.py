"""Rule baselines for robust_nav and the episode harness.

The baselines read only the policy observation (world frame) and the policy
info — the same thing a connectome controller or an LLM gets. A cell with
valid=0 is unknown, never empty. Each declares what it keeps in memory, so a
table can say which rows integrate their own motion:

    random_walk     memory none      uniform random move
    bump_turn       memory none      contact only: keep going, turn left or right
                                     at random when a move collides (no sight)
    seek_reactive   memory none      step toward a seen beacon; otherwise keep
                                     going, turning off cells seen or felt blocked
    seek_and_sweep  memory path      as LxM 095, plus a remembered beacon: path
                                     integration from `outcome`, a map of cells
                                     felt/seen blocked and visited, and where it last
                                     saw a beacon (dropped once that cell is in view
                                     without one); prefers unvisited neighbours

Task B (cue) baselines — they read the cue too, and only what task B gives:

    cue_follow      memory none      step along the cue: the best-aligned move not
                                     seen or just felt blocked; a seen beacon first;
                                     without a valid cue, seek_reactive
    cue_sweep       memory path      seek_and_sweep whose tie-break among equally
                                     visited neighbours is alignment with the cue:
                                     least visited first, then best aligned

The harness gives each episode a controller seed derived from the episode seed
(env.controller_seed), the same across conditions; the controller's RNG is its
own, apart from the layout and sensor RNGs.
"""

from __future__ import annotations

import random
import time

from lxm.envs.robust_nav.sensors import DELTAS, turn

MOVES = ("north", "east", "south", "west")


def seen_cells(obs: dict):
    """Yield (dx, dy, blocked, beacon) for the valid cells of a world-frame grid."""
    loc = obs["local"]
    assert loc["frame"] == "world", "the rule baselines read the world frame"
    R = loc["grid_radius"]
    for i, row in enumerate(loc["valid"]):
        for j, v in enumerate(row):
            if v:
                yield j - R, i - R, loc["blocked"][i][j], loc["beacon"][i][j]


def toward(dx: int, dy: int) -> list[str]:
    """Moves that reduce the offset, longer axis first."""
    axes = [("east" if dx > 0 else "west", abs(dx)), ("south" if dy > 0 else "north", abs(dy))]
    return [d for d, n in sorted(axes, key=lambda t: -t[1]) if n]


class Policy:
    memory = "none"

    def reset(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def act(self, obs: dict, info: dict | None) -> str:
        raise NotImplementedError


class RandomWalk(Policy):
    def act(self, obs, info):
        return self.rng.choice(MOVES)


class BumpTurn(Policy):
    def reset(self, seed=0):
        super().reset(seed)
        self.dir = None

    def act(self, obs, info):
        if self.dir is None:
            self.dir = obs["heading"]
        if obs["last"]["outcome"] == "collided":
            self.dir = turn(self.dir, self.rng.choice(("left", "right")))
        return self.dir


class SeekReactive(Policy):
    def reset(self, seed=0):
        super().reset(seed)
        self.dir = None

    def act(self, obs, info):
        cells = list(seen_cells(obs))
        blocked = {(dx, dy) for dx, dy, b, _ in cells if b}
        beacons = [(dx, dy) for dx, dy, _, g in cells if g]
        if beacons:
            bx, by = min(beacons, key=lambda c: abs(c[0]) + abs(c[1]))
            for d in toward(bx, by):
                if DELTAS[d] not in blocked:
                    self.dir = d
                    return d
        if self.dir is None:
            self.dir = obs["heading"]
        felt = obs["last"]["outcome"] == "collided"
        if felt or DELTAS[self.dir] in blocked:
            options = [turn(self.dir, s) for s in ("left", "right")]
            self.rng.shuffle(options)
            options.append(turn(self.dir, "back"))
            open_ = [d for d in options if DELTAS[d] not in blocked]
            self.dir = open_[0] if open_ else options[0]
        return self.dir


class SeekAndSweep(Policy):
    memory = "path"

    def reset(self, seed=0):
        super().reset(seed)
        self.pos = (0, 0)
        self.visits = {(0, 0): 1}
        self.felt: set[tuple] = set()       # collided into: contact is never noised
        self.seen: set[tuple] = set()       # latest valid reading says blocked
        self.target: tuple | None = None    # where a beacon was last seen
        self.last: str | None = None

    @property
    def blocked(self) -> set:
        return self.felt | self.seen

    def act(self, obs, info):
        out = obs["last"]["outcome"]
        if self.last is not None and out in ("moved", "collided"):
            dx, dy = DELTAS[self.last]
            nxt = (self.pos[0] + dx, self.pos[1] + dy)
            if out == "collided":
                self.felt.add(nxt)
            else:
                self.pos = nxt
                self.visits[nxt] = self.visits.get(nxt, 0) + 1
        beacons, empty = [], set()
        for dx, dy, b, g in seen_cells(obs):
            c = (self.pos[0] + dx, self.pos[1] + dy)
            (self.seen.add if b else self.seen.discard)(c)
            (beacons.append if g else empty.add)(c)
        if beacons:
            self.target = min(beacons, key=lambda c: abs(c[0] - self.pos[0]) + abs(c[1] - self.pos[1]))
        elif self.target in empty:
            self.target = None
        blocked = self.blocked
        if self.target is not None:
            for d in toward(self.target[0] - self.pos[0], self.target[1] - self.pos[1]):
                ddx, ddy = DELTAS[d]
                if (self.pos[0] + ddx, self.pos[1] + ddy) not in blocked:
                    self.last = d
                    return d
        self.last = sorted(MOVES, key=lambda d: (self._score(d, blocked, obs), self.rng.random()))[0]
        return self.last

    def _score(self, d, blocked, obs):
        ddx, ddy = DELTAS[d]
        c = (self.pos[0] + ddx, self.pos[1] + ddy)
        if c in blocked:
            return (2, 0, 0)
        return (0 if c not in self.visits else 1, self.visits.get(c, 0), 0 if d == self.last else 1)


def _cue(obs):
    """The world-frame cue vector, or None when invalid (or not task B)."""
    cue = obs.get("cue")
    if not cue or not cue["valid"]:
        return None
    assert obs["local"]["frame"] == "world", "the rule baselines read the world frame"
    return cue["dir"]


def _align(d, cue) -> float:
    return DELTAS[d][0] * cue[0] + DELTAS[d][1] * cue[1]


class CueFollow(SeekReactive):
    def act(self, obs, info):
        cue = _cue(obs)
        cells = list(seen_cells(obs))
        if cue is None or any(g for *_, g in cells):
            return super().act(obs, info)
        blocked = {(dx, dy) for dx, dy, b, _ in cells if b}
        felt = obs["last"]["action"] if obs["last"]["outcome"] == "collided" else None
        ranked = sorted(MOVES, key=lambda d: (-_align(d, cue), self.rng.random()))
        for d in ranked:
            if DELTAS[d] not in blocked and d != felt:
                self.dir = d
                return d
        self.dir = ranked[0]
        return self.dir


class CueSweep(SeekAndSweep):
    def _score(self, d, blocked, obs):
        cue = _cue(obs)
        if cue is None:
            return super()._score(d, blocked, obs)
        ddx, ddy = DELTAS[d]
        c = (self.pos[0] + ddx, self.pos[1] + ddy)
        if c in blocked:
            return (1, 0, 0)                  # blocked always ranks last
        return (0, self.visits.get(c, 0), -_align(d, cue))


POLICIES = {"random_walk": RandomWalk, "bump_turn": BumpTurn,
            "seek_reactive": SeekReactive, "seek_and_sweep": SeekAndSweep}
CUE_POLICIES = {"cue_follow": CueFollow, "cue_sweep": CueSweep}
ALL_POLICIES = {**POLICIES, **CUE_POLICIES}


class AbortEpisode(Exception):
    """Raise from act() to stop the episode on purpose (e.g. the driver's
    safety budget ran out). The episode is kept as end=aborted with the reason
    and the steps taken."""


def run_episode(env, policy, seed: int, condition: str = "nominal", *, rep: int = 0,
                save_to=None) -> dict:
    """One episode. A controller exception (call failure, timeout it raises)
    becomes a wait marked infra_fail in the evaluator record (cause=infra) —
    kept in the result, not dropped; the policy sees only that it waited, never
    the error text. AbortEpisode ends the episode as end=aborted. Optional
    `policy.sidecar()` -> dict is attached."""
    from lxm.envs.robust_nav.env import controller_seed
    obs = env.reset(seed=seed, condition=condition)
    policy.reset(seed=controller_seed(seed, rep))
    info = None
    while True:
        t0 = time.perf_counter()
        try:
            action, fail = policy.act(obs, info), None
        except AbortEpisode as e:
            env.abort(str(e))
            break
        except Exception as e:  # noqa: BLE001 — recorded, not hidden
            action, fail = "wait", f"{type(e).__name__}: {e}"[:200]
        meta = {"act_ms": round((time.perf_counter() - t0) * 1000, 3)}
        if fail:
            meta["infra_fail"] = fail
        obs, info, done = env.step(action, meta=meta)
        if done:
            break
    result = env.metrics()
    result["policy"] = type(policy).__name__
    result["memory"] = getattr(policy, "memory", None)
    result["rep"] = rep
    if hasattr(policy, "sidecar"):
        result["sidecar"] = policy.sidecar()
    if save_to is not None:
        env.save_trajectory(save_to)
    return result
