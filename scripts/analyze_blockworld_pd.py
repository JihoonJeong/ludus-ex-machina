"""Analyze Blockworld PD-flavor matches.

Handles both `prisoners_dilemma` (encounter-based PD) and
`externality_mushrooms` (public-goods PD) modes. Prints per-match
behavioral metrics and (when multiple match_ids supplied) the
cross-match aggregate.

Usage:
  python scripts/analyze_blockworld_pd.py prisoners_dilemma_test_001
  python scripts/analyze_blockworld_pd.py prisoners_dilemma_test_001 prisoners_dilemma_test_002 ...
  python scripts/analyze_blockworld_pd.py 'prisoners_dilemma_test_*'   # glob
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from glob import glob
from pathlib import Path


def _expand(args: list[str]) -> list[str]:
    """Resolve match_id args (literal or glob) to actual match_id strings."""
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
            else:
                print(f"warn: matches/{a}/result.json missing — skipping")
    return sorted(set(out))


def _load_match(match_id: str) -> tuple[dict, dict, list]:
    root = Path("matches") / match_id
    result = json.loads((root / "result.json").read_text())
    config = json.loads((root / "match_config.json").read_text())
    log = json.loads((root / "log.json").read_text())
    return result, config, log


def _verb_dist(log: list) -> dict[str, int]:
    c: Counter = Counter()
    for e in log:
        m = e.get("envelope", {}).get("move") or {}
        v = m.get("verb")
        if v:
            c[v] += 1
    return dict(c)


def _detect_tit_for_tat(encounter_log: list, agents: list[str]) -> dict:
    """For each agent, count: in how many encounters did they DEFECT *after*
    the partner DEFECTED in the previous encounter? (tit-for-tat C→D switch)
    Also count C→C maintained, D→D maintained, D→C forgiveness.
    """
    if len(agents) != 2 or len(encounter_log) < 2:
        return {a: {"after_partner_D": {"C": 0, "D": 0},
                    "after_partner_C": {"C": 0, "D": 0}} for a in agents}
    counters = {
        a: {"after_partner_D": {"C": 0, "D": 0},
            "after_partner_C": {"C": 0, "D": 0}}
        for a in agents
    }
    for prev, cur in zip(encounter_log[:-1], encounter_log[1:]):
        for aid in agents:
            other = [x for x in agents if x != aid][0]
            partner_prev = (prev.get("moves") or {}).get(other)
            self_cur = (cur.get("moves") or {}).get(aid)
            if partner_prev is None or self_cur is None:
                continue
            key = "after_partner_D" if partner_prev == "D" else "after_partner_C"
            counters[aid][key][self_cur] = counters[aid][key].get(self_cur, 0) + 1
    return counters


def analyze_prisoners_dilemma(match_id: str) -> dict:
    result, config, log = _load_match(match_id)
    agents = [a["agent_id"] for a in config.get("agents", [])]
    enc_log = result.get("encounter_log") or []
    outcomes = Counter(e.get("outcome") for e in enc_log)
    verbs = _verb_dist(log)
    tft = _detect_tit_for_tat(enc_log, agents)

    print(f"\n=== {match_id} (prisoners_dilemma) ===")
    print(f"Outcome label: {result.get('outcome')}")
    print(f"Winner: {result.get('winner')}, scores: {result.get('scores')}")
    print(f"Encounters: {len(enc_log)}  outcome dist: {dict(outcomes)}")
    print(f"Verbs: {verbs}")
    print(f"say_attempts: {result.get('say_attempts')}")
    bd = result.get("breakdown") or {}
    print(f"Coop pickups: {dict({aid: b.get('coop_pickups', 0) for aid, b in bd.items()})}")
    print(f"Defect pickups: {dict({aid: b.get('defect_pickups', 0) for aid, b in bd.items()})}")
    print(f"Tit-for-tat counters:")
    for aid, c in tft.items():
        print(f"  {aid}: after partner-D → {c['after_partner_D']}, after partner-C → {c['after_partner_C']}")
    return {
        "match_id": match_id,
        "mode": "prisoners_dilemma",
        "outcome": result.get("outcome"),
        "winner": result.get("winner"),
        "scores": result.get("scores"),
        "encounters": len(enc_log),
        "outcome_dist": dict(outcomes),
        "say_attempts": result.get("say_attempts"),
        "tit_for_tat": tft,
        "coop_pickups": {aid: b.get("coop_pickups", 0) for aid, b in bd.items()},
        "defect_pickups": {aid: b.get("defect_pickups", 0) for aid, b in bd.items()},
    }


def analyze_externality_mushrooms(match_id: str) -> dict:
    result, config, log = _load_match(match_id)
    agents = [a["agent_id"] for a in config.get("agents", [])]
    bd = result.get("breakdown") or {}
    pickup_log = result.get("em_pickup_log") or []
    verbs = _verb_dist(log)

    public_pick_ratio = {}
    for aid, b in bd.items():
        total = b.get("public_picks", 0) + b.get("selfish_picks", 0)
        public_pick_ratio[aid] = (
            b.get("public_picks", 0) / total if total else 0.0
        )

    # Pickup time-series: bucket public-pick fraction by 10-turn windows.
    turn_limit = 60
    bucket = 10
    series = []
    for start in range(1, turn_limit + 1, bucket):
        end = start + bucket
        window = [e for e in pickup_log if start <= e["turn"] < end]
        n_pub = sum(1 for e in window if e["type"] == "public")
        n = len(window)
        series.append({
            "window": f"T{start}-T{end-1}",
            "n": n,
            "public_ratio": n_pub / n if n else None,
        })

    print(f"\n=== {match_id} (externality_mushrooms) ===")
    print(f"Outcome label: {result.get('outcome')}")
    print(f"Winner: {result.get('winner')}, scores: {result.get('scores')}")
    print(f"Total pickups: {result.get('total_pickups')} "
          f"(public {result.get('total_public_pickups')}, selfish {result.get('total_selfish_pickups')})")
    print(f"Public pick ratio: {public_pick_ratio}")
    print(f"Per-agent breakdown:")
    for aid, b in bd.items():
        print(
            f"  {aid}: score={b['score']}, "
            f"selfish={b.get('selfish_picks', 0)}, "
            f"public={b.get('public_picks', 0)}, "
            f"externality_received={b.get('externality_received', 0)}"
        )
    print(f"Verbs: {verbs}")
    print(f"say_attempts: {result.get('say_attempts')}")
    print(f"Cooperation time-series (10-turn windows):")
    for s in series:
        if s["n"]:
            print(f"  {s['window']}: n={s['n']}, public_ratio={s['public_ratio']:.2f}")
        else:
            print(f"  {s['window']}: n=0")
    return {
        "match_id": match_id,
        "mode": "externality_mushrooms",
        "outcome": result.get("outcome"),
        "winner": result.get("winner"),
        "scores": result.get("scores"),
        "public_pick_ratio": public_pick_ratio,
        "total_pickups": result.get("total_pickups"),
        "say_attempts": result.get("say_attempts"),
        "breakdown": bd,
        "time_series": series,
    }


def aggregate(records: list[dict]) -> None:
    if len(records) < 2:
        return
    print("\n=== AGGREGATE ===")
    by_mode: dict[str, list[dict]] = {}
    for r in records:
        by_mode.setdefault(r["mode"], []).append(r)
    for mode, recs in by_mode.items():
        print(f"\n[{mode}] n={len(recs)}")
        outcomes = Counter(r["outcome"] for r in recs)
        winners = Counter(r["winner"] for r in recs)
        print(f"  outcome labels: {dict(outcomes)}")
        print(f"  winners: {dict(winners)}")
        if mode == "prisoners_dilemma":
            total_enc = Counter()
            for r in recs:
                for k, v in (r.get("outcome_dist") or {}).items():
                    total_enc[k] += v
            print(f"  total encounter-outcome dist: {dict(total_enc)}")
        if mode == "externality_mushrooms":
            ratios = []
            for r in recs:
                ratios.extend((r.get("public_pick_ratio") or {}).values())
            if ratios:
                print(
                    f"  public_pick_ratio: mean={sum(ratios) / len(ratios):.2f}, "
                    f"min={min(ratios):.2f}, max={max(ratios):.2f}"
                )


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: analyze_blockworld_pd.py <match_id> [match_id ...]")
        return 1
    match_ids = _expand(argv)
    if not match_ids:
        print("error: no matches found")
        return 1
    records = []
    for mid in match_ids:
        result_path = Path("matches") / mid / "result.json"
        result = json.loads(result_path.read_text())
        scenario_id = result.get("scenario_id", "")
        if "prisoners_dilemma" in scenario_id:
            records.append(analyze_prisoners_dilemma(mid))
        elif "externality_mushrooms" in scenario_id:
            records.append(analyze_externality_mushrooms(mid))
        else:
            print(f"warn: {mid} (scenario={scenario_id}) is not PD/EM — skipping")
    aggregate(records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
