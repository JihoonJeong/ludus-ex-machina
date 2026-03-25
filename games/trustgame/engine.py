"""Trust Game (Iterated Prisoner's Dilemma) engine for LxM."""

import random
from pathlib import Path

from lxm.engine import LxMGame


class TrustGame(LxMGame):
    """Iterated Prisoner's Dilemma with probabilistic termination.

    Each round after resolution, the game continues with probability
    CONTINUATION_PROB. Expected rounds ≈ 1/(1-p). Agents do not know
    when the game will end, preventing backward induction.
    """

    CONTINUATION_PROB = 0.85  # 15% chance to end each round
    MIN_ROUNDS = 5           # Always play at least this many
    MAX_ROUNDS = 50          # Hard cap safety limit

    PAYOFF_MATRIX = {
        ("cooperate", "cooperate"): (3, 3),
        ("cooperate", "defect"):    (0, 5),
        ("defect",    "cooperate"): (5, 0),
        ("defect",    "defect"):    (1, 1),
    }

    def get_rules(self) -> str:
        rules_path = Path(__file__).parent / "rules.md"
        return rules_path.read_text(encoding="utf-8")

    @staticmethod
    def _random_end_round(continuation_prob: float, min_rounds: int, max_rounds: int) -> int:
        """Pre-determine when the game ends using geometric distribution.

        Simulates flipping a coin after each round starting from min_rounds.
        """
        for r in range(min_rounds, max_rounds):
            if random.random() > continuation_prob:
                return r
        return max_rounds

    def initial_state(self, agents: list[dict]) -> dict:
        a0 = agents[0]["agent_id"]
        a1 = agents[1]["agent_id"]
        end_round = self._random_end_round(
            self.CONTINUATION_PROB, self.MIN_ROUNDS, self.MAX_ROUNDS
        )
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
                "end_round": end_round,  # Hidden from agents via filter
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
            "end_round": context.get("end_round", self.MAX_ROUNDS),
            "history": new_history,
            "cooperation_rate": new_coop_rate,
            "patterns": new_patterns,
        }
        return {"current": new_current, "context": new_context}

    def is_over(self, state: dict) -> bool:
        game = state["game"]
        current = game["current"]
        context = game["context"]
        rounds_played = context["rounds_played"]

        # Never end mid-round (while a move is pending)
        if current.get("pending_move") is not None:
            return False

        # Use pre-determined end round (set at game start)
        end_round = context.get("end_round", self.MAX_ROUNDS)
        return rounds_played >= end_round

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

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        """Build inline trust game prompt with round info and action format."""
        game = state["game"]
        current = game["current"]
        context = game["context"]
        match_id = state.get("lxm", {}).get("match_id", "")

        round_num = current["round"]
        scores = current["scores"]
        agents = list(scores.keys())
        opponent = [a for a in agents if a != agent_id][0]
        rounds_played = context["rounds_played"]

        # Recent history (last 5 rounds)
        history = context.get("history", [])
        recent = history[-5:] if history else []
        history_lines = []
        for r in recent:
            my_action = r.get(agent_id, "?")
            opp_action = r.get(opponent, "?")
            my_payoff = r.get("payoffs", {}).get(agent_id, "?")
            opp_payoff = r.get("payoffs", {}).get(opponent, "?")
            history_lines.append(f"  R{r['round']}: you={my_action}, them={opp_action} -> you={my_payoff}, them={opp_payoff}")

        history_str = "\n".join(history_lines) if history_lines else "  (no rounds played yet)"

        # Pending move info
        pending = current.get("pending_move")
        if pending == "submitted":
            pending_str = "Your opponent has already submitted their choice."
        elif pending is not None and isinstance(pending, dict):
            pending_str = "You have already submitted. Waiting for opponent."
        else:
            pending_str = "Both players choose simultaneously this round."

        lines = [
            f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}",
            f"Trust Game (Iterated Prisoner's Dilemma) | Round: {round_num}",
            f"",
            f"Scores: you={scores[agent_id]}, opponent={scores[opponent]}",
            f"Rounds played: {rounds_played}",
            f"",
            f"Payoff matrix:",
            f"  Both cooperate: 3/3",
            f"  You cooperate, they defect: 0/5",
            f"  You defect, they cooperate: 5/0",
            f"  Both defect: 1/1",
            f"",
            f"Recent history:",
            history_str,
            f"",
            f"{pending_str}",
            f"Actions: cooperate, defect",
            f"",
            f'Do NOT read any files. Write your move JSON to: moves/turn_{turn}_{agent_id}.json',
            f'Copy one of these exactly:',
            f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
            f'"move":{{"type":"choice","action":"cooperate"}}}}',
            f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
            f'"move":{{"type":"choice","action":"defect"}}}}',
        ]

        return "\n".join(lines)

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
        """Filter state for agent: mask pending_move and hide end_round."""
        import copy
        game = state.get("game", {})
        current = game.get("current", {})
        context = game.get("context", {})
        pending = current.get("pending_move")

        needs_filter = (
            (pending is not None and isinstance(pending, dict) and pending.get("agent_id") != agent_id)
            or "end_round" in context
        )

        if not needs_filter:
            return state

        filtered = copy.deepcopy(state)

        # Mask pending move
        f_pending = filtered["game"]["current"].get("pending_move")
        if f_pending is not None and isinstance(f_pending, dict) and f_pending.get("agent_id") != agent_id:
            filtered["game"]["current"]["pending_move"] = "submitted"

        # Hide end_round from agents
        filtered["game"]["context"].pop("end_round", None)

        return filtered
