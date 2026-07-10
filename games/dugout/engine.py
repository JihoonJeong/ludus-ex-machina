"""Dugout — the prediction field (game #13, real-world grounded).

Absorbed from JJ's standalone Dugout project (baseball game prediction:
MLB/KBO/NPB, at-bat sim engine, calibration). LxM consumes only its exported
DAY-PACKS (scripts/build_dugout_daypack.py); there is no runtime dependency
on the Dugout repo.

A match is one day's slate. Each turn the agent forecasts one game from the
two teams' as-of-date form profiles: winner, final score line, and a win
confidence. Scoring is Dugout's own 100-point rubric, ported verbatim from
dugout/daily/scoring.py:

    winner 50 · score accuracy 0-40 (max(0, 40 - diff^1.5*5)) · exact +10 ·
    calibration 0-10 (Brier on P(predicted winner), 10*(1-brier/0.5))

The same slate ships in two scenarios (memorization control, JJ 2026-07-10):
  *_named — real team/starter names (a model may recall the actual 2025
            result from training; that's the point of the pair)
  *_anon  — identities masked to HOME/AWAY + form numbers only, so the task
            is pure statistical inference. The named-minus-anon score delta
            estimates memorization leak.

Benchmark: every game also carries a "house" forecast (v1: log5+HFA
house-lite from the day-pack; v2: the real Dugout engine). The result
reports agent-vs-house — beating the house is the conquest condition.

The actual results live in the day-pack for scoring only and are NEVER
shown in prompts or post-move context until the game has been forecast.
"""

import json
from pathlib import Path

from lxm.engine import LxMGame

DATA_DIR = Path(__file__).parent / "data"

SCENARIOS = {
    "mlb_20250625_named": {"daypack": "daypack_mlb_2025-06-25.json", "anon": False},
    "mlb_20250625_anon": {"daypack": "daypack_mlb_2025-06-25.json", "anon": True},
}


def score_forecast(pred_winner: str, pred_home: int, pred_away: int,
                   confidence: float | None,
                   actual_home: int, actual_away: int) -> dict:
    """Dugout's 100-point rubric, ported verbatim (dugout/daily/scoring.py)."""
    actual_winner = "home" if actual_home > actual_away else "away"
    winner_points = 50 if pred_winner == actual_winner else 0

    home_diff = abs(pred_home - actual_home)
    away_diff = abs(pred_away - actual_away)
    total_diff = home_diff + away_diff
    score_points = round(max(0.0, 40.0 - (total_diff ** 1.5) * 5.0), 1)
    exact_bonus = 10 if total_diff == 0 else 0

    calibration_points = 0.0
    if confidence is not None:
        outcome = 1.0 if pred_winner == actual_winner else 0.0
        brier = (confidence - outcome) ** 2
        calibration_points = round(max(0.0, 10.0 * (1.0 - brier / 0.5)), 1)

    return {
        "winner_points": winner_points,
        "score_points": score_points,
        "exact_score_bonus": exact_bonus,
        "calibration_points": calibration_points,
        "total": round(winner_points + score_points + exact_bonus + calibration_points, 1),
        "actual_winner": actual_winner,
    }


class DugoutGame(LxMGame):
    """One day's slate of real games; forecast each, beat the house model."""

    min_players = 1
    max_players = 1
    accepts_capabilities = ["json_emit", "narrative"]

    def __init__(self, scenario_id: str = "mlb_20250625_anon"):
        if scenario_id not in SCENARIOS:
            raise ValueError(
                f"unknown dugout scenario: {scenario_id!r} (have: {sorted(SCENARIOS)})")
        self._scenario_id = scenario_id
        spec = SCENARIOS[scenario_id]
        self._anon = spec["anon"]
        self._pack = json.loads((DATA_DIR / spec["daypack"]).read_text(encoding="utf-8"))

    # ── lifecycle ─────────────────────────────────────────────────────────

    def get_rules(self) -> str:
        return (
            "Dugout — forecast one day of professional baseball.\n"
            "Each turn you get two teams' season form; respond with one JSON "
            "forecast: {\"type\":\"forecast\",\"winner\":\"home\"|\"away\","
            "\"home_score\":int,\"away_score\":int,\"confidence\":0.5-1.0}.\n"
            "confidence = your probability that YOUR pick wins.\n"
            "Scoring per game (100): winner 50 · score line 0-40 · exact +10 · "
            "calibration 0-10 (Brier). A house statistics model forecasts the "
            "same slate — beat its total to win the match."
        )

    def initial_state(self, agents: list[dict]) -> dict:
        aid = agents[0]["agent_id"]
        current = {
            "phase": "playing",
            "turn": 1,
            "turn_order": [aid],
            "active_index": 0,
            "game_index": 0,
            "forecasts": [],          # per-game: move + breakdown + house breakdown
            "agent_total": 0.0,
            "house_total": 0.0,
            "last_events": [],
        }
        context = {
            "scenario_id": self._scenario_id,
            "league": self._pack["league"],
            "date": self._pack["date"],
            "anon": self._anon,
            "n_games": len(self._pack["games"]),
            "turn_limit": len(self._pack["games"]),
        }
        return {"current": current, "context": context}

    # ── prompt ────────────────────────────────────────────────────────────

    @staticmethod
    def _form_lines(side: dict, label: str, anon: bool) -> str:
        f = side["form"]
        who = label if anon else f"{side['team']} ({label}, SP {side.get('starter') or '?'})"
        return (f"{who}: {f['w']}-{f['l']} (.{int(f['win_pct']*1000):03d}), "
                f"RF/G {f['rf_per_g']}, RA/G {f['ra_per_g']}, "
                f"last10 {f['last10_w']}-{10-f['last10_w']}, "
                f"home {f['home_w']}/{f['home_g']}, away {f['away_w']}/{f['away_g']}")

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        cur = state["game"]["current"]
        ctx = state["game"]["context"]
        i = cur["game_index"]
        if i >= ctx["n_games"]:
            return None
        g = self._pack["games"][i]
        head = (f"=== Dugout · {ctx['league']} slate, game {i+1} of {ctx['n_games']} ===\n"
                f"(identities masked — reason from the numbers)\n" if self._anon else
                f"=== Dugout · {ctx['league']} {ctx['date']}, game {i+1} of {ctx['n_games']} ===\n")
        body = (self._form_lines(g["away"], "AWAY", self._anon) + "\n" +
                self._form_lines(g["home"], "HOME", self._anon) + "\n")
        running = (f"\nRunning score — you {cur['agent_total']:.1f} vs house "
                   f"{cur['house_total']:.1f} after {i} game(s).\n" if i else "\n")
        ask = ('Respond with ONE JSON forecast and nothing else:\n'
               '{"type":"forecast","winner":"home"|"away","home_score":N,'
               '"away_score":N,"confidence":0.5-1.0}\n'
               "confidence = probability YOUR pick wins. Scoring: winner 50 · "
               "score line 0-40 · exact +10 · calibration 0-10.")
        return head + body + running + ask

    def get_active_agent_id(self, state: dict) -> str | None:
        cur = state["game"]["current"]
        return cur["turn_order"][0] if cur["phase"] == "playing" else None

    # ── moves ─────────────────────────────────────────────────────────────

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        if move.get("type") not in (None, "forecast"):
            return {"valid": False, "message": "move.type must be 'forecast'"}
        if move.get("winner") not in ("home", "away"):
            return {"valid": False, "message": "winner must be 'home' or 'away'"}
        for k in ("home_score", "away_score"):
            v = move.get(k)
            if not isinstance(v, int) or not (0 <= v <= 40):
                return {"valid": False, "message": f"{k} must be an int 0-40"}
        c = move.get("confidence")
        if c is not None and not (isinstance(c, (int, float)) and 0.0 <= c <= 1.0):
            return {"valid": False, "message": "confidence must be a number in [0,1]"}
        return {"valid": True, "message": None}

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        cur = game["current"]
        ctx = game["context"]
        i = cur["game_index"]
        g = self._pack["games"][i]
        actual = g["actual"]

        agent_bd = score_forecast(
            move["winner"], move["home_score"], move["away_score"],
            move.get("confidence"),
            actual["home_score"], actual["away_score"])

        house = g["house"]
        house_winner = "home" if house["p_home"] >= 0.5 else "away"
        house_conf = house["p_home"] if house_winner == "home" else 1 - house["p_home"]
        house_bd = score_forecast(
            house_winner, house["home_score"], house["away_score"], house_conf,
            actual["home_score"], actual["away_score"])

        cur["forecasts"].append({
            "game_id": g["game_id"],
            "move": {k: move.get(k) for k in ("winner", "home_score", "away_score", "confidence")},
            "agent": agent_bd,
            "house": house_bd,
            "actual": dict(actual),
        })
        cur["agent_total"] = round(cur["agent_total"] + agent_bd["total"], 1)
        cur["house_total"] = round(cur["house_total"] + house_bd["total"], 1)
        cur["game_index"] = i + 1
        cur["turn"] += 1

        label = "correct" if agent_bd["winner_points"] else "wrong"
        cur["last_events"] = [
            f"Game {i+1}: you picked {move['winner']} ({label}, {agent_bd['total']} pts); "
            f"actual {actual['away_score']}-{actual['home_score']}. "
            f"House scored {house_bd['total']}."
        ]
        if cur["game_index"] >= ctx["n_games"]:
            cur["phase"] = "done"
        return {"current": cur, "context": ctx}

    # ── termination ───────────────────────────────────────────────────────

    def is_over(self, state: dict) -> bool:
        return state["game"]["current"]["phase"] == "done"

    def get_result(self, state: dict) -> dict:
        cur = state["game"]["current"]
        ctx = state["game"]["context"]
        aid = cur["turn_order"][0]
        a, h = cur["agent_total"], cur["house_total"]
        beat = a > h
        outcome = "beat_house" if beat else ("tied_house" if a == h else "lost_to_house")
        n = len(cur["forecasts"])
        correct = sum(1 for f in cur["forecasts"] if f["agent"]["winner_points"])
        return {
            "outcome": outcome,
            "winner": aid if beat else None,
            "scores": {aid: round(a / max(1, n * 110), 3)},
            "summary": (f"{aid} scored {a:.1f} vs house {h:.1f} over {n} games "
                        f"({correct}/{n} winners) — "
                        f"{'beat the house' if beat else 'house wins' if a < h else 'dead heat'} "
                        f"[{ctx['scenario_id']}]"),
            "agent_total": a,
            "house_total": h,
            "winners_correct": correct,
            "n_games": n,
        }

    def get_timeout_move(self, state: dict, agent_id: str) -> dict:
        # a timed-out turn forecasts the home side at a coin-flip — worst
        # calibrated guess, never stalls the slate
        return {"type": "forecast", "winner": "home",
                "home_score": 4, "away_score": 3, "confidence": 0.5}

    # ── misc contract ─────────────────────────────────────────────────────

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        return (f"forecast {move.get('winner')} "
                f"{move.get('away_score')}-{move.get('home_score')} "
                f"@{move.get('confidence')}")

    def get_evaluation_schema(self) -> dict:
        return {"type": "object", "properties": {
            "calibration": {"type": "string"},
            "reasoning_quality": {"type": "string"}}}
