"""Body/world frames and the sensor model for robust_nav.

Frames
    world  rows = dy -R..+R (north first), cols = dx -R..+R (west first).
           The same axes as the actions: north = dy -1, east = dx +1.
    body   rows = forward +R..-R (ahead first), cols = right -R..+R (left
           first): the world grid turned so the heading points up.

Heading changes only on a successful move (the engine's `_do_move`); a blocked
move or a wait leaves it as it was. Left/right always mean the body's left and
right under the current heading, in both frames.

Sensing at observation index t (reset is t=0, the observation after step k is
t=k):
    1. truth   blocked (cannot be walked into: obstacle, no ground, off the
               world) and beacon, for every cell of the fixed (2R+1)^2 grid.
    2. known impairment -> valid=0 where the condition takes sight away (range,
               hemifield, blind). The value there is forced to 0; 0 with
               valid=0 does NOT mean empty.
    3. noise   undetected: flips values inside the valid field, valid stays 1.
               Its draws come from an RNG derived per step from
               (rng namespace, seed, condition, t), a fixed number per step, so
               neither the controller's RNG use nor the path moves the
               schedule; the agent's own cell is never noised.
"""

from __future__ import annotations

import random

HEADINGS = ("north", "east", "south", "west")          # clockwise
DELTAS = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
SIDES = ("front", "right", "back", "left")             # clockwise from the heading


def side_of(direction: str, heading: str) -> str:
    """Where `direction` lies relative to the body: front/right/back/left."""
    return SIDES[(HEADINGS.index(direction) - HEADINGS.index(heading)) % 4]


def turn(heading: str, side: str) -> str:
    """The world direction that lies at `side` of the body."""
    return HEADINGS[(HEADINGS.index(heading) + SIDES.index(side)) % 4]


def world_to_body(dx: int, dy: int, heading: str) -> tuple[int, int]:
    """World offset -> (forward, right) under `heading`."""
    fx, fy = DELTAS[heading]
    rx, ry = DELTAS[turn(heading, "right")]
    return dx * fx + dy * fy, dx * rx + dy * ry


def body_to_world(fwd: int, right: int, heading: str) -> tuple[int, int]:
    """(forward, right) under `heading` -> world offset."""
    fx, fy = DELTAS[heading]
    rx, ry = DELTAS[turn(heading, "right")]
    return fwd * fx + right * rx, fwd * fy + right * ry


def grid_offsets(radius: int, frame: str, heading: str) -> list[list[tuple[int, int]]]:
    """For each grid [row][col], the world offset (dx, dy) it shows."""
    n = 2 * radius + 1
    if frame == "world":
        return [[(j - radius, i - radius) for j in range(n)] for i in range(n)]
    if frame == "body":
        return [[body_to_world(radius - i, j - radius, heading) for j in range(n)] for i in range(n)]
    raise ValueError(f"unknown frame {frame!r}")


def active(condition: dict, t: int) -> bool:
    """Is the condition's impairment on at observation index t?"""
    imp = condition.get("impairment")
    if not imp:
        return False
    onset, release = condition.get("window", [0, None])
    return t >= onset and (release is None or t < release)


def _known_mask(imp: dict, dx: int, dy: int, heading: str) -> bool:
    """True where a known impairment takes the cell away."""
    kind = imp["kind"]
    if kind == "range":
        return max(abs(dx), abs(dy)) > imp["radius"]
    if kind == "hemifield":
        _, right = world_to_body(dx, dy, heading)
        return right < 0 if imp["side"] == "left" else right > 0
    if kind == "blind":
        return True
    return False


def sensor_rng(namespace: str, seed, condition_id: str, t: int) -> random.Random:
    return random.Random(f"{namespace}/sensor/{seed}/{condition_id}/{t}")


def sense(truth_blocked, truth_beacon, offsets, *, heading: str, condition: dict,
          condition_id: str, t: int, namespace: str, seed) -> dict:
    """Apply the condition to true grids. Returns blocked/beacon/valid grids
    (lists of lists of 0/1) as delivered to the policy."""
    n = len(offsets)
    on = active(condition, t)
    imp = condition.get("impairment") if on else None
    noisy = imp is not None and imp["kind"] == "noise"
    rng = sensor_rng(namespace, seed, condition_id, t) if noisy else None
    blocked = [[0] * n for _ in range(n)]
    beacon = [[0] * n for _ in range(n)]
    valid = [[1] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            dx, dy = offsets[i][j]
            b, g = truth_blocked[i][j], truth_beacon[i][j]
            if noisy:
                u1, u2 = rng.random(), rng.random()        # two draws per cell, always
                if (dx, dy) != (0, 0):
                    if u1 < imp["blocked_flip"]:
                        b = 1 - b
                    if g and u2 < imp["beacon_drop"]:
                        g = 0
                    elif not g and u2 < imp["beacon_spurious"]:
                        g = 1
            elif imp is not None and _known_mask(imp, dx, dy, heading):
                valid[i][j] = 0
                b = g = 0
            blocked[i][j], beacon[i][j] = b, g
    return {"blocked": blocked, "beacon": beacon, "valid": valid}
