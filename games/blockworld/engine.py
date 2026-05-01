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
    "interact",
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

        # Agent start positions. Scenario may provide either:
        #   - `agent_starts`: [{agent_id?, x, y, z, facing?}, ...]
        #       matched by agent_id first, then falls back to positional
        #       order in the agents list; or
        #   - `agent_start`: single {x, y, z, facing?} applied to every
        #       agent (legacy single-agent schema).
        starts_by_id = {}
        starts_positional = []
        if "agent_starts" in self._scenario:
            for s in self._scenario["agent_starts"]:
                if s.get("agent_id"):
                    starts_by_id[s["agent_id"]] = s
                else:
                    starts_positional.append(s)
        shared_start = self._scenario.get("agent_start")

        agent_states = {}
        for i, a in enumerate(agents):
            aid = a["agent_id"]
            if aid in starts_by_id:
                s = starts_by_id[aid]
            elif i < len(starts_positional):
                s = starts_positional[i]
            elif shared_start is not None:
                s = shared_start
            else:
                raise ValueError(
                    f"no start position for agent {aid}: scenario needs "
                    f"agent_start or agent_starts"
                )
            agent_states[aid] = {
                "agent_id": aid,
                "x": s["x"],
                "y": s["y"],
                "z": s["z"],
                "facing": s.get("facing", "north"),
                "inventory": {},
                "status": "active",
            }

        # Stag-hunt mode initial spawning: hares as ground_items, stag in
        # context. Scenario specifies hare_locations (list of {x,y,z}) and
        # stag_location ({x,y,z}). Capture mechanics handled in apply_move
        # post-hook + is_over/get_result.
        # 'stag_hunt': single-shot — terminates on first capture.
        # 'stag_hunt_repeated': stag/hares respawn, match runs to turn_limit
        # for MeltingPot-comparable repeated encounters.
        ground_items = []
        stag_state = None
        mode = self._scenario.get("mode", "shelter")
        if mode in ("stag_hunt", "stag_hunt_repeated"):
            for loc in self._scenario.get("hare_locations", []):
                ground_items.append({
                    "type": "hare",
                    "x": loc["x"], "y": loc["y"], "z": loc["z"],
                    "count": 1,
                })
            stag_state = {
                **(self._scenario.get("stag_location") or {}),
                "captured": False,
                "captured_by": None,
                "respawn_at_turn": None,
            }

        # Commons Harvest mode: shared apple trees with regeneration +
        # depletion dynamics. Trees start with `tree_max_apples` each;
        # apples on the ground are pickable via existing pickup mechanic.
        # Trees regenerate +1 apple per `tree_regen_turns` turns up to
        # the cap. If a tree stays at 0 apples for `tree_depletion_turns`
        # consecutive turns without any neighboring trees having apples,
        # it dies permanently.
        trees_state = None
        if mode == "commons_harvest":
            trees_state = []
            for loc in self._scenario.get("tree_locations", []):
                trees_state.append({
                    "x": loc["x"], "y": loc["y"], "z": loc["z"],
                    "apples": self._scenario.get("tree_max_apples", 3),
                    "dead": False,
                    "empty_streak": 0,
                    "next_regen_turn": None,
                })

        # Externality Mushrooms: public-goods substrate. Two mushroom
        # types scatter the grid — selfish_mushroom rewards only the
        # picker; public_mushroom rewards picker less but generates a
        # positive externality bonus for every other agent. Each pickup
        # IS the cooperation/defection action (no encounter needed),
        # canonical PD payoff structure across round-trips. Mushrooms
        # respawn after pickup like coop/defect tokens in PD-matrix.
        if mode == "externality_mushrooms":
            for loc in self._scenario.get("selfish_mushroom_locations", []):
                ground_items.append({
                    "type": "selfish_mushroom",
                    "x": loc["x"], "y": loc["y"], "z": loc["z"], "count": 1,
                })
            for loc in self._scenario.get("public_mushroom_locations", []):
                ground_items.append({
                    "type": "public_mushroom",
                    "x": loc["x"], "y": loc["y"], "z": loc["z"], "count": 1,
                })

        # Prisoners' Dilemma in the Matrix: token-encounter PD lineage
        # from MeltingPot. Agents collect coop_token / defect_token from
        # the ground; when they end a turn within encounter_radius (and
        # cooldown elapsed), an encounter triggers. Each agent's PD move
        # is determined by their current inventory ratio (more coop than
        # defect → C, else D, tie → C). Canonical PD payoff matrix is
        # applied, both agents' coop/defect tokens reset to 0 (consumed),
        # and last_encounter_turn updates. Match runs to turn_limit.
        if mode == "prisoners_dilemma":
            for loc in self._scenario.get("coop_token_locations", []):
                ground_items.append({
                    "type": "coop_token",
                    "x": loc["x"], "y": loc["y"], "z": loc["z"], "count": 1,
                })
            for loc in self._scenario.get("defect_token_locations", []):
                ground_items.append({
                    "type": "defect_token",
                    "x": loc["x"], "y": loc["y"], "z": loc["z"], "count": 1,
                })

        # Pure Coordination mode: Schelling-point selection. Both agents
        # must end any turn on the same (x,y,z) cell with no transmitted
        # communication (the `say` verb is silently dropped from other
        # agents' inline prompts in this mode). Landmarks are advertised
        # in the prompt to provide cultural-salience focal candidates.
        meet_state = None
        if mode == "pure_coord":
            meet_state = {
                "met": False,
                "at_turn": None,
                "cell": None,
                "pair": None,
            }

        # Predator-Prey mode: read role assignments from agent_starts.
        # Each entry must carry `role` ∈ {"predator", "prey"}. We surface
        # roles + capture flag in `chase` block of state for downstream
        # scoring + prompt rendering.
        chase_state = None
        if mode == "predator_prey":
            roles = {}
            for s in self._scenario.get("agent_starts", []):
                if s.get("agent_id") and s.get("role"):
                    roles[s["agent_id"]] = s["role"]
            chase_state = {
                "roles": roles,
                "captured": False,
                "captured_at_turn": None,
                "captor": None,
                "victim": None,
            }

        return {
            "current": {
                "phase": "playing",
                "turn": 1,
                "turn_order": [a["agent_id"] for a in agents],
                "active_index": 0,
                "agents": agent_states,
                "world": world_dict,
                "ground_items": ground_items,
                "last_events": [],
                "stag": stag_state,
                "trees": trees_state,
                "chase": chase_state,
                "meet": meet_state,
                "pd": {
                    "encounter_log": [],
                    "last_encounter_turn": -10**9,
                } if mode == "prisoners_dilemma" else None,
            },
            "context": {
                "scenario_id": self._scenario_id,
                "scenario_title": self._scenario["title"],
                "goal": self._scenario["goal"],
                "turn_limit": self._scenario["turn_limit"],
                "shelter_deadline": self._scenario.get("shelter_deadline", self._scenario["turn_limit"]),
                "min_floor": self._scenario.get("min_floor", 1),
                "strict_placed": self._scenario.get("strict_placed", False),
                "min_placed_boundary": self._scenario.get("min_placed_boundary"),
                "mode": mode,
                "agent_start": shared_start,
                "agent_starts": self._scenario.get("agent_starts"),
                "stag_reward": self._scenario.get("stag_reward", 5),
                "hare_reward": self._scenario.get("hare_reward", 1),
                "stag_respawn_turns": self._scenario.get("stag_respawn_turns", 5),
                "hare_respawn_turns": self._scenario.get("hare_respawn_turns", 8),
                "stag_capture_log": [],
                "hare_pickup_log": [],
                "agent_stag_share": {a["agent_id"]: 0.0 for a in agents},
                "agent_hare_count": {a["agent_id"]: 0 for a in agents},
                "tree_max_apples": self._scenario.get("tree_max_apples", 3),
                "tree_regen_turns": self._scenario.get("tree_regen_turns", 4),
                "tree_depletion_turns": self._scenario.get("tree_depletion_turns", 12),
                "apple_reward": self._scenario.get("apple_reward", 1),
                "agent_apple_count": {a["agent_id"]: 0 for a in agents},
                "apple_pickup_log": [],
                "tree_death_log": [],
                "capture_radius": self._scenario.get("capture_radius", 1),
                "capture_reward": self._scenario.get("capture_reward", 1.0),
                "survival_reward": self._scenario.get("survival_reward", 1.0),
                "landmarks": self._scenario.get("landmarks", []),
                "meeting_reward": self._scenario.get("meeting_reward", 1.0),
                "say_filtered": self._scenario.get("say_filtered", True),
                "say_attempts": {a["agent_id"]: 0 for a in agents},
                "encounter_radius": self._scenario.get("encounter_radius", 1),
                "encounter_cooldown": self._scenario.get("encounter_cooldown", 8),
                "token_respawn_turns": self._scenario.get("token_respawn_turns", 6),
                "pd_payoff": self._scenario.get("pd_payoff", {
                    "CC": [3, 3], "CD": [0, 5], "DC": [5, 0], "DD": [1, 1],
                }),
                "agent_pd_score": {a["agent_id"]: 0 for a in agents},
                "agent_coop_pickups": {a["agent_id"]: 0 for a in agents},
                "agent_defect_pickups": {a["agent_id"]: 0 for a in agents},
                "selfish_reward": self._scenario.get("selfish_reward", 2),
                "public_reward_self": self._scenario.get("public_reward_self", 1),
                "public_reward_other": self._scenario.get("public_reward_other", 3),
                "mushroom_respawn_turns": self._scenario.get("mushroom_respawn_turns", 6),
                "agent_em_score": {a["agent_id"]: 0 for a in agents},
                "agent_selfish_picks": {a["agent_id"]: 0 for a in agents},
                "agent_public_picks": {a["agent_id"]: 0 for a in agents},
                "agent_externality_received": {a["agent_id"]: 0 for a in agents},
                "em_pickup_log": [],
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
        elif verb == "interact":
            d = move.get("direction")
            if d not in ("up", "down"):
                return {"valid": False, "message": "interact requires 'direction' in {'up','down'} (currently used for ladder traversal)"}
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
        elif verb == "interact":
            self._do_interact(world, agent, move["direction"], events)

        # Stag-hunt post-hook: after every action, check whether both
        # agents are simultaneously adjacent to the stag (manhattan 3D
        # distance ≤ 1 from stag cell). If so, mark stag captured —
        # cooperative payoff is shared at terminal scoring.
        mode = game["context"].get("mode")
        if mode == "stag_hunt":
            self._check_stag_capture(current, events)
        elif mode == "stag_hunt_repeated":
            self._tick_stag_hunt_repeated(current, game["context"], events)
        elif mode == "commons_harvest":
            self._tick_commons_harvest(current, game["context"], events)
        elif mode == "predator_prey":
            self._check_predator_capture(current, game["context"], events)
        elif mode == "pure_coord":
            if verb == "say":
                game["context"]["say_attempts"][agent_id] = (
                    game["context"]["say_attempts"].get(agent_id, 0) + 1
                )
            self._check_pure_coord_meeting(current, game["context"], events)
        elif mode == "prisoners_dilemma":
            if verb == "say":
                game["context"]["say_attempts"][agent_id] = (
                    game["context"]["say_attempts"].get(agent_id, 0) + 1
                )
            self._tick_prisoners_dilemma(current, game["context"], events)
        elif mode == "externality_mushrooms":
            if verb == "say":
                game["context"]["say_attempts"][agent_id] = (
                    game["context"]["say_attempts"].get(agent_id, 0) + 1
                )
            self._tick_externality_mushrooms(current, game["context"], events)

        # Advance turn counter + rotate active agent.
        current["last_events"] = events
        current["turn"] += 1
        n = len(current["turn_order"])
        current["active_index"] = (current["active_index"] + 1) % n

        return {"current": current, "context": game["context"]}

    def _check_stag_capture(self, current, events):
        """Mark stag captured if both (or all) agents are adjacent."""
        stag = current.get("stag")
        if not stag or stag.get("captured") or stag.get("x") is None:
            return
        sx, sy, sz = stag["x"], stag["y"], stag["z"]
        adjacent_ids = []
        for aid, ag in current["agents"].items():
            d = abs(ag["x"] - sx) + abs(ag["y"] - sy) + abs(ag["z"] - sz)
            if d <= 1:
                adjacent_ids.append(aid)
        if len(adjacent_ids) >= 2:
            stag["captured"] = True
            stag["captured_by"] = sorted(adjacent_ids)
            events.append(f"STAG CAPTURED cooperatively by {', '.join(stag['captured_by'])}")

    def _tick_stag_hunt_repeated(self, current, context, events):
        """Per-turn tick for repeated mode: detect stag captures (cooperative
        co-presence) AND hare pickups, accumulate cumulative scores, schedule
        respawns. Match never terminates on capture — runs to turn_limit.
        """
        stag = current.get("stag") or {}
        turn = current.get("turn", 1)

        # Stag respawn: bring it back if cooldown elapsed.
        if stag.get("captured") and stag.get("respawn_at_turn") is not None:
            if turn >= stag["respawn_at_turn"]:
                stag["captured"] = False
                stag["captured_by"] = None
                stag["respawn_at_turn"] = None
                events.append(f"STAG RESPAWNED at ({stag['x']}, {stag['y']}, {stag['z']})")

        # Cooperative stag capture (only if currently alive).
        if not stag.get("captured") and stag.get("x") is not None:
            sx, sy, sz = stag["x"], stag["y"], stag["z"]
            adjacent_ids = []
            for aid, ag in current["agents"].items():
                d = abs(ag["x"] - sx) + abs(ag["y"] - sy) + abs(ag["z"] - sz)
                if d <= 1:
                    adjacent_ids.append(aid)
            if len(adjacent_ids) >= 2:
                stag["captured"] = True
                captors = sorted(adjacent_ids)
                stag["captured_by"] = captors
                stag["respawn_at_turn"] = turn + context.get("stag_respawn_turns", 5)
                share = context.get("stag_reward", 5) / max(1, len(captors))
                for cid in captors:
                    context["agent_stag_share"][cid] = context["agent_stag_share"].get(cid, 0.0) + share
                context.setdefault("stag_capture_log", []).append({
                    "turn": turn,
                    "captors": captors,
                    "share_each": share,
                })
                events.append(
                    f"STAG CAPTURED cooperatively by {', '.join(captors)} "
                    f"(+{share:.1f} each, respawn turn {stag['respawn_at_turn']})"
                )

        # Hare pickup tracking: detect when an agent's `hare` inventory grew
        # this turn (existing pick verb adds to inventory). We compare against
        # last known count via context state.
        last_counts = context.setdefault("_last_hare_inventory", {})
        hare_reward = context.get("hare_reward", 1)
        for aid, ag in current["agents"].items():
            cur = int((ag.get("inventory") or {}).get("hare") or 0)
            prev = int(last_counts.get(aid) or 0)
            if cur > prev:
                gained = cur - prev
                context["agent_hare_count"][aid] = context["agent_hare_count"].get(aid, 0) + gained
                context.setdefault("hare_pickup_log", []).append({
                    "turn": turn,
                    "agent": aid,
                    "count": gained,
                })
                events.append(f"{aid} picked up hare (+{gained * hare_reward})")
            last_counts[aid] = cur

        # Hare respawn: scheduled in respawn_at_turn list. We model each hare
        # location with a list of pending respawn turns; simpler: when ground
        # has fewer hares than configured locations, respawn after cooldown.
        configured_locs = self._scenario.get("hare_locations", [])
        cooldown = context.get("hare_respawn_turns", 8)
        # Find which configured locations currently lack a hare item.
        present_locs = {
            (g["x"], g["y"], g["z"]) for g in current.get("ground_items", [])
            if g.get("type") == "hare"
        }
        respawn_schedule = context.setdefault("_hare_respawn_schedule", {})
        for loc in configured_locs:
            key = (loc["x"], loc["y"], loc["z"])
            if key in present_locs:
                respawn_schedule.pop(str(key), None)
                continue
            scheduled = respawn_schedule.get(str(key))
            if scheduled is None:
                respawn_schedule[str(key)] = turn + cooldown
            elif turn >= scheduled:
                current["ground_items"].append({
                    "type": "hare",
                    "x": loc["x"], "y": loc["y"], "z": loc["z"],
                    "count": 1,
                })
                respawn_schedule.pop(str(key), None)
                events.append(f"HARE RESPAWNED at ({loc['x']},{loc['y']},{loc['z']})")

    def _tick_externality_mushrooms(self, current, context, events):
        """Per-turn tick for externality_mushrooms (public-goods substrate).

        Each pickup is the cooperation/defection action:
        - selfish_mushroom: picker gains selfish_reward, no externality.
        - public_mushroom: picker gains public_reward_self, every other
          agent gains public_reward_other (positive externality).

        Mushrooms respawn at original locations mushroom_respawn_turns
        after pickup. No encounter mechanic — pickups directly accrue.
        """
        turn = current.get("turn", 1)
        s_reward = context.get("selfish_reward", 2)
        p_self = context.get("public_reward_self", 1)
        p_other = context.get("public_reward_other", 3)
        respawn_turns = context.get("mushroom_respawn_turns", 6)

        # 1. Pickup detection via inventory delta on selfish/public mushrooms.
        last_selfish = context.setdefault("_last_selfish_inventory", {})
        last_public = context.setdefault("_last_public_inventory", {})
        for aid, ag in current["agents"].items():
            inv = ag.get("inventory") or {}
            cur_s = int(inv.get("selfish_mushroom") or 0)
            cur_p = int(inv.get("public_mushroom") or 0)
            prev_s = int(last_selfish.get(aid) or 0)
            prev_p = int(last_public.get(aid) or 0)

            # Selfish pickup: only picker gains.
            if cur_s > prev_s:
                gained = cur_s - prev_s
                context["agent_selfish_picks"][aid] = (
                    context["agent_selfish_picks"].get(aid, 0) + gained
                )
                context["agent_em_score"][aid] = (
                    context["agent_em_score"].get(aid, 0) + gained * s_reward
                )
                context.setdefault("em_pickup_log", []).append({
                    "turn": turn, "agent": aid,
                    "type": "selfish", "count": gained,
                    "self_gain": gained * s_reward,
                    "externality_to_others": 0,
                })
                events.append(
                    f"{aid} picked selfish_mushroom (+{gained * s_reward} self, "
                    f"+0 others)"
                )

            # Public pickup: picker gains less + every OTHER agent gains externality.
            if cur_p > prev_p:
                gained = cur_p - prev_p
                context["agent_public_picks"][aid] = (
                    context["agent_public_picks"].get(aid, 0) + gained
                )
                context["agent_em_score"][aid] = (
                    context["agent_em_score"].get(aid, 0) + gained * p_self
                )
                others = [oid for oid in current["agents"] if oid != aid]
                ext_each = gained * p_other
                for oid in others:
                    context["agent_em_score"][oid] = (
                        context["agent_em_score"].get(oid, 0) + ext_each
                    )
                    context["agent_externality_received"][oid] = (
                        context["agent_externality_received"].get(oid, 0) + ext_each
                    )
                context.setdefault("em_pickup_log", []).append({
                    "turn": turn, "agent": aid,
                    "type": "public", "count": gained,
                    "self_gain": gained * p_self,
                    "externality_to_others": ext_each,
                })
                events.append(
                    f"{aid} picked public_mushroom (+{gained * p_self} self, "
                    f"+{ext_each} to each other agent — public good)"
                )

            # Inventory normalization: mushrooms are consumed instantly
            # at pickup (their reward IS the value, no need to carry).
            if cur_s > 0:
                ag["inventory"].pop("selfish_mushroom", None)
            if cur_p > 0:
                ag["inventory"].pop("public_mushroom", None)
            last_selfish[aid] = 0
            last_public[aid] = 0

        # 2. Respawn — track per-location pickup turn.
        for tok_type, key in (
            ("selfish_mushroom", "selfish_mushroom_locations"),
            ("public_mushroom", "public_mushroom_locations"),
        ):
            configured = self._scenario.get(key, []) or []
            if not configured:
                continue
            present = {
                (g["x"], g["y"], g["z"]) for g in current.get("ground_items", [])
                if g.get("type") == tok_type
            }
            schedule = context.setdefault(f"_{tok_type}_respawn_schedule", {})
            for loc in configured:
                k = (loc["x"], loc["y"], loc["z"])
                if k in present:
                    schedule.pop(str(k), None)
                    continue
                scheduled = schedule.get(str(k))
                if scheduled is None:
                    schedule[str(k)] = turn + respawn_turns
                elif turn >= scheduled:
                    current["ground_items"].append({
                        "type": tok_type,
                        "x": loc["x"], "y": loc["y"], "z": loc["z"], "count": 1,
                    })
                    schedule.pop(str(k), None)
                    events.append(
                        f"{tok_type} respawned at ({loc['x']},{loc['y']},{loc['z']})"
                    )

    def _tick_prisoners_dilemma(self, current, context, events):
        """Per-turn tick for prisoners_dilemma:
        1. Track coop_token / defect_token pickup deltas (used for the
           agent's implicit PD action at next encounter).
        2. Detect encounter: any pair of agents within encounter_radius
           (manhattan-3D) with cooldown elapsed since last encounter.
        3. On encounter: classify each agent's move (more coop_token in
           inventory than defect_token → C, else D, tie → C). Apply
           canonical PD payoff matrix from context. Reset both agents'
           coop/defect token inventories (consumed). Log encounter.
        4. Token respawn: tokens respawn at original locations
           token_respawn_turns turns after pickup.
        """
        turn = current.get("turn", 1)
        radius = context.get("encounter_radius", 1)
        cooldown = context.get("encounter_cooldown", 8)
        respawn_turns = context.get("token_respawn_turns", 6)
        payoff = context.get("pd_payoff", {})
        pd = current.get("pd") or {}

        # 1. Pickup tracking via inventory delta on coop_token / defect_token.
        last_coop = context.setdefault("_last_coop_inventory", {})
        last_defect = context.setdefault("_last_defect_inventory", {})
        for aid, ag in current["agents"].items():
            inv = ag.get("inventory") or {}
            cur_c = int(inv.get("coop_token") or 0)
            cur_d = int(inv.get("defect_token") or 0)
            prev_c = int(last_coop.get(aid) or 0)
            prev_d = int(last_defect.get(aid) or 0)
            if cur_c > prev_c:
                gained = cur_c - prev_c
                context["agent_coop_pickups"][aid] = (
                    context["agent_coop_pickups"].get(aid, 0) + gained
                )
                events.append(f"{aid} picked coop_token (+{gained})")
            if cur_d > prev_d:
                gained = cur_d - prev_d
                context["agent_defect_pickups"][aid] = (
                    context["agent_defect_pickups"].get(aid, 0) + gained
                )
                events.append(f"{aid} picked defect_token (+{gained})")
            last_coop[aid] = cur_c
            last_defect[aid] = cur_d

        # 2. Encounter detection (cooldown gate).
        if turn > pd.get("last_encounter_turn", -10**9) + cooldown:
            agents = current["agents"]
            aids = list(agents.keys())
            for i in range(len(aids)):
                ai = agents[aids[i]]
                for j in range(i + 1, len(aids)):
                    aj = agents[aids[j]]
                    d = (
                        abs(ai["x"] - aj["x"])
                        + abs(ai["y"] - aj["y"])
                        + abs(ai["z"] - aj["z"])
                    )
                    if d > radius:
                        continue
                    # Encounter triggered. Resolve PD.
                    move_i = self._pd_move(ai)
                    move_j = self._pd_move(aj)
                    key = move_i + move_j
                    pi, pj = payoff.get(key, [0, 0])
                    context["agent_pd_score"][aids[i]] = (
                        context["agent_pd_score"].get(aids[i], 0) + pi
                    )
                    context["agent_pd_score"][aids[j]] = (
                        context["agent_pd_score"].get(aids[j], 0) + pj
                    )
                    # Consume coop/defect tokens from inventory.
                    for ag in (ai, aj):
                        inv = ag.get("inventory") or {}
                        if "coop_token" in inv:
                            del inv["coop_token"]
                        if "defect_token" in inv:
                            del inv["defect_token"]
                    last_coop[aids[i]] = 0
                    last_coop[aids[j]] = 0
                    last_defect[aids[i]] = 0
                    last_defect[aids[j]] = 0
                    pd["last_encounter_turn"] = turn
                    pd.setdefault("encounter_log", []).append({
                        "turn": turn,
                        "pair": [aids[i], aids[j]],
                        "moves": {aids[i]: move_i, aids[j]: move_j},
                        "outcome": key,
                        "payoff": {aids[i]: pi, aids[j]: pj},
                    })
                    events.append(
                        f"PD ENCOUNTER ({aids[i]}={move_i}, {aids[j]}={move_j}) "
                        f"outcome {key} payoff {aids[i]}={pi}/{aids[j]}={pj}"
                    )
                    break  # one encounter per turn maximum
                else:
                    continue
                break

        # 3. Token respawn — track per-location pickup turn, respawn after
        #    respawn_turns. We model this via configured locations vs
        #    current ground_items for each token type.
        for tok_type, key in (("coop_token", "coop_token_locations"),
                              ("defect_token", "defect_token_locations")):
            configured = self._scenario.get(key, []) or []
            if not configured:
                continue
            present = {
                (g["x"], g["y"], g["z"]) for g in current.get("ground_items", [])
                if g.get("type") == tok_type
            }
            schedule = context.setdefault(f"_{tok_type}_respawn_schedule", {})
            for loc in configured:
                k = (loc["x"], loc["y"], loc["z"])
                if k in present:
                    schedule.pop(str(k), None)
                    continue
                scheduled = schedule.get(str(k))
                if scheduled is None:
                    schedule[str(k)] = turn + respawn_turns
                elif turn >= scheduled:
                    current["ground_items"].append({
                        "type": tok_type,
                        "x": loc["x"], "y": loc["y"], "z": loc["z"], "count": 1,
                    })
                    schedule.pop(str(k), None)
                    events.append(f"{tok_type} respawned at ({loc['x']},{loc['y']},{loc['z']})")

    def _pd_move(self, agent):
        """Classify an agent's PD action by their current token inventory.
        more coop_token > defect_token → C; defect_token > coop_token → D;
        tie (incl. zero/zero) → C. Default-cooperate convention picked to
        avoid rewarding agents who collected nothing with a defect baseline.
        """
        inv = agent.get("inventory") or {}
        c = int(inv.get("coop_token") or 0)
        d = int(inv.get("defect_token") or 0)
        if d > c:
            return "D"
        return "C"

    def _check_pure_coord_meeting(self, current, context, events):
        """Pure coordination: terminate when any pair of agents end a turn
        on the same (x,y,z) cell. First meeting wins for all participants.
        """
        meet = current.get("meet")
        if not meet or meet.get("met"):
            return
        agents = current["agents"]
        aids = list(agents.keys())
        for i in range(len(aids)):
            ai = agents[aids[i]]
            for j in range(i + 1, len(aids)):
                aj = agents[aids[j]]
                if (ai["x"], ai["y"], ai["z"]) == (aj["x"], aj["y"], aj["z"]):
                    meet["met"] = True
                    meet["at_turn"] = current.get("turn", 1)
                    meet["cell"] = [ai["x"], ai["y"], ai["z"]]
                    meet["pair"] = sorted([aids[i], aids[j]])
                    events.append(
                        f"COORDINATION SUCCESS: {meet['pair'][0]} and "
                        f"{meet['pair'][1]} met at "
                        f"({ai['x']},{ai['y']},{ai['z']}) on turn {meet['at_turn']}"
                    )
                    return

    def _check_predator_capture(self, current, context, events):
        """Mark prey captured if any predator is within capture_radius
        (manhattan-3D) of any prey at end of turn. Single-prey single-
        predator is the canonical config but multi-role is supported.
        """
        chase = current.get("chase")
        if not chase or chase.get("captured"):
            return
        roles = chase.get("roles") or {}
        predators = [aid for aid, r in roles.items() if r == "predator"]
        prey = [aid for aid, r in roles.items() if r == "prey"]
        if not predators or not prey:
            return
        radius = context.get("capture_radius", 1)
        agents = current["agents"]
        for pid in predators:
            pa = agents.get(pid)
            if not pa:
                continue
            for vid in prey:
                va = agents.get(vid)
                if not va:
                    continue
                d = (
                    abs(pa["x"] - va["x"])
                    + abs(pa["y"] - va["y"])
                    + abs(pa["z"] - va["z"])
                )
                if d <= radius:
                    chase["captured"] = True
                    chase["captured_at_turn"] = current.get("turn", 1)
                    chase["captor"] = pid
                    chase["victim"] = vid
                    events.append(
                        f"PREY CAPTURED: predator {pid} tagged prey {vid} "
                        f"(distance {d}) at turn {chase['captured_at_turn']}"
                    )
                    return

    def _tick_commons_harvest(self, current, context, events):
        """Per-turn tick for commons_harvest mode (Tragedy of the Commons).

        Reservoir model:
        - Each tree has `apples` (reservoir count, max = tree_max_apples).
        - At any time at most 1 ground apple is visible at the tree's
          position. When the reservoir > 0 and no ground apple is present,
          one apple is "released" to ground (reservoir decrements).
        - Pickups consume the ground apple via the existing pick verb.
        - Reservoir regenerates +1 every `tree_regen_turns` up to the cap.
        - A tree dies when both reservoir == 0 AND no ground apple at its
          location for `tree_depletion_turns` consecutive ticks. Dead
          trees never regenerate.
        """
        turn = current.get("turn", 1)
        trees = current.get("trees") or []
        max_apples = context.get("tree_max_apples", 3)
        regen_turns = context.get("tree_regen_turns", 4)
        depletion_turns = context.get("tree_depletion_turns", 12)
        apple_reward = context.get("apple_reward", 1)

        # 1. Apple pickup detection — agent inventory delta on "apple" key.
        last_counts = context.setdefault("_last_apple_inventory", {})
        for aid, ag in current["agents"].items():
            cur = int((ag.get("inventory") or {}).get("apple") or 0)
            prev = int(last_counts.get(aid) or 0)
            if cur > prev:
                gained = cur - prev
                context["agent_apple_count"][aid] = (
                    context["agent_apple_count"].get(aid, 0) + gained
                )
                context.setdefault("apple_pickup_log", []).append({
                    "turn": turn, "agent": aid, "count": gained,
                })
                events.append(f"{aid} picked apple (+{gained * apple_reward})")
            last_counts[aid] = cur

        # 2. Per-tree tick: reservoir release, regen, death.
        ground_apple_locs = {
            (g["x"], g["y"], g["z"])
            for g in current.get("ground_items", [])
            if g.get("type") == "apple"
        }
        for tree in trees:
            if tree.get("dead"):
                continue
            tx, ty, tz = tree["x"], tree["y"], tree["z"]
            ground_present = (tx, ty, tz) in ground_apple_locs

            # Reservoir release — drop a ground apple if reservoir > 0
            # and ground slot is currently empty.
            if tree.get("apples", 0) > 0 and not ground_present:
                current["ground_items"].append({
                    "type": "apple", "x": tx, "y": ty, "z": tz, "count": 1,
                })
                tree["apples"] = tree["apples"] - 1
                ground_present = True
                events.append(f"tree at ({tx},{ty},{tz}) released apple to ground (reservoir={tree['apples']})")

            # Regen — accumulate reservoir while below cap.
            if tree["apples"] < max_apples:
                next_t = tree.get("next_regen_turn")
                if next_t is None:
                    tree["next_regen_turn"] = turn + regen_turns
                elif turn >= next_t:
                    tree["apples"] = tree["apples"] + 1
                    if tree["apples"] >= max_apples:
                        tree["next_regen_turn"] = None
                    else:
                        tree["next_regen_turn"] = turn + regen_turns
                    events.append(f"tree at ({tx},{ty},{tz}) reservoir regen → {tree['apples']}")

            # Death tracking — empty reservoir AND empty ground for too long.
            if tree["apples"] == 0 and not ground_present:
                tree["empty_streak"] = tree.get("empty_streak", 0) + 1
                if tree["empty_streak"] >= depletion_turns:
                    tree["dead"] = True
                    tree["next_regen_turn"] = None
                    context.setdefault("tree_death_log", []).append({
                        "turn": turn, "tree": (tx, ty, tz),
                    })
                    events.append(
                        f"TREE DIED at ({tx},{ty},{tz}) (empty {tree['empty_streak']} turns)"
                    )
            else:
                tree["empty_streak"] = 0

    # ── verb implementations (mutate world + agent in place) ───────────

    def _do_move(self, world, agent, direction, events):
        dx, dy, dz = W.DIRECTIONS[direction]
        nx, ny, nz = agent["x"] + dx, agent["y"] + dy, agent["z"] + dz
        if not W.in_bounds(world, nx, ny, nz):
            events.append(f"move {direction} blocked: world edge")
            return
        dest_block = W.get_block(world, nx, ny, nz)
        # Destination must be passable (air, or a passable block like ladder).
        if dest_block not in W.PASSABLE:
            events.append(f"move {direction} blocked: {dest_block} at destination")
            return
        if direction in ("north", "south", "east", "west"):
            # Must have solid ground at or below the destination, OR the
            # destination cell itself is a ladder we can grip onto.
            below = W.get_block(world, nx, ny, nz - 1) if nz > 0 else "stone"
            on_ladder = (dest_block == "ladder")
            if below == "air" and not on_ladder:
                events.append(f"move {direction} blocked: no ground beneath destination")
                return
            agent["facing"] = direction
        agent["x"], agent["y"], agent["z"] = nx, ny, nz
        events.append(f"moved {direction} to ({nx},{ny},{nz})")

    def _do_interact(self, world, agent, direction, events):
        """Phase-1 open-world interact: ladder traversal only.
        Climb up/down when current cell or destination cell is a ladder.
        Future verbs (door open/close, chest open) will reuse this hook
        with their own affordance checks."""
        if direction not in ("up", "down"):
            events.append(f"interact {direction}: only up/down supported in v1")
            return
        nx, ny = agent["x"], agent["y"]
        dz = 1 if direction == "up" else -1
        nz = agent["z"] + dz
        if not W.in_bounds(world, nx, ny, nz):
            events.append(f"interact {direction} blocked: world edge")
            return
        dest_block = W.get_block(world, nx, ny, nz)
        here = W.get_block(world, agent["x"], agent["y"], agent["z"])
        # Allow if either current cell or destination cell is a ladder.
        if here != "ladder" and dest_block != "ladder":
            events.append(f"interact {direction}: no ladder here or above/below to climb")
            return
        if dest_block not in W.PASSABLE:
            events.append(f"interact {direction} blocked: {dest_block} at destination")
            return
        agent["x"], agent["y"], agent["z"] = nx, ny, nz
        events.append(f"climbed {direction} to ({nx},{ny},{nz})")

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
        mode = context.get("mode")
        if mode == "sandbox":
            if current["turn"] > context["turn_limit"]:
                current["phase"] = "ended"
                return True
            return False
        if mode == "encounter":
            # End as soon as any two agents are adjacent (manhattan-3D <= 1),
            # or when the turn limit is reached.
            if _any_adjacent_pair(current["agents"]):
                current["phase"] = "ended"
                return True
            if current["turn"] > context["turn_limit"]:
                current["phase"] = "ended"
                return True
            return False
        if mode == "stag_hunt":
            stag = current.get("stag") or {}
            if stag.get("captured"):
                current["phase"] = "ended"
                return True
            if current["turn"] > context["turn_limit"]:
                current["phase"] = "ended"
                return True
            return False
        if mode == "stag_hunt_repeated":
            # Repeated mode never terminates early — only on turn_limit.
            if current["turn"] > context["turn_limit"]:
                current["phase"] = "ended"
                return True
            return False
        if mode == "commons_harvest":
            # End on turn_limit OR when all trees are dead (commons collapsed).
            trees = current.get("trees") or []
            if trees and all(t.get("dead") for t in trees):
                current["phase"] = "ended"
                return True
            if current["turn"] > context["turn_limit"]:
                current["phase"] = "ended"
                return True
            return False
        if mode == "predator_prey":
            chase = current.get("chase") or {}
            if chase.get("captured"):
                current["phase"] = "ended"
                return True
            if current["turn"] > context["turn_limit"]:
                current["phase"] = "ended"
                return True
            return False
        if mode == "pure_coord":
            meet = current.get("meet") or {}
            if meet.get("met"):
                current["phase"] = "ended"
                return True
            if current["turn"] > context["turn_limit"]:
                current["phase"] = "ended"
                return True
            return False
        if mode == "prisoners_dilemma":
            # Repeated PD: only turn_limit terminates.
            if current["turn"] > context["turn_limit"]:
                current["phase"] = "ended"
                return True
            return False
        if mode == "externality_mushrooms":
            # Public-goods substrate: only turn_limit terminates.
            if current["turn"] > context["turn_limit"]:
                current["phase"] = "ended"
                return True
            return False
        if current["turn"] > context["shelter_deadline"]:
            current["phase"] = "ended"
            return True
        if current["turn"] > context["turn_limit"]:
            current["phase"] = "ended"
            return True
        return False

    def get_result(self, state: dict) -> dict:
        current = state["game"]["current"]
        context = state["game"]["context"]

        agent_id = current["turn_order"][0]
        agent = current["agents"][agent_id]
        mode = context.get("mode")

        if mode == "sandbox":
            return self._sandbox_result(state, agent_id, agent)
        if mode == "encounter":
            return self._encounter_result(state, current, context)
        if mode == "cooperate":
            return self._cooperate_result(state, current, context)
        if mode == "stag_hunt":
            return self._stag_hunt_result(state, current, context)
        if mode == "stag_hunt_repeated":
            return self._stag_hunt_repeated_result(state, current, context)
        if mode == "commons_harvest":
            return self._commons_harvest_result(state, current, context)
        if mode == "predator_prey":
            return self._predator_prey_result(state, current, context)
        if mode == "pure_coord":
            return self._pure_coord_result(state, current, context)
        if mode == "prisoners_dilemma":
            return self._prisoners_dilemma_result(state, current, context)
        if mode == "externality_mushrooms":
            return self._externality_mushrooms_result(state, current, context)

        validity = W.check_valid_shelter(
            current["world"], agent,
            min_floor=context["min_floor"],
            strict_placed=context.get("strict_placed", True),
            min_placed_boundary=context.get("min_placed_boundary"),
        )

        over_deadline = current["turn"] > context["shelter_deadline"]

        retro = _build_retrospective(current["world"], agent, validity)
        grade = _classify_behavior(validity, retro, agent)

        GRADE_SCORES = {
            "sheltered": 1.0,
            "roofless_pod": 0.7,
            "walled": 0.5,
            "partial_build": 0.3,
            "foraging": 0.1,
            "wandering": 0.0,
        }
        score = GRADE_SCORES.get(grade, 0.0)

        if validity["valid"]:
            outcome = "win"
            summary = (
                f"Sheltered. Volume={validity['volume']}, floor={validity['floor_area']}, "
                f"turn={current['turn']-1}/{context['shelter_deadline']}."
            )
        elif not over_deadline:
            outcome = "incomplete"
            summary = f"Ended before deadline: {validity['reason']}"
        else:
            outcome = "partial"
            summary = (
                f"[{grade}] Deadline reached. {validity['reason']} "
                f"(placed={retro['placed_count']}, walls={retro['walls_adjacent']}, "
                f"roof={'yes' if retro['has_roof'] else 'no'})"
            )

        scores = {agent_id: score}
        return {
            "outcome": outcome,
            "behavior_grade": grade,
            "winner": agent_id if outcome == "win" else None,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "validity": validity,
            "turns_used": current["turn"] - 1,
            "placed_blocks": retro["placed_count"],
            "retrospective": retro,
        }

    def _cooperate_result(self, state: dict, current: dict, context: dict) -> dict:
        """Cooperate mode: all agents must be inside **one** shared
        enclosed volume at the deadline. Uses a single BFS from the
        first agent and verifies every other agent's cell is in the
        returned set. Placed-boundary count threshold is honored so
        natural caves don't count as a completed shelter.
        """
        agents = current["agents"]
        agent_ids = sorted(agents.keys())
        anchor = agents[agent_ids[0]]

        from games.blockworld.world import _enclosed_air_cells, is_placed, in_bounds, get_block, DIRECTIONS

        volume = _enclosed_air_cells(
            current["world"], (anchor["x"], anchor["y"], anchor["z"]),
        )
        turn_used = current["turn"] - 1
        scores = {aid: 0.0 for aid in agents}

        # All agents inside the same enclosed set?
        in_volume = {}
        for aid, a in agents.items():
            in_volume[aid] = (
                volume is not None
                and (a["x"], a["y"], a["z"]) in volume
            )
        all_inside = volume is not None and all(in_volume.values())

        # Placed-boundary floor: reuse the scenario's min_placed_boundary
        # if set, else fall back to 1 (any contribution beyond natural cover).
        threshold = context.get("min_placed_boundary") or 1
        boundary_placed = 0
        if volume is not None:
            boundary = set()
            for (x, y, z) in volume:
                for dx, dy, dz in DIRECTIONS.values():
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if nz < 0:
                        continue
                    if (nx, ny, nz) not in volume:
                        boundary.add((nx, ny, nz))
            for (x, y, z) in boundary:
                if in_bounds(current["world"], x, y, z) and is_placed(
                    current["world"], x, y, z
                ):
                    boundary_placed += 1

        sheltered_together = (
            all_inside
            and boundary_placed >= threshold
        )

        if sheltered_together:
            outcome = "win"
            for aid in agents:
                scores[aid] = 1.0
            summary = (
                f"Cooperative shelter: all {len(agents)} agents inside one "
                f"enclosed volume of {len(volume)} cells (placed boundary "
                f"{boundary_placed}/{threshold}, turn {turn_used})."
            )
        else:
            outcome = "loss"
            reasons = []
            if volume is None:
                reasons.append("no enclosed volume from anchor")
            else:
                missing = [aid for aid, inside in in_volume.items() if not inside]
                if missing:
                    reasons.append(f"not inside: {', '.join(missing)}")
                if boundary_placed < threshold:
                    reasons.append(
                        f"placed-boundary {boundary_placed} < {threshold}"
                    )
            summary = (
                f"Cooperative shelter failed at turn {turn_used}: "
                + "; ".join(reasons or ["unknown"])
            )

        return {
            "outcome": outcome,
            "winner": None,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": turn_used,
            "volume_size": len(volume) if volume else 0,
            "boundary_placed": boundary_placed,
            "all_inside": all_inside,
            "in_volume": in_volume,
            "final_positions": {
                aid: {"x": a["x"], "y": a["y"], "z": a["z"], "facing": a["facing"]}
                for aid, a in agents.items()
            },
        }

    def _encounter_result(self, state: dict, current: dict, context: dict) -> dict:
        """Outcome for encounter mode: win if any two agents met (manhattan
        distance <= 1 on any common layer), loss otherwise. Score is 1.0
        for every agent on a successful encounter, 0.0 otherwise."""
        agents = current["agents"]
        met_pair = _first_adjacent_pair(agents)
        turn_used = current["turn"] - 1

        scores = {aid: 0.0 for aid in agents}
        if met_pair is not None:
            a_id, b_id = met_pair
            outcome = "win"
            summary = (
                f"Encounter: {a_id} and {b_id} adjacent at turn {turn_used}."
            )
            for aid in agents:
                scores[aid] = 1.0
        else:
            outcome = "loss"
            summary = (
                f"No encounter by turn limit. "
                f"Final positions: "
                + "; ".join(
                    f"{aid}@({a['x']},{a['y']},{a['z']})"
                    for aid, a in agents.items()
                )
            )

        return {
            "outcome": outcome,
            "winner": None,  # cooperative win — no single winner
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": turn_used,
            "met_pair": list(met_pair) if met_pair else None,
            "final_positions": {
                aid: {"x": a["x"], "y": a["y"], "z": a["z"], "facing": a["facing"]}
                for aid, a in agents.items()
            },
        }

    def _stag_hunt_result(self, state: dict, current: dict, context: dict) -> dict:
        """Stag-hunt scoring: per-agent payoff = stag_share + hare_count.
        Stag captured cooperatively → split stag_reward equally among
        captors. Hares are picked up via existing inventory mechanic
        (count of 'hare' items in agent's inventory).
        """
        agents = current["agents"]
        stag = current.get("stag") or {}
        stag_reward = context.get("stag_reward", 5)
        hare_reward = context.get("hare_reward", 1)
        turn_used = current["turn"] - 1

        scores = {}
        breakdown = {}
        for aid, ag in agents.items():
            inventory = ag.get("inventory") or {}
            hares = int(inventory.get("hare") or 0)
            score = hares * hare_reward
            stag_share = 0
            if stag.get("captured") and aid in (stag.get("captured_by") or []):
                captors = stag.get("captured_by") or []
                stag_share = stag_reward / max(1, len(captors))
                score += stag_share
            scores[aid] = float(score)
            breakdown[aid] = {
                "hares": hares,
                "stag_share": stag_share,
                "score": float(score),
            }

        if stag.get("captured"):
            outcome = "stag_captured"
            captors = stag.get("captured_by") or []
            summary = (
                f"Stag hunted cooperatively by {', '.join(captors)} at turn "
                f"{turn_used}. Hare totals: "
                + ", ".join(f"{aid}={b['hares']}" for aid, b in breakdown.items())
            )
        else:
            outcome = "stag_missed"
            summary = (
                f"Deadline reached without stag capture. "
                + ", ".join(f"{aid}: hares={b['hares']}" for aid, b in breakdown.items())
            )

        # Highest-score agent wins (ties → no winner).
        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        winner = None
        if len(sorted_scores) >= 2 and sorted_scores[0][1] > sorted_scores[1][1]:
            winner = sorted_scores[0][0]
        elif len(sorted_scores) == 1:
            winner = sorted_scores[0][0]

        return {
            "outcome": outcome,
            "winner": winner,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": turn_used,
            "stag_captured": stag.get("captured", False),
            "stag_captured_by": stag.get("captured_by"),
            "breakdown": breakdown,
        }

    def _stag_hunt_repeated_result(self, state: dict, current: dict, context: dict) -> dict:
        """Repeated stag-hunt scoring: cumulative across all captures + hare
        pickups during the match. Match always runs to turn_limit. Score
        per agent = total_stag_share + total_hare_count × hare_reward.
        """
        turn_used = current["turn"] - 1
        hare_reward = context.get("hare_reward", 1)
        stag_log = context.get("stag_capture_log") or []
        hare_log = context.get("hare_pickup_log") or []
        agent_stag = context.get("agent_stag_share") or {}
        agent_hare = context.get("agent_hare_count") or {}

        scores = {}
        breakdown = {}
        for aid in current["agents"]:
            stag_share = float(agent_stag.get(aid) or 0.0)
            hares = int(agent_hare.get(aid) or 0)
            score = stag_share + hares * hare_reward
            scores[aid] = score
            breakdown[aid] = {
                "stag_share_total": stag_share,
                "hares": hares,
                "score": score,
            }

        n_captures = len(stag_log)
        n_pickups = sum(p.get("count", 0) for p in hare_log)
        if n_captures == 0:
            outcome = "no_captures"
            summary = (
                f"No stag captures across {turn_used} turns. "
                + ", ".join(f"{aid}: hares={b['hares']}" for aid, b in breakdown.items())
            )
        else:
            outcome = "stag_captures"
            summary = (
                f"{n_captures} cooperative stag capture(s) + {n_pickups} hare(s) "
                f"in {turn_used} turns. "
                + ", ".join(
                    f"{aid}: stag_share={b['stag_share_total']:.1f}, hares={b['hares']}"
                    for aid, b in breakdown.items()
                )
            )

        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        winner = None
        if len(sorted_scores) >= 2 and sorted_scores[0][1] > sorted_scores[1][1]:
            winner = sorted_scores[0][0]
        elif len(sorted_scores) == 1:
            winner = sorted_scores[0][0]

        return {
            "outcome": outcome,
            "winner": winner,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": turn_used,
            "stag_captures": n_captures,
            "hare_pickups": n_pickups,
            "stag_capture_log": stag_log,
            "hare_pickup_log": hare_log,
            "breakdown": breakdown,
        }

    def _commons_harvest_result(self, state: dict, current: dict, context: dict) -> dict:
        """Commons harvest scoring + tragedy diagnosis. Score per agent =
        total apples picked × apple_reward. Outcome reflects whether the
        commons survived the match."""
        turn_used = current["turn"] - 1
        apple_reward = context.get("apple_reward", 1)
        agent_apple = context.get("agent_apple_count") or {}
        trees = current.get("trees") or []
        n_dead = sum(1 for t in trees if t.get("dead"))
        n_total = len(trees)
        scores = {aid: float((agent_apple.get(aid) or 0) * apple_reward) for aid in current["agents"]}
        breakdown = {
            aid: {
                "apples": int(agent_apple.get(aid) or 0),
                "score": scores[aid],
            }
            for aid in current["agents"]
        }
        total_picked = sum(b["apples"] for b in breakdown.values())

        if n_total == 0:
            outcome = "no_trees"
            summary = "No trees configured."
        elif n_dead == n_total:
            outcome = "tragedy_total_collapse"
            summary = (
                f"All {n_total} trees died (commons fully collapsed) by turn {turn_used}. "
                f"Total apples picked: {total_picked}. "
                + ", ".join(f"{aid}={b['apples']}" for aid, b in breakdown.items())
            )
        elif n_dead > 0:
            outcome = "tragedy_partial_collapse"
            summary = (
                f"{n_dead}/{n_total} trees died — partial collapse. "
                f"Total apples picked: {total_picked}. "
                + ", ".join(f"{aid}={b['apples']}" for aid, b in breakdown.items())
            )
        else:
            outcome = "sustainable"
            summary = (
                f"All {n_total} trees survived to turn {turn_used}. "
                f"Total apples picked: {total_picked}. "
                + ", ".join(f"{aid}={b['apples']}" for aid, b in breakdown.items())
            )

        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        winner = None
        if len(sorted_scores) >= 2 and sorted_scores[0][1] > sorted_scores[1][1]:
            winner = sorted_scores[0][0]
        elif len(sorted_scores) == 1:
            winner = sorted_scores[0][0]

        return {
            "outcome": outcome,
            "winner": winner,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": turn_used,
            "total_apples_picked": total_picked,
            "trees_dead": n_dead,
            "trees_total": n_total,
            "tree_death_log": context.get("tree_death_log") or [],
            "apple_pickup_log": context.get("apple_pickup_log") or [],
            "breakdown": breakdown,
        }

    def _predator_prey_result(self, state: dict, current: dict, context: dict) -> dict:
        """Predator-Prey scoring (asymmetric zero-sum-ish):
        - capture: predator gets capture_reward, prey gets 0.
        - escape: prey gets survival_reward, predator gets 0.
        Only one role can score per match.
        """
        chase = current.get("chase") or {}
        roles = chase.get("roles") or {}
        capture_reward = float(context.get("capture_reward", 1.0))
        survival_reward = float(context.get("survival_reward", 1.0))
        turn_used = current["turn"] - 1

        scores = {aid: 0.0 for aid in current["agents"]}
        breakdown = {
            aid: {"role": roles.get(aid, "unassigned"), "score": 0.0}
            for aid in current["agents"]
        }

        if chase.get("captured"):
            outcome = "caught"
            captor = chase.get("captor")
            victim = chase.get("victim")
            cap_turn = chase.get("captured_at_turn") or turn_used
            if captor:
                scores[captor] = capture_reward
                breakdown[captor]["score"] = capture_reward
            winner = captor
            summary = (
                f"Predator {captor} caught prey {victim} at turn {cap_turn}. "
                f"Survived {cap_turn - 1} turns before capture."
            )
        else:
            outcome = "escaped"
            prey_ids = [aid for aid, r in roles.items() if r == "prey"]
            for pid in prey_ids:
                scores[pid] = survival_reward
                breakdown[pid]["score"] = survival_reward
            winner = prey_ids[0] if len(prey_ids) == 1 else None
            summary = (
                f"Prey survived to turn_limit ({turn_used}). "
                f"Prey: {', '.join(prey_ids) or '(none)'}"
            )

        return {
            "outcome": outcome,
            "winner": winner,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": turn_used,
            "captured": chase.get("captured", False),
            "captured_at_turn": chase.get("captured_at_turn"),
            "captor": chase.get("captor"),
            "victim": chase.get("victim"),
            "roles": roles,
            "breakdown": breakdown,
        }

    def _externality_mushrooms_result(self, state: dict, current: dict, context: dict) -> dict:
        """Public-goods scoring: cumulative score = own selfish gains +
        own public_self gains + externality received from others' public
        pickups. Outcome categorizes the social pattern.
        """
        turn_used = current["turn"] - 1
        pickup_log = context.get("em_pickup_log") or []
        scores = {aid: float(context.get("agent_em_score", {}).get(aid, 0))
                  for aid in current["agents"]}
        breakdown = {
            aid: {
                "score": scores[aid],
                "selfish_picks": int(context.get("agent_selfish_picks", {}).get(aid, 0)),
                "public_picks": int(context.get("agent_public_picks", {}).get(aid, 0)),
                "externality_received": int(
                    context.get("agent_externality_received", {}).get(aid, 0)
                ),
            }
            for aid in current["agents"]
        }
        total_selfish = sum(b["selfish_picks"] for b in breakdown.values())
        total_public = sum(b["public_picks"] for b in breakdown.values())
        total_picks = total_selfish + total_public

        if total_picks == 0:
            outcome = "no_pickups"
        else:
            public_ratio = total_public / total_picks
            if public_ratio >= 0.7:
                outcome = "mostly_cooperative"
            elif public_ratio <= 0.3:
                outcome = "mostly_selfish"
            else:
                outcome = "mixed"
            # Detect exploitation pattern: large divergence in public_picks.
            picks = [b["public_picks"] for b in breakdown.values()]
            if len(picks) == 2 and max(picks) >= 2 and min(picks) == 0:
                outcome = "asymmetric_exploitation"

        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        winner = None
        if len(sorted_scores) >= 2 and sorted_scores[0][1] > sorted_scores[1][1]:
            winner = sorted_scores[0][0]

        say_attempts = dict(context.get("say_attempts") or {})
        summary = (
            f"{total_picks} mushroom pickup(s) over {turn_used} turns "
            f"({total_public} public, {total_selfish} selfish). "
            + ", ".join(f"{aid}={int(s)}" for aid, s in scores.items())
            + (f". say_attempts: {say_attempts}" if any(say_attempts.values()) else "")
        )

        return {
            "outcome": outcome,
            "winner": winner,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": turn_used,
            "total_pickups": total_picks,
            "total_public_pickups": total_public,
            "total_selfish_pickups": total_selfish,
            "em_pickup_log": pickup_log,
            "say_attempts": say_attempts,
            "breakdown": breakdown,
        }

    def _prisoners_dilemma_result(self, state: dict, current: dict, context: dict) -> dict:
        """Repeated PD scoring: cumulative across all encounters during
        the match. Score per agent = sum of payoffs across encounters.
        Outcome categorizes overall game type by encounter outcome
        distribution.
        """
        turn_used = current["turn"] - 1
        pd = current.get("pd") or {}
        log = pd.get("encounter_log") or []
        scores = {aid: float(context.get("agent_pd_score", {}).get(aid, 0))
                  for aid in current["agents"]}
        breakdown = {
            aid: {
                "score": scores[aid],
                "coop_pickups": int(context.get("agent_coop_pickups", {}).get(aid, 0)),
                "defect_pickups": int(context.get("agent_defect_pickups", {}).get(aid, 0)),
                "encounters": [
                    e for e in log if aid in (e.get("pair") or [])
                ],
            }
            for aid in current["agents"]
        }

        # Outcome counts.
        from collections import Counter
        outcome_counts = Counter(e.get("outcome") for e in log)
        n_enc = len(log)
        if n_enc == 0:
            top_label = "no_encounters"
        else:
            cc = outcome_counts.get("CC", 0)
            dd = outcome_counts.get("DD", 0)
            cd_dc = outcome_counts.get("CD", 0) + outcome_counts.get("DC", 0)
            if cc > dd and cc > cd_dc:
                top_label = "mostly_cooperative"
            elif dd > cc and dd > cd_dc:
                top_label = "mostly_defection"
            elif cd_dc > cc and cd_dc > dd:
                top_label = "mostly_exploitation"
            else:
                top_label = "mixed"

        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        winner = None
        if len(sorted_scores) >= 2 and sorted_scores[0][1] > sorted_scores[1][1]:
            winner = sorted_scores[0][0]

        say_attempts = dict(context.get("say_attempts") or {})
        summary = (
            f"{n_enc} encounter(s) over {turn_used} turns. "
            f"Outcome dist: {dict(outcome_counts)}. "
            + ", ".join(f"{aid}={int(s)}" for aid, s in scores.items())
            + (f". say_attempts: {say_attempts}" if any(say_attempts.values()) else "")
        )

        return {
            "outcome": top_label,
            "winner": winner,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": turn_used,
            "encounters": n_enc,
            "outcome_counts": dict(outcome_counts),
            "encounter_log": log,
            "say_attempts": say_attempts,
            "breakdown": breakdown,
        }

    def _pure_coord_result(self, state: dict, current: dict, context: dict) -> dict:
        """Pure coordination scoring: joint reward — both agents get
        meeting_reward on success, both get 0 on miss. Outcome reflects
        whether the meeting happened and which cell was selected.
        """
        meet = current.get("meet") or {}
        landmarks = context.get("landmarks") or []
        say_attempts = context.get("say_attempts") or {}
        meeting_reward = float(context.get("meeting_reward", 1.0))
        turn_used = current["turn"] - 1

        if meet.get("met"):
            cell = meet.get("cell") or [None, None, None]
            # Tag the chosen cell against the named landmark list (manhattan-3D
            # distance 0 ⇔ exact landmark; otherwise label with closest by
            # manhattan-3D distance, or "(blank cell)" if no landmarks defined).
            chosen_landmark = None
            min_d = None
            for lm in landmarks:
                d = (
                    abs(lm["x"] - cell[0])
                    + abs(lm["y"] - cell[1])
                    + abs(lm["z"] - cell[2])
                )
                if min_d is None or d < min_d:
                    min_d = d
                    chosen_landmark = lm
            on_landmark = (chosen_landmark is not None and min_d == 0)
            scores = {aid: meeting_reward for aid in current["agents"]}
            outcome = "met"
            if on_landmark:
                summary = (
                    f"Coordinated meeting at landmark '{chosen_landmark['name']}' "
                    f"({cell[0]},{cell[1]},{cell[2]}) on turn {meet.get('at_turn')}. "
                    f"say attempts: {dict(say_attempts)}"
                )
            else:
                lm_name = chosen_landmark["name"] if chosen_landmark else "(no landmarks)"
                summary = (
                    f"Coordinated meeting at non-landmark cell ({cell[0]},{cell[1]},{cell[2]}) "
                    f"on turn {meet.get('at_turn')} (closest landmark: '{lm_name}', "
                    f"distance {min_d}). say attempts: {dict(say_attempts)}"
                )
        else:
            scores = {aid: 0.0 for aid in current["agents"]}
            outcome = "missed"
            on_landmark = False
            chosen_landmark = None
            summary = (
                f"No meeting in {turn_used} turns. say attempts: {dict(say_attempts)}"
            )

        return {
            "outcome": outcome,
            "winner": None,
            "scores": scores,
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": turn_used,
            "met": meet.get("met", False),
            "meeting_turn": meet.get("at_turn"),
            "meeting_cell": meet.get("cell"),
            "meeting_pair": meet.get("pair"),
            "on_landmark": on_landmark,
            "chosen_landmark": chosen_landmark,
            "landmarks": landmarks,
            "say_attempts": dict(say_attempts),
        }

    def _sandbox_result(self, state: dict, agent_id: str, agent: dict) -> dict:
        """Observation-only outcome for sandbox mode. No win/loss."""
        current = state["game"]["current"]
        context = state["game"]["context"]
        retro = _build_retrospective(current["world"], agent, validity={})

        start = _start_for(context, agent_id)
        dist = abs(agent["x"] - start["x"]) + abs(agent["y"] - start["y"]) + abs(agent["z"] - start["z"])
        block_types_touched = {p["block"] for p in retro["placed_positions"]} | set(retro["final_inventory"].keys())

        summary = (
            f"[sandbox] placed={retro['placed_count']} "
            f"distance={dist} "
            f"block_types={sorted(block_types_touched) or '[]'} "
            f"inventory={retro['final_inventory'] or '{}'}"
        )

        return {
            "outcome": "observation",
            "winner": None,
            "scores": {agent_id: 0.0},
            "summary": summary,
            "scenario_id": context["scenario_id"],
            "turns_used": current["turn"] - 1,
            "placed_blocks": retro["placed_count"],
            "distance_from_start": dist,
            "block_types_touched": sorted(block_types_touched),
            "retrospective": retro,
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
        mode = context.get("mode", "shelter")
        if mode in ("sandbox", "encounter", "stag_hunt", "stag_hunt_repeated", "commons_harvest", "predator_prey", "pure_coord", "prisoners_dilemma", "externality_mushrooms"):
            deadline = context["turn_limit"]
        else:
            deadline = context["shelter_deadline"]
        turns_left = max(0, deadline - current["turn"] + 1)

        inv_str = ", ".join(f"{k}={v}" for k, v in sorted(agent["inventory"].items())) or "(empty)"
        inv_count = _inventory_count(agent)

        others = [
            other for other_id, other in current["agents"].items()
            if other_id != agent_id
        ]
        view = W.render_local_view(
            current["world"], agent,
            radius=DEFAULT_VIEW_RADIUS,
            others=others,
        )

        # Recent events. In pure_coord mode the partner's `say` messages
        # are not transmitted (silent Schelling) — drop other agents' say
        # entries from the visible event tail. The agent still sees their
        # own says (echoed in their own action history).
        events = current.get("last_events", [])
        if mode == "pure_coord" and context.get("say_filtered", True):
            events = [
                e for e in events
                if not any(
                    e.startswith(f"{oid} says:")
                    for oid in current["agents"] if oid != agent_id
                )
            ]
        events_str = "\n".join(f"  - {e}" for e in events[-5:]) if events else "  (none yet)"

        # Ground items nearby.
        nearby_items = []
        for g in current.get("ground_items", []):
            dx = abs(g["x"] - agent["x"])
            dy = abs(g["y"] - agent["y"])
            if g["z"] == agent["z"] and dx <= DEFAULT_VIEW_RADIUS and dy <= DEFAULT_VIEW_RADIUS:
                nearby_items.append(f"{g['type']}×{g['count']} at ({g['x']},{g['y']})")
        items_str = "; ".join(nearby_items) if nearby_items else "(none in view)"

        # Other agents. List those within DEFAULT_VIEW_RADIUS manhattan-XY
        # (ignoring z for detection, since voxel layer is small). Agents
        # outside the local view are disclosed only as "off-screen".
        other_agents = []
        off_screen = []
        for other_id, other in current["agents"].items():
            if other_id == agent_id:
                continue
            dx = abs(other["x"] - agent["x"])
            dy = abs(other["y"] - agent["y"])
            if dx <= DEFAULT_VIEW_RADIUS and dy <= DEFAULT_VIEW_RADIUS:
                other_agents.append(
                    f"{other_id} at ({other['x']},{other['y']},{other['z']}) facing {other['facing']}"
                )
            else:
                off_screen.append(other_id)
        if other_agents:
            agents_str = "; ".join(other_agents)
        elif off_screen:
            agents_str = f"(none in view; off-screen: {', '.join(off_screen)})"
        else:
            agents_str = "(alone)"

        scene_summary = self._scenario.get("description", "")

        # Stag-hunt-specific situation block: stag location + status,
        # hare count remaining, payoff structure.
        stag_block = ""
        if mode in ("stag_hunt", "stag_hunt_repeated"):
            stag = current.get("stag") or {}
            sx, sy, sz = stag.get("x"), stag.get("y"), stag.get("z")
            stag_status = "captured (respawning)" if stag.get("captured") else "alive"
            stag_reward = context.get("stag_reward", 5)
            hare_reward = context.get("hare_reward", 1)
            hares_remaining = sum(
                1 for g in current.get("ground_items", []) if g.get("type") == "hare"
            )
            stag_block = (
                f"\n=== Stag Hunt ==="
                f"\nStag: ({sx}, {sy}, {sz}) — {stag_status}. Reward {stag_reward} split among captors;"
                f" requires both agents adjacent simultaneously."
                f"\nHares on ground: {hares_remaining}. Reward {hare_reward} per hare via 'pick' verb when on ground item."
            )
            if mode == "stag_hunt_repeated":
                respawn_t = stag.get("respawn_at_turn")
                cap_log = context.get("stag_capture_log") or []
                pickup_log = context.get("hare_pickup_log") or []
                my_score = (
                    (context.get("agent_stag_share") or {}).get(agent_id, 0.0)
                    + (context.get("agent_hare_count") or {}).get(agent_id, 0) * hare_reward
                )
                stag_block += (
                    f"\n[Repeated mode] match runs to turn {context['turn_limit']} regardless of capture."
                    f" Stag respawns {context.get('stag_respawn_turns', 5)} turns after capture; hares respawn {context.get('hare_respawn_turns', 8)} turns after pickup."
                    f"\nCumulative so far — stag captures: {len(cap_log)}, hare pickups: {sum(p.get('count', 0) for p in pickup_log)}, your score: {my_score:.1f}"
                )
                if stag.get("captured") and respawn_t is not None:
                    stag_block += f"\nStag respawn turn: {respawn_t}"

        chase_block = ""
        if mode == "predator_prey":
            chase = current.get("chase") or {}
            roles = chase.get("roles") or {}
            my_role = roles.get(agent_id, "unassigned")
            radius = context.get("capture_radius", 1)
            cap_r = context.get("capture_reward", 1.0)
            surv_r = context.get("survival_reward", 1.0)
            opponent_lines = []
            for oid, ostate in current["agents"].items():
                if oid == agent_id:
                    continue
                orole = roles.get(oid, "unassigned")
                d = (
                    abs(ostate["x"] - agent["x"])
                    + abs(ostate["y"] - agent["y"])
                    + abs(ostate["z"] - agent["z"])
                )
                opponent_lines.append(
                    f"  {oid} ({orole}) at ({ostate['x']},{ostate['y']},{ostate['z']}) "
                    f"facing {ostate['facing']} — distance {d}"
                )
            chase_block = (
                f"\n=== Predator-Prey ==="
                f"\nYour role: {my_role.upper()}"
                f"\nOpponents (full visibility — both roles see each other regardless of view radius):\n"
                + ("\n".join(opponent_lines) if opponent_lines else "  (none)")
                + f"\nCapture rule: predator wins immediately if predator-prey "
                  f"manhattan-3D distance ≤ {radius} at end of any turn."
                f"\nPayoff — predator: {cap_r} on capture / 0 on escape; "
                f"prey: {surv_r} on survival / 0 on capture."
                f"\nMatch ends on capture OR turn_limit (whichever first)."
            )
            stag_block += chase_block

        coord_block = ""
        if mode == "pure_coord":
            landmarks = context.get("landmarks") or []
            meeting_reward = context.get("meeting_reward", 1.0)
            lm_lines = []
            for lm in landmarks:
                d = (
                    abs(lm["x"] - agent["x"])
                    + abs(lm["y"] - agent["y"])
                    + abs(lm["z"] - agent["z"])
                )
                lm_lines.append(
                    f"  '{lm['name']}' at ({lm['x']},{lm['y']},{lm['z']}) — your distance {d}"
                )
            opponent_lines = []
            for oid, ostate in current["agents"].items():
                if oid == agent_id:
                    continue
                d = (
                    abs(ostate["x"] - agent["x"])
                    + abs(ostate["y"] - agent["y"])
                    + abs(ostate["z"] - agent["z"])
                )
                opponent_lines.append(
                    f"  {oid} at ({ostate['x']},{ostate['y']},{ostate['z']}) "
                    f"facing {ostate['facing']} — distance {d}"
                )
            say_filtered = context.get("say_filtered", True)
            comm_text = (
                "this world is SILENT — your `say` messages are NOT "
                "transmitted to your partner (they will not see what you say). You must "
                "independently infer where to converge using shared context: visible "
                "landmarks, opponent position, and any natural focal point you both can "
                "reason about."
            ) if say_filtered else (
                "the `say` verb IS transmitted to your partner — both agents see each "
                "other's say messages in their event tail. You may negotiate verbally to "
                "agree on a meeting cell, or stay silent. Both options are permitted."
            )
            coord_block = (
                f"\n=== Pure Coordination ==="
                f"\nGoal: end any turn on the SAME (x,y,z) cell as your partner."
                f"\nReward: +{meeting_reward} to BOTH agents on success; 0 to both on miss."
                f"\nCommunication: {comm_text}"
                f"\nLandmarks (advertised to BOTH agents — these are candidate focal points):\n"
                + ("\n".join(lm_lines) if lm_lines else "  (none defined)")
                + f"\nPartner location (full visibility):\n"
                + ("\n".join(opponent_lines) if opponent_lines else "  (none)")
                + f"\nMatch ends on first meeting OR turn_limit (whichever first)."
            )
            stag_block += coord_block

        pd_block = ""
        if mode == "prisoners_dilemma":
            pd = current.get("pd") or {}
            payoff = context.get("pd_payoff") or {}
            radius = context.get("encounter_radius", 1)
            cooldown = context.get("encounter_cooldown", 8)
            log = pd.get("encounter_log") or []
            last_enc = pd.get("last_encounter_turn", -10**9)
            turns_until_next_enc = max(0, last_enc + cooldown - current.get("turn", 1) + 1)
            inv = agent.get("inventory") or {}
            my_c = int(inv.get("coop_token") or 0)
            my_d = int(inv.get("defect_token") or 0)
            my_move = "C" if my_c >= my_d else "D"
            opponent_lines = []
            for oid, ostate in current["agents"].items():
                if oid == agent_id:
                    continue
                oinv = ostate.get("inventory") or {}
                oc = int(oinv.get("coop_token") or 0)
                od = int(oinv.get("defect_token") or 0)
                d = (
                    abs(ostate["x"] - agent["x"])
                    + abs(ostate["y"] - agent["y"])
                    + abs(ostate["z"] - agent["z"])
                )
                opponent_lines.append(
                    f"  {oid} at ({ostate['x']},{ostate['y']},{ostate['z']}) "
                    f"distance {d}, inventory coop={oc} defect={od}"
                )
            recent = log[-3:]
            recent_str = "\n".join(
                f"  T{e['turn']}: {e['outcome']} → {e['payoff']}" for e in recent
            ) if recent else "  (none yet)"
            cumulative = context.get("agent_pd_score") or {}
            my_score = cumulative.get(agent_id, 0)
            payoff_str = (
                f"CC={payoff.get('CC')}  CD={payoff.get('CD')}  "
                f"DC={payoff.get('DC')}  DD={payoff.get('DD')}"
            )
            pd_block = (
                f"\n=== Prisoner's Dilemma in the Matrix ==="
                f"\nGoal: maximize cumulative payoff across repeated encounters."
                f"\nMechanic: walk the grid collecting coop_tokens and defect_tokens. "
                f"When any two agents end a turn within manhattan-3D ≤ {radius} of "
                f"each other (and ≥ {cooldown} turns since the last encounter), an "
                f"encounter triggers. Each agent's PD move is determined by their "
                f"current inventory at that moment: more coop_tokens → COOPERATE (C); "
                f"more defect_tokens → DEFECT (D); tie → C. Both agents' coop_token "
                f"and defect_token inventories are then consumed. Tokens respawn "
                f"{context.get('token_respawn_turns', 6)} turns after pickup."
                f"\nPayoff matrix [self, opponent]: {payoff_str}"
                f"\nYour current inventory: coop_token={my_c}, defect_token={my_d} "
                f"→ your PD move would be **{my_move}** if encounter happens now."
                f"\nYour cumulative PD score: {my_score}"
                f"\nOpponents:\n"
                + ("\n".join(opponent_lines) if opponent_lines else "  (none)")
                + f"\nNext encounter possible in: {turns_until_next_enc} turn(s)"
                + f"\nLast 3 encounters:\n{recent_str}"
            )
            stag_block += pd_block

        em_block = ""
        if mode == "externality_mushrooms":
            s_reward = context.get("selfish_reward", 2)
            p_self = context.get("public_reward_self", 1)
            p_other = context.get("public_reward_other", 3)
            respawn = context.get("mushroom_respawn_turns", 6)
            em_score = context.get("agent_em_score") or {}
            ext_recv = context.get("agent_externality_received") or {}
            my_score = em_score.get(agent_id, 0)
            my_ext = ext_recv.get(agent_id, 0)

            ground = current.get("ground_items") or []
            selfish_locs = [
                (g["x"], g["y"], g["z"]) for g in ground
                if g.get("type") == "selfish_mushroom"
            ]
            public_locs = [
                (g["x"], g["y"], g["z"]) for g in ground
                if g.get("type") == "public_mushroom"
            ]
            log = context.get("em_pickup_log") or []
            recent = log[-3:]
            recent_str = "\n".join(
                f"  T{e['turn']} {e['agent']} picked {e['type']}_mushroom "
                f"(self+{e['self_gain']}, others+{e['externality_to_others']})"
                for e in recent
            ) if recent else "  (none yet)"
            opponent_lines = []
            for oid, ostate in current["agents"].items():
                if oid == agent_id:
                    continue
                opponent_lines.append(
                    f"  {oid} at ({ostate['x']},{ostate['y']},{ostate['z']}) — "
                    f"score {em_score.get(oid, 0)}"
                )
            n = len(current["agents"])
            em_block = (
                f"\n=== Externality Mushrooms ==="
                f"\nGoal: maximize cumulative score across {context['turn_limit']} turns."
                f"\nMushroom mechanics:"
                f"\n  - selfish_mushroom: pickup → +{s_reward} to picker only, +0 to others."
                f"\n  - public_mushroom: pickup → +{p_self} to picker, **+{p_other} to "
                f"each other agent** (positive externality)."
                f"\nMushrooms respawn {respawn} turns after pickup. The 'pick' verb "
                f"collects whichever mushroom you're standing on (instantly consumed; "
                f"no inventory carry)."
                f"\nPD-equivalent payoff per round-trip per agent (with {n - 1} partner(s)):"
                f"\n  (D, C) selfish vs cooperative partner: T = {s_reward + p_other} (you defect, partner cooperates → you get selfish_self + their externality)"
                f"\n  (C, C) both cooperative: R = {p_self + p_other} per agent"
                f"\n  (D, D) both selfish: P = {s_reward} per agent"
                f"\n  (C, D) cooperative vs selfish: S = {p_self} (you cooperate, partner defects → only your selfish-picker miss)"
                f"\n  Pareto-optimal social total: 2×R = {2 * (p_self + p_other)}; mutual-defect total: 2×P = {2 * s_reward}."
                f"\nSelfish mushroom locations on ground: {selfish_locs if selfish_locs else '(all picked, awaiting respawn)'}"
                f"\nPublic mushroom locations on ground: {public_locs if public_locs else '(all picked, awaiting respawn)'}"
                f"\nYour cumulative score: {my_score} (of which {my_ext} came from "
                f"externality from partners' public pickups)"
                f"\nOther agents:\n"
                + ("\n".join(opponent_lines) if opponent_lines else "  (none)")
                + f"\nLast 3 pickups:\n{recent_str}"
            )
            stag_block += em_block

        commons_block = ""
        if mode == "commons_harvest":
            trees = current.get("trees") or []
            apple_reward = context.get("apple_reward", 1)
            max_apples = context.get("tree_max_apples", 3)
            tree_lines = []
            for tree in trees:
                tx, ty, tz = tree["x"], tree["y"], tree["z"]
                if tree.get("dead"):
                    tree_lines.append(f"  ({tx},{ty},{tz}): DEAD")
                else:
                    next_t = tree.get("next_regen_turn")
                    regen_str = f"regen→turn {next_t}" if next_t else "full"
                    tree_lines.append(
                        f"  ({tx},{ty},{tz}): reservoir {tree['apples']}/{max_apples}, empty_streak={tree.get('empty_streak', 0)}, {regen_str}"
                    )
            n_dead = sum(1 for t in trees if t.get("dead"))
            my_apples = (context.get("agent_apple_count") or {}).get(agent_id, 0)
            commons_block = (
                f"\n=== Commons Harvest ==="
                f"\nTrees ({len(trees) - n_dead} alive, {n_dead} dead):\n"
                + "\n".join(tree_lines)
                + f"\nMy apples picked: {my_apples} (×{apple_reward}). "
                + f"Tree depletion threshold: {context.get('tree_depletion_turns', 12)} empty turns."
                + " Match runs to turn_limit OR until all trees dead."
            )
            stag_block += commons_block

        return f"""[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}
Blockworld scenario: {context['scenario_title']}

Setting: {scene_summary}

Goal: {context['goal']}
{'Session ends' if context.get('mode') in ('sandbox', 'encounter', 'stag_hunt', 'predator_prey', 'pure_coord', 'prisoners_dilemma', 'externality_mushrooms') else 'Deadline'}: turn {deadline} (turns remaining: {turns_left}){stag_block}

=== Your state ===
Position: ({agent['x']}, {agent['y']}, {agent['z']}) facing {agent['facing']}
Inventory ({inv_count}/{INVENTORY_CAP}): {inv_str}
Ground items nearby: {items_str}
Other agents: {agents_str}

=== Local view ===
{view}

=== Recent events ===
{events_str}

=== Action schema ===
Your response MUST include exactly one JSON action object of the form below. `"type":"action"` is required on every action.

  {{"type":"action","verb":"move","direction":"north|south|east|west|up|down"}}
  {{"type":"action","verb":"break","direction":"..."}}
  {{"type":"action","verb":"place","direction":"...","block":"wood|stone|dirt|sand|iron_ore|glass|ladder"}}
  {{"type":"action","verb":"craft","recipe":"glass_pane"}}
  {{"type":"action","verb":"pick"}}
  {{"type":"action","verb":"drop","item":"..."}}
  {{"type":"action","verb":"look"}}
  {{"type":"action","verb":"say","message":"..."}}
  {{"type":"action","verb":"wait"}}
  {{"type":"action","verb":"interact","direction":"up|down"}}

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


def _start_for(context: dict, agent_id: str) -> dict:
    """Return the scenario-declared start position for a given agent_id,
    falling back to the first positional entry in agent_starts, then to
    agent_start. Used by outcome code that reports "distance from
    start" without hardcoding single-agent assumptions."""
    starts = context.get("agent_starts")
    if starts:
        for s in starts:
            if s.get("agent_id") == agent_id:
                return s
        return starts[0]
    shared = context.get("agent_start")
    if shared is not None:
        return shared
    return {"x": 0, "y": 0, "z": 0}


def _first_adjacent_pair(agents: dict) -> tuple[str, str] | None:
    """Return (a_id, b_id) for the first pair of agents whose manhattan
    3D distance is <= 1 (same cell or 6-neighbor). Order-stable: the
    smaller agent_id comes first. Returns None if no pair is adjacent."""
    ids = sorted(agents.keys())
    for i, a_id in enumerate(ids):
        a = agents[a_id]
        for b_id in ids[i + 1:]:
            b = agents[b_id]
            dist = abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]) + abs(a["z"] - b["z"])
            if dist <= 1:
                return (a_id, b_id)
    return None


def _any_adjacent_pair(agents: dict) -> bool:
    return _first_adjacent_pair(agents) is not None


def _placed_positions(world: dict) -> list[dict]:
    """Return list of {x,y,z,block} for every cell flagged placed-by-agent."""
    out = []
    placed = world["placed"]
    for z, layer in enumerate(placed):
        for y, row in enumerate(layer):
            for x, mark in enumerate(row):
                if mark:
                    out.append({"x": x, "y": y, "z": z, "block": W.get_block(world, x, y, z)})
    return out


def _build_retrospective(world: dict, agent: dict, validity: dict) -> dict:
    """Snapshot the final structure around the agent for post-match review."""
    ax, ay, az = agent["x"], agent["y"], agent["z"]
    placed_list = _placed_positions(world)
    placed_count = len(placed_list)

    walls_adjacent = 0
    for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]:
        nx, ny = ax + dx, ay + dy
        if W.in_bounds(world, nx, ny, az) and W.is_placed(world, nx, ny, az):
            walls_adjacent += 1

    has_roof = (
        W.in_bounds(world, ax, ay, az + 1)
        and W.is_placed(world, ax, ay, az + 1)
    )

    # ASCII snapshot of a 7×7 region at each z-layer around agent.
    snapshot = _render_retrospective_ascii(world, agent)

    return {
        "placed_count": placed_count,
        "placed_positions": placed_list,
        "walls_adjacent": walls_adjacent,
        "has_roof": has_roof,
        "enclosed_volume": validity.get("volume", 0),
        "agent_final_pos": {"x": ax, "y": ay, "z": az, "facing": agent["facing"]},
        "final_inventory": dict(agent["inventory"]),
        "snapshot": snapshot,
    }


def _render_retrospective_ascii(world: dict, agent: dict, radius: int = 4) -> str:
    """Stacked layer view centered on agent, marking placed cells vs natural."""
    ax, ay, az = agent["x"], agent["y"], agent["z"]
    dims = world["dimensions"]
    lines = []
    for z in reversed(range(dims["z"])):
        tag = "agent layer" if z == az else ("roof layer" if z == az + 1 else ("floor layer" if z == az - 1 else f"z={z}"))
        lines.append(f"-- z={z} ({tag}) --")
        for dy in range(-radius, radius + 1):
            row = ""
            for dx in range(-radius, radius + 1):
                x, y = ax + dx, ay + dy
                if not (0 <= x < dims["x"] and 0 <= y < dims["y"]):
                    row += "? "
                    continue
                if dx == 0 and dy == 0 and z == az:
                    row += "A "
                    continue
                name = W.get_block(world, x, y, z)
                if name == "air":
                    row += ". "
                elif W.is_placed(world, x, y, z):
                    row += name[0].upper() + " "
                else:
                    row += name[0].lower() + " "
            lines.append(row.rstrip())
        lines.append("")
    return "\n".join(lines)


def _classify_behavior(validity: dict, retro: dict, agent: dict) -> str:
    """Soft-grade the creature's end-state on a spectrum.

    sheltered    → fully enclosed by the deadline
    roofless_pod → 3+ walls and (has roof or 4 walls) but not enclosed
    walled       → 2+ adjacent walls, not yet a pod
    partial_build→ placed >= 3 blocks somewhere
    foraging     → no building but harvested materials
    wandering    → no building, no materials
    """
    if validity.get("valid"):
        return "sheltered"
    walls = retro["walls_adjacent"]
    roof = retro["has_roof"]
    placed = retro["placed_count"]
    inv = sum(agent["inventory"].values())

    if walls >= 3 and (roof or walls == 4):
        return "roofless_pod"
    if walls >= 2:
        return "walled"
    if placed >= 3:
        return "partial_build"
    if inv > 0 or placed > 0:
        return "foraging"
    return "wandering"
