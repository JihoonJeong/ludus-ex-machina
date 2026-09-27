"""robust_nav v0.1 contract tests (Yeoul 152, LxM 096)."""

import hashlib
import json
from pathlib import Path

import pytest

from games.blockworld import world as W
from lxm.envs.robust_nav import (INFO_KEYS, OBS_KEYS, RobustNavEnv, body_to_world, controller_seed,
                                 side_of, turn, world_to_body)
from lxm.envs.robust_nav import layouts as L
from lxm.envs.robust_nav import seeds
from lxm.envs.robust_nav.baselines import POLICIES, Policy, RandomWalk, run_episode

DEV = seeds.load("dev")
FORBIDDEN_KEYS = {"x", "y", "z", "pos", "position", "goal", "target", "target_cell", "seed", "layout",
                  "dimensions", "shortest", "geo", "visits", "revisit", "condition", "true", "no_op"}


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def _place_env(seed=None, condition="nominal", frame="world"):
    env = RobustNavEnv(frame=frame)
    obs = env.reset(DEV[0] if seed is None else seed, condition)
    return env, obs


def _teleport(env, x, y, facing):
    a = env._agent()
    a["x"], a["y"], a["facing"] = x, y, facing


# --- frames ------------------------------------------------------------------------

def test_frames_round_trip_and_sides():
    for h in ("north", "east", "south", "west"):
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                assert body_to_world(*world_to_body(dx, dy, h), h) == (dx, dy)
        assert side_of(h, h) == "front"
        for s in ("front", "right", "back", "left"):
            assert side_of(turn(h, s), h) == s
    assert turn("north", "right") == "east" and turn("east", "right") == "south"
    assert world_to_body(1, 0, "north") == (0, 1)       # east is on the right when facing north
    assert world_to_body(0, 1, "east") == (0, 1)        # south is on the right when facing east
    assert world_to_body(0, -1, "west") == (0, 1)       # north is on the right when facing west


# --- the policy interface ---------------------------------------------------------------

def test_obs_and_info_carry_only_the_allowlist():
    env, obs = _place_env()
    assert tuple(obs) == OBS_KEYS
    assert set(obs["local"]) == {"frame", "grid_radius", "occlusion", "blocked", "beacon", "valid"}
    assert obs["local"]["occlusion"] == "none"
    for cond in env.config["conditions"]:
        obs = env.reset(DEV[1], cond)
        for _ in range(60):
            obs, info, done = env.step("north")
            assert tuple(obs) == OBS_KEYS
            assert set(info) <= set(INFO_KEYS) and tuple(info)[:4] == INFO_KEYS[:4]
            assert not FORBIDDEN_KEYS & set(_keys(obs)) and not FORBIDDEN_KEYS & set(_keys(info))
            n = 2 * env.R + 1
            for g in ("blocked", "beacon", "valid"):
                assert len(obs["local"][g]) == n and all(len(r) == n for r in obs["local"][g])
            if done:
                break


def test_start_view_has_no_beacon_and_obs_is_a_copy():
    for s in DEV:
        env, obs = _place_env(s)
        assert not any(any(r) for r in obs["local"]["beacon"])
        obs["local"]["blocked"][0][0] = 7                    # the policy cannot write back
        assert env.trajectory[0]["obs"]["blocked"][0][0] in "01"


def test_facing_unchanged_on_blocked_move_and_outcomes():
    env, obs = _place_env()
    world = env._world
    # find a walkable cell with an unwalkable east neighbour
    spot = next((x, y) for y in range(24) for x in range(24)
                if L.walkable(world, x, y) and not L.walkable(world, x + 1, y) and L.walkable(world, x, y - 1))
    _teleport(env, *spot, "north")
    obs, info, _ = env.step("east")
    assert info["outcome"] == "collided" and obs["last"] == {"action": "east", "outcome": "collided", "bump_side": "right"}
    assert obs["heading"] == "north" and env._pos() == spot
    assert info["reward"] == pytest.approx(env.reward["step"] + env.reward["collision"])
    obs, info, _ = env.step("wait")
    assert info["outcome"] == "waited" and obs["heading"] == "north" and obs["last"]["bump_side"] is None
    for bad in ("up", "jump", {"verb": "move", "direction": "up"}, {"verb": "place", "direction": "east"},
                {"verb": "move", "direction": "east", "message": "hi"}, None, 3):
        obs, info, _ = env.step(bad)
        assert info["outcome"] == "invalid" and obs["last"]["action"] == "wait" and env._pos() == spot
        assert info["reward"] == pytest.approx(env.reward["step"])
    obs, info, _ = env.step({"verb": "move", "direction": "north"})
    assert info["outcome"] == "moved" and obs["heading"] == "north" and env._pos() == (spot[0], spot[1] - 1)


def test_blocked_grid_agrees_with_the_engine():
    env, _ = _place_env(DEV[2])
    world = env._world
    checked = 0
    for (x, y) in [(x, y) for y in range(0, 24, 3) for x in range(0, 24, 3) if L.walkable(world, x, y)]:
        for d, (dx, dy) in {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}.items():
            _teleport(env, x, y, "north")
            env.t, env.done = 0, False
            obs = env._observe()
            i, j = env.R + dy, env.R + dx
            predicted = obs["local"]["blocked"][i][j]
            _, info, _ = env.step(d)
            if env._reached():
                env._current()["navigate"]["reached"] = False
                continue
            assert predicted == (info["outcome"] == "collided"), (x, y, d)
            checked += 1
    assert checked > 100


def test_engine_world_matches_layout_world():
    env, _ = _place_env(DEV[3])
    rebuilt = L.build_world(env.layout)
    for y in range(24):
        for x in range(24):
            for z in range(3):
                assert W.get_block(rebuilt, x, y, z) == W.get_block(env._world, x, y, z)


# --- conditions ---------------------------------------------------------------------------

def _grid_at(env, cond, t, x, y, facing):
    env.reset(DEV[0], cond)
    _teleport(env, x, y, facing)
    env.t = t
    return env._observe()["local"]


def test_masked_cells_are_zero_and_known_impairments_follow_the_window():
    env = RobustNavEnv()
    lay = L.make_layout(env.rng_ns, DEV[0], env.config["layout"], grid_radius=env.R)
    x, y = lay["start"]
    R = env.R
    loc = _grid_at(env, "short_range", 0, x, y, "north")
    for i in range(2 * R + 1):
        for j in range(2 * R + 1):
            inside = max(abs(i - R), abs(j - R)) <= 2
            assert loc["valid"][i][j] == int(inside)
            if not inside:
                assert loc["blocked"][i][j] == 0 and loc["beacon"][i][j] == 0
    assert all(all(r) for r in _grid_at(env, "blind_transient", 9, x, y, "north")["valid"])
    blind = _grid_at(env, "blind_transient", 10, x, y, "north")
    assert not any(any(r) for r in blind["valid"]) and not any(any(r) for r in blind["blocked"])
    assert all(all(r) for r in _grid_at(env, "blind_transient", 40, x, y, "north")["valid"])
    assert not any(any(r) for r in _grid_at(env, "blind_sustained", 99, x, y, "north")["valid"])


@pytest.mark.parametrize("facing,left_cells", [
    ("north", lambda dx, dy: dx < 0), ("south", lambda dx, dy: dx > 0),
    ("east", lambda dx, dy: dy < 0), ("west", lambda dx, dy: dy > 0)])
def test_hemifield_is_body_left_in_the_world_grid(facing, left_cells):
    env = RobustNavEnv()
    lay = L.make_layout(env.rng_ns, DEV[0], env.config["layout"], grid_radius=env.R)
    loc = _grid_at(env, "hemi_left_sustained", 20, *lay["start"], facing)
    R = env.R
    for i in range(2 * R + 1):
        for j in range(2 * R + 1):
            dx, dy = j - R, i - R
            assert loc["valid"][i][j] == int(not left_cells(dx, dy)), (facing, dx, dy)


def test_body_frame_puts_heading_up_and_left_on_the_left():
    wenv, benv = RobustNavEnv(frame="world"), RobustNavEnv(frame="body")
    lay = L.make_layout(wenv.rng_ns, DEV[4], wenv.config["layout"], grid_radius=wenv.R)
    x, y = lay["start"]
    R = wenv.R
    for facing in ("north", "east", "south", "west"):
        w = _grid_at(wenv, "nominal", 0, x, y, facing)
        b = _grid_at(benv, "nominal", 0, x, y, facing)
        for i in range(2 * R + 1):
            for j in range(2 * R + 1):
                dx, dy = body_to_world(R - i, j - R, facing)
                assert b["blocked"][i][j] == w["blocked"][R + dy][R + dx]
        hb = _grid_at(benv, "hemi_left_sustained", 20, x, y, facing)["valid"]
        for i in range(2 * R + 1):
            assert [hb[i][j] for j in range(2 * R + 1)] == [0] * R + [1] * (R + 1)


def test_noise_is_undetected_and_leaves_the_world_alone():
    env = RobustNavEnv()
    env.reset(DEV[5], "noise")
    clean = RobustNavEnv()
    clean_obs = clean.reset(DEV[5], "nominal")
    clean_blocked = ["".join(map(str, r)) for r in clean_obs["local"]["blocked"]]
    flips = 0
    for _ in range(40):
        obs, info, done = env.step("wait")
        row = env.trajectory[-1]
        assert all(all(c == "1" for c in r) for r in row["obs"]["valid"])
        flips += sum(a != b for ra, rb in zip(row["obs"]["blocked"], row["true"]["blocked"]) for a, b in zip(ra, rb))
        assert row["obs"]["blocked"][env.R][env.R] == "0"
        assert row["true"]["blocked"] == clean_blocked          # the world itself is untouched
    assert flips > 0


# --- RNG separation and determinism ------------------------------------------------------------

class _Scripted(Policy):
    """A fixed action sequence that burns a variable amount of its own RNG."""
    def __init__(self, burn):
        self.burn = burn

    def reset(self, seed=0):
        super().reset(seed)
        self.k = 0

    def act(self, obs, info):
        for _ in range(self.burn * (self.k % 5)):
            self.rng.random()
        self.k += 1
        return ("north", "east", "south", "west")[(self.k // 4) % 4]


def test_controller_rng_use_does_not_move_the_sensor_schedule():
    a, b = RobustNavEnv(), RobustNavEnv()
    run_episode(a, _Scripted(0), DEV[6], "noise")
    run_episode(b, _Scripted(97), DEV[6], "noise")
    assert [r["obs"] for r in a.trajectory] == [r["obs"] for r in b.trajectory]


def test_same_seed_same_episode_and_conditions_share_the_layout():
    a, b = RobustNavEnv(), RobustNavEnv()
    ra = run_episode(a, POLICIES["seek_and_sweep"](), DEV[7], "hemi_right_transient")
    rb = run_episode(b, POLICIES["seek_and_sweep"](), DEV[7], "hemi_right_transient")
    assert ra == {**rb, "act_ms_total": ra["act_ms_total"]} and a.trajectory[-1]["pos"] == b.trajectory[-1]["pos"]
    b.reset(DEV[7], "blind_sustained")
    assert a.layout == b.layout
    # a policy that never looks is unaffected by any sensor condition
    runs = {c: run_episode(RobustNavEnv(), RandomWalk(), DEV[7], c) for c in ("nominal", "blind_sustained", "noise")}
    assert len({json.dumps([r["end_turn"], r["reached"], r["counts"]]) for r in runs.values()}) == 1
    assert controller_seed(DEV[7]) != DEV[7] and controller_seed(DEV[7], 1) != controller_seed(DEV[7])


# --- seeds and layouts ----------------------------------------------------------------------------

def test_seed_splits_are_disjoint_new_and_reachable():
    dev, tune = seeds.load("dev"), seeds.load("tune")
    assert not set(dev) & set(tune) and not (set(dev) | set(tune)) & set(range(21))
    with pytest.raises(LookupError):
        seeds.load("final")
    env = RobustNavEnv()
    for s in dev + tune:
        lay = L.make_layout(env.rng_ns, s, env.config["layout"], grid_radius=env.R)
        world = L.build_world(lay)
        (sx, sy), (gx, gy) = lay["start"], lay["goal"]
        assert max(abs(sx - gx), abs(sy - gy)) > env.R
        assert L.distance_map(world, (gx, gy))[(sx, sy)] == lay["shortest"] >= 12
    assert L.make_layout(env.rng_ns, dev[0], env.config["layout"], grid_radius=env.R) == \
        L.make_layout(env.rng_ns, dev[0], env.config["layout"], grid_radius=env.R)


def test_sealed_final_manifest_matches_when_present():
    path = Path(__file__).resolve().parents[1] / "state/robust-nav/final-seeds-v0.json"
    if not path.exists():
        pytest.skip("final manifest is sealed and not on this machine")
    final = seeds.verify_final(path)
    assert len(final) == 100 and not set(final) & (set(seeds.load("dev")) | set(seeds.load("tune")))
    m = json.loads(seeds.MANIFEST_V0.read_text())
    assert m["splits"]["final"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


# --- episode, metrics, harness ----------------------------------------------------------------------

def test_budget_end_and_reward():
    env, _ = _place_env(DEV[8])
    total = 0.0
    for k in range(env.budget):
        obs, info, done = env.step("wait")
        total += info["reward"]
        if k < env.budget - 1:
            assert not done and "end" not in info
    assert done and info["end"] == "budget"
    assert total == pytest.approx(env.budget * env.reward["step"])
    m = env.metrics()
    assert m["reached"] is False and m["spl"] == 0.0 and m["end_turn"] == env.budget
    assert m["longest_stationary_run"] == env.budget and m["rates"]["waited"] == 1.0
    with pytest.raises(AssertionError):
        env.step("north")


def test_reaching_scores_spl_and_success_reward():
    env, _ = _place_env(DEV[9])
    goal = tuple(env.layout["goal"])
    dist = L.distance_map(env._world, goal)
    while True:
        x, y = env._pos()
        d = min(("north", "south", "east", "west"),
                key=lambda d: dist.get((x + {"east": 1, "west": -1}.get(d, 0), y + {"south": 1, "north": -1}.get(d, 0)), 10**6))
        obs, info, done = env.step(d)
        if done:
            break
    assert info["end"] == "reached" and info["reward"] == pytest.approx(env.reward["step"] + env.reward["success"])
    m = env.metrics()
    assert m["reached"] and m["end_turn"] == m["shortest"] and m["spl"] == 1.0
    assert m["search_steps"] is not None and m["approach_steps"] == m["end_turn"] - m["search_steps"]


def test_transient_condition_reports_resume_and_recovery():
    r = run_episode(RobustNavEnv(), POLICIES["seek_and_sweep"](), DEV[0], "blind_transient")
    imp = r["impairment"]
    assert imp["onset"] == 10 and imp["release"] == 40 and imp["resume_steps"] >= 1
    rec = imp["recovery"]
    assert rec is None or set(rec) >= {"new_cells", "geo_progress", "reached_in_window", "recovered"}
    s = run_episode(RobustNavEnv(), POLICIES["seek_and_sweep"](), DEV[0], "blind_sustained")
    assert s["impairment"]["recovery"] is None


class _Flaky(Policy):
    def act(self, obs, info):
        if obs["t"] % 3 == 1:
            raise TimeoutError("brain call timed out")
        return "east"


def test_infra_failure_is_a_recorded_wait_not_a_dropped_step(tmp_path):
    env = RobustNavEnv()
    r = run_episode(env, _Flaky(), DEV[10], "nominal", save_to=tmp_path / "traj.jsonl.gz")
    assert r["infra_fail"] > 0 and (r["reached"] or r["end_turn"] == env.budget)
    fails = [row for row in env.trajectory if row["meta"].get("infra_fail")]
    assert all(row["outcome"] == "waited" for row in fails)
    import gzip
    lines = gzip.open(tmp_path / "traj.jsonl.gz", "rt").read().splitlines()
    assert json.loads(lines[0])["kind"] == "header" and len(lines) == len(env.trajectory) + 1
