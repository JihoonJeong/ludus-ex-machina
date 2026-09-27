"""Export robust_nav trajectories as replays for viewer/static/robust_nav.html.

    # from a smoke directory (filter it: a whole smoke is thousands of episodes)
    .venv/bin/python scripts/robust_nav_export_replay.py \
        --smoke state/robust-nav/smoke-v0.2-b-dev \
        --policies cue_sweep,cue_follow --conditions nominal,blind_transient,ood_deadends --seeds 855072156
    # or single trajectory files
    .venv/bin/python scripts/robust_nav_export_replay.py --traj path/to/traj.jsonl.gz
    # a controller that reads its own encoded packet, not the env grid (Yeoul 158):
    .venv/bin/python scripts/robust_nav_export_replay.py --traj traj.jsonl.gz --policy-name fly_fafb \
        --info-condition "reduced: contact 2 bit + cue cos/sin" --policy-input policy.jsonl

    python viewer/server.py      # then open http://localhost:8080/robust_nav.html

A replay is evaluator data: it carries the voxel world rebuilt from the layout,
the header, every evaluator row (position, the observation delivered to the
policy, the true grids, cause, meta) and, from a smoke, the episode metrics
and the pair with its nominal twin. The page keeps what the policy received
and what only the evaluator knows in separate panels. Replays go to
state/robust-nav/replays/ (not committed) with an index.json the page lists.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxm.envs.robust_nav import layouts as L  # noqa: E402
from lxm.envs.robust_nav.env import load_config  # noqa: E402
from lxm.envs.robust_nav.metrics import episode_metrics, pair_recovery  # noqa: E402

FORMAT = 1
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "state" / "robust-nav" / "replays"


def read_trajectory(path) -> tuple[dict, list[dict]]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert lines and lines[0].get("kind") == "header", f"{path}: no header row"
    return lines[0], lines[1:]


def _metrics_for(header, rows):
    """Recompute metrics when the header's config resolves to the same hash."""
    try:
        cfg, sha = load_config(header.get("config") or None)
    except (OSError, KeyError, ValueError):
        return None
    if sha != header.get("config_sha256"):
        return None
    return episode_metrics(rows, header["layout"], header["condition_spec"], cfg, header=header)


def read_policy_input(path) -> dict:
    """A controller's own per-step input (what its encoder made from the env
    observation): jsonl, one object per step, keyed by its "t" (observation
    index) or else by line number from 0."""
    steps = {}
    with open(path, encoding="utf-8") as f:
        for k, line in enumerate(x for x in f if x.strip()):
            rec = json.loads(line)
            t = rec.get("t", k) if isinstance(rec, dict) else k
            steps[str(t)] = rec
    return steps


def build_replay(header: dict, rows: list[dict], *, policy=None, rep=0, metrics=None, pair=None,
                 info_condition=None, policy_input=None) -> dict:
    world = L.build_world(header["layout"])
    if metrics is None:
        metrics = _metrics_for(header, rows)
    return {
        "kind": "robust_nav_replay", "format": FORMAT,
        "policy": policy, "rep": rep,
        "header": header,
        "world": {"dimensions": world["dimensions"], "layers": world["layers"]},
        "rows": rows,
        "metrics": metrics,
        "pair": pair,
        # what the controller actually read: None = the env observation as is;
        # a label (and optionally its per-step packets) when it read its own encoding
        "info_condition": info_condition,
        "policy_input": policy_input,
    }


def replay_name(header: dict, policy, rep) -> str:
    frame = "" if header.get("frame", "world") == "world" else f"__{header['frame']}"
    return f"{header.get('task') or 'task'}__{header['condition']}__{policy or 'policy'}__{header['seed']}-r{rep}{frame}"


def index_entry(name: str, replay: dict) -> dict:
    h, m = replay["header"], replay["metrics"] or {}
    return {"name": name, "file": f"{name}.json", "task": h.get("task"), "version": h.get("version"),
            "condition": h["condition"], "family": h["layout"].get("family"), "seed": h["seed"],
            "policy": replay["policy"], "rep": replay["rep"], "frame": h.get("frame"),
            "end": h.get("end") or m.get("end"), "steps": len(replay["rows"]) - 1,
            "info_condition": replay.get("info_condition"),
            "reached": m.get("reached"), "spl": m.get("spl")}


def write(out: Path, name: str, replay: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(replay, separators=(",", ":")), encoding="utf-8")
    idx_path = out / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else {"format": FORMAT, "replays": []}
    entry = index_entry(name, replay)
    idx["replays"] = [e for e in idx["replays"] if e["name"] != name] + [entry]
    idx["replays"].sort(key=lambda e: (e["task"] or "", e["condition"], e["policy"] or "", e["seed"], e["rep"]))
    idx_path.write_text(json.dumps(idx, indent=1) + "\n", encoding="utf-8")
    return entry


def from_smoke(smoke: Path, policies, conditions, seeds, rep: int):
    results = [json.loads(line) for line in (smoke / "results.jsonl").read_text().splitlines() if line.strip()]
    key = lambda r: (r["policy"], r["condition"], r["seed"], r["rep"])  # noqa: E731
    by_key = {key(r): r for r in results}
    for r in results:
        if r["rep"] != rep or (policies and r["policy"] not in policies) \
                or (conditions and r["condition"] not in conditions) or (seeds and r["seed"] not in seeds):
            continue
        traj = smoke / "trajectories" / r["policy"] / r["condition"] / f"{r['seed']}-r{r['rep']}.jsonl.gz"
        if not traj.exists():
            print(f"  missing trajectory {traj} (smoke run with --no-trajectories?)")
            continue
        header, rows = read_trajectory(traj)
        twin = by_key.get((r["policy"], "nominal", r["seed"], r["rep"]))
        pair = pair_recovery(r, twin) if (twin and r["condition"] != "nominal"
                                          and (r.get("impairment") or {}).get("release") is not None) else None
        yield header, rows, r["policy"], r["rep"], r, pair


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=Path)
    ap.add_argument("--traj", type=Path, nargs="*")
    ap.add_argument("--policies", default="")
    ap.add_argument("--conditions", default="")
    ap.add_argument("--seeds", default="")
    ap.add_argument("--rep", type=int, default=0)
    ap.add_argument("--policy-name", default=None, help="policy label for --traj files")
    ap.add_argument("--info-condition", default=None,
                    help="what the controller read, when not the env observation as is (--traj)")
    ap.add_argument("--policy-input", type=Path, default=None,
                    help="jsonl of the controller's own per-step input packets (one --traj only)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    if not a.smoke and not a.traj:
        ap.error("give --smoke DIR or --traj FILE ...")
    split = lambda s: [x for x in s.split(",") if x]  # noqa: E731
    n = 0
    if a.smoke:
        seeds = [int(x) for x in split(a.seeds)]
        for header, rows, pol, rep, metrics, pair in from_smoke(a.smoke, split(a.policies), split(a.conditions),
                                                                seeds, a.rep):
            name = replay_name(header, pol, rep)
            e = write(a.out, name, build_replay(header, rows, policy=pol, rep=rep, metrics=metrics, pair=pair))
            print(f"  {name}  end={e['end']} steps={e['steps']}")
            n += 1
    if a.policy_input and len(a.traj or []) != 1:
        ap.error("--policy-input goes with exactly one --traj")
    packets = read_policy_input(a.policy_input) if a.policy_input else None
    for path in a.traj or []:
        header, rows = read_trajectory(path)
        name = replay_name(header, a.policy_name, a.rep)
        e = write(a.out, name, build_replay(header, rows, policy=a.policy_name, rep=a.rep,
                                            info_condition=a.info_condition, policy_input=packets))
        print(f"  {name}  end={e['end']} steps={e['steps']}")
        n += 1
    print(f"{n} replay(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
