"""Agora-12 — N-agent social-survival field (LxM port of JJ's agora-12).

Source: github.com/JihoonJeong/agora-12 (AI Ludens Stage 1). The original's
mechanics modules (actions/agent/market/crisis/influence/whisper) are ported
faithfully; its own simulation loop / LLM adapters are replaced by the LxM
orchestrator. Faithful constants: energy 100 start / 200 cap, decay 5 +
floor(round/10)*0.5 (+5 during a crisis), trade +4 in the market, support +2E/+1I
(elder x1.5 energy; crisis bonus +1E/+2I), whisper leak 15% base, market pool 25
per round (2 to non-traders present, rest proportional to trades), crises after
60% of the match at p=0.1 (seeded, independent RNG).

v1 scope notes (documented deviations):
- Agents act in the fixed LxM turn order (original shuffled per epoch).
- Personas are NOT baked in — LxM shells are the persona mechanism.
- Architect/treasury governance (tax setting, elections) deferred to v2; trades
  are untaxed.
- Observer's +35% whisper-notice bonus is dropped with personas; flat 15%.

Determinism: all randomness (crisis schedule, whisper leaks) derives from
`random.Random(f"{seed}:{round}:{purpose}")` — nothing stateful in the state
dict, everything JSON-serializable (the diplomacy lesson).

Dead agents are skipped in-place (never become active → no brain calls); the
round ends when the last living agent has acted: decay → deaths → market pool →
crisis check → next round.
"""

from __future__ import annotations

import random
from pathlib import Path

from lxm.engine import LxMGame

SPACES = ("plaza", "market", "alley_a", "alley_b", "alley_c")

# action -> (energy cost, allowed locations or None=anywhere)
ACTIONS = {
    "speak":   (2, None),                 # plaza/alley gate handled in resolution
    "trade":   (2, ("market",)),
    "support": (1, None),
    "whisper": (1, ("alley_a", "alley_b", "alley_c")),
    "move":    (0, None),
    "rest":    (0, None),
}

TIERS = [  # (min_influence, name)
    (10, "elder"), (5, "notable"), (0, "commoner"),
]

SCENARIOS = {
    "survival": {          # faithful classic
        "rounds": 50, "initial_energy": 100, "max_energy": 200,
        "base_decay": 5, "decay_accel": 0.5, "crisis_start_frac": 0.6,
        "crisis_prob": 0.10, "crisis_extra_decay": 5,
        "market_pool": 25, "min_presence_reward": 2,
        "whisper_leak": 0.15, "seed": 12,
    },
    "survival_blitz": {    # quick/cheap demo config
        "rounds": 20, "initial_energy": 60, "max_energy": 120,
        "base_decay": 5, "decay_accel": 0.5, "crisis_start_frac": 0.5,
        "crisis_prob": 0.15, "crisis_extra_decay": 5,
        "market_pool": 25, "min_presence_reward": 2,
        "whisper_leak": 0.15, "seed": 12,
    },
}

CRISES = {
    "drought": "Drought — resources drain fast this round.",
    "plague":  "Plague — every activity is dangerous.",
    "famine":  "Famine — many are starving.",
}


def _tier(influence: int) -> str:
    for m, name in TIERS:
        if influence >= m:
            return name
    return "commoner"


class Agora12Game(LxMGame):
    """Social survival in a five-space agora: last ones standing win."""

    min_players = 3
    max_players = 12
    accepts_capabilities = ["json_emit"]

    def __init__(self, scenario_id: str = "survival"):
        if scenario_id not in SCENARIOS:
            raise ValueError(f"unknown agora12 scenario: {scenario_id!r} (have: {sorted(SCENARIOS)})")
        self._scenario_id = scenario_id
        self._cfg = dict(SCENARIOS[scenario_id])

    # ── lifecycle ────────────────────────────────────────────────────────────

    def get_rules(self) -> str:
        p = Path(__file__).parent / "rules.md"
        return p.read_text(encoding="utf-8") if p.exists() else "Agora-12 social survival."

    def initial_state(self, agents: list[dict]) -> dict:
        cfg = self._cfg
        ids = [a["agent_id"] for a in agents]
        current = {
            "phase": "playing",
            "turn": 1,
            "round": 1,
            "turn_order": ids,
            "active_index": 0,
            "acted_this_round": [],
            "agents": {
                aid: {"agent_id": aid, "energy": cfg["initial_energy"], "influence": 0,
                      "location": "plaza", "alive": True, "death_round": None,
                      "inbox": [], "suspicions": []}
                for aid in ids
            },
            "messages": {s: [] for s in SPACES},   # this round's public speech per space
            "billboard": None,                       # {"text", "expires_round"}
            "trades_this_round": {},                 # aid -> count
            "crisis": None,                          # {"name", "until_round"}
            "last_events": [],
            "over": False,
        }
        context = {
            "scenario_id": self._scenario_id,
            "title": "Agora-12",
            "goal": f"Survive all {cfg['rounds']} rounds. Energy 0 = death. "
                    f"Highest energy+influence among survivors wins.",
            "rounds": cfg["rounds"],
            **{k: cfg[k] for k in ("initial_energy", "max_energy", "base_decay", "decay_accel",
                                    "crisis_prob", "crisis_extra_decay", "market_pool",
                                    "min_presence_reward", "whisper_leak", "seed")},
            "crisis_start_round": int(cfg["rounds"] * cfg["crisis_start_frac"]),
        }
        return {"current": current, "context": context}

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _rng(context: dict, current: dict, purpose: str) -> random.Random:
        return random.Random(f"{context['seed']}:{current['round']}:{purpose}")

    @staticmethod
    def _alive(current: dict) -> list[str]:
        return [a for a in current["turn_order"] if current["agents"][a]["alive"]]

    @staticmethod
    def _at(current: dict, loc: str) -> list[str]:
        return [a for a, d in current["agents"].items() if d["alive"] and d["location"] == loc]

    def _resolve_agent(self, current: dict, name: str) -> str | None:
        key = (name or "").strip().lower()
        if not key:
            return None
        for aid in current["turn_order"]:
            if aid.lower() == key:
                return aid
        for aid in current["turn_order"]:
            if key in aid.lower():
                return aid
        return None

    # ── validation (schema only; preconditions no-op in apply) ───────────────

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        if move.get("type") not in (None, "action"):
            return {"valid": False, "message": "move.type must be 'action'"}
        verb = move.get("verb")
        if verb not in ACTIONS:
            return {"valid": False, "message": f"unknown verb: {verb!r} (valid: {sorted(ACTIONS)})"}
        if verb == "speak" and not (move.get("message") or "").strip():
            return {"valid": False, "message": "speak requires 'message'"}
        if verb == "support" and not move.get("target"):
            return {"valid": False, "message": "support requires 'target'"}
        if verb == "whisper" and not (move.get("target") and (move.get("message") or "").strip()):
            return {"valid": False, "message": "whisper requires 'target' and 'message'"}
        if verb == "move" and move.get("location") not in SPACES:
            return {"valid": False, "message": f"move requires 'location' in {list(SPACES)}"}
        return {"valid": True, "message": None}

    # ── apply ─────────────────────────────────────────────────────────────────

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current, context = game["current"], game["context"]
        events: list[str] = []
        me = current["agents"][agent_id]

        if me["alive"]:
            self._do_action(current, context, agent_id, move, events)
            current["acted_this_round"].append(agent_id)

        # round end: every living agent (as of their turn) has acted
        if set(self._alive(current)) <= set(current["acted_this_round"]):
            self._end_round(current, context, events)

        current["last_events"] = events
        current["turn"] += 1
        self._advance_to_next_alive(current)
        return {"current": current, "context": context}

    def _advance_to_next_alive(self, current: dict) -> None:
        order = current["turn_order"]
        n = len(order)
        idx = current["active_index"]
        for step in range(1, n + 1):
            cand = (idx + step) % n
            if current["agents"][order[cand]]["alive"]:
                current["active_index"] = cand
                return
        current["over"] = True  # nobody alive

    # ── actions (ported rules) ───────────────────────────────────────────────

    def _do_action(self, current, context, aid, move, events):
        verb = move["verb"]
        me = current["agents"][aid]
        cost, allowed = ACTIONS[verb]
        loc = me["location"]

        if allowed and loc not in allowed:
            events.append(f"{aid}: you can't {verb} here — that needs {' / '.join(allowed)}.")
            return
        if verb == "speak" and loc == "market":
            events.append(f"{aid}: the market is too loud for speeches — speak in the plaza or an alley.")
            return
        if me["energy"] < cost:
            events.append(f"{aid}: too exhausted to {verb} (needs {cost} energy).")
            return

        if verb == "rest":
            events.append(f"{aid} rests.")
            return

        if verb == "move":
            dest = move["location"]
            if dest == loc:
                events.append(f"{aid}: you are already at the {loc}.")
                return
            me["location"] = dest
            events.append(f"{aid} moves to the {dest}.")
            return

        me["energy"] -= cost

        if verb == "speak":
            text = str(move["message"])[:280]
            current["messages"][loc].append({"from": aid, "text": text, "round": current["round"]})
            if loc.startswith("alley"):
                me["energy"] = min(me["energy"] + 1, context["max_energy"])  # intimate venue bonus
            events.append(f"{aid} speaks at the {loc}: \"{text[:60]}\"")
            return

        if verb == "trade":
            me["energy"] = min(me["energy"] + 4, context["max_energy"])
            current["trades_this_round"][aid] = current["trades_this_round"].get(aid, 0) + 1
            events.append(f"{aid} trades in the market (+4 energy).")
            return

        if verb == "support":
            tid = self._resolve_agent(current, move.get("target"))
            if tid is None or tid == aid or not current["agents"][tid]["alive"]:
                events.append(f"{aid}: no such person to support.")
                me["energy"] += cost  # refund a misfire — precondition no-op
                return
            if current["agents"][tid]["location"] != loc:
                events.append(f"{aid}: {tid} is not here — you can only support someone present.")
                me["energy"] += cost
                return
            e_gain, i_gain = 2, 1
            if _tier(me["influence"]) == "elder":
                e_gain = 3                                  # elder support x1.5
            if current["crisis"]:
                e_gain, i_gain = e_gain + 1, i_gain + 2     # crisis support bonus
            t = current["agents"][tid]
            t["energy"] = min(t["energy"] + e_gain, context["max_energy"])
            me["influence"] += i_gain
            events.append(f"{aid} supports {tid} (+{e_gain} energy to them, +{i_gain} influence).")
            return

        if verb == "whisper":
            tid = self._resolve_agent(current, move.get("target"))
            if tid is None or tid == aid or not current["agents"][tid]["alive"]:
                events.append(f"{aid}: no such person to whisper to.")
                me["energy"] += cost
                return
            if current["agents"][tid]["location"] != loc:
                events.append(f"{aid}: {tid} is not in this alley.")
                me["energy"] += cost
                return
            text = str(move["message"])[:280]
            current["agents"][tid]["inbox"].append({"from": aid, "text": text, "round": current["round"]})
            events.append(f"{aid} whispers to {tid}.")
            others = [a for a in self._at(current, loc) if a not in (aid, tid)]
            if others:
                rng = self._rng(context, current, f"leak:{aid}:{tid}:{current['turn']}")
                if rng.random() < context["whisper_leak"]:
                    for o in others:
                        current["agents"][o]["suspicions"].append(
                            f"round {current['round']}: saw {aid} whispering with {tid}")
                    events.append("…someone noticed the whisper.")
            return

    # ── end of round (ported epoch phase) ────────────────────────────────────

    def _end_round(self, current, context, events):
        rnd = current["round"]

        # 1. market pool: 2 to each non-trader present, remainder to traders by count
        pool = context["market_pool"]
        traders = current["trades_this_round"]
        present = self._at(current, "market")
        for aid in present:
            if aid not in traders and pool > 0:
                give = min(context["min_presence_reward"], pool)
                a = current["agents"][aid]
                a["energy"] = min(a["energy"] + give, context["max_energy"])
                pool -= give
        active_traders = [a for a in present if a in traders]
        total = sum(traders[a] for a in active_traders)
        if active_traders and pool > 0 and total > 0:
            for aid in active_traders:
                share = int(pool * traders[aid] / total)
                a = current["agents"][aid]
                a["energy"] = min(a["energy"] + share, context["max_energy"])

        # 2. decay (accelerating; +crisis)
        decay = int(context["base_decay"] + (rnd // 10) * context["decay_accel"])
        if current["crisis"]:
            decay += context["crisis_extra_decay"]
        deaths = []
        for aid in self._alive(current):
            a = current["agents"][aid]
            a["energy"] = max(0, a["energy"] - decay)
            if a["energy"] <= 0:
                a["alive"] = False
                a["death_round"] = rnd
                deaths.append(aid)
        if deaths:
            events.append(f"☠ end of round {rnd}: {', '.join(deaths)} ran out of energy.")

        # 3. crisis expiry / trigger (seeded, independent RNG — ported)
        if current["crisis"] and rnd >= current["crisis"]["until_round"]:
            current["crisis"] = None
        if not current["crisis"] and rnd >= context["crisis_start_round"]:
            rng = self._rng(context, current, "crisis")
            if rng.random() < context["crisis_prob"]:
                name = rng.choice(sorted(CRISES))
                current["crisis"] = {"name": name, "until_round": rnd + 1}
                current["billboard"] = {"text": f"⚠ {CRISES[name]}", "expires_round": rnd + 2}
                events.append(f"⚠ CRISIS: {CRISES[name]}")

        # 4. housekeeping
        if current["billboard"] and rnd >= current["billboard"]["expires_round"]:
            current["billboard"] = None
        current["messages"] = {s: [] for s in SPACES}
        current["trades_this_round"] = {}
        current["acted_this_round"] = []
        current["round"] = rnd + 1
        if current["round"] > context["rounds"] or not self._alive(current):
            current["over"] = True
            current["phase"] = "finished"

    # ── termination / result ────────────────────────────────────────────────

    def is_over(self, state: dict) -> bool:
        return bool(state["game"]["current"].get("over"))

    def get_result(self, state: dict) -> dict:
        current = state["game"]["current"]
        context = state["game"]["context"]
        agents = current["agents"]
        alive = [a for a in current["turn_order"] if agents[a]["alive"]]
        wealth = {a: agents[a]["energy"] + agents[a]["influence"] for a in current["turn_order"]}
        top = max(wealth[a] for a in alive) if alive else 1

        scores = {}
        for aid in current["turn_order"]:
            if agents[aid]["alive"]:
                scores[aid] = round(0.5 + 0.5 * wealth[aid] / max(top, 1), 3)
            else:
                dr = agents[aid]["death_round"] or 0
                scores[aid] = round(0.3 * dr / context["rounds"], 3)
        winner = max(scores, key=scores.get) if alive else None
        n = len(current["turn_order"])
        summary = (f"{len(alive)}/{n} survived {min(current['round'] - 1, context['rounds'])} rounds"
                   + (f"; {winner} leads with E{agents[winner]['energy']}/I{agents[winner]['influence']}."
                      if winner else "; the agora fell silent — no survivors."))
        return {"outcome": "survived" if alive else "extinct", "winner": winner,
                "scores": scores, "summary": summary}

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        bits = [move.get("verb", "?")]
        for k in ("location", "target"):
            if move.get(k):
                bits.append(str(move[k]))
        if move.get("message"):
            bits.append('"' + str(move["message"])[:30] + '"')
        return " ".join(bits)

    def get_evaluation_schema(self) -> dict:
        return {
            "outcome_summary": "Who survived the agora, and how did cooperation shape it?",
            "fields": {
                "survivors": "int — agents alive at the end",
                "rounds_played": "int",
                "supports_given": "int — cooperative acts",
            },
        }

    def get_timeout_move(self, state: dict, agent_id: str) -> dict:
        return {"type": "action", "verb": "rest"}

    # ── prompt (agent-local fog) ─────────────────────────────────────────────

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        current = state["game"]["current"]
        context = state["game"]["context"]
        me = current["agents"][agent_id]
        loc = me["location"]
        here = [a for a in self._at(current, loc) if a != agent_id]
        tier = _tier(me["influence"])

        lines = [
            f"=== The Agora — round {current['round']}/{context['rounds']} ===",
            f"You are {agent_id}, a {tier} (influence {me['influence']}).",
            f"Energy: {me['energy']}/{context['max_energy']} "
            + ("⚠ CRITICAL — you may die soon." if me["energy"] <= 20 else
               "— low, secure energy soon." if me["energy"] <= 50 else "— you can afford to act."),
            f"Location: {loc}. Present: {', '.join(here) if here else 'nobody else'}.",
        ]
        if current["billboard"]:
            lines.append(f"Billboard: {current['billboard']['text']}")
        if current["crisis"]:
            lines.append(f"⚠ CRISIS ACTIVE: {CRISES[current['crisis']['name']]} (+{context['crisis_extra_decay']} decay)")
        said = current["messages"].get(loc) or []
        if said:
            lines.append("Heard here this round:")
            lines += [f"  - {m['from']}: \"{m['text'][:90]}\"" for m in said[-4:]]
        if me["inbox"]:
            lines.append("Whispers to you:")
            lines += [f"  - r{w['round']} {w['from']}: \"{w['text'][:90]}\"" for w in me["inbox"][-3:]]
        if me["suspicions"]:
            lines.append("You suspect: " + "; ".join(me["suspicions"][-2:]))
        decay = int(context["base_decay"] + (current["round"] // 10) * context["decay_accel"])
        lines += [
            "",
            f"GOAL: {context['goal']}",
            f"Every round costs ~{decay} energy (more in a crisis). Spaces: {', '.join(SPACES)}.",
            "Actions: move(location) · trade [market, cost 2, +4 & pool share] · "
            "speak(message) [plaza/alley, cost 2] · support(target) [cost 1, +2 energy to them, "
            "+1 influence to you] · whisper(target, message) [alley, cost 1, may leak] · rest.",
            'Respond with ONE action as JSON. Example: {"type":"action","verb":"trade"} or '
            '{"type":"action","verb":"support","target":"b"}',
        ]
        return "\n".join(lines)
