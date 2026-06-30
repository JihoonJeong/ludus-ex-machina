"""Unit tests for lxm.wm_predict (Blockworld world-model eval helpers)."""

from lxm import wm_predict as wm


def _state(x=1, y=2, z=1, inv=None, cells=None, terrain=None):
    return {
        "agent": {"x": x, "y": y, "z": z, "facing": "north",
                  "inventory": inv or {}, "above": "air", "below": "grass"},
        "view": {"terrain": terrain or {"grass": 10},
                 "cells": cells if cells is not None else
                 [{"x": 1, "y": 1, "z": 1, "block": "dirt", "placed": True}]},
        "events": [{"text": "something"}],  # must be ignored by scoring
    }


# ── extract_prediction ──────────────────────────────────────────────────────

def test_extract_from_tag():
    txt = 'reasoning... <predicted_observation>{"agent": {"x": 5}}</predicted_observation> trailing'
    assert wm.extract_prediction(txt) == {"agent": {"x": 5}}


def test_extract_fallback_blob():
    assert wm.extract_prediction('no tag here {"a": 1} end') == {"a": 1}


def test_extract_none_on_garbage():
    assert wm.extract_prediction("no json at all") is None
    assert wm.extract_prediction("") is None
    assert wm.extract_prediction("<predicted_observation>not json</predicted_observation>") is None


def test_extract_multiline_json():
    txt = '<predicted_observation>\n{\n "agent": {"x": 1},\n "view": {}\n}\n</predicted_observation>'
    assert wm.extract_prediction(txt) == {"agent": {"x": 1}, "view": {}}


# ── compare_semantic ────────────────────────────────────────────────────────

def test_compare_exact():
    s = _state()
    c = wm.compare_semantic(s, s)
    assert c["exact"] is True
    assert c["factuality"] == 1.0
    assert c["agent_mismatches"] == {}


def test_compare_agent_mismatch():
    pred = _state(x=9)
    actual = _state(x=1)
    c = wm.compare_semantic(pred, actual)
    assert c["exact"] is False
    assert "x" in c["agent_mismatches"]
    assert c["agent_mismatches"]["x"] == {"predicted": 9, "actual": 1}
    assert 0.0 < c["factuality"] < 1.0


def test_compare_cells_diff():
    pred = _state(cells=[])
    actual = _state(cells=[{"x": 1, "y": 1, "z": 1, "block": "dirt", "placed": True}])
    c = wm.compare_semantic(pred, actual)
    assert c["cells_ok"] is False
    assert c["cells_missing"]  # the dirt cell present in actual, missing from pred
    assert not c["cells_extra"]


def test_compare_terrain_diff():
    c = wm.compare_semantic(_state(terrain={"grass": 9}), _state(terrain={"grass": 10}))
    assert c["terrain_ok"] is False
    assert c["exact"] is False


def test_compare_events_ignored():
    pred = _state()
    actual = _state()
    actual["events"] = [{"text": "totally different"}]
    assert wm.compare_semantic(pred, actual)["exact"] is True


def test_compare_non_dict():
    c = wm.compare_semantic(None, _state())
    assert c["format_ok"] is False
    assert c["exact"] is False
    assert c["factuality"] == 0.0


# ── is_no_op ────────────────────────────────────────────────────────────────

def test_is_no_op_true():
    s = _state()
    import copy
    assert wm.is_no_op(s, copy.deepcopy(s)) is True


def test_is_no_op_false_on_move():
    assert wm.is_no_op(_state(x=1), _state(x=2)) is False


def test_is_no_op_ignores_events():
    a, b = _state(), _state()
    b["events"] = [{"text": "x"}]
    assert wm.is_no_op(a, b) is True


# ── summarize ───────────────────────────────────────────────────────────────

def test_summarize():
    recs = [
        {"is_no_op": False, "comparison": {"exact": True, "factuality": 1.0}},
        {"is_no_op": False, "comparison": {"exact": False, "factuality": 0.5}},
        {"is_no_op": True, "comparison": {"exact": True, "factuality": 1.0}},
        {"is_no_op": True, "comparison": {"exact": False, "factuality": 0.8}},
    ]
    s = wm.summarize(recs)
    assert s["n"] == 4
    assert s["exact"] == 2
    assert s["exact_rate"] == 0.5
    assert s["active"]["n"] == 2 and s["active"]["exact"] == 1
    assert s["no_op"]["n"] == 2 and s["no_op"]["exact"] == 1


def test_summarize_empty():
    assert wm.summarize([])["n"] == 0


# ── generic layer: compare_facts / WMSpec / get_wm_spec (MUD + game-agnostic) ─

import pytest

from games.mud.engine import MudGame


def _mud():
    g = MudGame("astronomer_tower")
    return g, {"game": g.initial_state([{"agent_id": "a"}]), "lxm": {"match_id": "t"}}


def test_get_wm_spec_blockworld_and_mud():
    assert wm.get_wm_spec("blockworld").scored_keys == ("agent", "view")
    assert wm.get_wm_spec("mud").scored_keys == ("agent", "room", "flags")


def test_get_wm_spec_unknown_raises():
    with pytest.raises(ValueError):
        wm.get_wm_spec("nope")


def test_blockworld_spec_matches_legacy_helpers():
    """The blockworld spec must be behaviourally identical to the format-locked
    module functions (compare_semantic / is_no_op) it wraps."""
    spec = wm.get_wm_spec("blockworld")
    a, b = _state(x=1), _state(x=2)
    assert spec.is_no_op(a, _state(x=1)) is True
    assert spec.is_no_op(a, b) is False
    assert spec.compare(b, b) == wm.compare_semantic(b, b)


def test_compare_facts_exact():
    s = {"agent": {"location": "study", "inventory": []},
         "room": {"id": "study", "exits": {}}, "flags": {}}
    c = wm.compare_facts(s, s, ("agent", "room", "flags"))
    assert c["exact"] is True and c["factuality"] == 1.0 and c["mismatches"] == {}


def test_compare_facts_partial_mismatch():
    pred = {"agent": {"location": "landing", "inventory": []},
            "room": {"id": "study"}, "flags": {}}
    actual = {"agent": {"location": "study", "inventory": []},
              "room": {"id": "study"}, "flags": {}}
    c = wm.compare_facts(pred, actual, ("agent", "room", "flags"))
    assert c["exact"] is False
    assert "agent.location" in c["mismatches"]
    assert c["mismatches"]["agent.location"] == {"predicted": "landing", "actual": "study"}
    assert 0.0 < c["factuality"] < 1.0


def test_compare_facts_format_not_ok_when_key_missing():
    c = wm.compare_facts({"agent": {}}, {"agent": {}, "room": {}, "flags": {}},
                         ("agent", "room", "flags"))
    assert c["format_ok"] is False
    assert c["exact"] is False


def test_compare_facts_non_dict():
    c = wm.compare_facts(None, {"agent": {}}, ("agent",))
    assert c["format_ok"] is False and c["factuality"] == 0.0


def test_mud_spec_locked_go_is_no_op():
    g, st = _mud()
    spec = wm.get_wm_spec("mud")
    before = g.build_semantic_state("a", st)
    g.apply_move({"type": "action", "verb": "go", "direction": "east"}, "a", st)  # locked
    after = g.build_semantic_state("a", st)
    # turn advanced but is excluded from the scored projection
    assert before["turn"] != after["turn"]
    assert spec.is_no_op(before, after) is True


def test_mud_spec_effective_action_not_no_op():
    g, st = _mud()
    spec = wm.get_wm_spec("mud")
    before = g.build_semantic_state("a", st)
    g.apply_move({"type": "action", "verb": "take", "target": "star-chart"}, "a", st)
    after = g.build_semantic_state("a", st)
    assert spec.is_no_op(before, after) is False


def test_mud_spec_perfect_prediction_scores_exact():
    g, st = _mud()
    spec = wm.get_wm_spec("mud")
    g.apply_move({"type": "action", "verb": "take", "target": "star-chart"}, "a", st)
    after = g.build_semantic_state("a", st)
    perfect = spec.scored(after)  # an oracle that returns exactly the next scored state
    c = spec.compare(perfect, after)
    assert c["exact"] is True and c["factuality"] == 1.0


def test_mud_spec_lazy_prediction_flags_change():
    g, st = _mud()
    spec = wm.get_wm_spec("mud")
    before = g.build_semantic_state("a", st)
    g.apply_move({"type": "action", "verb": "take", "target": "star-chart"}, "a", st)
    after = g.build_semantic_state("a", st)
    lazy = spec.scored(before)  # a lazy predictor that echoes the BEFORE state
    c = spec.compare(lazy, after)
    assert c["exact"] is False
    assert any(k.startswith(("agent.", "room.")) for k in c["mismatches"])


def test_mud_spec_use_keeps_before_snapshot_independent():
    """Regression: build_semantic_state must deep-copy object state, else an
    in-place 'use' mutation corrupts the captured `before` snapshot."""
    g, st = _mud()
    spec = wm.get_wm_spec("mud")
    path = [("go", {"direction": "down"}), ("go", {"direction": "west"}),
            ("search", {"target": "globe"}), ("take", {"target": "saturn_ring"}),
            ("go", {"direction": "east"}), ("go", {"direction": "up"})]
    for verb, kw in path:
        g.apply_move({"type": "action", "verb": verb, **kw}, "a", st)
    before = g.build_semantic_state("a", st)
    g.apply_move({"type": "action", "verb": "use", "item": "saturn_ring", "target": "orrery"}, "a", st)
    after = g.build_semantic_state("a", st)
    orrery_before = next(o for o in before["room"]["objects"] if o["id"] == "orrery")
    assert orrery_before.get("state", {}).get("complete") is False  # NOT corrupted to True
    assert spec.is_no_op(before, after) is False
    orrery_after = next(o for o in after["room"]["objects"] if o["id"] == "orrery")
    assert orrery_after.get("state", {}).get("complete") is True   # completion localized to the object


def test_mud_build_prompt_uses_mud_instruction():
    g, st = _mud()
    spec = wm.get_wm_spec("mud")
    s = g.build_semantic_state("a", st)
    prompt = spec.build_prompt(s, {"type": "action", "verb": "look"})
    assert "MUD WORLD MODEL" in prompt
    assert "CURRENT STATE:" in prompt and "ACTION:" in prompt


# ── MUD review-driven scoring (Ludex Cody 2026-06-30): identity / fog / tags ──

def test_compare_mud_prose_insensitive():
    # same identity + mutable state, different prose name -> still exact (point 4)
    def _s(name):
        return {"agent": {"location": "study", "inventory": []},
                "room": {"id": "study", "name": name,
                         "objects": [{"id": "orrery", "name": name, "takeable": False,
                                      "state": {"complete": False}}], "exits": {}, "npcs": []},
                "flags": {}}
    c = wm.compare_mud(_s("BRASS ORRERY!!"), _s("brass orrery"), ("agent", "room", "flags"))
    assert c["exact"] is True and c["factuality"] == 1.0


def test_compare_mud_object_state_mismatch_caught():
    def _s(complete):
        return {"agent": {"location": "study", "inventory": []},
                "room": {"id": "study", "objects": [{"id": "orrery", "state": {"complete": complete}}],
                         "exits": {}, "npcs": []}, "flags": {}}
    c = wm.compare_mud(_s(True), _s(False), ("agent", "room", "flags"))
    assert c["exact"] is False and "room.objects" in c["mismatches"]


def test_compare_mud_format_ok_judged_on_raw_prediction():
    # model omits 'flags' -> format_ok False even though canonicalization fills it
    pred = {"agent": {"location": "study", "inventory": []},
            "room": {"id": "study", "objects": [], "exits": {}, "npcs": []}}
    actual = {"agent": {"location": "study", "inventory": []},
              "room": {"id": "study", "objects": [], "exits": {}, "npcs": []}, "flags": {}}
    c = wm.compare_mud(pred, actual, ("agent", "room", "flags"))
    assert c["format_ok"] is False and c["exact"] is False


def test_compare_mud_fog_mask_scores_agent_only():
    # destination room unknowable on first visit -> score only agent (point 3)
    pred = {"agent": {"location": "landing", "inventory": []},
            "room": {"id": "landing", "objects": [{"id": "WRONG_GUESS"}], "exits": {}, "npcs": []},
            "flags": {}}
    actual = {"agent": {"location": "landing", "inventory": []},
              "room": {"id": "landing", "objects": [{"id": "celestial_globe"}], "exits": {}, "npcs": []},
              "flags": {}}
    assert wm.compare_mud(pred, actual, ("agent", "room", "flags"))["exact"] is False
    assert wm.compare_mud(pred, actual, ("agent",))["exact"] is True


def test_wmspec_compare_keys_override():
    spec = wm.get_wm_spec("mud")
    pred = {"agent": {"location": "x"}, "room": {"id": "a"}, "flags": {}}
    actual = {"agent": {"location": "x"}, "room": {"id": "b"}, "flags": {}}
    assert spec.compare(pred, actual).get("exact") is False          # default keys: room differs
    assert spec.compare(pred, actual, keys=("agent",)).get("exact") is True


def test_classify_mud_noop_reasons():
    before = {"room": {"exits": {"east": {"to": "obs", "locked": True}, "down": {"to": "landing"}},
                       "objects": [{"id": "orrery", "name": "brass orrery"}]},
              "agent": {"inventory": []}}
    f = wm.classify_mud_noop
    assert f({"verb": "go", "direction": "east"}, before) == "locked-exit"
    assert f({"verb": "go", "direction": "north"}, before) == "no-such-exit"
    assert f({"verb": "take", "target": "brass key"}, before) == "absent-target"
    assert f({"verb": "examine", "target": "orrery"}, before) == "observation"
    assert f({"verb": "read", "target": "nonexistent"}, before) == "absent-target"
    assert f({"verb": "wait"}, before) == "observation"
    # a carried item is reachable for read/examine (engine resolves room + inventory)
    carrying = {"room": {"exits": {}, "objects": []},
                "agent": {"inventory": [{"id": "star_chart", "name": "star-chart"}]}}
    assert f({"verb": "read", "target": "star-chart"}, carrying) == "observation"
    assert f({"verb": "take", "target": "star_chart"}, carrying) == "already-held"


def test_summarize_mud_enrichments():
    recs = [
        {"is_no_op": True, "noop_reason": "locked-exit", "confabulated": False,
         "comparison": {"exact": True, "factuality": 1.0}},
        {"is_no_op": True, "noop_reason": "absent-target", "confabulated": True,
         "comparison": {"exact": False, "factuality": 0.5}},
        {"is_no_op": False, "missed": True, "comparison": {"exact": False, "factuality": 0.5}},
        {"is_no_op": False, "missed": False, "comparison": {"exact": True, "factuality": 1.0}},
    ]
    s = wm.summarize(recs)
    assert s["no_op_by_reason"]["locked-exit"] == {"n": 1, "exact": 1, "rate": 1.0}
    assert s["no_op_by_reason"]["absent-target"]["rate"] == 0.0
    assert s["over_prediction"]["confabulated"] == 1 and s["over_prediction"]["rate"] == 0.5
    assert s["under_prediction"]["missed"] == 1 and s["under_prediction"]["rate"] == 0.5


def test_summarize_blockworld_unaffected_by_enrichments():
    # records without the new fields -> no enrichment keys (Blockworld safe)
    s = wm.summarize([{"is_no_op": False, "comparison": {"exact": True, "factuality": 1.0}}])
    assert "no_op_by_reason" not in s and "over_prediction" not in s
