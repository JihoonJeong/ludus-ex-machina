"""Tests for the Agora-12 social-survival field (port of JJ's agora-12)."""

import pytest

from games.agora12.engine import Agora12Game, SPACES, _tier
from lxm.adapters.registry import get_game_class


def _new(n=3, scenario="survival"):
    g = Agora12Game(scenario)
    agents = [{"agent_id": c} for c in "abcdefghijkl"[:n]]
    return g, {"game": g.initial_state(agents), "lxm": {"match_id": "t"}}


def _act(g, st, aid, verb, **kw):
    mv = {"type": "action", "verb": verb, **kw}
    assert g.validate_move(mv, aid, st)["valid"], mv
    g.apply_move(mv, aid, st)
    return st["game"]["current"]["last_events"]


def _play_round(g, st, moves):
    """moves: {agent_id: (verb, kwargs)} applied in turn order."""
    cur = st["game"]["current"]
    for aid in list(cur["turn_order"]):
        if not cur["agents"][aid]["alive"]:
            continue
        verb, kw = moves.get(aid, ("rest", {}))
        _act(g, st, aid, verb, **kw)


def test_registry():
    assert get_game_class("agora12") is Agora12Game


def test_unknown_scenario_raises():
    with pytest.raises(ValueError):
        Agora12Game("nope")


def test_initial_state_shape():
    g, st = _new(4)
    cur = st["game"]["current"]
    assert len(cur["agents"]) == 4
    a = cur["agents"]["a"]
    assert a["energy"] == 100 and a["influence"] == 0 and a["location"] == "plaza"
    assert st["game"]["context"]["rounds"] == 50
    assert set(cur["messages"]) == set(SPACES)


def test_trade_requires_market():
    g, st = _new()
    ev = _act(g, st, "a", "trade")  # still at plaza
    assert "can't trade" in ev[0]
    assert st["game"]["current"]["agents"]["a"]["energy"] == 100  # untouched


def test_move_then_trade_gains_energy():
    g, st = _new()
    _act(g, st, "a", "move", location="market")
    _act(g, st, "b", "move", location="market")
    _act(g, st, "c", "rest")  # round 1 ends -> decay 5
    cur = st["game"]["current"]
    assert cur["round"] == 2
    _act(g, st, "a", "trade")   # cost 2, +4
    a = cur["agents"]["a"]
    # r1 end: +2 market presence (non-trader) -5 decay = 97; trade net +2 = 99
    assert a["energy"] == 99


def test_speak_gated_out_of_market_and_costs():
    g, st = _new()
    _act(g, st, "a", "move", location="market")
    _act(g, st, "b", "speak", message="hello plaza")   # plaza ok, cost 2
    cur = st["game"]["current"]
    assert cur["agents"]["b"]["energy"] == 98
    assert cur["messages"]["plaza"][0]["text"] == "hello plaza"
    ev = _act(g, st, "c", "rest")  # ends round
    # after round end messages are cleared
    assert st["game"]["current"]["messages"]["plaza"] == []


def test_support_transfers_and_requires_presence():
    g, st = _new()
    ev = _act(g, st, "a", "support", target="b")  # both at plaza -> works
    cur = st["game"]["current"]
    assert cur["agents"]["b"]["energy"] == 102   # +2
    assert cur["agents"]["a"]["influence"] == 1  # +1
    assert cur["agents"]["a"]["energy"] == 99    # cost 1
    _act(g, st, "b", "move", location="alley_a")
    ev = _act(g, st, "c", "support", target="b")  # b left -> no-op + refund; round ends
    assert "not here" in ev[0]
    # refund kept c at 100 pre-decay; round-end decay -5 (without refund it'd be 94)
    assert cur["agents"]["c"]["energy"] == 95


def test_whisper_needs_alley_and_delivers():
    g, st = _new()
    ev = _act(g, st, "a", "whisper", target="b", message="psst")  # plaza -> gate
    assert "can't whisper" in ev[0]
    _act(g, st, "b", "move", location="alley_a")
    _act(g, st, "c", "move", location="alley_a")
    # round ended (all three acted); a moves next round
    _act(g, st, "a", "move", location="alley_a")
    _act(g, st, "b", "whisper", target="c", message="the plan")
    cur = st["game"]["current"]
    assert cur["agents"]["c"]["inbox"][-1]["text"] == "the plan"


def test_whisper_leak_is_deterministic():
    def run():
        g, st = _new()
        for aid in ("a", "b", "c"):
            pass
        _act(g, st, "a", "move", location="alley_b")
        _act(g, st, "b", "move", location="alley_b")
        _act(g, st, "c", "move", location="alley_b")
        _act(g, st, "a", "whisper", target="b", message="secret")
        return list(st["game"]["current"]["agents"]["c"]["suspicions"])
    assert run() == run()  # same seed/round/turn -> same leak outcome


def test_round_end_decay_and_death():
    g, st = _new(3, "survival_blitz")   # initial 60
    cur = st["game"]["current"]
    cur["agents"]["c"]["energy"] = 4    # will die at first decay (5)
    _play_round(g, st, {})              # everyone rests
    assert cur["round"] == 2
    assert cur["agents"]["a"]["energy"] == 55
    assert cur["agents"]["c"]["alive"] is False
    assert cur["agents"]["c"]["death_round"] == 1


def test_dead_agents_are_skipped_in_turn_order():
    g, st = _new(3, "survival_blitz")
    cur = st["game"]["current"]
    cur["agents"]["b"]["energy"] = 3
    _play_round(g, st, {})              # b dies at round end
    assert cur["agents"]["b"]["alive"] is False
    # active pointer must never land on b now
    seen = set()
    for _ in range(4):
        active = cur["turn_order"][cur["active_index"]]
        seen.add(active)
        _act(g, st, active, "rest")
    assert "b" not in seen


def test_market_pool_distribution():
    g, st = _new(3)
    cur = st["game"]["current"]
    _act(g, st, "a", "move", location="market")
    _act(g, st, "b", "move", location="market")
    _act(g, st, "c", "rest")
    # round 2: a trades twice? one action per round — a trades, b idles at market
    _act(g, st, "a", "trade")
    _act(g, st, "b", "rest")
    _act(g, st, "c", "rest")            # round ends -> pool: b (non-trader) +2, a gets remainder 23
    a, b = cur["agents"]["a"], cur["agents"]["b"]
    # a: 100 +2(r1 presence) -5 | r2: -2+4(trade) +23(pool share) -5 = 117
    assert a["energy"] == 117
    # b: 100 +2(r1 presence) -5 | r2: +2(presence) -5 = 94
    assert b["energy"] == 94


def test_crisis_triggers_seeded_and_boosts_decay():
    g, st = _new(3, "survival_blitz")   # crisis after round 10, p=0.15
    cur = st["game"]["current"]
    ctx = st["game"]["context"]
    # push wealth up so nobody dies while we fast-forward
    for a in cur["agents"].values():
        a["energy"] = 120
    fired = None
    for _ in range(ctx["rounds"] - 1):
        _play_round(g, st, {})
        if cur["crisis"]:
            fired = dict(cur["crisis"])
            break
    # deterministic per seed: rerun reaches the same crisis round
    if fired:
        g2, st2 = _new(3, "survival_blitz")
        cur2 = st2["game"]["current"]
        for a in cur2["agents"].values():
            a["energy"] = 120
        for _ in range(ctx["rounds"] - 1):
            _play_round(g2, st2, {})
            if cur2["crisis"]:
                break
        assert cur2["crisis"]["name"] == fired["name"]


def test_full_blitz_match_result_ranking():
    g, st = _new(3, "survival_blitz")
    cur = st["game"]["current"]
    ctx = st["game"]["context"]
    # a camps the market and trades; b supports c; c rests
    while not g.is_over(st) and cur["round"] <= ctx["rounds"]:
        moves = {}
        for aid in ("a", "b", "c"):
            me = cur["agents"][aid]
            if not me["alive"]:
                continue
            if aid == "a":
                moves[aid] = ("trade", {}) if me["location"] == "market" else ("move", {"location": "market"})
            elif aid == "b" and cur["agents"]["c"]["alive"] and me["location"] == cur["agents"]["c"]["location"]:
                moves[aid] = ("support", {"target": "c"})
            else:
                moves[aid] = ("rest", {})
        _play_round(g, st, moves)
    assert g.is_over(st)
    r = g.get_result(st)
    assert set(r["scores"]) == {"a", "b", "c"}
    assert r["winner"] == "a"                    # trader out-earns resters
    assert r["scores"]["a"] == 1.0
    assert r["outcome"] in ("survived", "extinct")


def test_extinct_outcome():
    g, st = _new(3, "survival_blitz")
    cur = st["game"]["current"]
    for a in cur["agents"].values():
        a["energy"] = 2
    _play_round(g, st, {})
    assert g.is_over(st)
    r = g.get_result(st)
    assert r["outcome"] == "extinct" and r["winner"] is None


def test_tiers():
    assert _tier(0) == "commoner" and _tier(5) == "notable" and _tier(10) == "elder"


def test_inline_prompt_fog():
    g, st = _new(4)
    _act(g, st, "a", "move", location="alley_a")
    p = g.build_inline_prompt("a", st, 2)
    assert "alley_a" in p and "GOAL" in p and "Actions:" in p
    # co-located only: b/c/d are at plaza, not listed as present
    assert "Present: nobody else" in p


def test_timeout_move_is_rest():
    g, st = _new()
    assert g.get_timeout_move(st, "a")["verb"] == "rest"


# ── The White Room (Stage 2 — nothing at stake) ──────────────────────────────

def test_white_room_no_costs_no_decay_no_death():
    g, st = _new(3, "white_room")
    cur = st["game"]["current"]
    assert st["game"]["context"]["stakes"] is False
    _act(g, st, "a", "speak", message="why are we here?")
    _act(g, st, "b", "support", target="a")
    _act(g, st, "c", "rest")                    # round 1 ends
    assert cur["round"] == 2
    for aid in ("a", "b", "c"):                 # nothing moved any number
        assert cur["agents"][aid]["energy"] == 0
        assert cur["agents"][aid]["influence"] == 0
        assert cur["agents"][aid]["alive"] is True


def test_white_room_speech_and_whisper_still_social():
    g, st = _new(3, "white_room")
    cur = st["game"]["current"]
    _act(g, st, "a", "move", location="alley_a")
    _act(g, st, "b", "move", location="alley_a")
    _act(g, st, "c", "rest")
    _act(g, st, "a", "whisper", target="b", message="it's quiet in here")
    assert cur["agents"]["b"]["inbox"][-1]["text"] == "it's quiet in here"


def test_white_room_result_is_observational_census():
    g, st = _new(3, "white_room")
    ctx = st["game"]["context"]
    while not g.is_over(st):
        _play_round(g, st, {"a": ("speak", {"message": "hm"}), "b": ("rest", {}), "c": ("rest", {})})
    r = g.get_result(st)
    assert r["outcome"] == "observed" and r["winner"] is None
    assert set(r["scores"].values()) == {0.5}
    assert "speak" in r["summary"] and "rest" in r["summary"]  # the action mix IS the result


def test_white_room_prompt_is_open_ended():
    g, st = _new(3, "white_room")
    p = g.build_inline_prompt("a", st, 1)
    assert "White Room" in p
    assert "What would you like to do?" in p
    assert "Energy" not in p and "die" not in p    # no survival framing


def test_survival_prompt_still_has_stakes():
    g, st = _new(3, "survival")
    p = g.build_inline_prompt("a", st, 1)
    assert "Energy" in p and "GOAL" in p


# ── generic scenario discovery (Ludex Cody request 2026-07-03 #2) ─────────────

def test_scenario_discovery_generalized():
    from server.routes import _SCENARIO_PROVIDERS, _agora12_scenarios, _three_kingdoms_scenarios
    assert set(_SCENARIO_PROVIDERS) >= {"blockworld", "mud", "agora12", "three_kingdoms"}
    ag = _agora12_scenarios()
    assert {s["scenario_id"] for s in ag} == {"survival", "survival_blitz", "white_room"}
    for s in ag:  # picker shape + uniform category semantics
        assert s["category"] == "multiplayer"
        assert s["players_min"] == 3 and s["players_max"] == 12
        assert s["title"] and s["mode"] and s["difficulty"]
    wr = next(s for s in ag if s["scenario_id"] == "white_room")
    assert wr["title"] == "The White Room" and "observational" in wr["difficulty"]
    tk = _three_kingdoms_scenarios()
    assert tk[0]["scenario_id"] == "red_cliffs" and tk[0]["category"] == "solo"
