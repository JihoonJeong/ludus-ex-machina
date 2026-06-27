"""Diplomacy game engine for LxM — v1 "The Wheel".

A 5-power game of private negotiation and simultaneous secret orders. The board is
fully public; only the press (private messages) and the orders (until they resolve) are
hidden — the fog/mirror engine that makes betrayal legible in replay.

Turn model (one movement phase per year), serialised one seat per step exactly like
Avalon's vote/quest pending queues:

    press  → orders → [resolve] → retreats? → builds? → (next year) press

The orchestrator calls get_active_agent_id() each step; the engine keeps a single
`pending` queue per sub-phase and resolves the sub-phase the moment it empties.
"""

from __future__ import annotations

import copy
import os

from lxm.engine import LxMGame

from . import world
from .adjudicator import resolve

PRESS = "press"
ORDERS = "orders"
RETREATS = "retreats"
BUILDS = "builds"

_RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.md")


class DiplomacyGame(LxMGame):
    min_players = 3
    max_players = 5
    accepts_capabilities = ["json_emit"]

    def __init__(self, max_years: int = 12, press_rounds: int = 1):
        self.max_years = max_years
        self.press_rounds = max(1, press_rounds)
        self.final_year = 1900 + max_years

    # ------------------------------------------------------------------ rules
    def get_rules(self) -> str:
        try:
            with open(_RULES_PATH, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return "Diplomacy — negotiate, order armies (hold/move/support), hold 6 of 11 supply centers to win."

    # ------------------------------------------------------------ state helpers
    def _current(self, state: dict) -> dict:
        g = state.get("game") if isinstance(state.get("game"), dict) else state
        return g["current"]

    def _context(self, state: dict) -> dict:
        g = state.get("game") if isinstance(state.get("game"), dict) else state
        return g.get("context", {})

    def _active_seats(self, current: dict) -> list[str]:
        return [a for a in current["seat_order"]
                if current["players"][a]["status"] == "active"]

    def _units_of(self, current: dict, agent_id: str) -> list[str]:
        return [p for p, owner in current["units"].items() if owner == agent_id]

    def _sc_of(self, current: dict, agent_id: str) -> list[str]:
        return [p for p, owner in current["sc_owner"].items() if owner == agent_id]

    def _sc_count(self, current: dict, agent_id: str) -> int:
        return len(self._sc_of(current, agent_id))

    def _capital_of(self, current: dict, agent_id: str) -> str:
        return current["players"][agent_id]["capital"]

    # --------------------------------------------------------------- new game
    def initial_state(self, agents: list[dict]) -> dict:
        n = len(agents)
        if n < self.min_players or n > self.max_players:
            raise ValueError(f"Diplomacy requires {self.min_players}-{self.max_players} players, got {n}")

        seat_order = [a["agent_id"] for a in agents]

        # Self-assign powers to seats by participant order (cross-machine constraint).
        players: dict[str, dict] = {}
        units: dict[str, str] = {}
        sc_owner: dict[str, str | None] = {p: None for p in world.all_supply_centers()}
        for i, a in enumerate(agents):
            aid = a["agent_id"]
            power = world.POWERS[i]
            players[aid] = {
                "power": power["id"],
                "name": power["name"],
                "color": power["color"],
                "capital": power["capital"],
                "status": "active",
            }
            units[power["capital"]] = aid       # one starting army at the capital
            sc_owner[power["capital"]] = aid     # which it owns

        current = {
            "year": 1901,
            "phase": PRESS,
            "press_round": 0,
            "players": players,
            "seat_order": seat_order,
            "units": units,
            "sc_owner": sc_owner,
            "pending": list(seat_order),         # press: everyone talks
            "press_messages": [],                # [{from,to,text,year}] — filtered per seat
            "orders_submitted": {},              # {agent: {prov: spec}} — secret until resolve
            "dislodged": {},                     # {prov: {owner, attacker_from, forbidden}}
            "retreats_submitted": {},
            "builds_submitted": {},
            "last_resolution": None,             # the just-resolved movement (renderer)
            "winner": None,
            "co_leaders": [],
            "over": False,
        }
        context = {
            "years_played": 0,
            "sc_history": [],                    # [{year, counts}]
            "eliminations": [],                  # [{agent, year}]
            "order_history": [],                 # [{year, orders, outcomes}] (mirror layer)
        }
        return {"current": current, "context": context}

    # --------------------------------------------------------- turn ownership
    def get_active_agent_id(self, state: dict) -> str | None:
        current = self._current(state)
        pending = current.get("pending", [])
        return pending[0] if pending else None

    def is_agent_active(self, agent_id: str, state: dict) -> bool:
        current = self._current(state)
        return current["players"].get(agent_id, {}).get("status") == "active"

    # ------------------------------------------------------------------- fog
    def filter_state_for_agent(self, state: dict, agent_id: str) -> dict:
        filtered = copy.deepcopy(state)
        current = self._current(filtered)

        # secret orders: others show only "submitted"
        if current["phase"] == ORDERS:
            current["orders_submitted"] = {
                a: (v if a == agent_id else "submitted")
                for a, v in current["orders_submitted"].items()
            }
        # private press: only messages I sent or received (or broadcasts)
        current["press_messages"] = [
            m for m in current["press_messages"]
            if m["from"] == agent_id or m["to"] in (agent_id, "all")
        ]
        # others' retreats stay hidden until applied
        if current["phase"] == RETREATS:
            current["retreats_submitted"] = {
                a: (v if a == agent_id else "submitted")
                for a, v in current["retreats_submitted"].items()
            }
        return filtered

    # ------------------------------------------------------------- validation
    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        current = self._current(state)
        phase = current["phase"]
        mtype = move.get("type")

        if agent_id not in current.get("pending", []):
            return {"valid": False, "message": f"It is not {agent_id}'s turn ({phase} phase)."}

        if phase == PRESS:
            if mtype != "press":
                return {"valid": False, "message": f"Expected a 'press' move in the press phase, got '{mtype}'."}
            msgs = move.get("messages", [])
            if not isinstance(msgs, list):
                return {"valid": False, "message": "'messages' must be a list (may be empty to stay silent)."}
            valid_to = set(current["seat_order"]) | {"all"}
            for m in msgs:
                if not isinstance(m, dict) or "to" not in m or "text" not in m:
                    return {"valid": False, "message": "each message needs 'to' and 'text'."}
                if m["to"] not in valid_to:
                    return {"valid": False, "message": f"unknown recipient '{m['to']}' (use a player id or 'all')."}
            return {"valid": True, "message": None}

        if phase == ORDERS:
            if mtype != "orders":
                return {"valid": False, "message": f"Expected an 'orders' move in the orders phase, got '{mtype}'."}
            orders = move.get("orders", {})
            if not isinstance(orders, dict):
                return {"valid": False, "message": "'orders' must be an object mapping each of your provinces to an order."}
            owned = set(self._units_of(current, agent_id))
            for prov, spec in orders.items():
                if prov not in owned:
                    return {"valid": False, "message": f"You have no army in '{prov}'."}
                err = self._order_error(prov, spec)
                if err:
                    return {"valid": False, "message": err}
            return {"valid": True, "message": None}

        if phase == RETREATS:
            if mtype != "retreat":
                return {"valid": False, "message": f"Expected a 'retreat' move, got '{mtype}'."}
            retreats = move.get("retreats", {})
            if not isinstance(retreats, dict):
                return {"valid": False, "message": "'retreats' must map each dislodged province to a destination or 'disband'."}
            mine = {p: info for p, info in current["dislodged"].items() if info["owner"] == agent_id}
            for prov, dest in retreats.items():
                if prov not in mine:
                    return {"valid": False, "message": f"You have no dislodged army from '{prov}'."}
                if dest == "disband":
                    continue
                if dest not in world.neighbors(prov):
                    return {"valid": False, "message": f"'{dest}' does not border '{prov}'."}
                if dest in mine[prov]["forbidden"]:
                    return {"valid": False, "message": f"Cannot retreat to '{dest}' (occupied, attacker's origin, or a standoff)."}
            return {"valid": True, "message": None}

        if phase == BUILDS:
            if mtype != "build":
                return {"valid": False, "message": f"Expected a 'build' move, got '{mtype}'."}
            delta = self._sc_count(current, agent_id) - len(self._units_of(current, agent_id))
            builds = move.get("builds", []) or []
            disbands = move.get("disbands", []) or []
            if delta > 0:  # may build
                cap = self._capital_of(current, agent_id)
                if builds:
                    if builds != [cap]:
                        return {"valid": False, "message": f"You may only build in your home capital '{cap}'."}
                    if current["sc_owner"].get(cap) != agent_id or cap in current["units"]:
                        return {"valid": False, "message": f"Cannot build: '{cap}' must be owned by you and empty."}
            elif delta < 0:  # must disband -delta
                need = -delta
                if len(disbands) != need:
                    return {"valid": False, "message": f"You must disband exactly {need} army/armies."}
                owned = set(self._units_of(current, agent_id))
                for p in disbands:
                    if p not in owned:
                        return {"valid": False, "message": f"You have no army in '{p}' to disband."}
            return {"valid": True, "message": None}

        return {"valid": False, "message": f"No action expected in phase '{phase}'."}

    def _order_error(self, prov: str, spec) -> str | None:
        """None if the order spec is legal for an army at `prov`, else an error message."""
        if spec == "hold" or spec is None:
            return None
        if isinstance(spec, str):
            if spec not in world.neighbors(prov):
                return f"'{prov}' cannot move to '{spec}' (not adjacent)."
            return None
        if isinstance(spec, dict) and "support" in spec:
            target = spec["support"]
            frm = spec.get("from")
            if target not in world.neighbors(prov):
                return f"'{prov}' cannot support into '{target}' (not adjacent)."
            if frm is not None and target not in world.neighbors(frm):
                return f"'{frm}' cannot move to '{target}', so '{prov}' cannot support that move."
            return None
        return f"Unrecognised order for '{prov}': {spec!r}."

    @staticmethod
    def _norm_order(spec) -> dict:
        if spec == "hold" or spec is None:
            return {"type": "hold"}
        if isinstance(spec, str):
            return {"type": "move", "dest": spec}
        if isinstance(spec, dict) and "support" in spec:
            return {"type": "support", "target": spec["support"], "from": spec.get("from")}
        return {"type": "hold"}

    # ------------------------------------------------------------------ apply
    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        current = self._current(state)
        context = self._context(state)
        phase = current["phase"]

        if phase == PRESS:
            year = current["year"]
            for m in move.get("messages", []):
                current["press_messages"].append(
                    {"from": agent_id, "to": m["to"], "text": str(m["text"])[:1000], "year": year}
                )
            self._pop_and_maybe(current, context, agent_id, self._advance_press)

        elif phase == ORDERS:
            current["orders_submitted"][agent_id] = move.get("orders", {})
            self._pop_and_maybe(current, context, agent_id, self._resolve_orders)

        elif phase == RETREATS:
            current["retreats_submitted"][agent_id] = move.get("retreats", {})
            self._pop_and_maybe(current, context, agent_id, self._apply_retreats)

        elif phase == BUILDS:
            current["builds_submitted"][agent_id] = {
                "builds": move.get("builds", []) or [],
                "disbands": move.get("disbands", []) or [],
            }
            self._pop_and_maybe(current, context, agent_id, self._apply_builds)

        return {"current": current, "context": context}

    def _pop_and_maybe(self, current, context, agent_id, resolver):
        if agent_id in current["pending"]:
            current["pending"].remove(agent_id)
        if not current["pending"]:
            resolver(current, context)

    # ---------------------------------------------------------- phase engines
    def _begin_press(self, current, context):
        current["phase"] = PRESS
        current["press_round"] = 0
        current["pending"] = self._active_seats(current)

    def _advance_press(self, current, context):
        if current["press_round"] + 1 < self.press_rounds:
            current["press_round"] += 1
            current["pending"] = self._active_seats(current)
        else:
            self._begin_orders(current, context)

    def _begin_orders(self, current, context):
        current["phase"] = ORDERS
        current["orders_submitted"] = {}
        # only powers that actually have armies submit orders
        current["pending"] = [a for a in self._active_seats(current) if self._units_of(current, a)]
        if not current["pending"]:
            self._resolve_orders(current, context)

    def _resolve_orders(self, current, context):
        units = dict(current["units"])
        orders = {}
        for agent, spec_map in current["orders_submitted"].items():
            if spec_map == "submitted" or not isinstance(spec_map, dict):
                continue
            for prov, spec in spec_map.items():
                if units.get(prov) == agent:        # only orders for own armies
                    orders[prov] = self._norm_order(spec)

        res = resolve(units, orders)
        current["units"] = res["positions"]
        current["dislodged"] = res["dislodged"]
        current["last_resolution"] = {
            "year": current["year"],
            "orders": orders,                 # {prov: normalized order} — for arrows
            "outcomes": res["outcomes"],
            "standoffs": sorted(res["standoffs"]),
            "dislodged": {p: i["owner"] for p, i in res["dislodged"].items()},
        }
        context["order_history"].append({
            "year": current["year"],
            "outcomes": res["outcomes"],
        })

        if current["dislodged"]:
            self._begin_retreats(current, context)
        else:
            self._post_movement(current, context)

    def _begin_retreats(self, current, context):
        current["phase"] = RETREATS
        current["retreats_submitted"] = {}
        owners = []
        for info in current["dislodged"].values():
            if info["owner"] not in owners:
                owners.append(info["owner"])
        current["pending"] = [a for a in current["seat_order"] if a in owners]

    def _apply_retreats(self, current, context):
        # collect chosen destinations; conflicts (two units to same province) all disband
        chosen: dict[str, list[str]] = {}   # dest -> [origin provinces]
        disband = set()
        for agent, retreats in current["retreats_submitted"].items():
            if not isinstance(retreats, dict):
                retreats = {}
            for prov, info in current["dislodged"].items():
                if info["owner"] != agent:
                    continue
                dest = retreats.get(prov, "disband")
                if dest == "disband" or dest in info["forbidden"] or dest not in world.neighbors(prov):
                    disband.add(prov)
                else:
                    chosen.setdefault(dest, []).append(prov)
        # any dislodged unit not addressed by its owner -> disband
        addressed = {p for prov_list in chosen.values() for p in prov_list} | disband
        for prov in current["dislodged"]:
            if prov not in addressed:
                disband.add(prov)

        for dest, origins in chosen.items():
            if dest in current["units"] or len(origins) > 1:
                continue  # bounced/occupied -> those units are lost
            owner = current["dislodged"][origins[0]]["owner"]
            current["units"][dest] = owner
        current["dislodged"] = {}
        self._post_movement(current, context)

    def _post_movement(self, current, context):
        self._update_sc_ownership(current, context)
        self._begin_builds(current, context)

    def _update_sc_ownership(self, current, context):
        for prov, owner in current["units"].items():
            if world.is_supply_center(prov):
                current["sc_owner"][prov] = owner
        counts = {a: self._sc_count(current, a) for a in current["seat_order"]}
        context["sc_history"].append({"year": current["year"], "counts": counts})

    def _begin_builds(self, current, context):
        current["phase"] = BUILDS
        current["builds_submitted"] = {}
        pending = []
        for a in self._active_seats(current):
            if self._sc_count(current, a) != len(self._units_of(current, a)):
                pending.append(a)
        current["pending"] = pending
        if not pending:
            self._end_year(current, context)

    def _apply_builds(self, current, context):
        for agent, adj in current["builds_submitted"].items():
            if not isinstance(adj, dict):
                continue
            delta = self._sc_count(current, agent) - len(self._units_of(current, agent))
            if delta > 0:
                cap = self._capital_of(current, agent)
                if cap in (adj.get("builds") or []) and current["sc_owner"].get(cap) == agent and cap not in current["units"]:
                    current["units"][cap] = agent
            elif delta < 0:
                for p in (adj.get("disbands") or [])[: -delta]:
                    if current["units"].get(p) == agent:
                        del current["units"][p]
        self._end_year(current, context)

    def _end_year(self, current, context):
        context["years_played"] += 1
        # eliminations: no centers and no armies
        for a in current["seat_order"]:
            p = current["players"][a]
            if p["status"] == "active" and self._sc_count(current, a) == 0 and not self._units_of(current, a):
                p["status"] = "eliminated"
                context["eliminations"].append({"agent": a, "year": current["year"]})

        active = self._active_seats(current)
        leader = max(active, key=lambda a: self._sc_count(current, a)) if active else None

        if leader and self._sc_count(current, leader) >= world.WIN_SUPPLY_CENTERS:
            self._finish(current, leader, [leader])
        elif len(active) <= 1:
            self._finish(current, active[0] if active else None, active)
        elif current["year"] >= self.final_year:
            top = max(self._sc_count(current, a) for a in active)
            leaders = [a for a in active if self._sc_count(current, a) == top]
            self._finish(current, leaders[0] if len(leaders) == 1 else None, leaders)
        else:
            current["year"] += 1
            self._begin_press(current, context)

    def _finish(self, current, winner, leaders):
        current["winner"] = winner
        current["co_leaders"] = leaders
        current["over"] = True
        current["phase"] = "over"
        current["pending"] = []

    # ------------------------------------------------------------------- over
    def is_over(self, state: dict) -> bool:
        return bool(self._current(state).get("over"))

    def get_result(self, state: dict) -> dict:
        current = self._current(state)
        context = self._context(state)
        scores = {a: self._sc_count(current, a) for a in current["seat_order"]}
        ranking = sorted(current["seat_order"], key=lambda a: scores[a], reverse=True)
        winner = current.get("winner")

        def label(a):
            return f"{current['players'][a]['name']} ({a})"

        if winner:
            won = scores[winner] >= world.WIN_SUPPLY_CENTERS
            outcome = "domination" if won else "lead"
            summary = (f"{label(winner)} {'conquered the Wheel' if won else 'held the largest realm'} "
                       f"with {scores[winner]} of {len(world.all_supply_centers())} centers.")
        else:
            co = current.get("co_leaders", [])
            outcome = "draw"
            summary = "Stalemate — the Wheel is shared by " + ", ".join(label(a) for a in co) + "."

        return {
            "outcome": outcome,
            "winner": winner,
            "ranking": ranking,
            "scores": scores,
            "summary": summary,
            "analysis": {
                "years_played": context.get("years_played", 0),
                "final_sc": scores,
                "eliminations": context.get("eliminations", []),
                "co_leaders": current.get("co_leaders", []),
            },
        }

    # --------------------------------------------------------------- logging
    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        current = self._current(state)
        name = current["players"].get(agent_id, {}).get("name", agent_id)
        mtype = move.get("type")
        if mtype == "press":
            n = len(move.get("messages", []) or [])
            return f"{name}: {'sent ' + str(n) + ' message(s)' if n else 'stayed silent'}"
        if mtype == "orders":
            parts = []
            for prov, spec in (move.get("orders", {}) or {}).items():
                if isinstance(spec, dict) and "support" in spec:
                    parts.append(f"{prov} S {spec['support']}")
                elif isinstance(spec, str) and spec != "hold":
                    parts.append(f"{prov}→{spec}")
                else:
                    parts.append(f"{prov} H")
            return f"{name}: " + (", ".join(parts) if parts else "holds")
        if mtype == "retreat":
            return f"{name}: retreats " + ", ".join(f"{p}→{d}" for p, d in (move.get("retreats", {}) or {}).items())
        if mtype == "build":
            b = move.get("builds", []) or []
            d = move.get("disbands", []) or []
            bits = [f"+{x}" for x in b] + [f"-{x}" for x in d]
            return f"{name}: {' '.join(bits) if bits else 'no change'}"
        return f"{name}: {mtype}"

    # -------------------------------------------------------------- inline prompt
    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str:
        current = self._current(state)
        match_id = state.get("lxm", {}).get("match_id", "")
        me = current["players"][agent_id]
        phase = current["phase"]
        year = current["year"]
        ncenters = len(world.all_supply_centers())

        # scoreboard
        board_score = []
        for a in current["seat_order"]:
            p = current["players"][a]
            tag = " (you)" if a == agent_id else ""
            status = "" if p["status"] == "active" else " [eliminated]"
            board_score.append(f"  {p['name']}{tag}: {self._sc_count(current, a)} SC, "
                               f"{len(self._units_of(current, a))} armies{status}")

        # board
        board_lines = []
        for prov, meta in world.PROVINCES.items():
            occ = current["units"].get(prov)
            occ_name = current["players"][occ]["name"] if occ else "—"
            sc_owner = current["sc_owner"].get(prov)
            sc_name = current["players"][sc_owner]["name"] if sc_owner else "neutral"
            board_lines.append(f"  {meta['label']:<10} army:{occ_name:<8} center:{sc_name}")

        my_units = self._units_of(current, agent_id)
        unit_lines = [f"  {world.PROVINCES[u]['label']} → adjacent: "
                      f"{', '.join(world.PROVINCES[n]['label'] for n in sorted(world.neighbors(u)))}"
                      for u in my_units]

        # press received this game (already filtered for this agent upstream)
        press_lines = []
        for m in current["press_messages"][-12:]:
            frm = current["players"].get(m["from"], {}).get("name", m["from"])
            to = "all" if m["to"] == "all" else current["players"].get(m["to"], {}).get("name", m["to"])
            press_lines.append(f"  [{m['year']}] {frm}→{to}: {m['text']}")

        head = [
            f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}",
            f"DIPLOMACY \"The Wheel\" | Year {year} | Phase: {phase.upper()} | You are {me['name']}",
            f"Goal: control {world.WIN_SUPPLY_CENTERS} of {ncenters} supply centers.",
            "",
            "Standings:", *board_score,
            "",
            "Board (province | occupying army | center owner):", *board_lines,
            "",
            "Your armies and where they can go:", *(unit_lines or ["  (none)"]),
        ]
        if press_lines:
            head += ["", "Messages you can see:", *press_lines]
        head += [""]

        action = self._prompt_action(phase, agent_id, current, match_id, turn)
        tail = ["", "Do NOT read any files. Decide, then output the JSON move on its own line."]
        return "\n".join(head + action + tail)

    def _prompt_action(self, phase, agent_id, current, match_id, turn) -> list[str]:
        env = f'{{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},"move":'
        if phase == PRESS:
            return [
                "PRESS — send private messages to scheme, promise, or mislead (or stay silent).",
                "'to' is a player id (see Standings) or \"all\" to broadcast.",
                "Example:",
                f'  {env}{{"type":"press","messages":[{{"to":"all","text":"I propose we both push the Crown."}}]}}}}',
                "Stay silent:",
                f'  {env}{{"type":"press","messages":[]}}}}',
            ]
        if phase == ORDERS:
            units = self._units_of(current, agent_id)
            sample = units[0] if units else "yourunit"
            nb = sorted(world.neighbors(sample))[0] if units else "dest"
            return [
                "ORDERS — write one secret order per army. Others won't see them until they resolve.",
                "Each army maps to: \"hold\" | \"<adjacent province>\" (move) |",
                "  {\"support\":\"<prov>\"} (support a hold) | {\"support\":\"<dest>\",\"from\":\"<origin>\"} (support a move).",
                "Example:",
                f'  {env}{{"type":"orders","orders":{{"{sample}":"{nb}"}}}}}}',
            ]
        if phase == RETREATS:
            mine = [p for p, i in current["dislodged"].items() if i["owner"] == agent_id]
            opts = {}
            for p in mine:
                allowed = [n for n in world.neighbors(p) if n not in current["dislodged"][p]["forbidden"]]
                opts[p] = allowed
            return [
                "RETREATS — each dislodged army must retreat to an open bordering province, or disband.",
                f"Your dislodged armies & options: {opts}",
                "Example:",
                f'  {env}{{"type":"retreat","retreats":{{"{(mine or ["prov"])[0]}":"disband"}}}}}}',
            ]
        if phase == BUILDS:
            delta = self._sc_count(current, agent_id) - len(self._units_of(current, agent_id))
            if delta > 0:
                cap = self._capital_of(current, agent_id)
                return [
                    f"BUILDS — you hold {delta} more center(s) than armies; you may build in your capital {world.PROVINCES[cap]['label']} (if empty & owned).",
                    f'  {env}{{"type":"build","builds":["{cap}"]}}}}',
                    "Or skip:",
                    f'  {env}{{"type":"build","builds":[]}}}}',
                ]
            need = -delta
            return [
                f"BUILDS — you have {need} more army/armies than centers; you must disband {need}.",
                f"Your armies: {self._units_of(current, agent_id)}",
                f'  {env}{{"type":"build","disbands":{self._units_of(current, agent_id)[:need]}}}}}'.replace("'", '"'),
            ]
        return ["(no action)"]

    # ----------------------------------------------------------------- timeout
    def get_timeout_move(self, agent_id: str, game_state: dict) -> dict:
        current = self._current(game_state) if ("game" in game_state or "current" in game_state) else game_state
        phase = current.get("phase")
        if phase == PRESS:
            return {"type": "press", "messages": []}
        if phase == ORDERS:
            return {"type": "orders", "orders": {p: "hold" for p in self._units_of(current, agent_id)}}
        if phase == RETREATS:
            mine = [p for p, i in current["dislodged"].items() if i["owner"] == agent_id]
            return {"type": "retreat", "retreats": {p: "disband" for p in mine}}
        if phase == BUILDS:
            delta = self._sc_count(current, agent_id) - len(self._units_of(current, agent_id))
            if delta < 0:
                return {"type": "build", "disbands": self._units_of(current, agent_id)[: -delta]}
            return {"type": "build", "builds": []}
        return {"type": "press", "messages": []}

    # -------------------------------------------------------------- evaluation
    def get_evaluation_schema(self) -> dict:
        return {
            "scale": "1-10",
            "dimensions": [
                {"key": "diplomacy", "label": "Diplomatic skill", "desc": "Forming and using alliances through press."},
                {"key": "strategy", "label": "Strategic planning", "desc": "Tempo, target selection, supply-center growth."},
                {"key": "tactics", "label": "Tactical orders", "desc": "Effective use of support, standoffs, and dislodgement."},
                {"key": "deception", "label": "Deception & timing", "desc": "Well-timed betrayal vs. trustworthiness when it paid."},
            ],
        }
