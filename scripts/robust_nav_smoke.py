"""robust_nav dev smoke: rule baselines x conditions on a seed split.

    .venv/bin/python scripts/robust_nav_smoke.py --split dev \
        --out state/robust-nav/smoke-v0.1-dev

Writes results.jsonl (one row per episode, every episode), summary.json
(per condition x policy), run.json (commit, config and manifest hashes,
command) and trajectories/<policy>/<condition>/<seed>.jsonl.gz, and prints the
table. The final split is sealed and refused here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lxm.envs.robust_nav import RobustNavEnv, seeds  # noqa: E402
from lxm.envs.robust_nav.baselines import POLICIES, run_episode  # noqa: E402


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    ok = [r for r in rows if r["reached"]]
    imp = [r["impairment"] for r in rows if r.get("impairment")]
    rec = [i["recovery"] for i in imp if i.get("recovery")]
    return {
        "n": n, "reached": len(ok),
        "end_turn_median_all": _med([r["end_turn"] for r in rows]),
        "spl_mean_all": _mean([r["spl"] for r in rows]),
        "spl_mean_success": _mean([r["spl"] for r in ok]),
        "rates_mean": {k: _mean([r["rates"][k] for r in rows]) for k in ("moved", "collided", "waited", "invalid")},
        "longest_stationary_run_median": _med([r["longest_stationary_run"] for r in rows]),
        "revisit_moves_mean": _mean([r["revisit_moves"] for r in rows]),
        "backtracks_mean": _mean([r["backtracks"] for r in rows]),
        "distinct_cells_mean": _mean([r["distinct_cells"] for r in rows]),
        "search_steps_median": _med([r["search_steps"] for r in rows]),
        "never_saw_beacon": sum(1 for r in rows if r["search_steps"] is None),
        "resume_steps_median": _med([i["resume_steps"] for i in imp]) if imp else None,
        "recovery_applicable": len(rec),
        "recovered": sum(1 for x in rec if x["recovered"]),
        "infra_fail": sum(r["infra_fail"] for r in rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "tune"])
    ap.add_argument("--conditions", default="all")
    ap.add_argument("--policies", default="all")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--frame", default="world")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-trajectories", action="store_true")
    a = ap.parse_args()

    env = RobustNavEnv(frame=a.frame)
    conds = list(env.config["conditions"]) if a.conditions == "all" else a.conditions.split(",")
    pols = list(POLICIES) if a.policies == "all" else a.policies.split(",")
    split = seeds.load(a.split)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    with (out / "results.jsonl").open("w") as f:
        for p in pols:
            for c in conds:
                for s in split:
                    for rep in range(a.reps):
                        traj = None
                        if not a.no_trajectories:
                            d = out / "trajectories" / p / c
                            d.mkdir(parents=True, exist_ok=True)
                            traj = d / f"{s}-r{rep}.jsonl.gz"
                        r = run_episode(env, POLICIES[p](), s, c, rep=rep, save_to=traj)
                        r["policy"] = p
                        rows.append(r)
                        f.write(json.dumps(r) + "\n")

    summary = {c: {p: summarize([r for r in rows if r["policy"] == p and r["condition"] == c]) for p in pols}
               for c in conds}
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "lxm/envs/robust_nav"],
                                capture_output=True, text=True).stdout.strip())
    (out / "run.json").write_text(json.dumps({
        "version": env.version, "commit": commit, "robust_nav_dirty": dirty,
        "config_sha256": env.config_sha256,
        "seeds_manifest_sha256": hashlib.sha256(seeds.MANIFEST_V0.read_bytes()).hexdigest(),
        "split": a.split, "seeds": split, "reps": a.reps, "frame": a.frame,
        "conditions": conds, "policies": {p: POLICIES[p].memory for p in pols},
        "command": " ".join(sys.argv),
    }, indent=1) + "\n")

    print(f"{'condition':22s} {'policy':15s} {'reach':>6s} {'SPL(all)':>8s} {'end':>5s} "
          f"{'coll':>5s} {'stuck':>5s} {'revis':>5s} {'search':>6s} {'resume':>6s} {'recov':>6s}")
    for c in conds:
        for p in pols:
            s = summary[c][p]
            recov = f"{s['recovered']}/{s['recovery_applicable']}" if s["recovery_applicable"] else "-"
            fmt = lambda v: "-" if v is None else f"{v:.3f}"  # noqa: E731
            num = lambda v: "-" if v is None else f"{v:.4g}"  # noqa: E731
            print(f"{c:22s} {p:15s} {s['reached']:>3d}/{s['n']:<2d} {fmt(s['spl_mean_all']):>8s} "
                  f"{num(s['end_turn_median_all']):>5s} {fmt(s['rates_mean']['collided']):>5s} "
                  f"{num(s['longest_stationary_run_median']):>5s} {num(s['revisit_moves_mean']):>5s} "
                  f"{num(s['search_steps_median']):>6s} {num(s['resume_steps_median']):>6s} {recov:>6s}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
