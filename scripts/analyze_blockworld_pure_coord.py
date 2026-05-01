"""Analyze Blockworld pure_coord matches.

Per-match metrics: meeting outcome, min d_ab, commit detection
(longest run of an agent at one cell), landmark proximity at
key turns, say verb count and content.

Aggregate metrics: success rate, meeting-cell landmark dist,
say usage, min-distance distribution.

Usage:
  python scripts/analyze_blockworld_pure_coord.py pure_coord_test_001
  python scripts/analyze_blockworld_pure_coord.py 'pure_coord_test_*' 'pure_coord_chat_test_*'
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def _expand(args: list[str]) -> list[str]:
    matches_root = Path("matches")
    out: list[str] = []
    for a in args:
        if "*" in a or "?" in a:
            for d in matches_root.glob(a):
                if (d / "result.json").exists():
                    out.append(d.name)
        else:
            if (matches_root / a / "result.json").exists():
                out.append(a)
    return sorted(set(out))


def _load(match_id: str) -> tuple[dict, dict, list]:
    root = Path("matches") / match_id
    return (
        json.loads((root / "result.json").read_text()),
        json.loads((root / "match_config.json").read_text()),
        json.loads((root / "log.json").read_text()),
    )


def _trajectory(log: list, agents: list[str]) -> list[dict]:
    """Per-turn snapshot of agent positions + d_ab + says."""
    out = []
    for e in log:
        st = e.get("post_move_state", {})
        ag = st.get("agents") or {}
        if not all(a in ag for a in agents):
            continue
        positions = {a: (ag[a]["x"], ag[a]["y"], ag[a]["z"]) for a in agents}
        if len(agents) == 2:
            a, b = agents
            d = sum(abs(positions[a][i] - positions[b][i]) for i in range(3))
        else:
            d = None
        m = e.get("envelope", {}).get("move") or {}
        out.append({
            "turn": e.get("envelope", {}).get("turn"),
            "positions": positions,
            "d_ab": d,
            "verb": m.get("verb"),
            "agent_id": e.get("agent_id"),
            "say_message": m.get("message") if m.get("verb") == "say" else None,
        })
    return out


def _longest_commit(trajectory: list[dict], agent: str) -> tuple[tuple, int]:
    """Find the longest run of consecutive turns an agent stayed at one cell.
    Returns (cell, run_length).
    """
    best_cell = None
    best_len = 0
    cur_cell = None
    cur_len = 0
    for t in trajectory:
        pos = (t["positions"] or {}).get(agent)
        if pos is None:
            continue
        if pos == cur_cell:
            cur_len += 1
        else:
            cur_cell = pos
            cur_len = 1
        if cur_len > best_len:
            best_len = cur_len
            best_cell = cur_cell
    return best_cell, best_len


def _nearest_landmark(cell, landmarks: list[dict]) -> tuple[dict, int]:
    """Return (landmark, manhattan-3D distance) for the nearest one to cell."""
    if not cell or not landmarks:
        return None, None
    best = None
    best_d = None
    for lm in landmarks:
        d = abs(lm["x"] - cell[0]) + abs(lm["y"] - cell[1]) + abs(lm["z"] - cell[2])
        if best_d is None or d < best_d:
            best, best_d = lm, d
    return best, best_d


def analyze_match(match_id: str) -> dict:
    result, config, log = _load(match_id)
    agents = [a["agent_id"] for a in config.get("agents", [])]
    landmarks = result.get("landmarks") or []
    traj = _trajectory(log, agents)

    # Per-agent commit (longest stay) + nearest landmark to commit cell.
    commits = {}
    for a in agents:
        cell, run = _longest_commit(traj, a)
        lm, lm_d = _nearest_landmark(cell, landmarks)
        commits[a] = {
            "commit_cell": cell, "commit_run": run,
            "nearest_landmark": lm["name"] if lm else None,
            "lm_distance": lm_d,
        }

    # Distance trajectory.
    ds = [t["d_ab"] for t in traj if t["d_ab"] is not None]
    min_d = min(ds) if ds else None
    final_d = ds[-1] if ds else None

    # Says.
    says = [t for t in traj if t["verb"] == "say"]
    say_by_agent = Counter(t["agent_id"] for t in says)

    # Print summary.
    print(f"\n=== {match_id} (mode={result.get('scenario_id')}) ===")
    print(f"Outcome: {result.get('outcome')}, met={result.get('met')}, "
          f"meeting_turn={result.get('meeting_turn')}, "
          f"meeting_cell={result.get('meeting_cell')}")
    if result.get("met"):
        cl = result.get("chosen_landmark") or {}
        print(f"  on_landmark={result.get('on_landmark')}, "
              f"landmark={cl.get('name')}")
    print(f"Min d_ab: {min_d}, final d_ab: {final_d}")
    print(f"Say attempts ({sum(say_by_agent.values())} total): {dict(say_by_agent)}")
    if says:
        print(f"  first say (T{says[0]['turn']} {says[0]['agent_id']}): "
              f"{says[0]['say_message'][:100]!r}")
        if len(says) > 1:
            print(f"  last say (T{says[-1]['turn']} {says[-1]['agent_id']}): "
                  f"{says[-1]['say_message'][:100]!r}")
    print(f"Agent commits (longest stay):")
    for a, c in commits.items():
        print(f"  {a}: cell={c['commit_cell']}, run={c['commit_run']} turns, "
              f"nearest='{c['nearest_landmark']}' (d={c['lm_distance']})")

    return {
        "match_id": match_id,
        "scenario_id": result.get("scenario_id"),
        "met": result.get("met"),
        "meeting_turn": result.get("meeting_turn"),
        "meeting_cell": result.get("meeting_cell"),
        "chosen_landmark": (result.get("chosen_landmark") or {}).get("name"),
        "on_landmark": result.get("on_landmark"),
        "min_d_ab": min_d,
        "final_d_ab": final_d,
        "say_attempts": dict(say_by_agent),
        "n_says": sum(say_by_agent.values()),
        "commits": commits,
    }


def aggregate(records: list[dict]) -> None:
    if len(records) < 2:
        return
    print("\n=== AGGREGATE ===")
    by_scenario: dict[str, list[dict]] = {}
    for r in records:
        by_scenario.setdefault(r["scenario_id"] or "?", []).append(r)
    for sid, recs in by_scenario.items():
        n = len(recs)
        n_met = sum(1 for r in recs if r["met"])
        rate = n_met / n
        n_says = [r["n_says"] for r in recs]
        min_ds = [r["min_d_ab"] for r in recs if r["min_d_ab"] is not None]
        landmarks = Counter(r["chosen_landmark"] for r in recs if r["chosen_landmark"])
        # Commit landmark frequency (across both agents).
        commit_lm = Counter()
        for r in recs:
            for a, c in (r.get("commits") or {}).items():
                if c.get("nearest_landmark"):
                    commit_lm[c["nearest_landmark"]] += 1
        print(f"\n[{sid}] n={n}")
        print(f"  meeting success: {n_met}/{n} ({rate:.0%})")
        print(f"  say count: mean={sum(n_says) / n:.1f}, "
              f"min={min(n_says)}, max={max(n_says)}, "
              f"matches with say>0: {sum(1 for x in n_says if x > 0)}/{n}")
        if min_ds:
            print(f"  min d_ab: mean={sum(min_ds) / len(min_ds):.1f}, "
                  f"min={min(min_ds)}, max={max(min_ds)}")
        if landmarks:
            print(f"  meeting landmarks: {dict(landmarks)}")
        if commit_lm:
            print(f"  commit-cell landmark dist (across all agent-commits): {dict(commit_lm.most_common())}")


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: analyze_blockworld_pure_coord.py <match_id> [match_id ...]")
        return 1
    match_ids = _expand(argv)
    if not match_ids:
        print("error: no matches found")
        return 1
    records = []
    for mid in match_ids:
        result_path = Path("matches") / mid / "result.json"
        result = json.loads(result_path.read_text())
        sid = result.get("scenario_id", "")
        if not sid.startswith("pure_coord"):
            print(f"warn: {mid} (scenario={sid}) is not pure_coord — skipping")
            continue
        records.append(analyze_match(mid))
    aggregate(records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
