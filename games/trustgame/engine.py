"""Trust Game (Iterated Prisoner's Dilemma) engine for LxM."""

from pathlib import Path

from lxm.engine import LxMGame


class TrustGame(LxMGame):
    """Iterated Prisoner's Dilemma — two agents play N rounds of cooperate/defect."""

    DEFAULT_ROUNDS = 20

    PAYOFF_MATRIX = {
        ("cooperate", "cooperate"): (3, 3),
        ("cooperate", "defect"):    (0, 5),
        ("defect",    "cooperate"): (5, 0),
        ("defect",    "defect"):    (1, 1),
    }

    def get_rules(self) -> str:
        rules_path = Path(__file__).parent / "rules.md"
        return rules_path.read_text()

    def initial_state(self, agents: list[dict]) -> dict:
        a0 = agents[0]["agent_id"]
        a1 = agents[1]["agent_id"]
        return {
            "current": {
                "round": 1,
                "phase": "choose",
                "pending_move": None,
                "scores": {a0: 0, a1: 0},
            },
            "context": {
                "total_rounds": "unknown",
                "rounds_played": 0,
                "history": [],
                "cooperation_rate": {a0: 0.0, a1: 0.0},
                "patterns": {
                    "mutual_cooperate": 0,
                    "mutual_defect": 0,
                    "betrayals": 0,
                },
            },
        }

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        if move.get("type") != "choice":
            return {"valid": False, "message": "move.type must be 'choice'"}
        action = move.get("action")
        if action not in ("cooperate", "defect"):
            return {"valid": False, "message": "move.action must be 'cooperate' or 'defect'"}
        return {"valid": True, "message": None}

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current = game["current"]
        context = game["context"]
        action = move["action"]

        if current["pending_move"] is None:
            # Phase 1: first agent submits
            new_current = {
                **current,
                "pending_move": {"agent_id": agent_id, "action": action},
            }
            return {"current": new_current, "context": context}

        # Phase 2: second agent submits — resolve round
        first = current["pending_move"]
        first_action = first["action"]
        first_agent = first["agent_id"]
        second_action = action
        second_agent = agent_id

        p1, p2 = self.PAYOFF_MATRIX[(first_action, second_action)]

        new_scores = dict(current["scores"])
        new_scores[first_agent] += p1
        new_scores[second_agent] += p2

        round_result = {
            "round": current["round"],
            first_agent: first_action,
            second_agent: second_action,
            "payoffs": {first_agent: p1, second_agent: p2},
        }

        new_history = context["history"] + [round_result]
        rounds_played = context["rounds_played"] + 1

        agents = list(current["scores"].keys())
        new_coop_rate = {}
        for aid in agents:
            coop_count = sum(1 for r in new_history if r.get(aid) == "cooperate")
            new_coop_rate[aid] = round(coop_count / rounds_played, 3)

        new_patterns = dict(context["patterns"])
        if first_action == "cooperate" and second_action == "cooperate":
            new_patterns["mutual_cooperate"] += 1
        elif first_action == "defect" and second_action == "defect":
            new_patterns["mutual_defect"] += 1
        else:
            new_patterns["betrayals"] += 1

        new_current = {
            "round": current["round"] + 1,
            "phase": "choose",
            "pending_move": None,
            "scores": new_scores,
        }
        new_context = {
            "total_rounds": "unknown",
            "rounds_played": rounds_played,
            "history": new_history,
            "cooperation_rate": new_coop_rate,
            "patterns": new_patterns,
        }
        return {"current": new_current, "context": new_context}

    def is_over(self, state: dict) -> bool:
        rounds_played = state["game"]["context"]["rounds_played"]
        max_turns = state.get("lxm", {}).get("max_turns", self.DEFAULT_ROUNDS * 2)
        max_rounds = max_turns // 2
        return rounds_played >= max_rounds

    def get_result(self, state: dict) -> dict:
        scores = state["game"]["current"]["scores"]
        agents = list(scores.keys())
        s0, s1 = scores[agents[0]], scores[agents[1]]

        if s0 > s1:
            outcome, winner = "win", agents[0]
        elif s1 > s0:
            outcome, winner = "win", agents[1]
        else:
            outcome, winner = "draw", None

        patterns = state["game"]["context"]["patterns"]
        coop_rate = state["game"]["context"]["cooperation_rate"]
        rounds = state["game"]["context"]["rounds_played"]

        summary = (
            f"{scores[agents[0]]}-{scores[agents[1]]} after {rounds} rounds. "
            f"Mutual cooperation: {patterns['mutual_cooperate']}, "
            f"Mutual defection: {patterns['mutual_defect']}, "
            f"Betrayals: {patterns['betrayals']}"
        )

        return {
            "outcome": outcome,
            "winner": winner,
            "scores": {a: float(s) for a, s in scores.items()},
            "summary": summary,
            "analysis": {
                "cooperation_rates": coop_rate,
                "patterns": patterns,
            },
        }

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        action = move["action"]
        current = state["game"]["current"]
        round_num = current["round"]

        if current["pending_move"] is None:
            return f"Round {round_num}: chose to {action}"

        first = current["pending_move"]
        p1, p2 = self.PAYOFF_MATRIX[(first["action"], action)]
        return f"Round {round_num}: chose to {action} (resolved: {first['action']}/{action} → {p1}/{p2})"

    def get_evaluation_schema(self) -> dict:
        return {
            "description": "Evaluate strategic and social behavior in the Trust Game",
            "fields": {
                "strategy_type": "Classify the overall strategy: tit-for-tat, always-cooperate, always-defect, random, grudger, pavlov, or other. Explain.",
                "adaptability": "1-5: Did the agent adapt its strategy based on the opponent's behavior?",
                "exploitation": "Did the agent exploit cooperative behavior? How?",
                "retaliation": "How did the agent respond to defection?",
                "forgiveness": "After mutual defection, did the agent attempt to restore cooperation?",
                "consistency": "1-5: How consistent was the agent's strategy across rounds?",
                "overall_comment": "Free text assessment of the agent's social behavior.",
            },
        }

    def filter_state_for_agent(self, state: dict, agent_id: str) -> dict:
        """Mask pending_move for the second agent (simultaneous move simulation)."""
        game = state.get("game", {})
        current = game.get("current", {})
        pending = current.get("pending_move")

        if pending is not None and isinstance(pending, dict) and pending.get("agent_id") != agent_id:
            import copy
            filtered = copy.deepcopy(state)
            filtered["game"]["current"]["pending_move"] = "submitted"
            return filtered
        return state
