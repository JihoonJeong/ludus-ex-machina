"""robust_nav v0.3: replay export and the viewer route (Yeoul 157)."""

import importlib.util
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from lxm.envs.robust_nav import RobustNavEnv, seeds
from lxm.envs.robust_nav.baselines import ALL_POLICIES, run_episode

ROOT = Path(__file__).resolve().parents[1]
DEV = seeds.load("dev")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EXP = _load("robust_nav_export_replay", ROOT / "scripts" / "robust_nav_export_replay.py")


def test_replay_carries_the_world_rows_and_recomputed_metrics(tmp_path):
    env = RobustNavEnv("task_b_v0.2")
    r = run_episode(env, ALL_POLICIES["cue_sweep"](), DEV[0], "cue_loss_transient", save_to=tmp_path / "t.jsonl.gz")
    header, rows = EXP.read_trajectory(tmp_path / "t.jsonl.gz")
    rp = EXP.build_replay(header, rows, policy="cue_sweep")
    dims = rp["world"]["dimensions"]
    assert len(rp["world"]["layers"]) == dims["z"] and len(rp["world"]["layers"][0]) == dims["y"]
    assert rp["rows"] == env.trajectory and rp["header"]["condition"] == "cue_loss_transient"
    m = rp["metrics"]
    assert m is not None and (m["reached"], m["end_turn"], m["spl"], m["counts"]) == \
        (r["reached"], r["end_turn"], r["spl"], r["counts"])
    for row in rp["rows"]:                      # everything the page shows per step is there
        assert {"pos", "heading", "obs", "true", "outcome", "impaired", "cue"} <= set(row)


def test_metrics_are_dropped_when_the_config_hash_does_not_match(tmp_path):
    env = RobustNavEnv("task_a_v0.2")
    run_episode(env, ALL_POLICIES["random_walk"](), DEV[1], "nominal", save_to=tmp_path / "t.jsonl.gz")
    header, rows = EXP.read_trajectory(tmp_path / "t.jsonl.gz")
    header["config_sha256"] = "0" * 64
    assert EXP.build_replay(header, rows)["metrics"] is None


def test_index_replaces_by_name_and_names_carry_the_frame(tmp_path):
    out = tmp_path / "replays"
    for frame in ("world", "body", "world"):
        env = RobustNavEnv("task_a_v0.2", frame=frame)
        run_episode(env, ALL_POLICIES["random_walk"](), DEV[2], "hemi_left_transient", save_to=tmp_path / "t.jsonl")
        header, rows = EXP.read_trajectory(tmp_path / "t.jsonl")
        name = EXP.replay_name(header, "random_walk", 0)
        EXP.write(out, name, EXP.build_replay(header, rows, policy="random_walk"))
    idx = json.loads((out / "index.json").read_text())
    names = [e["name"] for e in idx["replays"]]
    assert len(names) == 2 and len(set(names)) == 2 and any(n.endswith("__body") for n in names)
    for e in idx["replays"]:
        assert (out / e["file"]).is_file() and e["steps"] == 100 and e["end"] == "budget"


def test_from_smoke_pairs_transient_runs_with_their_nominal_twin(tmp_path):
    smoke = tmp_path / "smoke"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "robust_nav_smoke.py"), "--config", "task_a_v0.2",
                    "--split", "dev", "--policies", "seek_and_sweep", "--conditions", "nominal,blind_transient",
                    "--out", str(smoke)], check=True, capture_output=True, cwd=ROOT)
    got = list(EXP.from_smoke(smoke, ["seek_and_sweep"], ["blind_transient", "nominal"], [DEV[3]], 0))
    assert {h["condition"] for h, *_ in got} == {"blind_transient", "nominal"}
    for header, rows, pol, rep, metrics, pair in got:
        assert metrics["seed"] == DEV[3] and len(rows) == metrics["end_turn"] + 1
        if header["condition"] == "nominal":
            assert pair is None
        else:
            assert pair["release"] == 40 and pair["reach"] in ("both", "nominal_only", "impaired_only", "neither")


# --- the viewer route ------------------------------------------------------------------

@pytest.fixture
def viewer(tmp_path, monkeypatch):
    vs = _load("lxm_viewer_server", ROOT / "viewer" / "server.py")
    monkeypatch.setattr(vs, "ROBUST_NAV_REPLAYS", tmp_path)
    (tmp_path / "index.json").write_text(json.dumps({"format": 1, "replays": []}))
    (tmp_path / "secret.txt").write_text("not json")
    srv = vs.ThreadingHTTPServer(("127.0.0.1", 0), vs.ViewerHandler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _status(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def test_viewer_serves_replays_and_nothing_else(viewer):
    assert _status(f"{viewer}/robust-nav-data/index.json") == (200, {"format": 1, "replays": []})
    assert _status(f"{viewer}/robust-nav-data/missing.json")[0] == 404
    assert _status(f"{viewer}/robust-nav-data/secret.txt")[0] == 400
    assert _status(f"{viewer}/robust-nav-data/../../state/lxm.seed")[0] in (400, 404)
    assert _status(f"{viewer}/robust-nav-data/a/../../x.json")[0] in (400, 404)
    with urllib.request.urlopen(f"{viewer}/robust_nav.html", timeout=5) as r:
        page = r.read().decode()
    assert r.status == 200 and "robust_nav.js" in page and "Evaluator only" in page


def test_a_reduced_input_controller_is_labelled_with_its_own_packets(tmp_path):
    """Yeoul 158: a controller that reads its own encoding must not look as if
    it read the env grid."""
    env = RobustNavEnv("task_b_v0.2", frame="body")
    run_episode(env, ALL_POLICIES["random_walk"](), DEV[4], "nominal", save_to=tmp_path / "t.jsonl")
    (tmp_path / "p.jsonl").write_text("".join(json.dumps({"t": t, "contact": [0, 0]}) + "\n" for t in range(0, 101, 2)))
    header, rows = EXP.read_trajectory(tmp_path / "t.jsonl")
    packets = EXP.read_policy_input(tmp_path / "p.jsonl")
    rp = EXP.build_replay(header, rows, policy="fly", info_condition="reduced: contact 2 bit", policy_input=packets)
    assert rp["info_condition"] == "reduced: contact 2 bit" and rp["policy_input"]["4"] == {"t": 4, "contact": [0, 0]}
    assert "5" not in rp["policy_input"]
    name = EXP.replay_name(header, "fly", 0)
    e = EXP.write(tmp_path / "out", name, rp)
    assert e["info_condition"] == "reduced: contact 2 bit"
    plain = EXP.build_replay(header, rows, policy="rw")
    assert plain["info_condition"] is None and plain["policy_input"] is None
