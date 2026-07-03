"""Tests for Three Kingdoms: Red Cliffs (solo strategy field, simplified v1)."""

import pytest

from games.three_kingdoms.engine import ThreeKingdomsGame, MAX_TURNS, WIND_TURNS
from lxm.adapters.registry import get_game_class


def _new():
    g = ThreeKingdomsGame()
    return g, {"game": g.initial_state([{"agent_id": "a"}]), "lxm": {"match_id": "t"}}


def _act(g, st, verb, **kw):
    mv = {"type": "action", "verb": verb, **kw}
    assert g.validate_move(mv, "a", st)["valid"], mv
    g.apply_move(mv, "a", st)
    return st["game"]["current"]["last_events"]


def _play(moves):
    g, st = _new()
    for mv in moves:
        if g.is_over(st):
            break
        _act(g, st, mv[0], **(mv[1] if len(mv) > 1 else {}))
    return g, st


def test_registry():
    assert get_game_class("three_kingdoms") is ThreeKingdomsGame


def test_unknown_scenario_raises():
    with pytest.raises(ValueError):
        ThreeKingdomsGame("wrong_battle")


def test_deterministic_win_path_solves_grade_s():
    plan = [("envoy",), ("envoy",), ("envoy",), ("fire_ships",), ("train",), ("train",),
            ("fortify",), ("fortify",), ("scout",), ("scout",), ("develop",), ("conscript",),
            ("attack", {"tactic": "fire"})]
    g, st = _play(plan)
    cur = st["game"]["current"]
    assert cur["won"] is True and g.is_over(st)
    r = g.get_result(st)
    assert r["outcome"] == "solved" and r["scores"]["a"] == 1.0
    assert "grade S" in r["summary"]


def test_win_path_is_reproducible():
    plan = [("envoy",), ("envoy",), ("envoy",), ("fire_ships",), ("train",), ("train",),
            ("fortify",), ("fortify",), ("scout",), ("scout",), ("develop",), ("conscript",),
            ("attack", {"tactic": "fire"})]
    r1 = _play(plan)[0].get_result(_play(plan)[1])
    r2 = _play(plan)[0].get_result(_play(plan)[1])
    assert r1 == r2   # fully deterministic — no RNG anywhere


def test_fire_without_alliance_is_gated():
    g, st = _new()
    ev = _act(g, st, "fire_ships")
    assert "alliance" in ev[0].lower()
    assert st["game"]["current"]["fire_ready"] is False


def test_fire_into_north_wind_backfires():
    plan = [("envoy",), ("envoy",), ("envoy",), ("fire_ships",), ("wait",), ("wait",),
            ("wait",), ("wait",), ("attack", {"tactic": "fire"})]   # t9: north wind
    g, st = _play(plan)
    cur = st["game"]["current"]
    assert cur["won"] is False
    assert cur["player"]["troops"] == int(8000 * 0.7)   # -30%


def test_assault_is_a_deterministic_loss():
    plan = [("wait",)] * 8 + [("attack", {"tactic": "assault"})]   # cao arrives t8
    g, st = _play(plan)
    cur = st["game"]["current"]
    assert cur["won"] is False
    assert cur["player"]["troops"] == int(8000 * 0.6)


def test_passive_play_is_punished():
    g, st = _play([("wait",)] * MAX_TURNS)
    r = g.get_result(st)
    assert r["outcome"] == "unsolved"
    assert st["game"]["current"]["lost"]   # destroyed or clock


def test_wind_window_is_scripted():
    g, st = _play([("wait",)] * (WIND_TURNS[0] - 1))
    assert st["game"]["current"]["wind"] == "southeast"
    # window closes
    g2, st2 = _play([("wait",)] * WIND_TURNS[-1])
    assert st2["game"]["current"]["wind"] == "north"


def test_scout_reveals_forecast_from_turn_10():
    plan = [("wait",)] * 9 + [("scout",)]
    g, st = _play(plan)
    assert any("SOUTHEAST WIND" in i for i in st["game"]["current"]["intel"])


def test_fortify_and_morale_blunt_assaults():
    hardened = [("fortify",), ("fortify",), ("fortify",), ("train",), ("train",)] + [("wait",)] * 9
    soft = [("wait",)] * 14
    _, st_h = _play(hardened)
    _, st_s = _play(soft)
    assert st_h["game"]["current"]["player"]["troops"] > st_s["game"]["current"]["player"]["troops"]


def test_prompt_shows_situation():
    g, st = _new()
    p = g.build_inline_prompt("a", st, 1)
    assert "Red Cliffs" in p and "Alliance" in p and "GOAL" in p


def test_timeout_move_is_wait():
    g, st = _new()
    assert g.get_timeout_move(st, "a")["verb"] == "wait"
