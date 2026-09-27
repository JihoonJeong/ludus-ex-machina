"""Episode metrics for robust_nav, from the evaluator trajectory.

Every episode is scored, failures included. Rows: row 0 is the reset
observation (t=0), row k the result of step k (`outcome` of the action taken
on observation k-1, `pos` after it, and the observation index t=k).

    reached, end, end_turn           end = reached | budget | aborted; end_turn =
                                     steps taken
    shortest, spl                    SPL = reached * shortest / max(shortest, steps)
    rates, counts                    moved / collided / waited / invalid / infra_wait
                                     over steps. `waited` is the policy's own wait;
                                     `infra_wait` is a wait the harness put in after
                                     the controller failed (v0.1.1: split out)
    stationary_steps                 steps that did not move
    longest_stationary_run           the longest run of them — "stuck in place"
    revisit_moves, backtracks        moves into a visited cell / straight back to
                                     where it stood two rows ago — "loops"
    distinct_cells                   cells stood on
    search_steps                     first observation index whose delivered view
                                     shows the TRUE beacon cell as a valid beacon —
                                     noise-made beacons do not count
    approach_steps                   steps from then to the end, when reached
    windows                          window_stats() for every release time a
                                     transient condition in the config uses — on
                                     EVERY episode, nominal included, so an impaired
                                     episode can be paired with its nominal twin
    impairment (when the condition has one):
      onset, release
      resume_steps                   steps from onset to the first move after it
                                     (None when onset is 0: nothing to resume from)
      moved_rate_impaired            share of impaired steps that moved
      recovery                       window_stats at this condition's release, plus
                                     the provisional binary `recovered` kept from
                                     v0.1 (not discriminative: random walk passes it
                                     — use pair_recovery() instead)
    infra_fail, act_ms_total

window_stats(release, W): the observation indices release < t <= release + W.
    status   reached_before_release | ended_before_release (budget/abort) |
             reached_in_window | truncated (budget/abort inside the window) |
             full_window
    new_cells            cells entered in the window never stood on up to release
    geo_progress         geodesic distance at release minus its minimum in the
                         window (evaluator-only)
    reached_in_window, steps_in_window, infra_in_window
    beacon_seen_before_release   the true beacon was seen at some t <= release

pair_recovery(impaired, nominal): the same policy, seed and rep; the same
observation-time window. Continuous values, raw and impaired-minus-nominal, and
`comparable` only when both windows are full. Nothing is zero-filled: a window
that did not happen is None, with its status saying why. Also, window-free:
`reach` (both / nominal_only / impaired_only / neither) and `delay` = impaired
minus nominal end_turn when both reached — for runs that end before or inside
the window (task B's cue-guided baselines mostly do).
"""

from __future__ import annotations

import statistics

WINDOW_STATUSES = ("reached_before_release", "ended_before_release", "reached_in_window",
                   "truncated", "full_window")


def _true_beacon_seen(row: dict) -> bool:
    obs, true = row["obs"], row["true"]
    for orow, trow, vrow in zip(obs["beacon"], true["beacon"], obs["valid"]):
        for j in range(len(orow)):
            if trow[j] == "1" and orow[j] == "1" and vrow[j] == "1":
                return True
    return False


def _kind(row: dict) -> str:
    if row["outcome"] == "waited" and row.get("cause") == "infra":
        return "infra_wait"
    return row["outcome"]


def window_stats(rows: list[dict], release: int, window: int, first_seen: int | None) -> dict:
    last = rows[-1]
    out = {"release": release, "window": window, "status": None, "steps_in_window": 0,
           "new_cells": None, "geo_progress": None, "reached_in_window": False, "infra_in_window": 0,
           "beacon_seen_before_release": first_seen is not None and first_seen <= release}
    if last["t"] <= release:
        out["status"] = "reached_before_release" if last["reached"] else "ended_before_release"
        return out
    before = {tuple(r["pos"]) for r in rows if r["t"] <= release}
    at = next(r for r in rows if r["t"] == release)
    win = [r for r in rows if release < r["t"] <= release + window]
    geos = [r["geo"] for r in win if r["geo"] is not None]
    reached = any(r["reached"] for r in win)
    out.update({
        "steps_in_window": len(win),
        "new_cells": len({tuple(r["pos"]) for r in win} - before),
        "geo_progress": (at["geo"] - min(geos)) if (geos and at["geo"] is not None) else None,
        "reached_in_window": reached,
        "infra_in_window": sum(1 for r in win if r.get("cause") == "infra"),
        "status": ("reached_in_window" if reached else
                   "full_window" if len(win) == window else "truncated"),
    })
    return out


def _releases(config: dict) -> list[int]:
    return sorted({c["window"][1] for c in config["conditions"].values()
                   if c.get("impairment") and c.get("window") and c["window"][1] is not None})


def episode_metrics(rows: list[dict], layout: dict, condition: dict, config: dict,
                    header: dict | None = None) -> dict:
    header = header or {}
    steps = rows[1:]
    n = len(steps)
    reached = bool(rows[-1]["reached"])
    shortest = layout["shortest"]
    kinds = [_kind(r) for r in steps]
    counts = {k: kinds.count(k) for k in ("moved", "collided", "waited", "invalid", "infra_wait")}

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
    W = config["recovery"]["window"]

    out = {
        "version": config["version"],
        "task": config.get("task"),
        "seed": layout["seed"],
        "condition": header.get("condition"),
        "family": layout.get("family"),
        "reached": reached,
        "end": header.get("end") or ("reached" if reached else "budget"),
        "abort_reason": header.get("abort_reason"),
        "end_turn": n, "budget": config["budget"],
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
        "windows": {str(rel): window_stats(rows, rel, W, first_seen) for rel in _releases(config)},
        "infra_fail": sum(1 for r in steps if (r.get("meta") or {}).get("infra_fail")),
        "act_ms_total": round(sum((r.get("meta") or {}).get("act_ms", 0.0) for r in steps), 3),
    }
    if layout.get("shortest_base") is not None:
        out["shortest_base"] = layout["shortest_base"]
    imp = condition.get("impairment")
    if imp:
        onset, release = condition.get("window", [0, None])
        impaired = [r for r in steps if onset < r["t"] and (release is None or r["t"] <= release)]
        first_move = next((r["t"] for r in steps if r["t"] > onset and r["outcome"] == "moved"), None)
        rec = None
        if release is not None:
            rec = dict(out["windows"][str(release)])
            if rec["status"] in ("reached_before_release", "ended_before_release"):
                rec = None                     # v0.1: no recovery row when it ended before release
            else:
                rec["recovered"] = rec["reached_in_window"] or rec["new_cells"] >= config["recovery"]["min_new_cells"]
        out["impairment"] = {
            "kind": imp["kind"], "onset": onset, "release": release,
            "resume_steps": (first_move - onset) if (first_move is not None and onset > 0) else None,
            "moved_rate_impaired": (round(sum(r["outcome"] == "moved" for r in impaired) / len(impaired), 4)
                                    if impaired else None),
            "recovery": rec,
        }
    return out


# --- pairing ---------------------------------------------------------------------------

PAIRED = ("new_cells", "geo_progress")


def pair_recovery(impaired: dict, nominal: dict) -> dict | None:
    """Pair a transient-condition episode with the nominal episode of the same
    policy, seed and rep over the same observation-time window."""
    imp = impaired.get("impairment") or {}
    rel = imp.get("release")
    if rel is None:
        return None
    assert (impaired["seed"], impaired.get("policy"), impaired.get("rep")) == \
        (nominal["seed"], nominal.get("policy"), nominal.get("rep")), "pair the same policy, seed and rep"
    a, b = impaired["windows"][str(rel)], nominal["windows"][str(rel)]
    comparable = a["status"] == "full_window" and b["status"] == "full_window"
    ri, rn = impaired["reached"], nominal["reached"]
    reach = "both" if ri and rn else "nominal_only" if rn else "impaired_only" if ri else "neither"
    out = {"release": rel, "impaired_status": a["status"], "nominal_status": b["status"],
           "reach": reach,
           "delay": {"impaired": impaired["end_turn"] if ri else None, "nominal": nominal["end_turn"] if rn else None,
                     "diff": (impaired["end_turn"] - nominal["end_turn"]) if reach == "both" else None},
           "comparable": comparable,
           "reached_in_window": {"impaired": a["reached_in_window"], "nominal": b["reached_in_window"]},
           "beacon_seen_before_release": {"impaired": a["beacon_seen_before_release"],
                                          "nominal": b["beacon_seen_before_release"]}}
    for k in PAIRED:
        ia, nb = a[k], b[k]
        out[k] = {"impaired": ia, "nominal": nb,
                  "diff": (ia - nb) if (comparable and ia is not None and nb is not None) else None}
    return out


def _stat(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "mean": None, "median": None}
    return {"n": len(xs), "mean": round(sum(xs) / len(xs), 3), "median": statistics.median(xs)}


def paired_summary(pairs: list[dict]) -> dict:
    """Denominators first: every pair is counted by status on both sides;
    differences only over comparable pairs; the beacon-seen subset is reported
    apart, with its selection named."""
    n = len(pairs)
    comp = [p for p in pairs if p["comparable"]]
    seen = [p for p in comp if p["beacon_seen_before_release"]["impaired"]
            and p["beacon_seen_before_release"]["nominal"]]
    count = lambda side: {s: sum(1 for p in pairs if p[side] == s) for s in WINDOW_STATUSES}  # noqa: E731
    return {
        "n": n,
        "impaired_status": count("impaired_status"),
        "nominal_status": count("nominal_status"),
        "comparable": len(comp),
        "reach": {k: sum(1 for p in pairs if p["reach"] == k)
                  for k in ("both", "nominal_only", "impaired_only", "neither")},
        "delay_both_reached": _stat([p["delay"]["diff"] for p in pairs]),
        "reached_in_window": {"impaired": sum(p["reached_in_window"]["impaired"] for p in pairs),
                              "nominal": sum(p["reached_in_window"]["nominal"] for p in pairs)},
        **{k: {"impaired": _stat([p[k]["impaired"] for p in comp]),
               "nominal": _stat([p[k]["nominal"] for p in comp]),
               "diff": _stat([p[k]["diff"] for p in comp])} for k in PAIRED},
        "subset_beacon_seen_before_release": {
            "selection": "comparable pairs whose true beacon was seen by release in BOTH runs — "
                         "a conditional sub-analysis, not the main measure",
            "n": len(seen),
            **{k: _stat([p[k]["diff"] for p in seen]) for k in PAIRED},
        },
    }
