"""Blockworld game engine — LxM game plugin.

2.5D voxel sandbox with scenario-based objectives. MVP shipped with the
`shelter_01` scenario — single-agent build-before-storm challenge.

World representation lives in `world.py`; this module wires it into the
LxMGame interface (initial_state / validate_move / apply_move /
is_over / get_result / build_inline_prompt).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lxm.engine import LxMGame
from games.blockworld import world as W

INVENTORY_CAP = 20
DEFAULT_VIEW_RADIUS = 5
LOOK_VIEW_RADIUS = 10

VALID_VERBS = {
    "move", "break", "place", "craft",
    "pick", "drop", "look", "say", "wait",
}

OPPOSITE_DIR = {
    "north": "south", "south": "north",
    "east": "west", "west": "east",
    "up": "down", "down": "up",
}


class BlockworldGame(LxMGame):
    """2.5D voxel sandbox with scenario-driven objectives."""

    def __init__(self, scenario_id: str = "shelter_01"):
        self._scenario_id = scenario_id
        self._scenario = _load_scenario(scenario_id)

    def get_rules(self) -> str:
        rules_path = Path(__file__).parent / "rules.md"
        return rules_path.read_text(encoding="utf-8")

    # ── state lifecycle ─────────────────────────────────────────────────

    def initial_state(self, agents: list[dict]) -> dict:
        seed = self._scenario["seed"]
        world_dict = W.generate_world(
            dimensions=self._scenario["dimensions"],
            seed=seed,
            terrain_profile=self._scenario["terrain_profile"],
        )

        # Agents seat into the scenario's starting positions (all at the
        # same spot by default — MVP is single agent but the plumbing
        # supports multi-agent).
        start = self._scenario["agent_start"]
        agent_states = {}
        for a in agents:
            agent_states[a["agent_id"]] = {
                "agent_id": a["agent_id"],
                "x": start["x"],
                "y": start["y"],
                "z": start["z"],
                "facing": start.get("facing", "north"),
                "inventory": {},  # {block_name: count}
                "status": "active",
            }

        return {
            "current": {
                "phase": "playing",
                "turn": 1,
                "turn_order": [a["agent_id"] for a in agents],
                "active_index": 0,
                "agents": agent_states,
                "world": world_dict,
                "ground_items": [],  # drops waiting to be picked up
                "last_events": [],   # short engine feedback per turn, for prompt
            },
            "context": {
                "scenario_id": self._scenario_id,
                "scenario_title": self._scenario["title"],
                "goal": self._scenario["goal"],
                "turn_limit": self._scenario["turn_limit"],
                "shelter_deadline": self._scenario["shelter_deadline"],
                "min_floor": self._scenario["min_floor"],
            },
        }

    # ── validation ──────────────────────────────────────────────────────

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        t = move.get("type")
        if t != "action":
            return {"valid": False, "message": "move.type must be 'action'"}
        verb = move.get("verb")
        if verb not in VALID_VERBS:
            return {"valid": False, "message": f"unknown verb: {verb!r}"}

        # Per-verb validation.
        if verb in ("move", "break"):
            d = move.get("direction")
            if d not in W.DIRECTIONS:
                return {"valid": False, "message": f"{verb} requires 'direction' in {sorted(W.DIRECTIONS)}"}
        elif verb == "place":
            d = move.get("direction")
            b = move.get("block")
            if d not in W.DIRECTIONS:
                return {"valid": False, "message": "place requires 'direction'"}
            if b not in W.BLOCK_IDS or b == "air":
                return {"valid": False, "message": f"place requires placeable 'block' (one of {sorted(k for k in W.BLOCK_IDS if k != 'air')})"}
        elif verb == "craft":
            if not move.get("recipe"):
                return {"valid": False, "message": "craft requires 'recipe'"}
        elif verb == "drop":
            if not move.get("item"):
                return {"valid": False, "message": "drop requires 'item'"}
        elif verb == "say":
            if not isinstance(move.get("message"), str):
                return {"valid": False, "message": "say requires string 'message'"}

        return {"valid": True, "message": None}

    # ── apply ───────────────────────────────────────────────────────────

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current = game["current"]
        world = current["world"]
        agent = current["agents"][agent_id]
        events: list[str] = []

        verb = move["verb"]

        if verb == "move":
            self._do_move(world, agent, move["direction"], events)
        elif verb == "break":
            self._do_break(world, agent, move["direction"], events)
        elif verb == "place":
            self._do_place(world, agent, move["direction"], move["block"], events)
        elif verb == "pick":
            self._do_pick(current, agent, events)
        elif verb == "drop":
            self._do_drop(current, agent, move["item"], events)
        elif verb == "craft":
            self._do_craft(agent, move["recipe"], events)
        elif verb == "look":
            events.append(f"{agent_id} looks around (radius {LOOK_VIEW_RADIUS})")
        elif verb == "say":
            events.append(f"{agent_id} says: {move['message'][:80]}")
        elif verb == "wait":
            events.append(f"{agent_id} waits")

        # Advance turn counter + rotate active agent.
        current["last_events"] = events
        current["turn"] += 1
        n = len(current["turn_order"])
        current["active_index"] = (current["active_index"] + 1) % n

        return {"current": current, "context": game["context"]}

    # ── verb implementations (mutate world + agent in place) ───────────

    def _do_move(self, world, agent, direction, events):
        dx, dy, dz = W.DIRECTIONS[direction]
        nx, ny, nz = agent["x"] + dx, agent["y"] + dy, agent["z"] + dz
        if not W.in_bounds(world, nx, ny, nz):
            events.append(f"move {direction} blocked: world edge")
            return
        dest_block = W.get_block(world, nx, ny, nz)
        # Vertical move rules: 'up' requires a block at (x,y,z) directly below
        # destination that you can climb on (i.e. dest must be air AND adjacent
        # to something solid we can step from). MVP: simplify to "destination
        # must be air". Scenarios with towers will just require placing a
        # block beside you before moving up.
        if dest_block != "air":
            events.append(f"move {direction} blocked: {dest_block} at destination")
            return
        if direction in ("north", "south", "east", "west"):
            # Must have solid ground at or below the destination.
            below = W.get_block(world, nx, ny, nz - 1) if nz > 0 else "stone"
            if below == "air":
                events.append(f"move {direction} blocked: no ground beneath destination")
                return
            agent["facing"] = direction
        agent["x"], agent["y"], agent["z"] = nx, ny, nz
        events.append(f"moved {direction} to ({nx},{ny},{nz})")

    def _do_break(self, world, agent, direction, events):
        dx, dy, dz = W.DIRECTIONS[direction]
        tx, ty, tz = agent["x"] + dx, agent["y"] + dy, agent["z"] + dz
        if not W.in_bounds(world, tx, ty, tz):
            events.append(f"break {direction}: out of bounds")
            return
        block = W.get_block(world, tx, ty, tz)
        if block == "air":
            events.append(f"break {direction}: nothing there")
            return
        if W.HARDNESS[block] is None:
            events.append(f"break {direction}: {block} is unbreakable")
            return
        # MVP: always 1 turn to break (simplification — hardness system would
        # require per-block progress tracking; defer to later scenarios).
        drop = W.DROP_ON_BREAK[block]
        if drop is None:
            events.append(f"broke {block} (no drop)")
        else:
            if _inventory_count(agent) + 1 > INVENTORY_CAP:
                events.append(f"break {direction}: inventory full (cap {INVENTORY_CAP})")
                return
            agent["inventory"][drop] = agent["inventory"].get(drop, 0) + 1
            events.append(f"broke {block} at ({tx},{ty},{tz}), +1 {drop}")
        W.set_block(world, tx, ty, tz, "air", placed_by_agent=False)

    def _do_place(self, world, agent, direction, block, events):
        dx, dy, dz = W.DIRECTIONS[direction]
        tx, ty, tz = agent["x"] + dx, agent["y"] + dy, agent["z"] + dz
        if not W.in_bounds(world, tx, ty, tz):
            events.append(f"place {direction}: out of bounds")
            return
        if W.get_block(world, tx, ty, tz) != "air":
            events.append(f"place {direction}: cell not empty")
            return
        if agent["inventory"].get(block, 0) <= 0:
            events.append(f"place {block}: not in inventory")
            return
        agent["inventory"][block] -= 1
        if agent["inventory"][block] == 0:
            del agent["inventory"][block]
        W.set_block(world, tx, ty, tz, block, placed_by_agent=True)
        events.append(f"placed {block} at ({tx},{ty},{tz})")

    def _do_pick(self, current, agent, events):
        ground = current["ground_items"]
        here = [g for g in ground if g["x"] == agent["x"] and g["y"] == agent["y"] and g["z"] == agent["z"]]
        if not here:
            events.append("pick: nothing at your cell")
            return
        if _inventory_count(agent) + 1 > INVENTORY_CAP:
            events.append(f"pick: inventory full (cap {INVENTORY_CAP})")
            return
        item = here[0]
        agent["inventory"][item["type"]] = agent["inventory"].get(item["type"], 0) + 1
        item["count"] -= 1
        if item["count"] <= 0:
            ground.remove(item)
        events.append(f"picked 1 {item['type']}")

    def _do_drop(self, current, agent, item, events):
        if agent["inventory"].get(item, 0) <= 0:
            events.append(f"drop {item}: not in inventory")
            return
        agent["inventory"][item] -= 1
        if agent["inventory"][item] == 0:
            del agent["inventory"][item]
        # Merge with existing stack at this cell if present.
        for g in current["ground_items"]:
            if g["x"] == agent["x"] and g["y"] == agent["y"] and g["z"] == agent["z"] and g["type"] == item:
                g["count"] += 1
                break
        else:
            current["ground_items"].append({
                "x": agent["x"], "y": agent["y"], "z": agent["z"],
                "type": item, "count": 1,
            })
        events.append(f"dropped 1 {item}")

    def _do_craft(self, agent, recipe, events):
        # MVP: only glass_pane recipe.
        if recipe == "glass_pane":
            if agent["inventory"].get("sand", 0) >= 2 and agent["inventory"].get("wood", 0) >= 1:
                agent["inventory"]["sand"] -= 2
                if agent["inventory"]["sand"] == 0: del agent["inventory"]["sand"]
                agent["inventory"]["wood"] -= 1
                if agent["inventory"]["wood"] == 0: del agent["inventory"]["wood"]
                agent["inventory"]["glass"] = agent["inventory"].get("glass", 0) + 1
                events.append("crafted glass (2 sand + 1 wood)")
            else:
                events.append("craft glass_pane: need 2 sand + 1 wood")
        else:
            events.append(f"unknown recipe: {recipe!r}")

    # ── game-over & result ─────────────────────────────────────────────

    def is_over(self, state: dict) -> bool:
        current = state["game"]["current"]
        context = state["game"]["context"]
        if current.get("phase") == "ended":
            return True
        # Shelter deadline reached — evaluate.
        if current["turn"] > context["shelter_deadline"]:
            current["phase"] = "ended"
            return True
        if current["turn"] > context["turn_limit"]:
            current["phase"] = "ended"
            return True
        # Early-end option: agent has declared done? (not supported in MVP)
        return False

    def get_result(self, state: dict) -> dict:
        current = state["game"]["current"]
        context = state["game"]["context"]

        # MVP: single-agent shelter scenario.
        agent_id = current["turn_order"][0]
        agent = current["agents"][agent_id]
        validity = W.check_valid_shelter(
            current["world"], agent,
            min_floor=context["min_floor"],
        )

        over_deadline = current["turn"] > context["shelter_deadline"]

        if validity["valid"]:
            outcome = "win"
            summary = (
                f"Shelter completed. Volume={validity['volume']}, floor={validity['floor_area']}, "
                f"turn={current['turn']-1}/{context['shelter_deadline']}."
            )
        elif not over_deadline:
            outcome = "incomplete"  # turn limit but not deadline (shouldn't reach)
            summary = f"Ended before deadline: {validity['reason']}"
        else:
            # Partial credit: shelter exists somewhere but invalid, vs no shelter attempt.
            placed_count = _count_placed(current["world"])
            if placed_count >= context["min_floor"]:
                outcome = "partial"
                summary = f"Deadline reached. {validity['reason']} (placed blocks: {placed_count})"
            else:
                outcome = "loss"
                summary = f"Deadline reached with no meaningful shelter. {validity['reason']}"

        scores = {agent_id: 1.0 if outcome == "win" else (0.5 if outcome == "partial" else 0.0)}
        return {
            "outcome": outcome,
            "winner": agent_id if outcome == "win" else None,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "validity": validity,
            "turns_used": current["turn"] - 1,
            "placed_blocks": _count_placed(current["world"]),
        }

    # ── utility ─────────────────────────────────────────────────────────

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        verb = move.get("verb", "?")
        if verb == "move": return f"{agent_id}: move {move.get('direction')}"
        if verb == "break": return f"{agent_id}: break {move.get('direction')}"
        if verb == "place": return f"{agent_id}: place {move.get('block')} {move.get('direction')}"
        if verb == "say": return f"{agent_id}: say {move.get('message','')[:40]!r}"
        return f"{agent_id}: {verb}"

    def get_evaluation_schema(self) -> dict:
        return {
            "description": "Evaluate agent's building and resource-gathering behavior.",
            "fields": {
                "strategy": "Did the agent plan ahead (gather materials first) or build reactively?",
                "efficiency": "1-5: How efficiently did the agent use turns?",
                "material_choice": "Did the agent prefer wood (fast) / stone (durable) / dirt (weak-abundant)?",
                "overbuild": "Did the agent stop at min 3x3 or build a larger structure?",
                "recovery": "If an early mistake happened, did the agent recover?",
                "voice": "Register notes — did the agent's reasoning stay in their native voice?",
            },
        }

    # ── inline prompt builder ──────────────────────────────────────────

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        game = state["game"]
        current = game["current"]
        context = game["context"]
        match_id = state.get("lxm", {}).get("match_id", "")
        agent = current["agents"][agent_id]
        deadline = context["shelter_deadline"]
        turns_left = max(0, deadline - current["turn"] + 1)

        inv_str = ", ".join(f"{k}={v}" for k, v in sorted(agent["inventory"].items())) or "(empty)"
        inv_count = _inventory_count(agent)

        view = W.render_local_view(current["world"], agent, radius=DEFAULT_VIEW_RADIUS)

        # Recent events.
        events = current.get("last_events", [])
        events_str = "\n".join(f"  - {e}" for e in events[-5:]) if events else "  (none yet)"

        # Ground items nearby.
        nearby_items = []
        for g in current.get("ground_items", []):
            dx = abs(g["x"] - agent["x"])
            dy = abs(g["y"] - agent["y"])
            if g["z"] == agent["z"] and dx <= DEFAULT_VIEW_RADIUS and dy <= DEFAULT_VIEW_RADIUS:
                nearby_items.append(f"{g['type']}×{g['count']} at ({g['x']},{g['y']})")
        items_str = "; ".join(nearby_items) if nearby_items else "(none in view)"

        scene_summary = self._scenario.get("description", "")

        return f"""[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}
Blockworld scenario: {context['scenario_title']}

Setting: {scene_summary}

Goal: {context['goal']}
Deadline: turn {deadline} (turns remaining: {turns_left})

=== Your state ===
Position: ({agent['x']}, {agent['y']}, {agent['z']}) facing {agent['facing']}
Inventory ({inv_count}/{INVENTORY_CAP}): {inv_str}
Ground items nearby: {items_str}

=== Local view ===
{view}

=== Recent events ===
{events_str}

=== Action schema ===
Your response MUST include exactly one JSON action object of the form below. `"type":"action"` is required on every action.

  {{"type":"action","verb":"move","direction":"north|south|east|west|up|down"}}
  {{"type":"action","verb":"break","direction":"..."}}
  {{"type":"action","verb":"place","direction":"...","block":"wood|stone|dirt|sand|iron_ore|glass"}}
  {{"type":"action","verb":"craft","recipe":"glass_pane"}}
  {{"type":"action","verb":"pick"}}
  {{"type":"action","verb":"drop","item":"..."}}
  {{"type":"action","verb":"look"}}
  {{"type":"action","verb":"say","message":"..."}}
  {{"type":"action","verb":"wait"}}

Brief prose reflection before the JSON is welcome. The JSON is required — without it, your turn is forfeited.
"""


# ── helpers ─────────────────────────────────────────────────────────────

def _load_scenario(scenario_id: str) -> dict:
    path = Path(__file__).parent / "scenarios" / scenario_id / "scenario.json"
    if not path.exists():
        raise FileNotFoundError(f"scenario not found: {scenario_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _inventory_count(agent: dict) -> int:
    return sum(agent["inventory"].values())


def _count_placed(world: dict) -> int:
    """Count total placed-by-agent blocks in the world."""
    return sum(sum(sum(row) for row in layer) for layer in world["placed"])
