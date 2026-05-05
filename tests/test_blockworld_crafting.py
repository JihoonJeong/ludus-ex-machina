"""Crafting catalog tests — Blockworld Gen 4 (recipes.py)."""
from __future__ import annotations

import pytest

from games.blockworld.engine import BlockworldGame, INVENTORY_CAP
from games.blockworld.recipes import RECIPES, get_recipe, recipe_ids


# ── catalog shape ────────────────────────────────────────────────────────

def test_catalog_has_seed_recipes():
    assert set(recipe_ids()) >= {"planks", "stick", "ladder", "stone_brick", "glass"}


def test_recipes_have_required_fields():
    for rid, spec in RECIPES.items():
        assert isinstance(spec.get("inputs"), dict) and spec["inputs"]
        assert isinstance(spec.get("outputs"), dict) and spec["outputs"]
        assert all(isinstance(c, int) and c > 0 for c in spec["inputs"].values())
        assert all(isinstance(c, int) and c > 0 for c in spec["outputs"].values())
        assert isinstance(spec.get("description"), str)


# ── _do_craft direct ─────────────────────────────────────────────────────

def _agent(inventory):
    return {"inventory": dict(inventory)}


@pytest.fixture
def game():
    # sandbox_open_01 has mode='sandbox' and is the canonical creative substrate.
    return BlockworldGame("sandbox_open_01")


@pytest.mark.parametrize("recipe_id,inv_in,inv_out", [
    ("planks",      {"wood": 1},                 {"planks": 4}),
    ("stick",       {"planks": 2},               {"planks": 0, "stick": 4}),
    ("ladder",      {"stick": 7},                {"stick": 0, "ladder": 3}),
    ("stone_brick", {"stone": 4},                {"stone": 0, "stone_brick": 4}),
    ("glass",       {"sand": 1},                 {"glass": 1}),
])
def test_recipe_success(game, recipe_id, inv_in, inv_out):
    agent = _agent(inv_in)
    events = []
    game._do_craft(agent, recipe_id, events)
    for item, count in inv_out.items():
        if count == 0:
            assert item not in agent["inventory"], f"{item} should be consumed"
        else:
            assert agent["inventory"].get(item, 0) == count, f"expected {count} {item}"
    assert any("crafted" in e for e in events)


def test_insufficient_inputs_no_change(game):
    agent = _agent({"wood": 0})
    events = []
    game._do_craft(agent, "planks", events)
    assert agent["inventory"] == {"wood": 0}
    assert any("need" in e for e in events)


def test_unknown_recipe_event(game):
    agent = _agent({"wood": 99})
    events = []
    game._do_craft(agent, "foo_bar", events)
    assert agent["inventory"] == {"wood": 99}
    assert any("unknown recipe" in e for e in events)


def test_inventory_cap_blocks_craft(game):
    # 1 wood → 4 planks. Start inventory full minus 3 → would overshoot.
    agent = _agent({"wood": 1, "stone": INVENTORY_CAP - 1 - 2})  # net post-craft = (cap-3) + 4 = cap+1
    events = []
    game._do_craft(agent, "planks", events)
    # Reject and leave wood intact.
    assert agent["inventory"]["wood"] == 1
    assert "planks" not in agent["inventory"]
    assert any("inventory full" in e for e in events)


# ── validate_move recipe gate ────────────────────────────────────────────

def test_validate_move_rejects_unknown_recipe(game):
    state = {"game": game.initial_state([{"agent_id": "a"}])}
    res = game.validate_move({"type": "action", "verb": "craft", "recipe": "nonsense"}, "a", state)
    assert res["valid"] is False
    assert "unknown" in res["message"]


def test_validate_move_accepts_known_recipe(game):
    state = {"game": game.initial_state([{"agent_id": "a"}])}
    res = game.validate_move({"type": "action", "verb": "craft", "recipe": "planks"}, "a", state)
    assert res["valid"] is True


def test_validate_move_requires_recipe_field(game):
    state = {"game": game.initial_state([{"agent_id": "a"}])}
    res = game.validate_move({"type": "action", "verb": "craft"}, "a", state)
    assert res["valid"] is False
    assert "recipe" in res["message"]


# ── apply_move integration ───────────────────────────────────────────────

# ── inline prompt mode-gated catalog disclosure ────────────────────────

def test_paper1_prompt_byte_identical_block_list():
    """Paper-1 modes (pure_coord, predator_prey, etc.) must keep the legacy
    block list and `glass_pane` recipe string in the inline prompt — even
    though the catalog has expanded — so already-completed runs and
    in-flight codex matches stay comparable."""
    paper1_scenarios = [
        "pure_coord_01", "pure_coord_02", "pure_coord_03",
        "predator_prey_01", "prisoners_dilemma_01",
        "single_navigate_01", "externality_mushrooms_01",
        "commons_harvest_01", "stag_hunt_01", "stag_hunt_repeated_01",
    ]
    legacy_block_line = '"block":"wood|stone|dirt|sand|iron_ore|glass|ladder"'
    legacy_recipe_line = '"recipe":"glass_pane"'
    for sid in paper1_scenarios:
        g = BlockworldGame(sid)
        # Single-agent scenarios (single_navigate) only support one start.
        try:
            state = {"game": g.initial_state([{"agent_id": "a"}, {"agent_id": "b"}])}
        except ValueError:
            state = {"game": g.initial_state([{"agent_id": "a"}])}
        prompt = g.build_inline_prompt("a", state, 1)
        assert legacy_block_line in prompt, f"{sid}: paper-1 block list changed"
        assert legacy_recipe_line in prompt, f"{sid}: paper-1 recipe string changed"
        assert "=== Creative session ===" not in prompt, f"{sid}: leaked sandbox block"


def test_paper1_scenarios_start_with_empty_inventory():
    """Paper-1 scenarios must NOT pre-stock inventory — a regression of
    that would change runtime behavior in already-completed and in-flight
    matches."""
    paper1_scenarios = [
        "pure_coord_01", "pure_coord_02", "pure_coord_03",
        "predator_prey_01", "prisoners_dilemma_01",
        "single_navigate_01", "externality_mushrooms_01",
        "commons_harvest_01", "stag_hunt_01", "stag_hunt_repeated_01",
    ]
    for sid in paper1_scenarios:
        g = BlockworldGame(sid)
        try:
            state = g.initial_state([{"agent_id": "a"}, {"agent_id": "b"}])
        except ValueError:
            state = g.initial_state([{"agent_id": "a"}])
        for aid, ag in state["current"]["agents"].items():
            assert ag["inventory"] == {}, (
                f"{sid} agent {aid} starts with non-empty inventory: {ag['inventory']}"
            )


def test_creative_build_pre_stock():
    """creative_build_01 must pre-stock wood×8 + stone×8 + planks×4."""
    g = BlockworldGame("creative_build_01")
    state = g.initial_state([{"agent_id": "a"}])
    inv = state["current"]["agents"]["a"]["inventory"]
    assert inv == {"wood": 8, "stone": 8, "planks": 4}


def test_creative_open_no_pre_stock():
    """creative_open_01 starts empty (no pre-stock specified)."""
    g = BlockworldGame("creative_open_01")
    state = g.initial_state([{"agent_id": "a"}])
    assert state["current"]["agents"]["a"]["inventory"] == {}


def test_pre_stock_over_cap_rejected():
    """Pre-stocked inventory exceeding INVENTORY_CAP must raise."""
    import pytest
    g = BlockworldGame("creative_build_01")
    # Patch the loaded scenario's start to over-cap.
    g._scenario["agent_start"]["inventory"] = {"wood": 25}
    with pytest.raises(ValueError, match="INVENTORY_CAP"):
        g.initial_state([{"agent_id": "a"}])


def test_flat_default_terrain_profile():
    """flat_default produces grass with dirt rim only — no trees, stone, water."""
    from games.blockworld import world as W
    w = W.generate_world({"x": 16, "y": 16, "z": 3}, seed=42, terrain_profile="flat_default")
    layers = w["layers"]
    seen_blocks = set()
    for z_layer in layers:
        for row in z_layer:
            for v in row:
                seen_blocks.add(W.BLOCK_TYPES[v])
    # Should only see air, grass, dirt — no decoration.
    assert seen_blocks <= {"air", "grass", "dirt"}, f"unexpected blocks: {seen_blocks}"


def test_sandbox_prompt_expanded_catalog():
    """Sandbox mode must advertise the full BLOCK_TYPES + recipe catalog
    and include a Creative session block."""
    g = BlockworldGame("sandbox_open_01")
    state = {"game": g.initial_state([{"agent_id": "a"}])}
    prompt = g.build_inline_prompt("a", state, 1)
    # Expanded catalog: new blocks present in the place line.
    assert "planks" in prompt
    assert "stone_brick" in prompt
    # Recipe catalog present (alternation with all 5 ids).
    for rid in ("planks", "stick", "ladder", "stone_brick", "glass"):
        assert f'|{rid}' in prompt or f'"{rid}' in prompt, f"recipe {rid} missing"
    assert "=== Creative session ===" in prompt
    # Verb preconditions clarification (gemma3 EM no_pickups diagnosis,
    # 2026-05-05 — Ray): `pick` reads cell-current item only.
    assert "Verb preconditions" in prompt
    assert "current cell" in prompt.lower() or "CURRENT cell" in prompt


def test_pick_precondition_absent_in_paper1_modes():
    """Paper-1 modes must NOT receive the new verb-preconditions block —
    keeps the byte-identical prompt invariant intact."""
    paper1_scenarios = [
        "pure_coord_01", "pure_coord_02", "pure_coord_03",
        "predator_prey_01", "prisoners_dilemma_01",
        "single_navigate_01", "externality_mushrooms_01",
        "commons_harvest_01", "stag_hunt_01", "stag_hunt_repeated_01",
    ]
    for sid in paper1_scenarios:
        g = BlockworldGame(sid)
        try:
            state = {"game": g.initial_state([{"agent_id": "a"}, {"agent_id": "b"}])}
        except ValueError:
            state = {"game": g.initial_state([{"agent_id": "a"}])}
        prompt = g.build_inline_prompt("a", state, 1)
        assert "Verb preconditions" not in prompt, f"{sid}: leaked verb-precondition block"


# ── intent capture (paper 2 V1 — Claim C') ─────────────────────────────

def test_intent_field_validates_as_string():
    g = BlockworldGame("creative_build_01")
    state = {"game": g.initial_state([{"agent_id": "a"}])}
    # Valid intent on a place verb.
    res = g.validate_move(
        {"type": "action", "verb": "place", "direction": "north", "block": "planks", "intent": "I plan to build a tower."},
        "a", state,
    )
    assert res["valid"] is True
    # Non-string intent rejected.
    res = g.validate_move(
        {"type": "action", "verb": "wait", "intent": 42},
        "a", state,
    )
    assert res["valid"] is False
    assert "intent" in res["message"]


def test_intent_appended_to_context_log():
    g = BlockworldGame("creative_build_01")
    state = {"game": g.initial_state([{"agent_id": "a"}])}
    g.apply_move(
        {"type": "action", "verb": "wait", "intent": "I will build a tower."},
        "a", state,
    )
    log = state["game"]["context"]["intent_log"]
    assert len(log) == 1
    assert log[0]["agent_id"] == "a"
    assert log[0]["text"] == "I will build a tower."


def test_intent_log_initialized_for_sandbox():
    g = BlockworldGame("creative_build_01")
    state = g.initial_state([{"agent_id": "a"}])
    assert state["context"]["intent_log"] == []
    assert state["context"]["intent_capture_turns"] == [1, 25, 50, 75]
    assert state["context"]["final_assessment_turn"] == 100


def test_intent_block_in_prompt_at_capture_turn():
    g = BlockworldGame("creative_build_01")
    state = {"game": g.initial_state([{"agent_id": "a"}])}
    # T1 — initial declaration.
    p1 = g.build_inline_prompt("a", state, 1)
    assert "Initial intent declaration" in p1
    assert '"intent"' in p1
    # T25 — mid-match check.
    p25 = g.build_inline_prompt("a", state, 25)
    assert "Intent check" in p25
    # T100 — final assessment.
    p100 = g.build_inline_prompt("a", state, 100)
    assert "Final assessment" in p100
    # T10 — non-capture turn, no intent block.
    p10 = g.build_inline_prompt("a", state, 10)
    assert "Initial intent declaration" not in p10
    assert "Intent check" not in p10
    assert "Final assessment" not in p10


def test_intent_blocks_absent_in_paper1_modes():
    """Paper-1 prompts must remain byte-identical — no intent block leakage."""
    g = BlockworldGame("pure_coord_03")
    state = {"game": g.initial_state([{"agent_id": "a"}, {"agent_id": "b"}])}
    for t in [1, 25, 50, 75, 100]:
        p = g.build_inline_prompt("a", state, t)
        assert "Initial intent declaration" not in p
        assert "Intent check" not in p
        assert "Final assessment" not in p


def test_apply_move_craft_consumes_and_produces(game):
    state = {"game": game.initial_state([{"agent_id": "a"}])}
    # Inject inputs into agent inventory then issue craft.
    state["game"]["current"]["agents"]["a"]["inventory"] = {"wood": 1}
    game.apply_move({"type": "action", "verb": "craft", "recipe": "planks"}, "a", state)
    inv = state["game"]["current"]["agents"]["a"]["inventory"]
    assert inv.get("planks") == 4
    assert "wood" not in inv
