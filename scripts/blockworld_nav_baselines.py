#!/usr/bin/env python3
"""Run the rule baselines on hidden-target navigation and print the metrics.

    .venv/bin/python scripts/blockworld_nav_baselines.py --seeds 1-20 --view-radius 5 \
        --out state/blockworld-nav/<stamp>

Seeds are layouts (start, beacon, walls) from layout_for_seed(); seed 0 means
the scenario file's own layout. Each episode's trajectory is written as jsonl
under --out, and a summary.json beside it. The same env and metrics are what a
connectome controller plugs into (lxm/envs/blockworld_env.py).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lxm.envs.blockworld_baselines import POLICIES, run_episode  # noqa: E402
from lxm.envs.blockworld_env import BlockworldEnv  # noqa: E402


def parse_seeds(text: str) -> list[int]:
    out = []
    for part in text.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part.strip():
            out.append(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="hidden_target_nav_01")
    ap.add_argument("--seeds", default="0-9")
    ap.add_argument("--policies", default=",".join(POLICIES))
    ap.add_argument("--view-radius", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = a.out or ROOT / "matches" / "blockworld-nav" / stamp
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name in a.policies.split(","):
        rows = []
        for seed in parse_seeds(a.seeds):
            env = BlockworldEnv(a.scenario, view_radius=a.view_radius)
            m = run_episode(env, POLICIES[name](seed=seed), seed=None if seed == 0 else seed)
            env.save_trajectory(out / f"{name}-seed{seed}.jsonl")
            rows.append(m)
        ok = [r for r in rows if r["reached"]]
        eff = [r["path_efficiency"] for r in ok]
        s = {"episodes": len(rows), "reached": len(ok),
             "median_steps_reached": statistics.median(r["steps"] for r in ok) if ok else None,
             "median_path_efficiency": statistics.median(eff) if eff else None,
             "mean_no_op_rate": round(statistics.mean(r["no_op_rate"] for r in rows), 3),
             "mean_revisit_rate": round(statistics.mean(r["revisit_rate"] for r in rows), 3),
             "median_search_steps": statistics.median([r["search_steps"] for r in rows if r["search_steps"] is not None] or [0]),
             "median_approach_steps": statistics.median([r["approach_steps"] for r in ok if r["approach_steps"] is not None] or [0]),
             "episodes_detail": rows}
        summary[name] = s
        print(f"{name:15s} reached {len(ok)}/{len(rows)}  median steps {s['median_steps_reached']}  "
              f"path eff {s['median_path_efficiency']}  no-op {s['mean_no_op_rate']}  revisit {s['mean_revisit_rate']}  "
              f"search {s['median_search_steps']} / approach {s['median_approach_steps']}")
    (out / "summary.json").write_text(json.dumps({"scenario": a.scenario, "seeds": a.seeds,
                                                   "view_radius": a.view_radius, "policies": summary},
                                                  indent=1), encoding="utf-8")
    print("→", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
