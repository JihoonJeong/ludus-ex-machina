"""Episode metrics for robust_nav, from the evaluator trajectory.

Every episode is scored, failures included. Rows: row 0 is the reset
observation, row k the result of step k (`outcome` of the action taken on
observation k-1, `pos` after it).

    reached, end_turn                 end_turn = steps taken (budget if not reached)
    shortest, spl                     SPL = reached * shortest / max(shortest, steps)
    rates                             moved / collided / waited / invalid over steps
    stationary_steps                  steps that did not move (collided, waited, invalid)
    longest_stationary_run            the longest run of them — "stuck in place"
    revisit_moves, backtracks         moves into a visited cell / straight back to
                                      where it stood two rows ago — "loops"
    distinct_cells                    cells stood on
    search_steps                      first row whose delivered view shows the TRUE
                                      beacon cell as beacon (valid) — spurious noise
                                      beacons do not count
    approach_steps                    steps from then to the end, when reached
    impairment (when the condition has one):
      onset, release
      resume_steps                    steps from onset to the first move after it
                                      (None when onset is 0: nothing to resume from)
      moved_rate_impaired             share of impaired steps that moved
      recovery (transient only; None when the episode ended before release):
        new_cells                     cells entered within `window` steps after
                                      release that were never stood on before it
        geo_progress                  geodesic distance to the goal at release minus
                                      its minimum within the window (evaluator-only)
        reached_in_window
        recovered                     reached_in_window or new_cells >= min_new_cells
                                      (provisional thresholds from the config — one
                                      move is not a recovery)
    infra_fail                        steps whose action the harness replaced by a
                                      wait because the controller failed (kept, not
                                      dropped)
    act_ms_total                      controller wall-clock, when the harness timed it
"""

from __future__ import annotations


def _true_beacon_seen(row: dict) -> bool:
    obs, true = row["obs"], row["true"]
    for i, (orow, trow, vrow) in enumerate(zip(obs["beacon"], true["beacon"], obs["valid"])):
        for j in range(len(orow)):
            if trow[j] == "1" and orow[j] == "1" and vrow[j] == "1":
                return True
    return False


def episode_metrics(rows: list[dict], layout: dict, condition: dict, config: dict,
                    header: dict | None = None) -> dict:
    steps = rows[1:]
    n = len(steps)
    reached = bool(rows[-1]["reached"])
    shortest = layout["shortest"]
    counts = {k: sum(1 for r in steps if r["outcome"] == k) for k in ("moved", "collided", "waited", "invalid")}

    longest = run = 0
    for r in steps:
        run = run + 1 if r["outcome"] != "moved" else 0
        longest = max(longest, run)

    visited = {tuple(rows[0]["pos"])}
    revisits = backtracks = 0
    for k, r in enumerate(steps, start=1):
        p = tuple(r["pos"])
        if r["outcome"] == "moved":
            if p in visited:
                revisits += 1
            if k >= 2 and p == tuple(rows[k - 2]["pos"]):
                backtracks += 1
        visited.add(p)

    first_seen = next((r["t"] for r in rows if _true_beacon_seen(r)), None)

    out = {
        "version": config["version"],
        "seed": layout["seed"],
        "condition": (header or {}).get("condition"),
        "reached": reached, "end_turn": n, "budget": config["budget"],
        "shortest": shortest,
        "spl": round(shortest / max(shortest, n), 4) if reached else 0.0,
        "return": round(sum(r["reward"] for r in steps), 4),
        "rates": {k: round(v / n, 4) if n else None for k, v in counts.items()},
        "counts": counts,
        "stationary_steps": n - counts["moved"],
        "longest_stationary_run": longest,
        "revisit_moves": revisits, "backtracks": backtracks,
        "distinct_cells": len(visited),
        "search_steps": first_seen,
        "approach_steps": (n - first_seen) if (reached and first_seen is not None) else None,
        "infra_fail": sum(1 for r in steps if (r.get("meta") or {}).get("infra_fail")),
        "act_ms_total": round(sum((r.get("meta") or {}).get("act_ms", 0.0) for r in steps), 3),
    }
    imp = condition.get("impairment")
    if imp:
        onset, release = condition.get("window", [0, None])
        impaired = [r for r in steps if onset < r["t"] and (release is None or r["t"] <= release)]
        first_move = next((r["t"] for r in steps if r["t"] > onset and r["outcome"] == "moved"), None)
        out["impairment"] = {
            "kind": imp["kind"], "onset": onset, "release": release,
            "resume_steps": (first_move - onset) if (first_move is not None and onset > 0) else None,
            "moved_rate_impaired": (round(sum(r["outcome"] == "moved" for r in impaired) / len(impaired), 4)
                                    if impaired else None),
            "recovery": _recovery(rows, release, config["recovery"]) if release is not None else None,
        }
    return out


def _recovery(rows: list[dict], release: int, spec: dict) -> dict | None:
    if rows[-1]["t"] <= release:                 # ended (reached or budget) before release
        return None
    window = spec["window"]
    before = {tuple(r["pos"]) for r in rows if r["t"] <= release}
    at_release = next(r for r in rows if r["t"] == release)
    win = [r for r in rows if release < r["t"] <= release + window]
    new_cells = {tuple(r["pos"]) for r in win} - before
    geos = [r["geo"] for r in win if r["geo"] is not None]
    reached_in = any(r["reached"] for r in win)
    return {
        "window": window, "steps_in_window": len(win),
        "new_cells": len(new_cells),
        "geo_progress": (at_release["geo"] - min(geos)) if (geos and at_release["geo"] is not None) else None,
        "reached_in_window": reached_in,
        "recovered": reached_in or len(new_cells) >= spec["min_new_cells"],
    }
