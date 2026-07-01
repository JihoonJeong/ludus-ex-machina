"""MUD engine — generic verb interpreter over an authored zone (zones.py).

LxMGame plugin. Single-agent first; multi-agent-capable. Deterministic verbs so
the field doubles as a language world-model testbed (predict (state,action)->next).
Preconditions resolve to no-ops in apply_move (state unchanged) — the world-model
no-op-fidelity property.

State (`current`):
  agents[aid] = {agent_id, location, visited:[rid]}
  objects[oid] = {name, loc:"room:<rid>"|"inv:<aid>"|"in:<cid>"|None, visible, takeable, ...}
  locks[lid]   = {locked, key}
  npcs[nid]    = {name, loc, talk, give}
  flags, won, last_events
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

from lxm.engine import LxMGame
from games.mud import zones as Z


def _norm(s: str) -> str:
    """Normalize an object/npc reference for forgiving matching: case-fold and
    collapse separators (space / hyphen / underscore) to a single space. So a
    creature calling 'saturn ring', 'Saturn-ring', or 'saturn_ring' all resolve
    to the same object (id `saturn_ring`, display 'Saturn-ring'). Fixes the
    dead-end where an LLM's natural phrasing no-op'd (Ludex Cody, 2026-07-02)."""
    return re.sub(r"[\s_\-]+", " ", (s or "").strip().lower())

DIRECTIONS = ("north", "south", "east", "west", "up", "down", "in", "out")
VERBS = {
    "go", "look", "examine", "take", "drop", "open", "close",
    "unlock", "use", "talk", "give", "search", "read", "wait",
}
_NEEDS_TARGET = {"examine", "take", "drop", "open", "close", "search", "read", "talk"}


class MudGame(LxMGame):
    """Text-adventure field. 16-bit adventure soul, deterministic world model."""

    min_players = 1
    max_players = 4
    accepts_capabilities = ["json_emit"]

    def __init__(self, scenario_id: str = "astronomer_tower"):
        self._scenario_id = scenario_id
        self._zone = Z.get_zone(scenario_id)

    # ── lifecycle ───────────────────────────────────────────────────────────

    def get_rules(self) -> str:
        p = Path(__file__).parent / "rules.md"
        return p.read_text(encoding="utf-8") if p.exists() else "MUD text adventure."

    def initial_state(self, agents: list[dict]) -> dict:
        z = self._zone
        start = z["start_room"]
        agent_states = {
            a["agent_id"]: {"agent_id": a["agent_id"], "location": start, "visited": [start]}
            for a in agents
        }
        current = {
            "phase": "playing",
            "turn": 1,
            "turn_order": [a["agent_id"] for a in agents],
            "active_index": 0,
            "agents": agent_states,
            "rooms": z["rooms"],
            "locks": z.get("locks", {}),
            "objects": z["objects"],
            "npcs": z.get("npcs", {}),
            "flags": {},
            "won": False,
            "winner": None,
            "last_events": [],
        }
        context = {
            "scenario_id": z["scenario_id"],
            "title": z["title"],
            "goal": z["goal"],
            "goal_object": z["goal_object"],
            "turn_limit": z.get("turn_limit", 60),
        }
        return {"current": current, "context": context}

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _room_of(current: dict, aid: str) -> str:
        return current["agents"][aid]["location"]

    @staticmethod
    def _inventory(current: dict, aid: str) -> list[str]:
        return [oid for oid, o in current["objects"].items() if o.get("loc") == f"inv:{aid}"]

    def _visible_room_objects(self, current: dict, rid: str) -> list[str]:
        out = []
        for oid, o in current["objects"].items():
            if o.get("loc") == f"room:{rid}" and o.get("visible", True):
                out.append(oid)
            # contents of an open container in this room
            loc = o.get("loc") or ""
            if loc.startswith("in:") and o.get("visible", True):
                cid = loc[3:]
                cont = current["objects"].get(cid)
                if cont and cont.get("loc") == f"room:{rid}" and cont.get("open"):
                    out.append(oid)
        return out

    def _npcs_in_room(self, current: dict, rid: str) -> list[str]:
        return [nid for nid, n in current["npcs"].items() if n.get("loc") == rid]

    def _obj_descriptor(self, current: dict, oid: str) -> dict:
        """Agent-local object descriptor — identical shape in room.objects and
        agent.inventory, so take/drop relocate it unchanged (WM determinism)."""
        o = current["objects"][oid]
        entry = {"id": oid, "name": o["name"], "takeable": bool(o.get("takeable"))}
        if o.get("container"):
            entry["container"] = True
            entry["open"] = bool(o.get("open"))
            entry["locked"] = bool(o.get("locked"))
        if o.get("state"):
            entry["state"] = copy.deepcopy(o["state"])  # independent snapshot (WM before/after)
        return entry

    def _resolve_object(self, current: dict, aid: str, name: str) -> str | None:
        """Match an object the agent can reach (room + inventory) by id or name."""
        if not name:
            return None
        rid = self._room_of(current, aid)
        candidates = self._visible_room_objects(current, rid) + self._inventory(current, aid)
        key = _norm(name)
        if not key:
            return None
        for oid in candidates:                       # exact id or name (case/separator-insensitive)
            if _norm(oid) == key or _norm(current["objects"][oid]["name"]) == key:
                return oid
        for oid in candidates:                       # substring fallback on normalized name/id
            if key in _norm(current["objects"][oid]["name"]) or key in _norm(oid):
                return oid
        return None

    def _resolve_npc(self, current: dict, aid: str, name: str) -> str | None:
        if not name:
            return None
        rid = self._room_of(current, aid)
        key = _norm(name)
        for nid in self._npcs_in_room(current, rid):
            if _norm(nid) == key or key in _norm(current["npcs"][nid]["name"]):
                return nid
        return None

    # ── validation (schema only; preconditions -> no-op in apply) ────────────

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        if move.get("type") not in (None, "action"):
            return {"valid": False, "message": "move.type must be 'action'"}
        verb = move.get("verb")
        if verb not in VERBS:
            return {"valid": False, "message": f"unknown verb: {verb!r} (valid: {sorted(VERBS)})"}
        if verb == "go" and not move.get("direction"):
            return {"valid": False, "message": "go requires 'direction'"}
        if verb in _NEEDS_TARGET and not move.get("target"):
            return {"valid": False, "message": f"{verb} requires 'target'"}
        if verb in ("use", "give") and not (move.get("item") and move.get("target")):
            return {"valid": False, "message": f"{verb} requires 'item' and 'target'"}
        if verb == "unlock" and not move.get("target"):
            return {"valid": False, "message": "unlock requires 'target' (exit direction or object)"}
        return {"valid": True, "message": None}

    # ── apply (deterministic; mutates current in place, returns game block) ───

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current = game["current"]
        context = game["context"]
        verb = move["verb"]
        events: list[str] = []

        handler = getattr(self, f"_do_{verb}", None)
        if handler:
            handler(current, context, agent_id, move, events)

        # win check: goal object now in the agent's inventory
        goal = context["goal_object"]
        if not current["won"] and current["objects"].get(goal, {}).get("loc") == f"inv:{agent_id}":
            current["won"] = True
            current["winner"] = agent_id
            current["phase"] = "won"
            events.append(f"✦ You hold the {current['objects'][goal]['name']}. The zone is solved!")

        current["last_events"] = events
        current["turn"] += 1
        n = len(current["turn_order"])
        current["active_index"] = (current["active_index"] + 1) % n
        return {"current": current, "context": context}

    def _do_go(self, current, context, aid, move, events):
        rid = self._room_of(current, aid)
        d = move["direction"]
        exit_ = current["rooms"][rid]["exits"].get(d)
        if not exit_:
            events.append(f"You can't go {d} from here.")
            return
        lock_id = exit_.get("lock")
        if lock_id and current["locks"].get(lock_id, {}).get("locked"):
            events.append(f"The way {d} is locked.")
            return
        dest = exit_["to"]
        current["agents"][aid]["location"] = dest
        if dest not in current["agents"][aid]["visited"]:
            current["agents"][aid]["visited"].append(dest)
        events.append(f"You go {d} to {current['rooms'][dest]['name']}.")

    def _do_look(self, current, context, aid, move, events):
        events.append("You survey the room.")

    def _do_examine(self, current, context, aid, move, events):
        oid = self._resolve_object(current, aid, move.get("target", ""))
        if not oid:
            events.append(f"You see no {move.get('target')} here.")
            return
        events.append(current["objects"][oid].get("examine", "Nothing special."))

    def _do_read(self, current, context, aid, move, events):
        oid = self._resolve_object(current, aid, move.get("target", ""))
        o = current["objects"].get(oid) if oid else None
        if o and o.get("read"):
            events.append(f"It reads: {o['read']}")
        else:
            events.append("There's nothing to read there.")

    def _do_take(self, current, context, aid, move, events):
        oid = self._resolve_object(current, aid, move.get("target", ""))
        if not oid:
            events.append(f"There's no {move.get('target')} here.")
            return
        o = current["objects"][oid]
        if not o.get("takeable"):
            events.append(f"You can't take the {o['name']}.")
            return
        if o.get("loc") == f"inv:{aid}":
            events.append(f"You already have the {o['name']}.")
            return
        o["loc"] = f"inv:{aid}"
        events.append(f"You take the {o['name']}.")

    def _do_drop(self, current, context, aid, move, events):
        oid = self._resolve_object(current, aid, move.get("target", ""))
        if not oid or current["objects"][oid].get("loc") != f"inv:{aid}":
            events.append(f"You aren't carrying that.")
            return
        current["objects"][oid]["loc"] = f"room:{self._room_of(current, aid)}"
        events.append(f"You drop the {current['objects'][oid]['name']}.")

    def _do_open(self, current, context, aid, move, events):
        oid = self._resolve_object(current, aid, move.get("target", ""))
        o = current["objects"].get(oid) if oid else None
        if not o or not o.get("container"):
            events.append("That isn't something you can open.")
            return
        if o.get("locked"):
            events.append(f"The {o['name']} is locked.")
            return
        if o.get("open"):
            events.append(f"The {o['name']} is already open.")
            return
        o["open"] = True
        contents = [current["objects"][c]["name"] for c in current["objects"]
                    if current["objects"][c].get("loc") == f"in:{oid}"]
        events.append(f"You open the {o['name']}." +
                      (f" Inside: {', '.join(contents)}." if contents else " It's empty."))

    def _do_close(self, current, context, aid, move, events):
        oid = self._resolve_object(current, aid, move.get("target", ""))
        o = current["objects"].get(oid) if oid else None
        if o and o.get("container") and o.get("open"):
            o["open"] = False
            events.append(f"You close the {o['name']}.")
        else:
            events.append("That isn't open.")

    def _lock_for_target(self, current, aid, target):
        """Resolve an unlock target to a lock id. Returns (kind, id) or (None, None)."""
        rid = self._room_of(current, aid)
        exits = current["rooms"][rid]["exits"]
        if target in exits and exits[target].get("lock"):
            return "lock", exits[target]["lock"]
        if target in current["locks"]:
            return "lock", target
        oid = self._resolve_object(current, aid, target)
        if oid and current["objects"][oid].get("locked"):
            return "object", oid
        return None, None

    def _do_unlock(self, current, context, aid, move, events):
        kind, lid = self._lock_for_target(current, aid, move.get("target", ""))
        inv = self._inventory(current, aid)
        if kind == "lock":
            lock = current["locks"][lid]
            if not lock.get("locked"):
                events.append("It's already unlocked.")
                return
            if lock["key"] in inv:
                lock["locked"] = False
                events.append(f"You unlock it with the {current['objects'][lock['key']]['name']}.")
            else:
                events.append("It's locked, and you don't have the key.")
        elif kind == "object":
            o = current["objects"][lid]
            key = o.get("key")
            if key and key in inv:
                o["locked"] = False
                events.append(f"You unlock the {o['name']}.")
            else:
                events.append(f"The {o['name']} is locked, and you don't have the key.")
        else:
            events.append("There's nothing to unlock there.")

    def _do_use(self, current, context, aid, move, events):
        item = self._resolve_object(current, aid, move.get("item", ""))
        # target may be an object, an exit/lock, etc.
        tgt_obj = self._resolve_object(current, aid, move.get("target", ""))
        if not item or current["objects"][item].get("loc") != f"inv:{aid}":
            events.append(f"You aren't carrying the {move.get('item')}.")
            return

        # 1) authored interaction (item id, target id)
        inter = self._zone.get("interactions", {})
        key = (item, tgt_obj) if tgt_obj else None
        spec = inter.get(key) if key else None
        # zone interactions are deep-copied per-init only at top level; rebuild lookup by ids
        if spec is None:
            for (i, t), s in inter.items():
                if i == item and t == tgt_obj:
                    spec = s
                    break
        if spec is not None:
            for f, v in (spec.get("set_flags") or {}).items():
                current["flags"][f] = v
            for o_id, st in (spec.get("object_state") or {}).items():
                current["objects"][o_id].setdefault("state", {}).update(st)
            for r in (spec.get("reveal") or []):
                current["objects"][r]["visible"] = True
            if spec.get("consume"):
                current["objects"][spec["consume"]]["loc"] = None
            events.append(spec.get("event", "Something happens."))
            return

        # 2) use a key on a locked thing -> unlock
        kind, lid = self._lock_for_target(current, aid, move.get("target", ""))
        if kind:
            self._do_unlock(current, context, aid, {"target": move.get("target")}, events)
            return

        if tgt_obj:
            # Item + target both recognized, but no interaction — clear feedback
            # that the TARGET is wrong (not the item name), so a creature doesn't
            # loop re-casing the item (Ludex Cody 2026-07-02: Lyra's dead-end).
            events.append(
                f"The {current['objects'][item]['name']} has no effect on "
                f"the {current['objects'][tgt_obj]['name']}."
            )
        else:
            events.append("Nothing happens.")

    def _do_search(self, current, context, aid, move, events):
        oid = self._resolve_object(current, aid, move.get("target", ""))
        searches = self._zone.get("search", {})
        spec = searches.get(oid) if oid else None
        if spec is None:
            events.append("You search, but find nothing.")
            return
        for r in spec.get("reveal", []):
            current["objects"][r]["visible"] = True
        events.append(spec.get("event", "You find something."))

    def _do_talk(self, current, context, aid, move, events):
        nid = self._resolve_npc(current, aid, move.get("target", ""))
        if not nid:
            events.append(f"There's no {move.get('target')} to talk to here.")
            return
        events.append(current["npcs"][nid].get("talk", "They have nothing to say."))

    def _do_give(self, current, context, aid, move, events):
        nid = self._resolve_npc(current, aid, move.get("target", ""))
        item = self._resolve_object(current, aid, move.get("item", ""))
        if not nid:
            events.append(f"There's no {move.get('target')} here.")
            return
        if not item or current["objects"][item].get("loc") != f"inv:{aid}":
            events.append(f"You aren't carrying the {move.get('item')}.")
            return
        give = (current["npcs"][nid].get("give") or {}).get(item)
        if not give:
            events.append(f"{current['npcs'][nid]['name']} isn't interested in that.")
            return
        current["objects"][item]["loc"] = None  # consumed
        for f, v in (give.get("set_flags") or {}).items():
            current["flags"][f] = v
        events.append(give.get("event", "They accept it."))

    def _do_wait(self, current, context, aid, move, events):
        events.append("Time passes.")

    # ── termination ─────────────────────────────────────────────────────────

    def is_over(self, state: dict) -> bool:
        current = state["game"]["current"]
        if current.get("won"):
            return True
        return current["turn"] > state["game"]["context"]["turn_limit"]

    def get_result(self, state: dict) -> dict:
        current = state["game"]["current"]
        context = state["game"]["context"]
        if current.get("won"):
            w = current["winner"]
            turns = current["turn"] - 1
            return {"outcome": "solved", "winner": w,
                    "scores": {aid: (1.0 if aid == w else 0.0) for aid in current["turn_order"]},
                    "summary": f"{w} solved {context['title']} in {turns} turns."}
        return {"outcome": "unsolved", "winner": None,
                "scores": {aid: 0.0 for aid in current["turn_order"]},
                "summary": f"The zone went unsolved within {context['turn_limit']} turns."}

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        verb = move.get("verb", "?")
        bits = [verb]
        for k in ("direction", "item", "target"):
            if move.get(k):
                bits.append(str(move[k]))
        return " ".join(bits)

    def get_evaluation_schema(self) -> dict:
        return {
            "outcome_summary": "Did the adventurer solve the zone, and how efficiently?",
            "fields": {
                "solved": "bool — was the goal object obtained",
                "turns_used": "int — turns taken",
                "rooms_visited": "int — distinct rooms entered",
            },
        }

    # ── prompt + semantic state (agent-local / fog) ──────────────────────────

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        current = state["game"]["current"]
        context = state["game"]["context"]
        rid = self._room_of(current, agent_id)
        room = current["rooms"][rid]
        objs = [current["objects"][o]["name"] for o in self._visible_room_objects(current, rid)]
        npcs = [current["npcs"][n]["name"] for n in self._npcs_in_room(current, rid)]
        exits = []
        for d, e in room["exits"].items():
            locked = bool(e.get("lock") and current["locks"].get(e["lock"], {}).get("locked"))
            exits.append(f"{d}{' (locked)' if locked else ''}")
        inv = [current["objects"][o]["name"] for o in self._inventory(current, agent_id)]
        ev = current.get("last_events") or []

        lines = [
            f"=== {room['name']} ===",
            room["desc"],
            "",
            f"Exits: {', '.join(exits) if exits else '(none)'}",
            f"You see: {', '.join(objs) if objs else 'nothing of note'}",
        ]
        if npcs:
            lines.append(f"Present: {', '.join(npcs)}")
        lines += [
            f"Inventory: {', '.join(inv) if inv else '(empty)'}",
            "",
            f"GOAL: {context['goal']}",
        ]
        if ev:
            lines += ["", "Last:"] + [f"  - {e}" for e in ev[-3:]]
        lines += [
            "",
            "Respond with ONE action as JSON. Verbs: go(direction), look, examine(target),",
            "take(target), drop(target), open(target), close(target), unlock(target[,item]),",
            "use(item,target), talk(target), give(item,target), search(target), read(target), wait.",
            'Example: {"type":"action","verb":"use","item":"saturn ring","target":"orrery"}',
        ]
        return "\n".join(lines)

    def build_semantic_state(self, agent_id: str, state: dict) -> dict:
        """Agent-local, diff-able semantic view (room scope) — world-model contract."""
        game = state["game"] if isinstance(state.get("game"), dict) else state
        current = game["current"]
        context = game.get("context", {})
        rid = self._room_of(current, agent_id)
        room = current["rooms"][rid]

        objs = sorted((self._obj_descriptor(current, oid)
                       for oid in self._visible_room_objects(current, rid)),
                      key=lambda e: e["id"])

        exits = {}
        for d, e in room["exits"].items():
            exits[d] = {"to": e["to"],
                        "locked": bool(e.get("lock") and current["locks"].get(e["lock"], {}).get("locked"))}

        # inventory carries the SAME descriptors as room.objects so take/drop are
        # pure relocations — the carried item's full identity stays observable.
        inv = [self._obj_descriptor(current, oid)
               for oid in sorted(self._inventory(current, agent_id))]
        npcs = [{"id": n, "name": current["npcs"][n]["name"]} for n in sorted(self._npcs_in_room(current, rid))]

        return {
            "contract_version": 1,
            "game": "mud",
            "scenario": context.get("scenario_id"),
            "turn": current.get("turn"),
            "agent": {"id": agent_id, "location": rid, "inventory": inv},
            "room": {"id": rid, "name": room["name"], "exits": exits, "objects": objs, "npcs": npcs},
            "flags": dict(current.get("flags") or {}),
            "events": [{"text": e} for e in (current.get("last_events") or [])[-4:]],
        }

    def get_timeout_move(self, state: dict, agent_id: str) -> dict:
        return {"type": "action", "verb": "look"}
