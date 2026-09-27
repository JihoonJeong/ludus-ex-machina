"""robust_nav dev smoke: rule baselines x conditions on a seed split.

    .venv/bin/python scripts/robust_nav_smoke.py --split dev \
        --out state/robust-nav/smoke-v0.1-dev
    .venv/bin/python scripts/robust_nav_smoke.py --config task_b_v0.2 --split dev \
        --out state/robust-nav/smoke-v0.2-b-dev

--config: task_a_v0.1 (default) | task_a_v0.2 | task_b_v0.2 | a path. Task B
runs the cue baselines too.

Writes results.jsonl (one row per episode, every episode), summary.json
(per condition x policy, with the paired-recovery summary for transient
conditions and structure stats for OOD conditions), run.json (commit, config
and manifest hashes, command) and trajectories/<policy>/<condition>/<seed>.jsonl.gz,
and prints the tables. The final split is sealed and refused here.
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
from lxm.envs.robust_nav import layouts as L  # noqa: E402
from lxm.envs.robust_nav.baselines import ALL_POLICIES, POLICIES, run_episode  # noqa: E402
from lxm.envs.robust_nav.metrics import pair_recovery, paired_summary  # noqa: E402


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
        "rates_mean": {k: _mean([r["rates"].get(k) for r in rows])
                       for k in ("moved", "collided", "waited", "invalid", "infra_wait")},
        "end": {e: sum(1 for r in rows if r.get("end") == e) for e in ("reached", "budget", "aborted")},
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
    ap.add_argument("--config", default="task_a_v0.1")
    ap.add_argument("--split", default="dev", choices=["dev", "tune"])
    ap.add_argument("--conditions", default="all")
    ap.add_argument("--policies", default="all")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--frame", default="world")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-trajectories", action="store_true")
    a = ap.parse_args()

    env = RobustNavEnv(a.config, frame=a.frame)
    conds = list(env.config["conditions"]) if a.conditions == "all" else a.conditions.split(",")
    catalogue = ALL_POLICIES if env.task == "cue_nav" else POLICIES
    pols = list(catalogue) if a.policies == "all" else a.policies.split(",")
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
                        r = run_episode(env, ALL_POLICIES[p](), s, c, rep=rep, save_to=traj)
                        r["policy"] = p
                        rows.append(r)
                        f.write(json.dumps(r) + "\n")

    summary = {c: {p: summarize([r for r in rows if r["policy"] == p and r["condition"] == c]) for p in pols}
               for c in conds}
    # paired recovery: each transient-condition episode against its nominal twin
    key = lambda r: (r["policy"], r["seed"], r["rep"])  # noqa: E731
    nominal = {key(r): r for r in rows if r["condition"] == "nominal"}
    transient = [c for c in conds if (env.config["conditions"][c].get("window") or [0, None])[1] is not None
                 and env.config["conditions"][c].get("impairment")]
    if nominal:
        for c in transient:
            for p in pols:
                pairs = [pair_recovery(r, nominal[key(r)]) for r in rows
                         if r["policy"] == p and r["condition"] == c and key(r) in nominal]
                summary[c][p]["paired_recovery"] = paired_summary(pairs)
    # OOD structure: what the family changed, per condition (policy-independent)
    struct = {}
    for c in conds:
        spec = env.config["conditions"][c]
        if c == "nominal" or spec.get("layout"):
            st = []
            for s in split:
                env.reset(s, c)
                st.append(L.structure_stats(env.layout))
            struct[c] = {k: _mean([x[k] for x in st]) for k in
                         ("shortest", "detour_ratio", "dead_end_cells", "corridor_cells", "walkable")}
    summary["_structure"] = struct
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "lxm/envs/robust_nav"],
                                capture_output=True, text=True).stdout.strip())
    (out / "run.json").write_text(json.dumps({
        "version": env.version, "config": a.config, "task": env.task, "commit": commit, "robust_nav_dirty": dirty,
        "config_sha256": env.config_sha256,
        "seeds_manifest_sha256": hashlib.sha256(seeds.MANIFEST_V0.read_bytes()).hexdigest(),
        "split": a.split, "seeds": split, "reps": a.reps, "frame": a.frame,
        "conditions": conds, "policies": {p: ALL_POLICIES[p].memory for p in pols},
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
    if any("paired_recovery" in summary[c][p] for c in transient for p in pols):
        print("paired recovery (impaired vs its nominal twin, observation window release < t <= release+W)")
        print(f"{'condition':22s} {'policy':15s} {'N':>3s} {'imp pre/in/full/trunc':>22s} {'nom pre/in/full/trunc':>22s} "
              f"{'comp':>4s} {'dNew':>6s} {'dGeo':>6s} {'reachW i/n':>10s} {'both/nom/imp/nei':>16s} {'delay':>6s}")
        for c in transient:
            for p in pols:
                pr = summary[c][p].get("paired_recovery")
                if not pr:
                    continue
                st4 = lambda d: f"{d['reached_before_release'] + d['ended_before_release']}/{d['reached_in_window']}/{d['full_window']}/{d['truncated']}"  # noqa: E731
                f1 = lambda v: "-" if v is None else f"{v:+.2f}"  # noqa: E731
                print(f"{c:22s} {p:15s} {pr['n']:>3d} {st4(pr['impaired_status']):>22s} {st4(pr['nominal_status']):>22s} "
                      f"{pr['comparable']:>4d} {f1(pr['new_cells']['diff']['mean']):>6s} {f1(pr['geo_progress']['diff']['mean']):>6s} "
                      f"{pr['reached_in_window']['impaired']:>4d}/{pr['reached_in_window']['nominal']:<5d}"
                      f"{'/'.join(str(pr['reach'][k]) for k in ('both', 'nominal_only', 'impaired_only', 'neither')):>16s} "
                      f"{f1(pr['delay_both_reached']['mean']):>6s}")
        print()
    if len(struct) > 1:
        print("structure (evaluator-only, mean over the split)")
        for c, v in struct.items():
            print(f"  {c:16s} shortest {v['shortest']:6.1f}  detour {v['detour_ratio']:.2f}  "
                  f"dead-end cells {v['dead_end_cells']:5.1f}  corridor cells {v['corridor_cells']:5.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
