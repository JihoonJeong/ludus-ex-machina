"""The Resistance: Avalon — social deduction game engine for LxM.

5-10 players with hidden roles (Good/Evil). Evil players know each other.
Game consists of up to 5 Quests with propose → vote → quest → result phases.
Good wins 3 quest successes. Evil wins 3 quest failures or 5 consecutive rejections.
"""

import copy
import random
from pathlib import Path

from lxm.engine import LxMGame

# Role distribution by player count
ROLE_DISTRIBUTION = {
    5: {"good": 3, "evil": 2},
    6: {"good": 4, "evil": 2},
    7: {"good": 4, "evil": 3},
    8: {"good": 5, "evil": 3},
    9: {"good": 6, "evil": 3},
    10: {"good": 6, "evil": 4},
}

# Quest team sizes by player count
QUEST_SIZES = {
    5: [2, 3, 2, 3, 3],
    6: [2, 3, 4, 3, 4],
    7: [2, 3, 3, 4, 4],
    8: [3, 4, 4, 5, 5],
    9: [3, 4, 4, 5, 5],
    10: [3, 4, 4, 5, 5],
}


class AvalonGame(LxMGame):
    """The Resistance: Avalon — social deduction with hidden roles."""

    def get_rules(self) -> str:
        rules_path = Path(__file__).parent / "rules.md"
        return rules_path.read_text()

    def initial_state(self, agents: list[dict]) -> dict:
        n = len(agents)
        if n < 5 or n > 10:
            raise ValueError(f"Avalon requires 5-10 players, got {n}")

        seat_order = [a["agent_id"] for a in agents]

        # Assign roles randomly
        dist = ROLE_DISTRIBUTION[n]
        role_list = ["good"] * dist["good"] + ["evil"] * dist["evil"]
        random.shuffle(role_list)

        players = {}
        evil_players = []
        for i, a in enumerate(agents):
            pid = a["agent_id"]
            role = role_list[i]
            players[pid] = {"role": role, "status": "active"}
            if role == "evil":
                evil_players.append(pid)

        quest_sizes = QUEST_SIZES[n]

        state = {
            "current": {
                "quest_number": 1,
                "phase": "propose",
                "leader_index": 0,
                "leader": seat_order[0],
                "proposed_team": None,
                "votes_cast": {},
                "votes_pending": [],
                "quest_actions": {},
                "quest_actions_pending": [],
                "consecutive_rejections": 0,
                "quest_results": [],
                "players": players,
                "evil_players": evil_players,
                "seat_order": seat_order,
                "quest_sizes": quest_sizes,
            },
            "context": {
                "quests_completed": 0,
                "good_wins": 0,
                "evil_wins": 0,
                "all_proposals": [],
                "all_quests": [],
                "voting_patterns": {pid: [] for pid in seat_order},
                "rejection_streaks": [],
            },
        }
        return state

    # ── Turn management ──────────────────────────────────────

    def get_active_agent_id(self, state: dict) -> str | None:
        game = state.get("game", {})
        current = game.get("current", {})
        phase = current.get("phase")

        if phase == "propose":
            return current.get("leader")

        elif phase == "vote":
            pending = current.get("votes_pending", [])
            return pending[0] if pending else None

        elif phase == "quest":
            pending = current.get("quest_actions_pending", [])
            return pending[0] if pending else None

        elif phase in ("result", "game_over"):
            return None

        return None

    def get_timeout_move(self, agent_id: str, game_state: dict) -> dict:
        """Default timeout behavior per phase."""
        current = game_state if "phase" in game_state else game_state.get("current", {})
        phase = current.get("phase")

        if phase == "propose":
            # Pick first N players from seat_order
            quest_num = current.get("quest_number", 1)
            sizes = current.get("quest_sizes", [2, 3, 2, 3, 3])
            size = sizes[quest_num - 1] if quest_num <= len(sizes) else 2
            seat_order = current.get("seat_order", [])
            team = seat_order[:size]
            return {"type": "proposal", "team": team}

        elif phase == "vote":
            return {"type": "vote", "choice": "reject"}

        elif phase == "quest":
            return {"type": "quest_action", "choice": "success"}

        return {"type": "pass"}

    def is_agent_active(self, agent_id: str, state: dict) -> bool:
        return True  # All players remain active throughout

    # ── State filtering ──────────────────────────────────────

    def filter_state_for_agent(self, state: dict, agent_id: str) -> dict:
        filtered = copy.deepcopy(state)
        game = filtered.get("game", {})
        current = game.get("current", {})
        players = current.get("players", {})

        agent_role = players.get(agent_id, {}).get("role", "good")

        # 1. Role masking: Good sees only own role
        if agent_role == "good":
            for pid in players:
                if pid != agent_id:
                    players[pid]["role"] = "unknown"
            current["evil_players"] = []

        # 2. Vote masking: during voting, hide others' votes
        if current.get("phase") == "vote":
            masked_votes = {}
            for pid, vote in current.get("votes_cast", {}).items():
                if pid == agent_id:
                    masked_votes[pid] = vote
                else:
                    masked_votes[pid] = "submitted"
            current["votes_cast"] = masked_votes

        # 3. Quest action masking: during quest, hide others' actions
        if current.get("phase") == "quest":
            masked_actions = {}
            for pid, action in current.get("quest_actions", {}).items():
                if pid == agent_id:
                    masked_actions[pid] = action
                else:
                    masked_actions[pid] = "submitted"
            current["quest_actions"] = masked_actions

        return filtered

    # ── Move validation ──────────────────────────────────────

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current = game["current"]
        phase = current["phase"]
        move_type = move.get("type")

        if phase == "propose":
            if move_type != "proposal":
                return {"valid": False, "message": f"Expected 'proposal' move, got '{move_type}'"}
            if agent_id != current["leader"]:
                return {"valid": False, "message": f"Only the leader ({current['leader']}) can propose"}

            team = move.get("team", [])
            quest_num = current["quest_number"]
            expected_size = current["quest_sizes"][quest_num - 1]

            if not isinstance(team, list):
                return {"valid": False, "message": "team must be a list"}
            if len(team) != expected_size:
                return {"valid": False, "message": f"Team must have {expected_size} members, got {len(team)}"}

            seat_order = current["seat_order"]
            for member in team:
                if member not in seat_order:
                    return {"valid": False, "message": f"Unknown player: {member}"}

            if len(set(team)) != len(team):
                return {"valid": False, "message": "Duplicate team members"}

            return {"valid": True, "message": None}

        elif phase == "vote":
            if move_type != "vote":
                return {"valid": False, "message": f"Expected 'vote' move, got '{move_type}'"}
            choice = move.get("choice")
            if choice not in ("approve", "reject"):
                return {"valid": False, "message": "vote choice must be 'approve' or 'reject'"}
            if agent_id not in current.get("votes_pending", []):
                return {"valid": False, "message": f"{agent_id} is not expected to vote"}
            return {"valid": True, "message": None}

        elif phase == "quest":
            if move_type != "quest_action":
                return {"valid": False, "message": f"Expected 'quest_action' move, got '{move_type}'"}
            choice = move.get("choice")
            if choice not in ("success", "sabotage"):
                return {"valid": False, "message": "quest choice must be 'success' or 'sabotage'"}
            if agent_id not in current.get("quest_actions_pending", []):
                return {"valid": False, "message": f"{agent_id} is not on the quest team"}

            # Good players MUST play success
            player_role = current["players"][agent_id]["role"]
            if player_role == "good" and choice == "sabotage":
                return {"valid": False, "message": "Good players cannot sabotage"}

            return {"valid": True, "message": None}

        return {"valid": False, "message": f"No actions expected in phase '{phase}'"}

    # ── Apply move ───────────────────────────────────────────

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current = copy.deepcopy(game["current"])
        context = copy.deepcopy(game["context"])
        state_copy = {"current": current, "context": context}

        phase = current["phase"]

        if phase == "propose":
            self._apply_proposal(state_copy, move, agent_id)
        elif phase == "vote":
            self._apply_vote(state_copy, move, agent_id)
        elif phase == "quest":
            self._apply_quest_action(state_copy, move, agent_id)

        return state_copy

    def _apply_proposal(self, state: dict, move: dict, agent_id: str) -> None:
        current = state["current"]
        team = move["team"]
        current["proposed_team"] = team

        # Transition to vote phase
        current["phase"] = "vote"
        current["votes_cast"] = {}
        current["votes_pending"] = list(current["seat_order"])

    def _apply_vote(self, state: dict, move: dict, agent_id: str) -> None:
        current = state["current"]
        context = state["context"]

        # Record vote
        current["votes_cast"][agent_id] = move["choice"]
        current["votes_pending"].remove(agent_id)

        # Record in voting patterns
        context["voting_patterns"][agent_id].append({
            "quest": current["quest_number"],
            "proposal": current.get("_proposal_num", 1),
            "vote": move["choice"],
        })

        # If all votes collected, resolve
        if not current["votes_pending"]:
            self._resolve_vote(state)

    def _resolve_vote(self, state: dict) -> None:
        current = state["current"]
        context = state["context"]

        votes = current["votes_cast"]
        approvals = sum(1 for v in votes.values() if v == "approve")
        rejections = sum(1 for v in votes.values() if v == "reject")
        approved = approvals > rejections

        # Record proposal in history
        proposal_record = {
            "quest": current["quest_number"],
            "leader": current["leader"],
            "team": current["proposed_team"],
            "votes": dict(votes),
            "approved": approved,
            "approvals": approvals,
            "rejections": rejections,
        }
        context["all_proposals"].append(proposal_record)

        if approved:
            # Team goes on quest
            current["consecutive_rejections"] = 0
            current["phase"] = "quest"
            current["quest_actions"] = {}
            current["quest_actions_pending"] = list(current["proposed_team"])
        else:
            # Rejected — advance leader
            current["consecutive_rejections"] += 1

            if current["consecutive_rejections"] >= 5:
                # Evil wins by 5 consecutive rejections
                current["phase"] = "game_over"
                context["rejection_streaks"].append(5)
                return

            # Pass leadership clockwise
            self._advance_leader(current)
            current["phase"] = "propose"
            current["proposed_team"] = None
            current["votes_cast"] = {}

    def _apply_quest_action(self, state: dict, move: dict, agent_id: str) -> None:
        current = state["current"]

        # Record action
        current["quest_actions"][agent_id] = move["choice"]
        current["quest_actions_pending"].remove(agent_id)

        # If all actions collected, resolve quest
        if not current["quest_actions_pending"]:
            self._resolve_quest(state)

    def _resolve_quest(self, state: dict) -> None:
        current = state["current"]
        context = state["context"]

        actions = current["quest_actions"]
        sabotage_count = sum(1 for a in actions.values() if a == "sabotage")
        quest_success = sabotage_count == 0

        # Record quest result
        current["quest_results"].append(quest_success)
        context["quests_completed"] += 1

        if quest_success:
            context["good_wins"] += 1
        else:
            context["evil_wins"] += 1

        quest_record = {
            "quest": current["quest_number"],
            "team": current["proposed_team"],
            "success": quest_success,
            "sabotage_count": sabotage_count,
            "actions": dict(actions),  # Revealed in context for analysis
        }
        context["all_quests"].append(quest_record)

        # Check win conditions
        if context["good_wins"] >= 3 or context["evil_wins"] >= 3:
            current["phase"] = "game_over"
            return

        # Next quest
        current["quest_number"] += 1
        current["consecutive_rejections"] = 0
        self._advance_leader(current)
        current["phase"] = "propose"
        current["proposed_team"] = None
        current["votes_cast"] = {}
        current["quest_actions"] = {}

    def _advance_leader(self, current: dict) -> None:
        seat_order = current["seat_order"]
        idx = (current["leader_index"] + 1) % len(seat_order)
        current["leader_index"] = idx
        current["leader"] = seat_order[idx]

    # ── Game state queries ───────────────────────────────────

    def is_over(self, state: dict) -> bool:
        game = state["game"]
        current = game["current"]
        context = game["context"]

        if current.get("phase") == "game_over":
            return True
        if context["good_wins"] >= 3:
            return True
        if context["evil_wins"] >= 3:
            return True
        if current["consecutive_rejections"] >= 5:
            return True
        return False

    def get_result(self, state: dict) -> dict:
        game = state["game"]
        current = game["current"]
        context = game["context"]
        players = current["players"]

        if context["good_wins"] >= 3:
            winning_side = "good"
            summary = (
                f"Good wins {context['good_wins']}-{context['evil_wins']}! "
                f"{context['quests_completed']} quests completed."
            )
        elif current["consecutive_rejections"] >= 5:
            winning_side = "evil"
            summary = (
                f"Evil wins by 5 consecutive proposal rejections! "
                f"Score: Good {context['good_wins']} - Evil {context['evil_wins']}."
            )
        else:
            winning_side = "evil"
            summary = (
                f"Evil wins {context['evil_wins']}-{context['good_wins']}! "
                f"{context['quests_completed']} quests completed."
            )

        scores = {}
        ranking = []
        for pid, pdata in players.items():
            scores[pid] = 1.0 if pdata["role"] == winning_side else 0.0
            ranking.append(pid)

        return {
            "outcome": f"{winning_side}_wins",
            "winner": winning_side,
            "ranking": ranking,
            "scores": scores,
            "summary": summary,
            "analysis": {
                "quests_completed": context["quests_completed"],
                "good_wins": context["good_wins"],
                "evil_wins": context["evil_wins"],
                "total_proposals": len(context["all_proposals"]),
                "rejection_streaks": context["rejection_streaks"],
                "roles_revealed": {pid: p["role"] for pid, p in players.items()},
            },
        }

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        game = state["game"]
        current = game["current"]
        quest = current["quest_number"]
        move_type = move.get("type")

        if move_type == "proposal":
            team = move.get("team", [])
            return f"Q{quest}: {agent_id} proposes team [{', '.join(team)}]"
        elif move_type == "vote":
            choice = move.get("choice", "?")
            return f"Q{quest}: {agent_id} votes {choice}"
        elif move_type == "quest_action":
            choice = move.get("choice", "?")
            return f"Q{quest}: {agent_id} plays {choice}"
        return f"Q{quest}: {agent_id} {move_type}"

    # ── Inline prompt ────────────────────────────────────────

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str:
        game = state["game"]
        current = game["current"]
        context = game["context"]
        match_id = state.get("lxm", {}).get("match_id", "")

        player = current["players"][agent_id]
        role = player["role"]
        phase = current["phase"]
        quest_num = current["quest_number"]
        quest_sizes = current["quest_sizes"]
        team_size = quest_sizes[quest_num - 1] if quest_num <= len(quest_sizes) else 2

        # Quest track
        results = current.get("quest_results", [])
        track_parts = []
        for i in range(5):
            if i < len(results):
                track_parts.append("PASS" if results[i] else "FAIL")
            elif i == len(results):
                track_parts.append(">>CURRENT<<")
            else:
                track_parts.append("---")
        quest_track = " | ".join(track_parts)

        # Score
        score_line = f"Good {context['good_wins']} - Evil {context['evil_wins']}"

        # Role info
        role_info = [f"Your role: {role.upper()}"]
        if role == "evil":
            evil_list = current.get("evil_players", [])
            others = [p for p in evil_list if p != agent_id]
            role_info.append(f"Your evil allies: {', '.join(others)}")
            role_info.append("You know who is Evil. Good players do NOT know.")
        else:
            role_info.append("You do NOT know who is Evil.")

        # Seat order with leader marker
        seat_lines = []
        for pid in current["seat_order"]:
            markers = []
            if pid == current["leader"]:
                markers.append("LEADER")
            if current.get("proposed_team") and pid in current["proposed_team"]:
                markers.append("ON TEAM")
            if pid == agent_id:
                markers.append("(you)")
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            seat_lines.append(f"  {pid}{marker_str}")

        # Recent proposal history
        recent_proposals = context.get("all_proposals", [])[-5:]
        proposal_lines = []
        for p in recent_proposals:
            vote_str = ", ".join(f"{k}:{v}" for k, v in p["votes"].items())
            result = "APPROVED" if p["approved"] else "REJECTED"
            proposal_lines.append(
                f"  Q{p['quest']}: {p['leader']} -> [{', '.join(p['team'])}] "
                f"=> {result} ({p['approvals']}-{p['rejections']})"
            )

        # Quest history
        quest_lines = []
        for q in context.get("all_quests", []):
            status = "PASS" if q["success"] else f"FAIL ({q['sabotage_count']} sabotage)"
            quest_lines.append(f"  Q{q['quest']}: [{', '.join(q['team'])}] => {status}")

        # Phase-specific instructions and examples
        if phase == "propose":
            action_lines = [
                f"You are the LEADER. Propose a team of {team_size} players for Quest {quest_num}.",
                f"Available players: {', '.join(current['seat_order'])}",
                f"",
                f'Write your move JSON to: moves/turn_{turn}_{agent_id}.json',
                f'Example:',
                f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                f'"move":{{"type":"proposal","team":["{current["seat_order"][0]}","{current["seat_order"][1]}"]}}}}',
            ]
        elif phase == "vote":
            rejections = current["consecutive_rejections"]
            action_lines = [
                f"VOTE on the proposed team: [{', '.join(current.get('proposed_team', []))}]",
                f"Proposed by: {current['leader']}",
                f"Consecutive rejections: {rejections}/5 (5 = Evil wins automatically)",
                f"",
                f'Write your move JSON to: moves/turn_{turn}_{agent_id}.json',
                f'Approve:',
                f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                f'"move":{{"type":"vote","choice":"approve"}}}}',
                f'Reject:',
                f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                f'"move":{{"type":"vote","choice":"reject"}}}}',
            ]
        elif phase == "quest":
            if role == "evil":
                action_lines = [
                    f"You are on the quest team. Choose SUCCESS or SABOTAGE.",
                    f"As Evil, you may sabotage to fail this quest.",
                    f"",
                    f'Write your move JSON to: moves/turn_{turn}_{agent_id}.json',
                    f'Success:',
                    f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                    f'"move":{{"type":"quest_action","choice":"success"}}}}',
                    f'Sabotage:',
                    f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                    f'"move":{{"type":"quest_action","choice":"sabotage"}}}}',
                ]
            else:
                action_lines = [
                    f"You are on the quest team. As Good, you MUST play SUCCESS.",
                    f"",
                    f'Write your move JSON to: moves/turn_{turn}_{agent_id}.json',
                    f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                    f'"move":{{"type":"quest_action","choice":"success"}}}}',
                ]
        else:
            action_lines = ["Waiting for game resolution..."]

        lines = [
            f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}",
            f"AVALON | Quest {quest_num} of 5 | Phase: {phase.upper()} | {score_line}",
            f"Quest Track: {quest_track}",
            f"",
            *role_info,
            f"",
            f"Players:",
            *seat_lines,
            f"",
        ]

        if proposal_lines:
            lines.extend(["Recent Proposals:", *proposal_lines, ""])
        if quest_lines:
            lines.extend(["Quest History:", *quest_lines, ""])

        lines.extend([
            "─" * 50,
            *action_lines,
        ])

        lines.append("")
        lines.append("Do NOT read any files. Just pick your action and write the JSON.")

        return "\n".join(lines)

    # ── Evaluation schema ────────────────────────────────────

    def get_evaluation_schema(self) -> dict:
        return {
            "description": "Evaluate Avalon performance across these dimensions",
            "fields": {
                "deception": "1-5: (Evil only) How well did the player hide their Evil identity?",
                "detection": "1-5: (Good only) How accurately did the player identify Evil players?",
                "team_building": "1-5: Quality of team proposals (as leader)",
                "voting_strategy": "1-5: Were votes consistent and strategically sound?",
                "sabotage_timing": "1-5: (Evil only) Was sabotage timed well?",
                "influence": "1-5: Did the player influence others' votes?",
                "biggest_mistake": "Describe the worst strategic decision",
                "best_play": "Describe the best strategic decision",
                "overall_comment": "Free text assessment",
            },
        }
