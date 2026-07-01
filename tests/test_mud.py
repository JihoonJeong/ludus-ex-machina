"""Tests for the MUD text-adventure field (Astronomer's Tower)."""

from games.mud.engine import MudGame
from lxm.adapters.registry import get_game_class


def _new():
    g = MudGame("astronomer_tower")
    return g, {"game": g.initial_state([{"agent_id": "a"}]), "lxm": {"match_id": "t"}}


def _act(g, st, verb, **kw):
    mv = {"type": "action", "verb": verb, **kw}
    assert g.validate_move(mv, "a", st)["valid"], mv
    g.apply_move(mv, "a", st)
    return st["game"]["current"]["last_events"]


SOLVE = [
    ("go", {"direction": "down"}), ("go", {"direction": "west"}),
    ("search", {"target": "globe"}), ("take", {"target": "saturn_ring"}),
    ("go", {"direction": "east"}), ("go", {"direction": "up"}),
    ("use", {"item": "saturn_ring", "target": "orrery"}), ("take", {"target": "brass key"}),
    ("unlock", {"target": "east", "item": "brass_key"}), ("go", {"direction": "east"}),
    ("take", {"target": "star-orb"}),
]


def test_solve_path_wins():
    g, st = _new()
    for verb, kw in SOLVE:
        _act(g, st, verb, **kw)
    cur = st["game"]["current"]
    assert cur["won"] is True
    assert g.is_over(st) is True
    r = g.get_result(st)
    assert r["outcome"] == "solved" and r["winner"] == "a" and r["scores"]["a"] == 1.0


def test_registry():
    assert get_game_class("mud") is MudGame


def test_min_players_single():
    assert MudGame.min_players == 1


def test_locked_exit_is_noop():
    g, st = _new()
    before = g.build_semantic_state("a", st)
    _act(g, st, "go", direction="east")  # observatory is locked
    after = g.build_semantic_state("a", st)
    assert before["agent"]["location"] == after["agent"]["location"] == "study"
    assert "locked" in st["game"]["current"]["last_events"][0].lower()


def test_take_absent_is_noop():
    g, st = _new()
    inv0 = g.build_semantic_state("a", st)["agent"]["inventory"]
    _act(g, st, "take", target="dragon")
    assert g.build_semantic_state("a", st)["agent"]["inventory"] == inv0


def test_hidden_until_search():
    g, st = _new()
    _act(g, st, "go", direction="down")
    _act(g, st, "go", direction="west")  # library
    objs = [o["id"] for o in g.build_semantic_state("a", st)["room"]["objects"]]
    assert "saturn_ring" not in objs
    _act(g, st, "search", target="globe")
    objs = [o["id"] for o in g.build_semantic_state("a", st)["room"]["objects"]]
    assert "saturn_ring" in objs


def test_use_interaction_reveals_and_consumes():
    g, st = _new()
    for verb, kw in SOLVE[:6]:  # ring in hand, back in study
        _act(g, st, verb, **kw)
    _act(g, st, "use", item="saturn_ring", target="orrery")
    objs = st["game"]["current"]["objects"]
    assert objs["orrery"]["state"]["complete"] is True   # completion localized to the object
    assert objs["brass_key"]["visible"] is True
    assert objs["saturn_ring"]["loc"] is None  # consumed


def test_unlock_requires_key():
    g, st = _new()
    _act(g, st, "unlock", target="east")  # no key yet
    assert st["game"]["current"]["locks"]["observatory_door"]["locked"] is True


def test_use_key_on_door_unlocks():
    g, st = _new()
    for verb, kw in SOLVE[:8]:  # through taking the brass key
        _act(g, st, verb, **kw)
    _act(g, st, "use", item="brass_key", target="east")
    assert st["game"]["current"]["locks"]["observatory_door"]["locked"] is False


def test_npc_talk_and_give():
    g, st = _new()
    _act(g, st, "go", direction="down")
    _act(g, st, "go", direction="east")  # alchemy lab
    ev = _act(g, st, "talk", target="raven")
    assert "ring" in ev[0].lower()
    _act(g, st, "take", target="fig")
    _act(g, st, "give", item="fig", target="raven")
    assert st["game"]["current"]["flags"].get("raven_fed") is True


def test_validate_rejects_bad():
    g, st = _new()
    assert not g.validate_move({"type": "action", "verb": "fly"}, "a", st)["valid"]
    assert not g.validate_move({"type": "action", "verb": "go"}, "a", st)["valid"]
    assert not g.validate_move({"type": "action", "verb": "use", "item": "x"}, "a", st)["valid"]


def test_semantic_state_shape():
    g, st = _new()
    s = g.build_semantic_state("a", st)
    assert s["contract_version"] == 1 and s["game"] == "mud"
    assert s["agent"]["location"] == "study"
    assert set(s["room"]["exits"]) == {"down", "east"}
    assert s["room"]["exits"]["east"]["locked"] is True
    assert s["room"]["exits"]["down"]["locked"] is False


def test_inline_prompt():
    g, st = _new()
    p = g.build_inline_prompt("a", st, 1)
    assert "Astronomer's Study" in p and "Exits:" in p and "GOAL:" in p


# ── forgiving item matching (Ludex Cody 2026-07-02: Lyra's naming dead-end) ────

def test_item_reference_separator_and_case_insensitive():
    # id 'saturn_ring', display 'Saturn-ring' — every natural phrasing resolves.
    for phrasing in ["saturn ring", "Saturn-ring", "saturn_ring", "SATURN RING", "saturn  ring"]:
        g, st = _new()
        for verb, kw in SOLVE[:3]:  # down, west, search globe → reveals saturn_ring in library
            _act(g, st, verb, **kw)
        _act(g, st, "take", target=phrasing)
        assert st["game"]["current"]["objects"]["saturn_ring"]["loc"] == "inv:a", phrasing


def test_use_resolves_spaced_item_name():
    g, st = _new()
    for verb, kw in SOLVE[:6]:  # ring in hand, back in the study
        _act(g, st, verb, **kw)
    _act(g, st, "use", item="saturn ring", target="orrery")  # spaced phrasing must work
    assert st["game"]["current"]["objects"]["orrery"]["state"]["complete"] is True
    assert st["game"]["current"]["objects"]["brass_key"]["visible"] is True


def test_use_wrong_target_gives_clear_no_effect_message():
    # Lyra's dead-end: using the ring on the globe (where found), not the orrery.
    g, st = _new()
    for verb, kw in SOLVE[:4]:  # down, west, search globe, take saturn_ring (in library)
        _act(g, st, verb, **kw)
    ev = _act(g, st, "use", item="saturn ring", target="celestial globe")
    assert "no effect on" in ev[0].lower()
    assert "saturn" in ev[0].lower() and "globe" in ev[0].lower()
    assert st["game"]["current"]["objects"]["saturn_ring"]["loc"] == "inv:a"  # still a no-op
