"""Tests for the Diplomacy game engine and its order adjudicator."""

import pytest

from games.diplomacy import world
from games.diplomacy.adjudicator import resolve
from games.diplomacy.engine import DiplomacyGame


# --------------------------------------------------------------------- helpers
def wrap(game, n=5):
    agents = [{"agent_id": f"p{i}", "display_name": f"P{i}", "seat": i} for i in range(n)]
    return {"game": game.initial_state(agents), "lxm": {"match_id": "t"}}


def cur(game, state):
    return game._current(state)


def step(game, state, move):
    aid = game.get_active_agent_id(state)
    v = game.validate_move(move, aid, state)
    assert v["valid"], f"{aid} {move} -> {v}"
    state["game"] = game.apply_move(move, aid, state)
    return aid


def advance_press(game, state):
    while cur(game, state)["phase"] == "press":
        step(game, state, {"type": "press", "messages": []})


def drive(game, state, decide, cap=800):
    turns = 0
    while not game.is_over(state) and turns < cap:
        aid = game.get_active_agent_id(state)
        assert aid is not None
        step(game, state, decide(aid, state))
        turns += 1
    return turns


# ------------------------------------------------------------------- the map
class TestWorld:
    def test_counts(self):
        assert len(world.PROVINCES) == 11
        assert len(world.all_supply_centers()) == 11
        assert len(world.POWERS) == 5

    def test_adjacency_symmetric(self):
        for a, nbrs in world.ADJACENCY.items():
            for b in nbrs:
                assert a in world.ADJACENCY[b]

    def test_capitals_are_home_centers(self):
        for power in world.POWERS:
            assert world.PROVINCES[power["capital"]]["home"] == power["id"]


# ------------------------------------------------------------- adjudication
class TestAdjudicator:
    def _run(self, units, orders):
        return resolve(units, orders)

    def test_supported_attack_dislodges(self):
        r = self._run(
            {"pyre": "crimson", "ashmoor": "gold", "duskgate": "gold"},
            {"ashmoor": {"type": "move", "dest": "pyre"},
             "duskgate": {"type": "support", "target": "pyre", "from": "ashmoor"}},
        )
        assert r["positions"]["pyre"] == "gold"
        assert "pyre" in r["dislodged"]

    def test_standoff_bounces(self):
        r = self._run(
            {"ashmoor": "crimson", "sunreach": "gold"},
            {"ashmoor": {"type": "move", "dest": "crown"},
             "sunreach": {"type": "move", "dest": "crown"}},
        )
        assert "crown" not in r["positions"]
        assert r["positions"]["ashmoor"] == "crimson"
        assert "crown" in r["standoffs"]

    def test_support_cut_defends(self):
        r = self._run(
            {"pyre": "crimson", "ashmoor": "gold", "duskgate": "gold", "coldwater": "crimson"},
            {"ashmoor": {"type": "move", "dest": "pyre"},
             "duskgate": {"type": "support", "target": "pyre", "from": "ashmoor"},
             "coldwater": {"type": "move", "dest": "duskgate"}},
        )
        assert r["positions"]["pyre"] == "crimson"          # attack only strength 1
        assert not r["dislodged"]
        assert r["outcomes"]["duskgate"] == "support-cut"

    def test_head_to_head_equal_bounces(self):
        r = self._run(
            {"ashmoor": "crimson", "sunreach": "gold"},
            {"ashmoor": {"type": "move", "dest": "sunreach"},
             "sunreach": {"type": "move", "dest": "ashmoor"}},
        )
        assert r["positions"] == {"ashmoor": "crimson", "sunreach": "gold"}

    def test_head_to_head_supported_dislodges(self):
        r = self._run(
            {"ashmoor": "crimson", "sunreach": "gold", "solace": "crimson"},
            {"ashmoor": {"type": "move", "dest": "sunreach"},
             "sunreach": {"type": "move", "dest": "ashmoor"},
             "solace": {"type": "support", "target": "sunreach", "from": "ashmoor"}},
        )
        assert r["positions"]["sunreach"] == "crimson"
        assert "sunreach" in r["dislodged"]
        assert "ashmoor" not in r["positions"]              # vacated by the mover

    def test_rotation_all_move(self):
        r = self._run(
            {"ashmoor": "crimson", "crown": "gold", "sunreach": "verdant"},
            {"ashmoor": {"type": "move", "dest": "crown"},
             "crown": {"type": "move", "dest": "sunreach"},
             "sunreach": {"type": "move", "dest": "ashmoor"}},
        )
        assert r["positions"] == {"crown": "crimson", "sunreach": "gold", "ashmoor": "verdant"}
        assert not r["dislodged"]

    def test_cannot_self_dislodge(self):
        r = self._run(
            {"ashmoor": "crimson", "pyre": "crimson", "duskgate": "crimson"},
            {"ashmoor": {"type": "move", "dest": "pyre"},
             "duskgate": {"type": "support", "target": "pyre", "from": "ashmoor"}},
        )
        assert r["positions"] == {"ashmoor": "crimson", "pyre": "crimson", "duskgate": "crimson"}
        assert not r["dislodged"]

    def test_illegal_move_becomes_hold(self):
        # tarn and pyre are not adjacent; move is dropped to a hold
        r = self._run({"tarn": "azure"}, {"tarn": {"type": "move", "dest": "pyre"}})
        assert r["positions"]["tarn"] == "azure"

    def test_dislodge_result_json_serializable(self):
        # regression: dislodged.forbidden was a set -> crashed the match log writer
        import json
        r = self._run(
            {"pyre": "crimson", "ashmoor": "gold", "duskgate": "gold"},
            {"ashmoor": {"type": "move", "dest": "pyre"},
             "duskgate": {"type": "support", "target": "pyre", "from": "ashmoor"}},
        )
        assert "pyre" in r["dislodged"]
        assert isinstance(r["dislodged"]["pyre"]["forbidden"], list)
        json.dumps(r)  # must not raise


# --------------------------------------------------------------- initial state
class TestInitialState:
    def test_five_player_assignment(self):
        g = DiplomacyGame()
        c = g.initial_state([{"agent_id": f"p{i}", "seat": i} for i in range(5)])["current"]
        assert c["players"]["p0"]["power"] == "crimson"
        assert c["players"]["p4"]["power"] == "violet"
        # one army + owned center per capital, neutrals unowned
        assert c["units"] == {"pyre": "p0", "solace": "p1", "thorne": "p2", "tarn": "p3", "vael": "p4"}
        assert c["sc_owner"]["pyre"] == "p0"
        assert c["sc_owner"]["crown"] is None
        assert c["phase"] == "press"

    def test_three_player_leaves_neutral_capitals(self):
        g = DiplomacyGame()
        c = g.initial_state([{"agent_id": f"p{i}", "seat": i} for i in range(3)])["current"]
        assert set(c["units"].values()) == {"p0", "p1", "p2"}
        assert "tarn" not in c["units"] and c["sc_owner"]["tarn"] is None  # azure unseated

    def test_player_bounds(self):
        g = DiplomacyGame()
        with pytest.raises(ValueError):
            g.initial_state([{"agent_id": "p0", "seat": 0}, {"agent_id": "p1", "seat": 1}])
        with pytest.raises(ValueError):
            g.initial_state([{"agent_id": f"p{i}", "seat": i} for i in range(6)])


# ---------------------------------------------------------------- phase flow
class TestPhaseFlow:
    def test_press_then_orders(self):
        g = DiplomacyGame(press_rounds=1)
        s = wrap(g)
        # all five take a press turn, in seat order
        seen = []
        while cur(g, s)["phase"] == "press":
            seen.append(step(g, s, {"type": "press", "messages": []}))
        assert seen == ["p0", "p1", "p2", "p3", "p4"]
        assert cur(g, s)["phase"] == "orders"

    def test_orders_resolve_advances_year(self):
        g = DiplomacyGame()
        s = wrap(g)
        advance_press(g, s)
        # everyone holds -> no dislodge, no builds -> straight to next year's press
        while cur(g, s)["phase"] == "orders":
            aid = g.get_active_agent_id(s)
            step(g, s, {"type": "orders", "orders": {p: "hold" for p in g._units_of(cur(g, s), aid)}})
        assert cur(g, s)["year"] == 1902
        assert cur(g, s)["phase"] == "press"


# ----------------------------------------------------------------- validation
class TestValidation:
    def test_wrong_phase_rejected(self):
        g = DiplomacyGame()
        s = wrap(g)  # press phase
        aid = g.get_active_agent_id(s)
        assert not g.validate_move({"type": "orders", "orders": {}}, aid, s)["valid"]

    def test_already_acted_rejected(self):
        # pending is set-like (any member may submit, like Avalon votes); but once an
        # agent has acted it is removed and may not act again this sub-phase.
        g = DiplomacyGame()
        s = wrap(g)
        advance_press(g, s)
        p0 = g.get_active_agent_id(s)
        step(g, s, {"type": "orders", "orders": {"pyre": "ashmoor"}})
        assert not g.validate_move({"type": "orders", "orders": {"pyre": "hold"}}, p0, s)["valid"]

    def test_illegal_order_rejected(self):
        g = DiplomacyGame()
        s = wrap(g)
        advance_press(g, s)
        aid = g.get_active_agent_id(s)  # p0, army in pyre
        # pyre not adjacent to tarn
        assert not g.validate_move({"type": "orders", "orders": {"pyre": "tarn"}}, aid, s)["valid"]
        # ordering a unit you don't own
        assert not g.validate_move({"type": "orders", "orders": {"solace": "hold"}}, aid, s)["valid"]

    def test_legal_order_accepted(self):
        g = DiplomacyGame()
        s = wrap(g)
        advance_press(g, s)
        aid = g.get_active_agent_id(s)
        assert g.validate_move({"type": "orders", "orders": {"pyre": "ashmoor"}}, aid, s)["valid"]


# ------------------------------------------------------------------- fog
class TestFog:
    def test_orders_hidden_until_resolved(self):
        g = DiplomacyGame()
        s = wrap(g)
        advance_press(g, s)
        p0 = g.get_active_agent_id(s)
        step(g, s, {"type": "orders", "orders": {"pyre": "ashmoor"}})  # p0 submits, now p1 to move
        seen_by_p1 = g.filter_state_for_agent(s, "p1")["game"]["current"]["orders_submitted"]
        seen_by_p0 = g.filter_state_for_agent(s, p0)["game"]["current"]["orders_submitted"]
        assert seen_by_p1["p0"] == "submitted"
        assert seen_by_p0["p0"] == {"pyre": "ashmoor"}

    def test_private_press_masked(self):
        g = DiplomacyGame()
        s = wrap(g)
        step(g, s, {"type": "press", "messages": [{"to": "p1", "text": "secret pact"}]})  # p0 -> p1
        p1_view = g.filter_state_for_agent(s, "p1")["game"]["current"]["press_messages"]
        p2_view = g.filter_state_for_agent(s, "p2")["game"]["current"]["press_messages"]
        assert any(m["text"] == "secret pact" for m in p1_view)
        assert p2_view == []


# ---------------------------------------------------------------- timeout
class TestTimeout:
    def test_timeout_moves_valid_each_phase(self):
        g = DiplomacyGame()
        s = wrap(g)
        for _ in range(40):  # walk a couple of years; every forced move must validate
            if g.is_over(s):
                break
            aid = g.get_active_agent_id(s)
            mv = g.get_timeout_move(aid, s)
            assert g.validate_move(mv, aid, s)["valid"], (cur(g, s)["phase"], mv)
            step(g, s, mv)


class TestSerialization:
    def test_state_serializable_after_dislodge(self):
        # the full game state (incl. dislodged.forbidden) must be JSON-serializable
        # every turn — the orchestrator writes it to the match log after each move.
        import json
        g = DiplomacyGame()
        s = wrap(g, 5)
        c = cur(g, s)
        c["units"] = {"pyre": "p0", "ashmoor": "p1", "duskgate": "p1"}
        c["phase"] = "orders"
        c["pending"] = ["p1"]
        c["orders_submitted"] = {}
        move = {"type": "orders",
                "orders": {"ashmoor": "pyre", "duskgate": {"support": "pyre", "from": "ashmoor"}}}
        assert g.validate_move(move, "p1", s)["valid"]
        s["game"] = g.apply_move(move, "p1", s)
        c2 = cur(g, s)
        assert "pyre" in c2["dislodged"]      # the attack dislodged p0
        json.dumps(s)                         # must not raise (regression)


# ---------------------------------------------------------------- full games
class TestFullGame:
    def test_all_hold_is_draw(self):
        g = DiplomacyGame(max_years=4)
        s = wrap(g)
        drive(g, s, lambda aid, st: g.get_timeout_move(aid, st))
        res = g.get_result(s)
        assert g.is_over(s)
        assert res["outcome"] == "draw"
        assert all(v == 1 for v in res["scores"].values())

    def test_greedy_expansion_wins(self):
        g = DiplomacyGame(max_years=25)
        s = wrap(g)

        def decide(aid, st):
            c = cur(g, st)
            ph = c["phase"]
            units = g._units_of(c, aid)
            scs = g._sc_of(c, aid)
            if ph == "press":
                return {"type": "press", "messages": []}
            if ph == "orders":
                if aid != "p0":
                    return {"type": "orders", "orders": {p: "hold" for p in units}}
                orders, taken = {}, set()
                for u in units:
                    grab = [n for n in world.neighbors(u)
                            if world.is_supply_center(n) and c["sc_owner"].get(n) != "p0"
                            and n not in c["units"] and n not in taken]
                    orders[u] = grab[0] if grab else "hold"
                    if grab:
                        taken.add(grab[0])
                return {"type": "orders", "orders": orders}
            if ph == "retreats":
                mine = [p for p, i in c["dislodged"].items() if i["owner"] == aid]
                return {"type": "retreat", "retreats": {p: "disband" for p in mine}}
            if ph == "builds":
                delta = len(scs) - len(units)
                if delta > 0:
                    cap = c["players"][aid]["capital"]
                    can = c["sc_owner"].get(cap) == aid and cap not in c["units"]
                    return {"type": "build", "builds": [cap] if can else []}
                if delta < 0:
                    return {"type": "build", "disbands": units[:-delta]}
                return {"type": "build", "builds": []}
            return g.get_timeout_move(aid, st)

        drive(g, s, decide)
        res = g.get_result(s)
        assert res["outcome"] == "domination"
        assert res["winner"] == "p0"
        assert res["scores"]["p0"] >= world.WIN_SUPPLY_CENTERS
