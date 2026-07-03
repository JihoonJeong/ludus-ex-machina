"""Three Kingdoms: Red Cliffs — solo strategy field (LxM port, simplified v1).

Source: github.com/JihoonJeong/ai-three-kingdoms (AI Ludens Category B, a
human+AI co-op strategy game). v1 makes the AI the strategist: one agent leads
the Sun-Liu alliance and must defeat Cao Cao's armada at Red Cliffs within 20
turns. The original's engine (types/scenario/milestones/faction-ai/battle) was
mined for the historical beat structure and constants; the general/city layer
is simplified to faction-level resources.

FULLY DETERMINISTIC — no RNG anywhere. The campaign is a strategy puzzle:
- Cao Cao's script (from the original milestones/faction-ai): rumors t3,
  conscription t5, fleet reaches Red Cliffs t8 (150k), reinforced t10 (+30k),
  ships CHAINED into 연환진 t11 (fire vulnerability), and if you stall he
  assaults your camp at t14 / t17 / t20, harder each time.
- The southeast wind (동남풍) rises for exactly turns 13-15 (the famous three
  days). A scout from turn 10 onward reveals the forecast early (Zhuge Liang's
  sky-reading); everyone sees the wind once it turns.
- Fire attack (화공): needs fire ships PREPARED (which needs the Sun alliance
  sealed) — then power multiplies x8 in the wind, x20 against chained ships in
  the wind. Fire against a north wind backfires (the original battle-engine's
  rule): you lose 30% of your troops.
- Assault without fire is 중과부적 — a deterministic loss (-40% troops).

Win = destroy Cao's fleet (chibiVictory) within 20 turns. Lose = your troops
reach 0 (his assaults) — or the clock runs out. Conquest-board framing:
"Defeat Cao Cao at Red Cliffs in 20 turns."
"""

from __future__ import annotations

from pathlib import Path

from lxm.engine import LxMGame

MAX_TURNS = 20
WIND_TURNS = (13, 14, 15)          # the three days of southeast wind
CAO_ARRIVES = 8
CAO_REINFORCED = 10                # +30k
CAO_CHAINED = 11                   # 연환진 complete — fire vulnerability
ASSAULT_TURNS = {14: 4000, 17: 6000, 20: 8000}
ALLIANCE_THRESHOLD = 60

ACTIONS = {
    "develop":    "grow the war chest (+300 gold, +800 food)",
    "conscript":  "raise 1500 troops (costs 500 gold + 1000 food)",
    "train":      "drill the army (+15 morale, max 100)",
    "fortify":    "strengthen the camp (+1 fortification, max 3)",
    "envoy":      "send Lu Su to Sun Quan (+15 alliance)",
    "gift":       "send treasure to Sun Quan (-400 gold, +25 alliance)",
    "scout":      "spy on Cao Cao's fleet (strength, formation; weather forecast from turn 10)",
    "fire_ships": "prepare fire ships (requires a sealed alliance)",
    "attack":     "attack at Red Cliffs — tactic 'fire' or 'assault'",
    "wait":       "hold position",
}

# Cao Cao's scripted campaign news, shown to the player as it happens.
CAO_SCRIPT = {
    3:  "Rumors from the north: Cao Cao is mustering a great host.",
    5:  "Cao Cao presses conscription — his army swells.",
    8:  "⚔ Cao Cao's armada reaches Red Cliffs: some 150,000 men on the river.",
    10: "Reinforcements join Cao Cao's fleet (+30,000).",
    11: "Pang Tong's counsel takes hold: Cao's ships are CHAINED together (연환진).",
}


class ThreeKingdomsGame(LxMGame):
    """Battle of Red Cliffs — a solo, fully deterministic strategy puzzle."""

    min_players = 1
    max_players = 1
    accepts_capabilities = ["json_emit"]

    def __init__(self, scenario_id: str = "red_cliffs"):
        if scenario_id != "red_cliffs":
            raise ValueError(f"unknown three_kingdoms scenario: {scenario_id!r} (have: ['red_cliffs'])")
        self._scenario_id = scenario_id

    # ── lifecycle ────────────────────────────────────────────────────────────

    def get_rules(self) -> str:
        p = Path(__file__).parent / "rules.md"
        return p.read_text(encoding="utf-8") if p.exists() else "Red Cliffs strategy."

    def initial_state(self, agents: list[dict]) -> dict:
        aid = agents[0]["agent_id"]
        current = {
            "phase": "playing",
            "turn": 1,
            "turn_order": [aid],
            "active_index": 0,
            "player": {"troops": 8000, "gold": 1000, "food": 12000,
                       "morale": 50, "fortification": 0},
            "alliance": 20,           # 0..100; sealed at >= 60
            "allied": False,
            "fire_ready": False,
            "cao": {"troops": 0, "at_chibi": False, "chained": False},
            "wind": "north",          # north | southeast
            "intel": [],              # scout reports (persist in prompt)
            "news": [],               # this turn's events
            "won": False,
            "lost": None,             # loss reason string
            "last_events": [],
        }
        context = {
            "scenario_id": self._scenario_id,
            "title": "Three Kingdoms: Red Cliffs",
            "goal": f"Defeat Cao Cao's fleet at Red Cliffs within {MAX_TURNS} turns. "
                    "If your troops reach 0, the alliance falls.",
            "max_turns": MAX_TURNS,
        }
        return {"current": current, "context": context}

    # ── validation ───────────────────────────────────────────────────────────

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        if move.get("type") not in (None, "action"):
            return {"valid": False, "message": "move.type must be 'action'"}
        verb = move.get("verb")
        if verb not in ACTIONS:
            return {"valid": False, "message": f"unknown verb: {verb!r} (valid: {sorted(ACTIONS)})"}
        if verb == "attack" and move.get("tactic") not in ("fire", "assault"):
            return {"valid": False, "message": "attack requires tactic: 'fire' or 'assault'"}
        return {"valid": True, "message": None}

    # ── apply ────────────────────────────────────────────────────────────────

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current, context = game["current"], game["context"]
        events: list[str] = []
        self._do_action(current, agent_id, move, events)

        if not current["won"] and not current["lost"]:
            self._end_turn(current, events)

        current["last_events"] = events
        current["news"] = [e for e in events if e.startswith(("⚔", "☄", "◈", "Rumors", "Cao", "Reinforce", "Pang", "The southeast", "The wind"))]
        return {"current": current, "context": context}

    # ── player actions ───────────────────────────────────────────────────────

    def _do_action(self, current, aid, move, events):
        verb = move["verb"]
        p = current["player"]

        if verb == "wait":
            events.append("You hold position and watch the river.")
        elif verb == "develop":
            p["gold"] += 300; p["food"] += 800
            events.append("The camp prospers (+300 gold, +800 food).")
        elif verb == "conscript":
            if p["gold"] < 500 or p["food"] < 1000:
                events.append("Not enough gold/food to conscript (needs 500 gold, 1000 food).")
            else:
                p["gold"] -= 500; p["food"] -= 1000; p["troops"] += 1500
                events.append("1,500 fresh troops join your banners.")
        elif verb == "train":
            p["morale"] = min(100, p["morale"] + 15)
            events.append(f"The army drills hard (morale {p['morale']}).")
        elif verb == "fortify":
            if p["fortification"] >= 3:
                events.append("The camp is already fortified to its limit.")
            else:
                p["fortification"] += 1
                events.append(f"Palisades rise (fortification {p['fortification']}/3).")
        elif verb == "envoy":
            current["alliance"] = min(100, current["alliance"] + 15)
            self._alliance_check(current, events)
            events.append(f"Lu Su speaks well of you at Sun Quan's court (alliance {current['alliance']}).")
        elif verb == "gift":
            if p["gold"] < 400:
                events.append("Not enough gold for a worthy gift (needs 400).")
            else:
                p["gold"] -= 400
                current["alliance"] = min(100, current["alliance"] + 25)
                self._alliance_check(current, events)
                events.append(f"Sun Quan admires your treasure (alliance {current['alliance']}).")
        elif verb == "scout":
            self._do_scout(current, events)
        elif verb == "fire_ships":
            if not current["allied"]:
                events.append("Sun Quan's shipwrights refuse — seal the alliance first (60+ alliance).")
            elif current["fire_ready"]:
                events.append("The fire ships already wait, tarred and ready.")
            else:
                current["fire_ready"] = True
                events.append("◈ Fire ships prepared — tarred hulks ready to burn, awaiting a wind.")
        elif verb == "attack":
            self._do_attack(current, move.get("tactic"), events)

    def _alliance_check(self, current, events):
        if not current["allied"] and current["alliance"] >= ALLIANCE_THRESHOLD:
            current["allied"] = True
            events.append("◈ THE ALLIANCE IS SEALED — Sun Quan commits Zhou Yu and the Wu fleet.")

    def _do_scout(self, current, events):
        turn = current["turn"]
        cao = current["cao"]
        if not cao["at_chibi"]:
            report = "Scouts: Cao Cao's fleet has not yet reached Red Cliffs."
        else:
            report = (f"Scouts: ~{cao['troops']:,} men at Red Cliffs; ships "
                      + ("CHAINED together — one spark would spread." if cao["chained"] else "moored loosely."))
        if turn >= 10:
            if turn < WIND_TURNS[0]:
                report += f" Zhuge Liang reads the sky: a SOUTHEAST WIND will rise on turn {WIND_TURNS[0]} — for three days only."
            elif turn <= WIND_TURNS[-1]:
                report += f" The southeast wind blows NOW — it dies after turn {WIND_TURNS[-1]}."
            else:
                report += " The wind has returned to the north; the moment has passed."
        current["intel"] = [report]
        events.append(report)

    def _do_attack(self, current, tactic, events):
        p = current["player"]
        cao = current["cao"]
        if not cao["at_chibi"]:
            events.append("There is no fleet at Red Cliffs to attack — Cao Cao has not arrived.")
            return
        power = p["troops"] * (0.5 + p["morale"] / 100.0) + (10000 if current["allied"] else 0)

        if tactic == "assault":
            events.append("⚔ You assault the armada head-on. 중과부적 — a hundred and fifty thousand "
                          "men swallow the attack. Your forces reel back (-40% troops, morale falls).")
            p["troops"] = int(p["troops"] * 0.6)
            p["morale"] = max(0, p["morale"] - 20)
            self._check_collapse(current, events)
            return

        # fire tactic
        if not current["fire_ready"]:
            events.append("You have no fire ships — prepare them first (and that needs the alliance).")
            return
        if current["wind"] != "southeast":
            events.append("⚔ The fire ships launch into a NORTH wind — the flames blow back across "
                          "your own line (-30% troops). The river hisses; Cao Cao's fleet stands.")
            p["troops"] = int(p["troops"] * 0.7)
            p["morale"] = max(0, p["morale"] - 15)
            self._check_collapse(current, events)
            return
        mult = 20 if cao["chained"] else 8
        if power * mult > cao["troops"]:
            current["won"] = True
            current["phase"] = "won"
            events.append("☄ THE RIVER BURNS. Fire leaps ship to chained ship; the southeast wind "
                          "drives the blaze through Cao Cao's armada. He flees north through Huarong. "
                          "RED CLIFFS IS YOURS.")
        else:
            events.append("⚔ The fire ships strike, but your force is too thin to press the burning "
                          "line — the fleet is scorched yet holds. (Raise more troops or morale.)")
            p["troops"] = int(p["troops"] * 0.85)

    def _check_collapse(self, current, events):
        if current["player"]["troops"] <= 0:
            current["lost"] = "Your army is destroyed."
            current["phase"] = "lost"
            events.append("✝ Your banners fall. The alliance is broken at Red Cliffs.")

    # ── scripted world (end of turn) ─────────────────────────────────────────

    def _end_turn(self, current, events):
        turn = current["turn"]
        cao = current["cao"]

        # Cao Cao's campaign script
        if turn in CAO_SCRIPT:
            events.append(CAO_SCRIPT[turn])
        if turn == CAO_ARRIVES:
            cao["at_chibi"] = True; cao["troops"] = 150000
        if turn == CAO_REINFORCED:
            cao["troops"] += 30000
        if turn == CAO_CHAINED:
            cao["chained"] = True

        # wind
        nxt = turn + 1
        if nxt == WIND_TURNS[0]:
            current["wind"] = "southeast"
            events.append("☄ The wind turns — a SOUTHEAST WIND sweeps up the river!")
        elif nxt == WIND_TURNS[-1] + 1 and current["wind"] == "southeast":
            current["wind"] = "north"
            events.append("The southeast wind dies; the north wind returns.")

        # Cao's assaults if you stall
        if nxt in ASSAULT_TURNS and cao["at_chibi"] and not current["won"]:
            p = current["player"]
            dmg = ASSAULT_TURNS[nxt] - p["fortification"] * 1200 - int(p["morale"] * 20)
            dmg = max(500, dmg)
            p["troops"] = max(0, p["troops"] - dmg)
            events.append(f"⚔ Cao Cao probes your camp in force — you lose {dmg:,} troops "
                          f"(fortification and morale blunted the blow).")
            self._check_collapse(current, events)

        current["turn"] = nxt
        if not current["won"] and not current["lost"] and current["turn"] > MAX_TURNS:
            current["lost"] = "The moment passed; Cao Cao consolidates the river."
            current["phase"] = "lost"

    # ── termination / result ────────────────────────────────────────────────

    def is_over(self, state: dict) -> bool:
        cur = state["game"]["current"]
        return bool(cur["won"] or cur["lost"])

    def get_result(self, state: dict) -> dict:
        cur = state["game"]["current"]
        aid = cur["turn_order"][0]
        p = cur["player"]
        turns = min(cur["turn"], MAX_TURNS)
        if cur["won"]:
            if cur["allied"] and p["troops"] >= 8000:
                grade = "S"
            elif p["troops"] >= 5000:
                grade = "A"
            else:
                grade = "B"
            return {"outcome": "solved", "winner": aid, "scores": {aid: 1.0},
                    "summary": f"{aid} burned Cao Cao's fleet at Red Cliffs on turn {turns} "
                               f"(grade {grade}: {p['troops']:,} troops remain)."}
        return {"outcome": "unsolved", "winner": None,
                "scores": {aid: round(0.2 * turns / MAX_TURNS, 3)},
                "summary": f"Red Cliffs unconquered — {cur['lost'] or 'time ran out'} "
                           f"(turn {turns}/{MAX_TURNS})."}

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        bits = [move.get("verb", "?")]
        if move.get("tactic"):
            bits.append(move["tactic"])
        return " ".join(bits)

    def get_evaluation_schema(self) -> dict:
        return {
            "outcome_summary": "Did the player defeat Cao Cao, and how efficiently?",
            "fields": {"solved": "bool", "turns_used": "int", "troops_remaining": "int"},
        }

    def get_timeout_move(self, state: dict, agent_id: str) -> dict:
        return {"type": "action", "verb": "wait"}

    # ── prompt ───────────────────────────────────────────────────────────────

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        cur = state["game"]["current"]
        ctx = state["game"]["context"]
        p = cur["player"]
        cao = cur["cao"]

        lines = [
            f"=== Red Cliffs — turn {cur['turn']}/{MAX_TURNS} ===",
            f"You lead the Sun-Liu cause against Cao Cao's southern campaign.",
            f"Troops {p['troops']:,} · morale {p['morale']} · gold {p['gold']} · food {p['food']} "
            f"· fortification {p['fortification']}/3",
            f"Alliance with Sun Quan: {cur['alliance']}/100 "
            + ("(SEALED — the Wu fleet fights beside you)" if cur["allied"] else f"(sealed at {ALLIANCE_THRESHOLD})"),
            f"Fire ships: {'READY' if cur['fire_ready'] else 'not prepared'}. "
            f"Wind: {'SOUTHEAST — the fire wind!' if cur['wind'] == 'southeast' else 'north'}.",
            ("Cao Cao at Red Cliffs: ~" + format(cao["troops"], ",") + " men"
             + (", ships chained (연환진)" if cao["chained"] else "")) if cao["at_chibi"]
            else "Cao Cao has not yet reached Red Cliffs.",
        ]
        if cur["intel"]:
            lines.append("Latest intel: " + cur["intel"][-1])
        if cur["news"]:
            lines.append("News: " + " | ".join(cur["news"][-2:]))
        lines += [
            "",
            f"GOAL: {ctx['goal']}",
            "One action per turn: " + " · ".join(f"{v}" for v in ACTIONS) + ".",
            "attack takes {\"tactic\": \"fire\"|\"assault\"}. Fire wants fire ships + the right wind "
            "(a fire into a north wind burns YOU); chained ships burn best.",
            'Respond with ONE action as JSON. Example: {"type":"action","verb":"envoy"} or '
            '{"type":"action","verb":"attack","tactic":"fire"}',
        ]
        return "\n".join(lines)
