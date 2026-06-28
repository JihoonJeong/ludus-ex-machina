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
