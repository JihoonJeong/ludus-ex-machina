"""Tests for the Dugout prediction field (day-pack backtest, game #13)."""

import pytest

from games.dugout.engine import DugoutGame, SCENARIOS, score_forecast
from lxm.adapters.registry import get_game_class


def _new(scenario="mlb_20250625_anon"):
    g = DugoutGame(scenario_id=scenario)
    return g, {"game": g.initial_state([{"agent_id": "a"}]), "lxm": {"match_id": "t"}}


def _forecast(g, st, **kw):
    mv = {"type": "forecast", **kw}
    v = g.validate_move(mv, "a", st)
    assert v["valid"], v["message"]
    g.apply_move(mv, "a", st)
    return st["game"]["current"]


# ── rubric port (must mirror dugout/daily/scoring.py exactly) ─────────────────

def test_rubric_perfect_forecast():
    bd = score_forecast("home", 5, 3, 1.0, actual_home=5, actual_away=3)
    assert bd["winner_points"] == 50
    assert bd["score_points"] == 40.0
    assert bd["exact_score_bonus"] == 10
    assert bd["calibration_points"] == 10.0
    assert bd["total"] == 110.0


def test_rubric_wrong_winner_zero_confidence_floor():
    # wrong pick at high confidence: Brier (0.9-0)^2=0.81 → calibration 0
    bd = score_forecast("home", 5, 3, 0.9, actual_home=2, actual_away=6)
    assert bd["winner_points"] == 0
    assert bd["calibration_points"] == 0.0


def test_rubric_score_error_curve():
    # total_diff=1 → 40-5=35; diff=2 → 40-2^1.5*5≈25.9; matches dugout formula
    bd1 = score_forecast("home", 5, 3, None, actual_home=5, actual_away=2)
    assert bd1["score_points"] == 35.0
    bd2 = score_forecast("home", 5, 3, None, actual_home=6, actual_away=2)
    assert bd2["score_points"] == pytest.approx(25.9, abs=0.1)


def test_rubric_coinflip_confidence_gives_half_calibration():
    bd = score_forecast("home", 4, 3, 0.5, actual_home=5, actual_away=3)
    assert bd["calibration_points"] == 5.0  # Brier 0.25 → 5 pts either way


# ── engine lifecycle ─────────────────────────────────────────────────────────

def test_registered_in_registry():
    assert get_game_class("dugout") is DugoutGame


def test_scenarios_pair_shares_daypack():
    a, n = SCENARIOS["mlb_20250625_anon"], SCENARIOS["mlb_20250625_named"]
    assert a["daypack"] == n["daypack"] and a["anon"] and not n["anon"]


def test_full_slate_match_and_result():
    g, st = _new()
    n = st["game"]["context"]["n_games"]
    assert n >= 10
    for _ in range(n):
        _forecast(g, st, winner="home", home_score=5, away_score=3, confidence=0.6)
    assert g.is_over(st)
    r = g.get_result(st)
    assert r["outcome"] in ("beat_house", "lost_to_house", "tied_house")
    assert r["n_games"] == n
    assert r["agent_total"] > 0  # always-home earns some winner points somewhere


def test_actuals_never_leak_into_prompt():
    # the day-pack's `actual` block must never be rendered into any prompt —
    # neither the word itself nor the house forecast (which would anchor)
    g, st = _new("mlb_20250625_named")
    n = st["game"]["context"]["n_games"]
    for i in range(n):
        p = g.build_inline_prompt("a", st, i + 1)
        assert "actual" not in p.lower()
        # the running you-vs-house total is fine; the CURRENT game's house
        # forecast (its win prob) must not appear as an anchor
        gm = g._pack["games"][st["game"]["current"]["game_index"]]
        assert "p_home" not in p and str(gm["house"]["p_home"]) not in p
        _forecast(g, st, winner="away", home_score=2, away_score=6, confidence=0.55)


def test_anon_masks_identities_named_shows_them():
    ga, sa = _new("mlb_20250625_anon")
    gn, sn = _new("mlb_20250625_named")
    pa = ga.build_inline_prompt("a", sa, 1)
    pn = gn.build_inline_prompt("a", sn, 1)
    team = gn._pack["games"][0]["home"]["team"]
    starter = gn._pack["games"][0]["home"]["starter"]
    assert team in pn and (starter or "?") in pn
    assert team not in pa and (not starter or starter not in pa)
    assert "masked" in pa


def test_house_scored_on_same_rubric():
    g, st = _new()
    _forecast(g, st, winner="home", home_score=4, away_score=2, confidence=0.7)
    f = st["game"]["current"]["forecasts"][0]
    assert set(f["house"].keys()) == set(f["agent"].keys())
    assert 0 <= f["house"]["total"] <= 110


def test_validate_rejects_bad_moves():
    g, st = _new()
    assert not g.validate_move({"type": "forecast", "winner": "draw",
                                "home_score": 3, "away_score": 2}, "a", st)["valid"]
    assert not g.validate_move({"type": "forecast", "winner": "home",
                                "home_score": -1, "away_score": 2}, "a", st)["valid"]
    assert not g.validate_move({"type": "forecast", "winner": "home",
                                "home_score": 3, "away_score": 2,
                                "confidence": 1.7}, "a", st)["valid"]


def test_timeout_move_is_valid():
    g, st = _new()
    tm = g.get_timeout_move(st, "a")
    assert g.validate_move(tm, "a", st)["valid"]


def test_scenarios_discovery():
    from server.routes import _dugout_scenarios
    rows = _dugout_scenarios()
    ids = {r["scenario_id"] for r in rows}
    assert ids == set(SCENARIOS)
    for r in rows:
        assert r["category"] == "solo" and r["players"] == 1
