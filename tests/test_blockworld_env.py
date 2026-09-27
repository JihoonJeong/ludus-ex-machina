"""BlockworldEnv: the interface a connectome controller, a rule baseline and an
LLM share must not carry the map or the target, and must be reproducible."""

import json
import re


from games.blockworld.engine import BlockworldGame
from lxm.envs.blockworld_baselines import POLICIES, RandomWalk, SeekAndSweep, run_episode
from lxm.envs.blockworld_env import BlockworldEnv, layout_for_seed, shortest_path_len



def test_relative_observation_carries_no_position_map_or_target():
    env = BlockworldEnv("hidden_target_nav_01")
    obs = env.reset()
    blob = json.dumps(obs)
    assert set(obs) == {"turn", "agent", "view"}
    assert not {"x", "y", "z"} & set(obs["agent"])
    assert "dimensions" not in obs["view"] and "events" not in obs
    assert obs["view"]["items"] == []                          # the beacon starts out of sight
    for bucket in ("cells", "items", "agents"):
        for o in obs["view"][bucket]:
            assert not {"x", "y", "z"} & set(o)
    assert '"x"' not in blob


def test_the_llm_path_does_not_name_the_target_either():
    g = BlockworldGame("hidden_target_nav_01")
    tc = g._scenario["target_cell"]
    st = {"game": g.initial_state([{"agent_id": "a"}])}
    text = g.build_inline_prompt("a", st, 1) + g._scenario["goal"] + g._scenario["description"]
    assert not re.search(rf"{tc['x']}\s*,\s*{tc['y']}", text)
    assert "24x24" not in g._scenario["description"]


def test_seeded_layouts_are_deterministic_reachable_and_start_out_of_sight():
    base = BlockworldGame("hidden_target_nav_01")._scenario
    a, b = layout_for_seed(base, 7), layout_for_seed(base, 7)
    assert a == b and a != layout_for_seed(base, 8)
    for seed in range(1, 11):
        env = BlockworldEnv("hidden_target_nav_01")
        obs = env.reset(seed=seed)
        assert obs["view"]["items"] == []
        m = env.metrics()
        assert m["shortest"] is not None and m["shortest"] >= 12


def test_walking_into_the_wall_is_a_no_op_and_verbs_outside_the_subset_are_a_wait():
    env = BlockworldEnv("hidden_target_nav_01")
    env.reset()
    # start (4,4); the wall is at x=11 — walk east until blocked
    info = None
    for _ in range(10):
        _, info, _ = env.step("east")
        if info["no_op"]:
            break
    assert info["no_op"] and env._pos() == (10, 4)
    _, info, _ = env.step({"verb": "break", "direction": "east"})
    assert info["invalid"] and env._pos() == (10, 4)


def test_reaching_the_beacon_ends_the_episode_with_metrics():
    env = BlockworldEnv("hidden_target_nav_01")
    m = run_episode(env, SeekAndSweep(seed=0))
    assert m["reached"] and m["steps"] <= 100
    assert 0 < m["path_efficiency"] <= 1 and m["first_seen_step"] is not None
    assert m["search_steps"] + m["approach_steps"] == m["steps"]


def test_the_random_floor_and_the_sweep_differ_and_trajectories_are_written(tmp_path):
    env = BlockworldEnv("hidden_target_nav_01")
    r = run_episode(env, RandomWalk(seed=1), seed=3)
    env.save_trajectory(tmp_path / "t.jsonl")
    rows = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert rows[0]["t"] == 0 and len(rows) == r["steps"] + 1
    s = run_episode(BlockworldEnv("hidden_target_nav_01"), SeekAndSweep(seed=1), seed=3)
    assert s["reached"]


def test_a_smaller_view_radius_is_honoured():
    env = BlockworldEnv("hidden_target_nav_01", view_radius=2)
    obs = env.reset()
    assert obs["view"]["radius"] == 2
    assert all(abs(c["dx"]) <= 2 and abs(c["dy"]) <= 2 for c in obs["view"]["cells"])
