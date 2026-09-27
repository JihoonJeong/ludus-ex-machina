"""robust_nav v0.1.1 (metrics after Yeoul 153/154) and v0.2 (task B cue,
condition 6 OOD structure) — Yeoul 155."""

import json
import math

import pytest

from lxm.envs.robust_nav import RobustNavEnv, load_config
from lxm.envs.robust_nav import layouts as L
from lxm.envs.robust_nav import seeds
from lxm.envs.robust_nav.baselines import (ALL_POLICIES, POLICIES, AbortEpisode, Policy, run_episode)
from lxm.envs.robust_nav.metrics import WINDOW_STATUSES, pair_recovery, paired_summary
from lxm.envs.robust_nav.sensors import body_to_world, world_to_body

DEV = seeds.load("dev")


def _run(cfg, policy, cond, seeds_=DEV):
    env = RobustNavEnv(cfg)
    out = []
    for s in seeds_:
        r = run_episode(env, ALL_POLICIES[policy](), s, cond)
        r["policy"] = policy
        out.append(r)
    return out


# --- v0.1 is preserved -------------------------------------------------------------------

@pytest.mark.parametrize("policy,cond,reached", [
    ("seek_reactive", "nominal", 11), ("seek_reactive", "hemi_left_sustained", 1),
    ("seek_and_sweep", "nominal", 10), ("seek_and_sweep", "hemi_left_sustained", 7),
    ("seek_and_sweep", "noise", 7), ("seek_and_sweep", "blind_sustained", 4)])
def test_v01_dev_numbers_reproduce(policy, cond, reached):
    """The LxM 097 table, which Yeoul reproduced (154)."""
    rs = _run(None, policy, cond)
    assert sum(r["reached"] for r in rs) == reached
    if (policy, cond) == ("seek_and_sweep", "nominal"):
        assert round(sum(r["spl"] for r in rs) / len(rs), 4) == 0.5201


def test_v02_configs_extend_v01_unchanged():
    base, base_sha = load_config()
    assert base["version"] == "robust_nav_v0.1.1"
    for name in ("task_a_v0.2", "task_b_v0.2"):
        cfg, sha = load_config(name)
        assert sha != base_sha and cfg["rng_namespace"] == base["rng_namespace"]
        for cid, c in base["conditions"].items():
            assert cfg["conditions"][cid] == c
        for k in ("grid_radius", "budget", "reward", "layout", "actions", "occlusion"):
            assert cfg[k] == base[k]
    a = [r["end_turn"] for r in _run("task_a_v0.2", "seek_and_sweep", "hemi_right_transient", DEV[:4])]
    b = [r["end_turn"] for r in _run(None, "seek_and_sweep", "hemi_right_transient", DEV[:4])]
    assert a == b


# --- v0.1.1: time, infra cause, abort ---------------------------------------------------------

def test_t_is_the_observation_index_and_windows_are_half_open():
    env = RobustNavEnv()
    obs = env.reset(DEV[0], "blind_transient")
    assert obs["t"] == 0 and obs["last"] == {"action": None, "outcome": None, "bump_side": None}
    for k in range(1, 45):
        obs, info, done = env.step("wait")
        assert obs["t"] == info["t"] == k == len(env.trajectory) - 1
    imp = {r["t"]: r["impaired"] for r in env.trajectory}
    assert (imp[9], imp[10], imp[39], imp[40]) == (False, True, True, False)
    assert all(set(r) == {"0"} for r in env.trajectory[10]["obs"]["valid"])
    assert all(set(r) == {"1"} for r in env.trajectory[40]["obs"]["valid"])


class _Flaky(Policy):
    def reset(self, seed=0):
        super().reset(seed)
        self.seen = []

    def act(self, obs, info):
        self.seen.append(json.dumps([obs, info]))
        if obs["t"] % 3 == 1:
            raise TimeoutError("provider said: quota exceeded for key sk-XYZ")
        return ("east", "south", "west", "north")[obs["t"] % 4]


def test_infra_waits_are_counted_apart_and_never_reach_the_policy():
    env = RobustNavEnv()
    pol = _Flaky()
    r = run_episode(env, pol, DEV[1], "nominal")
    assert r["counts"]["infra_wait"] == r["infra_fail"] > 0
    assert r["counts"]["waited"] == 0                      # the policy itself never waited
    assert sum(r["counts"].values()) == r["end_turn"]
    infra_rows = [row for row in env.trajectory[1:] if row["cause"] == "infra"]
    assert len(infra_rows) == r["infra_fail"] and all(row["outcome"] == "waited" for row in infra_rows)
    assert all(row["cause"] == "policy" for row in env.trajectory[1:] if not row["meta"].get("infra_fail"))
    assert not any("quota" in s or "sk-XYZ" in s or "infra" in s for s in pol.seen)


class _Quitter(Policy):
    def act(self, obs, info):
        if obs["t"] == 5:
            raise AbortEpisode("driver safety budget: 5 calls")
        return "east"


def test_abort_is_kept_with_reason_and_steps(tmp_path):
    env = RobustNavEnv()
    r = run_episode(env, _Quitter(), DEV[2], "nominal", save_to=tmp_path / "t.jsonl")
    assert r["end"] == "aborted" and r["end_turn"] == 5 and "safety budget" in r["abort_reason"]
    assert r["reached"] is False and r["spl"] == 0.0
    head = json.loads((tmp_path / "t.jsonl").read_text().splitlines()[0])
    assert head["end"] == "aborted" and head["steps"] == 5


# --- v0.1.1: paired recovery ---------------------------------------------------------------

def test_every_episode_carries_windows_and_pairs_are_honest():
    nom = {r["seed"]: r for r in _run(None, "seek_and_sweep", "nominal")}
    imp = _run(None, "seek_and_sweep", "blind_transient")
    pairs = []
    for r in imp:
        assert set(nom[r["seed"]]["windows"]) == {"40"}
        p = pair_recovery(r, nom[r["seed"]])
        pairs.append(p)
        assert p["impaired_status"] in WINDOW_STATUSES and p["nominal_status"] in WINDOW_STATUSES
        for k in ("new_cells", "geo_progress"):
            if p["comparable"]:
                assert p[k]["diff"] == p[k]["impaired"] - p[k]["nominal"]
            else:
                assert p[k]["diff"] is None
        for side in ("impaired", "nominal"):
            if p[f"{side}_status"] in ("reached_before_release", "ended_before_release"):
                assert p["new_cells"][side] is None and p["geo_progress"][side] is None   # not zero-filled
        assert p["reach"] in ("both", "nominal_only", "impaired_only", "neither")
        if p["reach"] == "both":
            assert p["delay"]["diff"] == r["end_turn"] - nom[r["seed"]]["end_turn"]
        else:
            assert p["delay"]["diff"] is None
    s = paired_summary(pairs)
    assert sum(s["reach"].values()) == s["n"] and s["delay_both_reached"]["n"] == s["reach"]["both"]
    assert s["n"] == len(imp) == sum(s["impaired_status"].values()) == sum(s["nominal_status"].values())
    assert s["comparable"] == sum(p["comparable"] for p in pairs)
    assert s["new_cells"]["diff"]["n"] == s["comparable"]
    assert s["subset_beacon_seen_before_release"]["n"] <= s["comparable"]
    with pytest.raises(AssertionError):
        pair_recovery(imp[0], nom[imp[1]["seed"]])


# --- v0.2: condition 6 (OOD structure) -----------------------------------------------------------

OOD = ("ood_corridors", "ood_deadends", "ood_detour")


def test_ood_keeps_start_goal_and_changes_only_obstacles():
    env = RobustNavEnv("task_a_v0.2")
    for s in DEV:
        env.reset(s, "nominal")
        base = env.layout
        for c in OOD:
            env.reset(s, c)
            o = env.layout
            for k in ("start", "goal", "heading", "terrain_seed", "dimensions", "seed"):
                assert o[k] == base[k]
            assert o["family"] == env.config["conditions"][c]["layout"]["family"] and o["base_family"] == "walls_v0"
            assert o["obstacles"] != base["obstacles"] and o["shortest_base"] == base["shortest"]
            world = L.build_world(o)
            assert L.walkable(world, *o["start"]) and L.walkable(world, *o["goal"])
            assert L.distance_map(world, tuple(o["goal"]))[tuple(o["start"])] == o["shortest"]
            assert 12 <= o["shortest"] <= 70
            walk = [(x, y) for y in range(24) for x in range(24) if L.walkable(world, x, y)]
            assert len(L.distance_map(world, tuple(o["start"]))) >= 0.9 * len(walk)   # no cut in two
            env.reset(s, c)
            assert env.layout == o                                                    # deterministic


def test_ood_families_differ_from_the_dev_family_where_they_should():
    env = RobustNavEnv("task_a_v0.2")
    stats = {c: [] for c in ("nominal",) + OOD}
    for s in DEV:
        for c in stats:
            env.reset(s, c)
            stats[c].append(L.structure_stats(env.layout))
    mean = lambda c, k: sum(r[k] for r in stats[c]) / len(stats[c])  # noqa: E731
    assert mean("ood_corridors", "corridor_cells") > 4 * mean("nominal", "corridor_cells")
    assert mean("ood_deadends", "dead_end_cells") > 10 * max(mean("nominal", "dead_end_cells"), 1)
    assert mean("ood_detour", "detour_ratio") > mean("nominal", "detour_ratio") + 0.2


# --- v0.2: task B cue -----------------------------------------------------------------------------

def _teleport(env, x, y, facing):
    a = env._agent()
    a["x"], a["y"], a["facing"] = x, y, facing


def _cue_at(env, cond, t, x, y, facing, seed=DEV[0]):
    env.reset(seed, cond)
    _teleport(env, x, y, facing)
    env.t = t
    return env._observe()


def test_task_b_obs_has_the_cue_and_task_a_does_not():
    a, b = RobustNavEnv("task_a_v0.2"), RobustNavEnv("task_b_v0.2")
    assert "cue" not in a.reset(DEV[0]) and "cue" not in a.spec()
    obs = b.reset(DEV[0])
    assert tuple(obs) == ("t", "heading", "last", "local", "cue") and set(obs["cue"]) == {"dir", "valid"}
    assert b.spec()["cue"]["distance"] is False and b.spec()["obs_keys"][-1] == "cue"


def test_cue_points_at_the_goal_with_no_distance():
    env = RobustNavEnv("task_b_v0.2")
    env.reset(DEV[0])
    gx, gy = env.layout["goal"]
    world = env._world
    checked = 0
    for x in range(24):
        for y in range(24):
            if not L.walkable(world, x, y) or (x, y) == (gx, gy):
                continue
            c = _cue_at(env, "nominal", 3, x, y, "north")["cue"]
            ux, uy = c["dir"]
            assert c["valid"] == 1 and abs(math.hypot(ux, uy) - 1) < 1e-3
            d = math.hypot(gx - x, gy - y)
            assert (ux * (gx - x) + uy * (gy - y)) / d > 0.999
            checked += 1
    assert checked > 300
    # same bearing, different distance -> the same cue
    same = {tuple(_cue_at(env, "nominal", 3, gx - k, gy, "east")["cue"]["dir"])
            for k in (1, 2, 3, 4) if L.walkable(world, gx - k, gy)}
    assert len(same) <= 1


def test_body_cue_is_the_world_cue_turned():
    w, b = RobustNavEnv("task_b_v0.2"), RobustNavEnv("task_b_v0.2", frame="body")
    lay = L.make_layout(w.rng_ns, DEV[1], w.config["layout"], grid_radius=w.R)
    x, y = lay["start"]
    for facing in ("north", "east", "south", "west"):
        cw = _cue_at(w, "nominal", 2, x, y, facing, DEV[1])["cue"]["dir"]
        cb = _cue_at(b, "nominal", 2, x, y, facing, DEV[1])["cue"]["dir"]
        back = body_to_world(cb[0], cb[1], facing)
        assert abs(back[0] - cw[0]) < 1e-3 and abs(back[1] - cw[1]) < 1e-3
        f, r = world_to_body(cw[0], cw[1], facing)
        assert abs(f - cb[0]) < 1e-3 and abs(r - cb[1]) < 1e-3


def test_sight_conditions_leave_the_cue_and_cue_conditions_leave_the_grid():
    env = RobustNavEnv("task_b_v0.2")
    lay = L.make_layout(env.rng_ns, DEV[2], env.config["layout"], grid_radius=env.R)
    x, y = lay["start"]
    ref = _cue_at(env, "nominal", 20, x, y, "west", DEV[2])
    for cond in ("short_range", "hemi_left_sustained", "blind_sustained", "noise"):
        assert _cue_at(env, cond, 20, x, y, "west", DEV[2])["cue"] == ref["cue"]
    lost = _cue_at(env, "cue_loss_transient", 20, x, y, "west", DEV[2])
    assert lost["cue"] == {"dir": [0.0, 0.0], "valid": 0} and lost["local"] == ref["local"]
    assert _cue_at(env, "cue_loss_transient", 40, x, y, "west", DEV[2])["cue"] == ref["cue"]
    assert _cue_at(env, "cue_loss_transient", 9, x, y, "west", DEV[2])["cue"] == ref["cue"]
    noisy = _cue_at(env, "cue_noise", 20, x, y, "west", DEV[2])
    assert noisy["cue"]["valid"] == 1 and noisy["local"] == ref["local"]
    assert noisy["cue"]["dir"] != ref["cue"]["dir"] and abs(math.hypot(*noisy["cue"]["dir"]) - 1) < 1e-3


class _Burner(Policy):
    def __init__(self, burn):
        self.burn = burn

    def reset(self, seed=0):
        super().reset(seed)
        self.k = 0

    def act(self, obs, info):
        for _ in range(self.burn * (self.k % 7)):
            self.rng.random()
        self.k += 1
        return ("north", "east", "south", "west")[(self.k // 3) % 4]


def test_cue_noise_schedule_ignores_controller_rng():
    a, b = RobustNavEnv("task_b_v0.2"), RobustNavEnv("task_b_v0.2")
    run_episode(a, _Burner(0), DEV[3], "cue_noise")
    run_episode(b, _Burner(53), DEV[3], "cue_noise")
    assert [r["cue"] for r in a.trajectory] == [r["cue"] for r in b.trajectory]


def test_a_cue_blind_policy_is_untouched_by_the_cue():
    a = _run("task_a_v0.2", "seek_and_sweep", "nominal", DEV[:6])
    b = _run("task_b_v0.2", "seek_and_sweep", "nominal", DEV[:6])
    assert [(r["reached"], r["end_turn"]) for r in a] == [(r["reached"], r["end_turn"]) for r in b]
    c = _run("task_b_v0.2", "seek_and_sweep", "cue_loss_sustained", DEV[:6])
    assert [(r["reached"], r["end_turn"]) for r in b] == [(r["reached"], r["end_turn"]) for r in c]


def test_cue_sweep_never_prefers_a_blocked_cell():
    """Regression: a blocked neighbour once outranked a much-visited open one,
    and the policy hammered the end of a dead-end alley."""
    from lxm.envs.robust_nav.baselines import CueSweep
    pol = CueSweep()
    pol.reset(0)
    pol.visits = {(0, 0): 1, (0, -1): 40}
    pol.felt = {(1, 0), (-1, 0), (0, 1)}
    obs = {"cue": {"dir": [0.0, 1.0], "valid": 1}, "local": {"frame": "world"}}
    assert min(("north", "east", "south", "west"), key=lambda d: pol._score(d, pol.blocked, obs)) == "north"
    rs = _run("task_b_v0.2", "cue_sweep", "ood_deadends")
    assert max(r["longest_stationary_run"] for r in rs) < 10


def test_cue_baselines_run_every_task_b_condition():
    env = RobustNavEnv("task_b_v0.2")
    for cond in env.config["conditions"]:
        for p in ("cue_follow", "cue_sweep"):
            r = run_episode(env, ALL_POLICIES[p](), DEV[4], cond)
            assert r["end"] in ("reached", "budget") and r["task"] == "cue_nav"
    assert set(POLICIES) < set(ALL_POLICIES)
