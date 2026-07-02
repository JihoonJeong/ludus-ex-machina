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


GRIMHOLD_SOLVE = [
    ("go", {"direction": "north"}), ("go", {"direction": "east"}),
    ("search", {"target": "sarcophagus"}), ("take", {"target": "bone charm"}),
    ("go", {"direction": "west"}), ("go", {"direction": "west"}),
    ("use", {"item": "bone charm", "target": "gargoyle"}), ("take", {"target": "rune-etched key"}),
    ("go", {"direction": "east"}), ("go", {"direction": "north"}),
    ("unlock", {"target": "reliquary"}), ("open", {"target": "reliquary"}),
    ("take", {"target": "silver sigil"}),
    ("go", {"direction": "south"}), ("go", {"direction": "west"}),
    ("unlock", {"target": "north"}), ("go", {"direction": "north"}),
    ("take", {"target": "emberheart"}),
]


def test_grimhold_registered_and_solvable():
    g = MudGame("grimhold_keep")
    st = {"game": g.initial_state([{"agent_id": "a"}]), "lxm": {"match_id": "t"}}
    for verb, kw in GRIMHOLD_SOLVE:
        _act(g, st, verb, **kw)
    cur = st["game"]["current"]
    assert cur["won"] is True and g.is_over(st) is True
    r = g.get_result(st)
    assert r["outcome"] == "solved" and r["winner"] == "a" and r["scores"]["a"] == 1.0


def test_grimhold_gargoyle_gates_the_key():
    # The rune key must stay hidden until the charm awakens the gargoyle
    # (deep-dependency-chain axis: no shortcut past a gate).
    g = MudGame("grimhold_keep")
    st = {"game": g.initial_state([{"agent_id": "a"}]), "lxm": {"match_id": "t"}}
    assert g.build_semantic_state("a", st) is not None
    # jump straight to the hall and try to take the key before charming
    for verb, kw in [("go", {"direction": "north"}), ("go", {"direction": "west"})]:
        _act(g, st, verb, **kw)
    _act(g, st, "take", target="rune-etched key")
    assert st["game"]["current"]["objects"]["rune_key"].get("visible") is False
    assert st["game"]["current"]["objects"]["rune_key"]["loc"] == "room:great_hall"


EREBUS_SOLVE = [
    ("go", {"direction": "in"}), ("go", {"direction": "aft"}),
    ("take", {"target": "coolant canister"}), ("take", {"target": "routing lever"}),
    ("go", {"direction": "fore"}), ("go", {"direction": "port"}),
    ("take", {"target": "plasma igniter"}),
    ("use", {"item": "coolant canister", "target": "coolant port"}),
    ("use", {"item": "plasma igniter", "target": "reactor"}),
    ("go", {"direction": "starboard"}),
    ("use", {"item": "routing lever", "target": "power console"}),
    ("go", {"direction": "fore"}), ("take", {"target": "nav-core"}),
]


def _erebus():
    g = MudGame("ss_erebus")
    return g, {"game": g.initial_state([{"agent_id": "a"}]), "lxm": {"match_id": "t"}}


def test_erebus_registered_and_solvable():
    g, st = _erebus()
    for verb, kw in EREBUS_SOLVE:
        _act(g, st, verb, **kw)
    assert st["game"]["current"]["won"] is True
    r = g.get_result(st)
    assert r["outcome"] == "solved" and r["scores"]["a"] == 1.0


def test_erebus_ignition_requires_coolant_first():
    # mutable-state ordering: igniting before coolant is a no-op (reactor stays offline).
    g, st = _erebus()
    for verb, kw in [("go", {"direction": "in"}), ("go", {"direction": "port"}),
                     ("take", {"target": "plasma igniter"})]:
        _act(g, st, verb, **kw)
    ev = _act(g, st, "use", item="plasma igniter", target="reactor")
    assert st["game"]["current"]["objects"]["reactor"]["state"]["online"] is False
    assert "coolant" in ev[0].lower()  # clear reason, not a generic "nothing happens"
    assert st["game"]["current"]["flags"].get("reactor_online") is not True


def test_erebus_power_routing_requires_reactor_and_unlocks_door():
    # routing before the reactor is online is a no-op; the bridge door stays sealed.
    g, st = _erebus()
    for verb, kw in [("go", {"direction": "in"}), ("go", {"direction": "aft"}),
                     ("take", {"target": "routing lever"}), ("go", {"direction": "fore"})]:
        _act(g, st, verb, **kw)
    _act(g, st, "use", item="routing lever", target="power console")
    assert st["game"]["current"]["locks"]["bridge_door"]["locked"] is True  # gate held


def test_use_requires_gate_backcompat_no_requires_still_fires():
    # An interaction without `requires` must fire unconditionally (Tower/Grimhold).
    g = MudGame("astronomer_tower")
    st = {"game": g.initial_state([{"agent_id": "a"}]), "lxm": {"match_id": "t"}}
    for verb, kw in SOLVE[:6]:
        _act(g, st, verb, **kw)
    _act(g, st, "use", item="saturn_ring", target="orrery")
    assert st["game"]["current"]["objects"]["orrery"]["state"]["complete"] is True


COVE_SOLVE = [
    ("take", {"target": "sugar fig"}),
    ("go", {"direction": "north"}), ("use", {"item": "sugar fig", "target": "blossoms"}),
    ("take", {"target": "glimmermoth"}),
    ("go", {"direction": "south"}), ("go", {"direction": "east"}),
    ("take", {"target": "silver fish"}), ("use", {"item": "silver fish", "target": "pool"}),
    ("take", {"target": "tide-newt"}),
    ("go", {"direction": "west"}), ("go", {"direction": "west"}),
    ("take", {"target": "honey comb"}), ("use", {"item": "honey comb", "target": "den"}),
    ("take", {"target": "ember-vole"}),
]


def _cove():
    g = MudGame("critter_cove")
    return g, {"game": g.initial_state([{"agent_id": "a"}]), "lxm": {"match_id": "t"}}


def test_cove_multi_collect_solve():
    g, st = _cove()
    for verb, kw in COVE_SOLVE:
        _act(g, st, verb, **kw)
    assert st["game"]["current"]["won"] is True
    r = g.get_result(st)
    assert r["outcome"] == "solved" and r["scores"]["a"] == 1.0


def test_cove_partial_collection_does_not_win():
    # holding 2 of 3 critters must NOT win (collect-set requires ALL).
    g, st = _cove()
    for verb, kw in COVE_SOLVE[:9]:  # through catching the tide-newt (2 of 3)
        _act(g, st, verb, **kw)
    inv = g.build_semantic_state("a", st)["agent"]["inventory"]
    ids = {o["id"] for o in inv}
    assert "glimmermoth" in ids and "tide_newt" in ids and "ember_vole" not in ids
    assert st["game"]["current"]["won"] is False


def test_cove_wrong_bait_is_noop():
    # relevance axis: the wrong bait doesn't reveal the critter (clear no-op).
    g, st = _cove()
    _act(g, st, "take", target="sugar fig")
    _act(g, st, "go", direction="west"); _act(g, st, "take", target="honey comb")
    _act(g, st, "go", direction="east"); _act(g, st, "go", direction="north")  # grove w/ moth
    ev = _act(g, st, "use", item="honey comb", target="blossoms")  # moth wants the fig
    assert st["game"]["current"]["objects"]["glimmermoth"]["visible"] is False
    assert "no effect" in ev[0].lower()


def test_cove_collect_progress_cue_on_pickup():
    g, st = _cove()
    for verb, kw in COVE_SOLVE[:3]:  # bring fig, lure moth
        _act(g, st, verb, **kw)
    ev = _act(g, st, "take", target="glimmermoth")
    assert any("1/3" in e for e in ev)


def test_use_wrong_target_gives_clear_no_effect_message():
    # Lyra's dead-end: using the ring on the globe (where found), not the orrery.
    g, st = _new()
    for verb, kw in SOLVE[:4]:  # down, west, search globe, take saturn_ring (in library)
        _act(g, st, verb, **kw)
    ev = _act(g, st, "use", item="saturn ring", target="celestial globe")
    assert "no effect on" in ev[0].lower()
    assert "saturn" in ev[0].lower() and "globe" in ev[0].lower()
    assert st["game"]["current"]["objects"]["saturn_ring"]["loc"] == "inv:a"  # still a no-op
