#!/usr/bin/env python3
"""Shared behavioral scorer for MUD discovery runs — the joint DV for the
LxM×Ludex organ-ablation co-design.

The core is one pure function, `score_log(entries)`, so both labs compute the
same numbers from the same log shape. It takes the accepted-turn envelopes and
returns the act-vs-inquire index plus movement/coverage metrics.

    action_index = (act + go) / inquiry     # per-turn verbs
      act     = take/use/open/unlock/give/drop   (manipulating the world)
      inquiry = examine/search/talk/read/look    (gathering information)
      go      = movement

Loaders bridge the two log sources:
  - load_local(match_dir):   LxM arena matches/<id>/log.json
  - load_live(match_id):     Ludex plane record lxm:match:<id> (orchestrator.log)
Both yield the identical entry list, so score_log is source-agnostic.

CLI:
  python scripts/action_index.py --local matches/mud_grimhold_keep_haiku_01
  python scripts/action_index.py --manifest _relay/...grimhold-match-ids.json
"""

import argparse
import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

ACT = {"take", "use", "open", "unlock", "give", "drop"}
INQUIRY = {"examine", "search", "talk", "read", "look"}

# Ordered solve-chain flags per zone → chain-depth = how many leading links fired
# (Ray's primary graded DV). Linear: depth stops at the first unfired link, so a
# creature that fires link 3 but not link 2 still scores 1 (order matters). Keep
# in sync with the zone `interactions` set_flags in games/mud/zones.py.
CHAIN_FLAGS = {
    "tidewater_warren": ["sluice_open", "lantern_lit", "chasm_bridged", "seal_broken"],
    # P3 variant: 4 spatial links + the 4-step inferred-order rite (graded 0..8)
    "tidewater_warren_p3": ["sluice_open", "lantern_lit", "chasm_bridged", "seal_broken",
                            "moon_set", "salt_set", "storm_set", "ebb_set"],
    # v6 de-cluttered zone: 1 spatial link + the same 4-step rite (graded 0..5)
    "tide_chapel": ["door_pried", "moon_set", "salt_set", "storm_set", "ebb_set"],
    # v6.1 arbitrary order (salt→ebb→moon→storm) — inscription is the sole source
    "tide_chapel_v61": ["door_pried", "salt_set", "ebb_set", "moon_set", "storm_set"],
    "ss_erebus": ["coolant_loaded", "reactor_online", "bridge_powered"],
}


def _all_flags(state: dict) -> dict:
    """Recursively collect the flags dict from a post_move_state (schema varies
    across local arena logs and the plane's orchestrator snapshot)."""
    found = {}

    def dig(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "flags" and isinstance(v, dict):
                    found.update(v)
                elif isinstance(v, dict):
                    dig(v)
    dig(state)
    return found


def chain_depth(entries: list, scenario: str) -> int | None:
    """Max leading-link depth reached over the run (linear, order-respecting)."""
    chain = CHAIN_FLAGS.get(scenario)
    if not chain:
        return None
    reached = set()
    for e in entries:
        for f, v in _all_flags(e.get("post_move_state") or {}).items():
            if v:
                reached.add(f)
    d = 0
    for f in chain:
        if f in reached:
            d += 1
        else:
            break
    return d


def score_log(entries: list) -> dict | None:
    """Score a list of accepted-turn log entries. Source-agnostic.

    Each entry must expose envelope.move.verb and (optionally)
    post_move_state.agents.<id>.location for coverage/revisit.
    """
    acc = [e for e in entries if e.get("result") == "accepted"]
    if not acc:
        return None
    verbs = Counter(e["envelope"]["move"].get("verb", "?") for e in acc)
    n = len(acc)
    go = verbs.get("go", 0)
    inq = sum(verbs.get(k, 0) for k in INQUIRY)
    act = sum(verbs.get(k, 0) for k in ACT)

    locs = []
    for e in acc:
        agents = (e.get("post_move_state") or {}).get("agents") or {}
        for a in agents.values():
            if isinstance(a, dict) and "location" in a:
                locs.append(a["location"])
    seen, revisits = set(), 0
    for loc in locs:
        if loc in seen:
            revisits += 1
        seen.add(loc)

    scenario = None
    for e in acc:
        scenario = (e.get("post_move_context") or {}).get("scenario_id")
        if scenario:
            break

    out = {
        "turns": n,
        "go_per_turn": round(go / n, 3),
        "inquiry_per_turn": round(inq / n, 3),
        "act_per_turn": round(act / n, 3),
        "action_index": round((go + act) / max(0.01, inq), 3),  # manipulation-check, NOT efficacy DV
        "rooms": len(seen),
        "revisit_rate": round(revisits / max(1, len(locs)), 3),
        "verbs": dict(verbs.most_common()),
    }
    cd = chain_depth(acc, scenario)
    if cd is not None:
        out["chain_depth"] = cd  # Ray's primary graded efficacy DV
    return out


def load_local(match_dir: str) -> list:
    return json.loads((Path(match_dir) / "log.json").read_text(encoding="utf-8"))


def load_live(match_id: str, redis=None) -> list:
    """Load a Ludex plane match's turn log from Redis (orchestrator.log)."""
    if redis is None:
        redis = _redis()
    key = match_id if match_id.startswith("lxm:match:") else f"lxm:match:{match_id}"
    d = redis.get_json(key)
    if not d:
        return []
    return (d.get("orchestrator") or {}).get("log") or []


def _redis():
    for line in Path(".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))
    sys.path.insert(0, ".")
    from server.redis_client import UpstashRedis
    return UpstashRedis()


def _agg(scores: list) -> dict:
    """Mean of per-match metrics over an arm."""
    scores = [s for s in scores if s]
    if not scores:
        return {}
    keys = ("action_index", "go_per_turn", "inquiry_per_turn", "act_per_turn",
            "revisit_rate", "turns", "rooms")
    return {"n": len(scores),
            **{k: round(sum(s[k] for s in scores) / len(scores), 3) for k in keys}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="local match dir (matches/<id>)")
    ap.add_argument("--live", help="single live match id")
    ap.add_argument("--manifest", help="JSON with {arm: [match_id,...]} under match_ids")
    ap.add_argument("--glob", help="glob of local match dirs, e.g. 'matches/mud_grimhold_*'")
    args = ap.parse_args()

    if args.local:
        print(json.dumps(score_log(load_local(args.local)), indent=2, ensure_ascii=False))
    elif args.live:
        print(json.dumps(score_log(load_live(args.live)), indent=2, ensure_ascii=False))
    elif args.glob:
        for d in sorted(glob.glob(args.glob)):
            s = score_log(load_local(d))
            if s:
                print(f"{Path(d).name:34} a-idx {s['action_index']:7} "
                      f"go {s['go_per_turn']:.2f} inq {s['inquiry_per_turn']:.2f} "
                      f"act {s['act_per_turn']:.2f} revisit {s['revisit_rate']:.2f}")
    elif args.manifest:
        m = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        redis = _redis()
        print(f"# {m.get('zone')} · {m.get('creature')} · {m.get('brain')} · effort={m.get('effort')}")
        arms = m["match_ids"]
        agg_rows = {}
        for arm, ids in arms.items():
            scores = [score_log(load_live(mid, redis)) for mid in ids]
            agg_rows[arm] = _agg(scores)
        print(f"\n{'arm':8} {'n':>3} {'a-idx':>7} {'go/t':>6} {'inq/t':>6} {'act/t':>6} "
              f"{'revisit':>8} {'rooms':>6} {'turns':>6}")
        for arm, a in agg_rows.items():
            if not a:
                continue
            print(f"{arm:8} {a['n']:3} {a['action_index']:7} {a['go_per_turn']:6} "
                  f"{a['inquiry_per_turn']:6} {a['act_per_turn']:6} {a['revisit_rate']:8} "
                  f"{a['rooms']:6} {a['turns']:6}")
    else:
        ap.error("one of --local/--live/--manifest/--glob required")


if __name__ == "__main__":
    main()
