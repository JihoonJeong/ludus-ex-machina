"""Blockworld crafting recipe catalog.

A recipe maps a multiset of input items in inventory to a multiset of
output items in inventory. Outputs may be either placeable blocks
(present in `BLOCK_TYPES`) or inventory-only intermediates (e.g. stick).

Schema:
    RECIPES[recipe_id] = {
        "inputs":  {item_name: count, ...},
        "outputs": {item_name: count, ...},
        "description": str,
    }

Adding a recipe whose output is a placeable block requires a matching
entry in `world.BLOCK_TYPES` / `HARDNESS` / `DROP_ON_BREAK`.
Inventory-only items (e.g. stick) need no world.py change.
"""

from __future__ import annotations

RECIPES: dict[str, dict] = {
    "planks": {
        "inputs":  {"wood": 1},
        "outputs": {"planks": 4},
        "description": "Split a wood log into 4 planks (placeable).",
    },
    "stick": {
        "inputs":  {"planks": 2},
        "outputs": {"stick": 4},
        "description": "Whittle 2 planks into 4 sticks (inventory-only intermediate).",
    },
    "ladder": {
        "inputs":  {"stick": 7},
        "outputs": {"ladder": 3},
        "description": "Lash 7 sticks into 3 ladders for vertical movement.",
    },
    "stone_brick": {
        "inputs":  {"stone": 4},
        "outputs": {"stone_brick": 4},
        "description": "Cut 4 stone into 4 stone bricks (durable, decorative).",
    },
    "glass": {
        "inputs":  {"sand": 1},
        "outputs": {"glass": 1},
        "description": "Fuse 1 sand into 1 glass (placeable, transparent).",
    },
}


def get_recipe(recipe_id: str) -> dict | None:
    """Return the recipe dict, or None if unknown."""
    return RECIPES.get(recipe_id)


def recipe_ids() -> list[str]:
    """All registered recipe IDs (stable order)."""
    return list(RECIPES.keys())
