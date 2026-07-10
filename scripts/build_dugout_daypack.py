#!/usr/bin/env python3
"""Build a Dugout day-pack: one day's MLB slate + as-of-date team form + actuals.

Reads the Dugout project's cached schedule (~/Projects/dugout/cache/
schedule_2025.json — game_id/date/teams/starters/final scores) and emits a
self-contained JSON the LxM `dugout` game engine consumes. LxM takes NO
runtime dependency on the Dugout repo: this script is the only bridge, and
the day-pack is committed.

Leakage rule: every aggregate for a slate on date D is computed from games
STRICTLY BEFORE D. The actual result rides along for scoring only (the
engine never shows it to the agent).

House-lite baseline: log5 of the teams' as-of win% plus a flat home-field
bump — a placeholder column until the real Dugout engine's calibrated
predictions are wired in (v2 live mode). Score predictions for the house
use each side's blended runs-for/runs-against rates.

    python scripts/build_dugout_daypack.py --date 2025-06-25
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

SCHEDULE = Path.home() / "Projects/dugout/cache/schedule_2025.json"
OUT_DIR = Path(__file__).resolve().parent.parent / "games/dugout/data"
HFA = 0.040  # flat home-field bump on the log5 line


def log5(a: float, b: float) -> float:
    """P(A beats B) from the teams' win percentages (Bill James log5)."""
    denom = a * (1 - b) + b * (1 - a)
    return 0.5 if denom == 0 else (a * (1 - b)) / denom


def team_form(games: list, team: str, before: str) -> dict | None:
    """Aggregate a team's results from Final games strictly before `before`."""
    rows = []
    for g in games:
        if g["date"] >= before or g.get("status") != "Final":
            continue
        if g["home_team_id"] == team:
            rows.append((g["date"], g["home_score"], g["away_score"], True))
        elif g["away_team_id"] == team:
            rows.append((g["date"], g["away_score"], g["home_score"], False))
    if len(rows) < 20:  # too early in the season to have a meaningful profile
        return None
    rows.sort()
    w = sum(1 for _, rf, ra, _ in rows if rf > ra)
    rf = sum(r[1] for r in rows)
    ra = sum(r[2] for r in rows)
    last10 = rows[-10:]
    home_rows = [(rf_, ra_) for _, rf_, ra_, home in rows if home]
    away_rows = [(rf_, ra_) for _, rf_, ra_, home in rows if not home]
    return {
        "g": len(rows),
        "w": w,
        "l": len(rows) - w,
        "win_pct": round(w / len(rows), 3),
        "rf_per_g": round(rf / len(rows), 2),
        "ra_per_g": round(ra / len(rows), 2),
        "last10_w": sum(1 for _, rf_, ra_, _ in last10 if rf_ > ra_),
        "home_w": sum(1 for rf_, ra_ in home_rows if rf_ > ra_),
        "home_g": len(home_rows),
        "away_w": sum(1 for rf_, ra_ in away_rows if rf_ > ra_),
        "away_g": len(away_rows),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="slate date, e.g. 2025-06-25")
    args = ap.parse_args()

    sched = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    slate = [g for g in sched
             if g["date"] == args.date and g.get("status") == "Final"
             and g.get("home_score") is not None]
    if not slate:
        raise SystemExit(f"no Final games on {args.date}")
    slate.sort(key=lambda g: g["game_id"])

    out_games = []
    for g in slate:
        home, away = g["home_team_id"], g["away_team_id"]
        hf = team_form(sched, home, args.date)
        af = team_form(sched, away, args.date)
        if not hf or not af:
            continue
        p_home = min(0.95, max(0.05, log5(hf["win_pct"], af["win_pct"]) + HFA))
        # house score line: each side's runs blend (its offense vs opponent's defense)
        house_home = round((hf["rf_per_g"] + af["ra_per_g"]) / 2)
        house_away = round((af["rf_per_g"] + hf["ra_per_g"]) / 2)
        if house_home == house_away:  # a tie line is useless in baseball
            house_home += 1 if p_home >= 0.5 else -1 or 1
        out_games.append({
            "game_id": g["game_id"],
            "home": {"team": home, "starter": g.get("home_starter_name"), "form": hf},
            "away": {"team": away, "starter": g.get("away_starter_name"), "form": af},
            "house": {"p_home": round(p_home, 3),
                      "home_score": house_home, "away_score": house_away},
            "actual": {"home_score": g["home_score"], "away_score": g["away_score"],
                       "winner": "home" if g["home_score"] > g["away_score"] else "away"},
        })

    pack = {"league": "MLB", "season": 2025, "date": args.date,
            "source": "dugout cache/schedule_2025.json",
            "leakage_rule": "all form aggregates use games strictly before date",
            "games": out_games}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"daypack_mlb_{args.date}.json"
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out_games)} games → {out}")


if __name__ == "__main__":
    main()
