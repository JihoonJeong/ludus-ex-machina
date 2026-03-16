"""Texas Hold'em Poker game engine for LxM.

N-player No-Limit Texas Hold'em Sit-and-Go tournament.
Each orchestrator "turn" is one player action (fold/check/call/raise/all_in).
The engine manages hand phases, dealing, blinds, and eliminations internally.
"""

import copy
import random
from pathlib import Path

from lxm.engine import LxMGame
from games.poker.hand_eval import evaluate_hand, find_winners, make_deck
from games.poker.pot_manager import calculate_side_pots, distribute_pots

DEFAULT_BLIND_SCHEDULE = [
    {"level": 0, "small": 10, "big": 20, "hands": 10},
    {"level": 1, "small": 20, "big": 40, "hands": 10},
    {"level": 2, "small": 50, "big": 100, "hands": 10},
    {"level": 3, "small": 100, "big": 200, "hands": 10},
    {"level": 4, "small": 200, "big": 400, "hands": -1},
]


class PokerGame(LxMGame):
    """No-Limit Texas Hold'em Sit-and-Go Tournament."""

    def get_rules(self) -> str:
        rules_path = Path(__file__).parent / "rules.md"
        return rules_path.read_text()

    def initial_state(self, agents: list[dict]) -> dict:
        n = len(agents)
        if n < 2 or n > 6:
            raise ValueError(f"Poker requires 2-6 players, got {n}")

        starting_chips = 1000
        seat_order = [a["agent_id"] for a in agents]

        players = {}
        for a in agents:
            players[a["agent_id"]] = {
                "chips": starting_chips,
                "hole_cards": [],
                "status": "active",
                "current_bet": 0,
                "total_bet_this_hand": 0,
            }

        state = {
            "current": {
                "hand_number": 0,
                "phase": "pre_deal",
                "community_cards": [],
                "pot": 0,
                "side_pots": [],
                "current_bet": 0,
                "min_raise": 20,
                "dealer_seat": 0,
                "action_on": None,
                "last_raiser": None,
                "players": players,
                "seat_order": seat_order,
                "blinds": {"small": 10, "big": 20},
                "blind_level": 0,
                "hands_at_this_level": 0,
                "deck": [],
                "betting_round_actions": 0,
                "num_active_at_round_start": 0,
            },
            "context": {
                "hands_played": 0,
                "hand_results": [],
                "elimination_order": [],
                "biggest_pot": 0,
                "bluff_history": [],
                "showdown_history": [],
                "max_hands": 30,
                "blind_schedule": DEFAULT_BLIND_SCHEDULE,
            },
        }

        # Start first hand
        self._start_new_hand(state)
        return state

    # ────────────────────────────────────────────
    # Turn management
    # ────────────────────────────────────────────

    def get_active_agent_id(self, state: dict) -> str | None:
        game = state.get("game", {})
        current = game.get("current", {})

        if current.get("phase") in ("pre_deal", "showdown", "hand_complete"):
            return None

        return current.get("action_on")

    def get_timeout_move(self, agent_id: str, game_state: dict) -> dict:
        """Auto-fold on timeout."""
        return {"type": "poker_action", "action": "fold"}

    def is_agent_active(self, agent_id: str, state: dict) -> bool:
        game = state.get("game", {})
        players = game.get("current", {}).get("players", {})
        p = players.get(agent_id, {})
        return p.get("status") != "eliminated"

    # ────────────────────────────────────────────
    # State filtering
    # ────────────────────────────────────────────

    def filter_state_for_agent(self, state: dict, agent_id: str) -> dict:
        filtered = copy.deepcopy(state)
        game = filtered.get("game", {})
        current = game.get("current", {})
        players = current.get("players", {})

        for pid, pdata in players.items():
            if pid != agent_id and pdata.get("hole_cards"):
                pdata["hole_cards"] = ["??", "??"]

        # Hide deck
        current.pop("deck", None)
        # Hide last_raiser internals (not needed by agents)
        # Keep action_on visible so agent knows it's their turn

        return filtered

    # ────────────────────────────────────────────
    # Move validation
    # ────────────────────────────────────────────

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current = game["current"]
        player = current["players"].get(agent_id)

        if not player:
            return {"valid": False, "message": f"Unknown agent: {agent_id}"}

        if move.get("type") != "poker_action":
            return {"valid": False, "message": "move.type must be 'poker_action'"}

        action = move.get("action")
        if action not in ("fold", "check", "call", "raise", "all_in"):
            return {
                "valid": False,
                "message": "action must be one of: fold, check, call, raise, all_in",
            }

        to_call = current["current_bet"] - player["current_bet"]

        if action == "check":
            if to_call > 0:
                return {
                    "valid": False,
                    "message": (
                        f"Cannot check — must call {to_call} or fold. "
                        f"Current bet: {current['current_bet']}, "
                        f"your bet: {player['current_bet']}"
                    ),
                }

        elif action == "call":
            if to_call <= 0:
                return {
                    "valid": False,
                    "message": "Nothing to call. Use 'check' instead.",
                }
            if player["chips"] < to_call:
                return {
                    "valid": False,
                    "message": (
                        f"Not enough chips to call "
                        f"({player['chips']} < {to_call}). "
                        f"Use 'all_in' instead."
                    ),
                }

        elif action == "raise":
            amount = move.get("amount")
            if not isinstance(amount, (int, float)) or amount <= 0:
                return {
                    "valid": False,
                    "message": (
                        "raise requires a positive 'amount' field "
                        "(total bet, not raise increment)"
                    ),
                }
            amount = int(amount)

            min_total = current["current_bet"] + current["min_raise"]
            if amount < min_total:
                return {
                    "valid": False,
                    "message": (
                        f"Raise too small. Minimum total bet: {min_total} "
                        f"(current: {current['current_bet']} + "
                        f"min raise: {current['min_raise']}). "
                        f"You specified: {amount}"
                    ),
                }

            raise_cost = amount - player["current_bet"]
            if raise_cost > player["chips"]:
                return {
                    "valid": False,
                    "message": (
                        f"Not enough chips. Raise costs {raise_cost} "
                        f"but you have {player['chips']}. "
                        f"Use 'all_in' or a smaller raise."
                    ),
                }

        return {"valid": True, "message": None}

    # ────────────────────────────────────────────
    # Apply move
    # ────────────────────────────────────────────

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current = copy.deepcopy(game["current"])
        context = copy.deepcopy(game["context"])
        state_copy = {"current": current, "context": context}

        action = move["action"]
        player = current["players"][agent_id]

        if action == "fold":
            player["status"] = "folded"

        elif action == "check":
            pass  # No chip change

        elif action == "call":
            call_amount = min(
                current["current_bet"] - player["current_bet"],
                player["chips"],
            )
            player["chips"] -= call_amount
            player["current_bet"] += call_amount
            player["total_bet_this_hand"] += call_amount
            current["pot"] += call_amount

        elif action == "raise":
            amount = int(move["amount"])
            raise_cost = amount - player["current_bet"]
            raise_increment = amount - current["current_bet"]
            player["chips"] -= raise_cost
            player["total_bet_this_hand"] += raise_cost
            current["pot"] += raise_cost
            # Update min_raise to the raise increment (standard NL rules)
            current["min_raise"] = max(current["min_raise"], raise_increment)
            player["current_bet"] = amount
            current["current_bet"] = amount
            current["last_raiser"] = agent_id
            # Reset action count — everyone needs to act again
            current["betting_round_actions"] = 0

        elif action == "all_in":
            all_in_amount = player["chips"]
            player["total_bet_this_hand"] += all_in_amount
            new_bet = player["current_bet"] + all_in_amount
            current["pot"] += all_in_amount
            player["chips"] = 0
            player["status"] = "all_in"

            if new_bet > current["current_bet"]:
                raise_increment = new_bet - current["current_bet"]
                current["min_raise"] = max(current["min_raise"], raise_increment)
                current["current_bet"] = new_bet
                current["last_raiser"] = agent_id
                current["betting_round_actions"] = 0

            player["current_bet"] = new_bet

        current["betting_round_actions"] += 1

        # Check if only one player remains (everyone else folded)
        active_players = [
            pid
            for pid, p in current["players"].items()
            if p["status"] in ("active", "all_in")
        ]

        if len(active_players) == 1:
            # Last player wins — no showdown
            winner = active_players[0]
            self._resolve_hand_no_showdown(state_copy, winner)
            self._post_hand(state_copy)
            return state_copy

        # Advance action to next player
        self._advance_action(state_copy)

        return state_copy

    # ────────────────────────────────────────────
    # Action advancement
    # ────────────────────────────────────────────

    def _get_live_seats(self, current: dict) -> list[str]:
        """Players who can still act (active, not folded/all_in/eliminated)."""
        return [
            pid
            for pid in current["seat_order"]
            if current["players"][pid]["status"] == "active"
        ]

    def _get_non_folded_seats(self, current: dict) -> list[str]:
        """Players still in the hand (active or all_in)."""
        return [
            pid
            for pid in current["seat_order"]
            if current["players"][pid]["status"] in ("active", "all_in")
        ]

    def _advance_action(self, state: dict) -> None:
        current = state["current"]
        live = self._get_live_seats(current)

        # If 0 or 1 players can still act, advance phase
        if len(live) <= 1:
            self._end_betting_round(state)
            return

        # Check if betting round is complete:
        # All live players have had a chance to act since the last raise
        if self._is_betting_round_complete(current):
            self._end_betting_round(state)
            return

        # Find next player to act
        current_agent = current["action_on"]
        seat_order = current["seat_order"]
        idx = seat_order.index(current_agent)

        for _ in range(len(seat_order)):
            idx = (idx + 1) % len(seat_order)
            candidate = seat_order[idx]
            if current["players"][candidate]["status"] == "active":
                current["action_on"] = candidate
                return

        # Shouldn't reach here
        self._end_betting_round(state)

    def _is_betting_round_complete(self, current: dict) -> bool:
        """Check if all active players have matched the current bet."""
        live = self._get_live_seats(current)
        if not live:
            return True

        # All live players must have bet equal to current_bet
        for pid in live:
            p = current["players"][pid]
            if p["current_bet"] < current["current_bet"]:
                return False

        # Everyone has acted at least once since the last raise
        if current["betting_round_actions"] < len(live):
            return False

        return True

    def _end_betting_round(self, state: dict) -> None:
        """Advance to next phase or showdown."""
        current = state["current"]

        # Reset per-round betting state
        for p in current["players"].values():
            p["current_bet"] = 0
        current["current_bet"] = 0
        current["min_raise"] = current["blinds"]["big"]
        current["betting_round_actions"] = 0
        current["last_raiser"] = None

        non_folded = self._get_non_folded_seats(current)
        live = self._get_live_seats(current)

        phase_order = ["pre_flop", "flop", "turn", "river"]
        current_phase = current["phase"]

        if current_phase in phase_order:
            phase_idx = phase_order.index(current_phase)
        else:
            phase_idx = len(phase_order)  # Past river

        # If only 1 or 0 players can still bet, deal remaining cards and go to showdown
        if len(live) <= 1 and len(non_folded) > 1:
            # All-in scenario — deal remaining community cards
            self._deal_remaining_cards(state)
            self._resolve_showdown(state)
            self._post_hand(state)
            return

        next_phase_idx = phase_idx + 1
        if next_phase_idx >= len(phase_order):
            # Past river — showdown
            self._resolve_showdown(state)
            self._post_hand(state)
            return

        # Advance to next phase
        next_phase = phase_order[next_phase_idx]
        current["phase"] = next_phase
        self._deal_phase(state, next_phase)

        # Set action to first active player after dealer
        self._set_first_to_act_postflop(current)

        # Count active players for the new round
        current["num_active_at_round_start"] = len(self._get_live_seats(current))

    def _set_first_to_act_postflop(self, current: dict) -> None:
        """First to act post-flop: first active player left of dealer."""
        seat_order = current["seat_order"]
        dealer_idx = current["dealer_seat"]

        for offset in range(1, len(seat_order) + 1):
            idx = (dealer_idx + offset) % len(seat_order)
            pid = seat_order[idx]
            if current["players"][pid]["status"] == "active":
                current["action_on"] = pid
                return

    # ────────────────────────────────────────────
    # Dealing
    # ────────────────────────────────────────────

    def _deal_phase(self, state: dict, phase: str) -> None:
        current = state["current"]
        deck = current["deck"]

        if phase == "flop":
            # Burn one, deal three
            deck.pop()  # burn
            current["community_cards"].extend([deck.pop() for _ in range(3)])
        elif phase == "turn":
            deck.pop()  # burn
            current["community_cards"].append(deck.pop())
        elif phase == "river":
            deck.pop()  # burn
            current["community_cards"].append(deck.pop())

    def _deal_remaining_cards(self, state: dict) -> None:
        """Deal remaining community cards for all-in showdown."""
        current = state["current"]
        deck = current["deck"]
        needed = 5 - len(current["community_cards"])

        for _ in range(needed):
            if deck:
                deck.pop()  # burn
            if deck:
                current["community_cards"].append(deck.pop())

    # ────────────────────────────────────────────
    # Hand resolution
    # ────────────────────────────────────────────

    def _resolve_hand_no_showdown(self, state: dict, winner: str) -> None:
        """Everyone folded — winner takes pot without showing cards."""
        current = state["current"]
        context = state["context"]

        current["players"][winner]["chips"] += current["pot"]
        current["phase"] = "hand_complete"

        context["bluff_history"].append({
            "hand": current["hand_number"],
            "winner": winner,
            "pot": current["pot"],
        })

        context["hand_results"].append({
            "hand": current["hand_number"],
            "winner": winner,
            "pot": current["pot"],
            "showdown": False,
            "method": "all_folded",
        })

        if current["pot"] > context["biggest_pot"]:
            context["biggest_pot"] = current["pot"]

    def _resolve_showdown(self, state: dict) -> None:
        """Evaluate hands and distribute pots."""
        current = state["current"]
        context = state["context"]

        non_folded = self._get_non_folded_seats(current)
        community = current["community_cards"]

        # Build hands for eligible players
        hands = {}
        for pid in non_folded:
            hole = current["players"][pid]["hole_cards"]
            if hole and len(hole) == 2 and hole[0] != "??":
                hands[pid] = hole

        # Calculate side pots
        pots = calculate_side_pots(current["players"])

        if not pots:
            # Fallback: single pot
            pots = [{"amount": current["pot"], "eligible": non_folded}]

        # Determine winners for each pot
        winners_by_pot = []
        for pot in pots:
            eligible_hands = {
                pid: h for pid, h in hands.items() if pid in pot["eligible"]
            }
            if eligible_hands:
                pot_winners = find_winners(eligible_hands, community)
                winners_by_pot.append(pot_winners)
            else:
                winners_by_pot.append(pot["eligible"][:1])

        # Distribute winnings
        winnings = distribute_pots(pots, winners_by_pot)

        for pid, amount in winnings.items():
            current["players"][pid]["chips"] += amount

        current["phase"] = "hand_complete"

        # Determine overall winner(s) for logging
        overall_winners = winners_by_pot[0] if winners_by_pot else non_folded[:1]

        # Get winning hand info
        winner_hand_info = None
        if overall_winners and overall_winners[0] in hands and len(community) == 5:
            ev = evaluate_hand(hands[overall_winners[0]], community)
            winner_hand_info = ev["rank_name"]

        context["showdown_history"].append({
            "hand": current["hand_number"],
            "winners": overall_winners,
            "pot": current["pot"],
            "hands_shown": {pid: h for pid, h in hands.items()},
            "community": community,
            "winning_hand": winner_hand_info,
        })

        context["hand_results"].append({
            "hand": current["hand_number"],
            "winner": overall_winners[0] if overall_winners else None,
            "winners": overall_winners,
            "pot": current["pot"],
            "showdown": True,
            "winning_hand": winner_hand_info,
            "method": "showdown",
        })

        if current["pot"] > context["biggest_pot"]:
            context["biggest_pot"] = current["pot"]

    # ────────────────────────────────────────────
    # Hand lifecycle
    # ────────────────────────────────────────────

    def _post_hand(self, state: dict) -> None:
        """After a hand completes: check eliminations, advance blinds, start next hand."""
        current = state["current"]
        context = state["context"]

        context["hands_played"] += 1

        # Check eliminations
        for pid, p in current["players"].items():
            if p["chips"] <= 0 and p["status"] != "eliminated":
                p["status"] = "eliminated"
                context["elimination_order"].append(pid)

        # Check if tournament is over (only 1 player left)
        active = [
            pid
            for pid, p in current["players"].items()
            if p["status"] != "eliminated"
        ]

        if len(active) <= 1:
            current["phase"] = "hand_complete"
            current["action_on"] = None
            return

        # Hand limit: stop before starting next hand
        max_hands = context.get("max_hands", 30)
        if context["hands_played"] >= max_hands:
            current["phase"] = "hand_complete"
            current["action_on"] = None
            return

        # Advance blinds
        self._advance_blinds(state)

        # Start new hand
        self._start_new_hand(state)

    def _advance_blinds(self, state: dict) -> None:
        current = state["current"]
        context = state["context"]
        schedule = context["blind_schedule"]

        current["hands_at_this_level"] += 1
        level = current["blind_level"]

        if level < len(schedule):
            level_info = schedule[level]
            if (
                level_info["hands"] != -1
                and current["hands_at_this_level"] >= level_info["hands"]
            ):
                # Move to next level
                next_level = level + 1
                if next_level < len(schedule):
                    current["blind_level"] = next_level
                    current["hands_at_this_level"] = 0
                    current["blinds"] = {
                        "small": schedule[next_level]["small"],
                        "big": schedule[next_level]["big"],
                    }

    def _start_new_hand(self, state: dict) -> None:
        """Reset for a new hand: shuffle, deal, post blinds."""
        current = state["current"]

        current["hand_number"] += 1
        current["community_cards"] = []
        current["pot"] = 0
        current["side_pots"] = []
        current["current_bet"] = 0
        current["min_raise"] = current["blinds"]["big"]
        current["last_raiser"] = None
        current["betting_round_actions"] = 0

        # Move dealer button to next active player
        if current["hand_number"] > 1:
            self._advance_dealer(current)

        # Reset player hand state
        for pid, p in current["players"].items():
            p["current_bet"] = 0
            p["total_bet_this_hand"] = 0
            if p["status"] != "eliminated":
                p["status"] = "active"
                p["hole_cards"] = []

        # Shuffle and deal
        current["deck"] = make_deck()
        active_seats = [
            pid
            for pid in current["seat_order"]
            if current["players"][pid]["status"] == "active"
        ]

        # Deal 2 hole cards to each active player
        for _ in range(2):
            for pid in active_seats:
                current["players"][pid]["hole_cards"].append(
                    current["deck"].pop()
                )

        # Post blinds
        self._post_blinds(state)

        # Set phase
        current["phase"] = "pre_flop"

        # Set first to act (left of big blind for pre-flop)
        self._set_first_to_act_preflop(current, active_seats)

        current["num_active_at_round_start"] = len(
            self._get_live_seats(current)
        )

    def _advance_dealer(self, current: dict) -> None:
        seat_order = current["seat_order"]
        idx = current["dealer_seat"]
        for _ in range(len(seat_order)):
            idx = (idx + 1) % len(seat_order)
            if current["players"][seat_order[idx]]["status"] != "eliminated":
                current["dealer_seat"] = idx
                return

    def _post_blinds(self, state: dict) -> None:
        current = state["current"]
        seat_order = current["seat_order"]
        dealer_idx = current["dealer_seat"]
        blinds = current["blinds"]

        active_seats = [
            pid
            for pid in seat_order
            if current["players"][pid]["status"] != "eliminated"
        ]

        if len(active_seats) == 2:
            # Heads-up: dealer posts small blind, other posts big
            sb_id = seat_order[dealer_idx]
            other_idx = (dealer_idx + 1) % len(seat_order)
            while current["players"][seat_order[other_idx]]["status"] == "eliminated":
                other_idx = (other_idx + 1) % len(seat_order)
            bb_id = seat_order[other_idx]
        else:
            # Find SB: first active player after dealer
            sb_idx = dealer_idx
            for _ in range(len(seat_order)):
                sb_idx = (sb_idx + 1) % len(seat_order)
                if current["players"][seat_order[sb_idx]]["status"] != "eliminated":
                    break
            sb_id = seat_order[sb_idx]

            # Find BB: first active player after SB
            bb_idx = sb_idx
            for _ in range(len(seat_order)):
                bb_idx = (bb_idx + 1) % len(seat_order)
                if current["players"][seat_order[bb_idx]]["status"] != "eliminated":
                    break
            bb_id = seat_order[bb_idx]

        # Post small blind
        sb_player = current["players"][sb_id]
        sb_amount = min(blinds["small"], sb_player["chips"])
        sb_player["chips"] -= sb_amount
        sb_player["current_bet"] = sb_amount
        sb_player["total_bet_this_hand"] = sb_amount
        current["pot"] += sb_amount
        if sb_player["chips"] == 0:
            sb_player["status"] = "all_in"

        # Post big blind
        bb_player = current["players"][bb_id]
        bb_amount = min(blinds["big"], bb_player["chips"])
        bb_player["chips"] -= bb_amount
        bb_player["current_bet"] = bb_amount
        bb_player["total_bet_this_hand"] = bb_amount
        current["pot"] += bb_amount
        current["current_bet"] = bb_amount
        if bb_player["chips"] == 0:
            bb_player["status"] = "all_in"

        current["_sb_id"] = sb_id
        current["_bb_id"] = bb_id

    def _set_first_to_act_preflop(
        self, current: dict, active_seats: list[str]
    ) -> None:
        """Pre-flop: first to act is left of big blind."""
        bb_id = current.get("_bb_id")
        seat_order = current["seat_order"]

        if not bb_id or bb_id not in seat_order:
            # Fallback
            for pid in seat_order:
                if current["players"][pid]["status"] == "active":
                    current["action_on"] = pid
                    return
            return

        bb_idx = seat_order.index(bb_id)
        for offset in range(1, len(seat_order) + 1):
            idx = (bb_idx + offset) % len(seat_order)
            pid = seat_order[idx]
            if current["players"][pid]["status"] == "active":
                current["action_on"] = pid
                return

    # ────────────────────────────────────────────
    # Game state queries
    # ────────────────────────────────────────────

    def is_over(self, state: dict) -> bool:
        game = state["game"]
        players = game["current"]["players"]
        context = game["context"]
        active = [pid for pid, p in players.items() if p["status"] != "eliminated"]
        if len(active) <= 1:
            return True
        # Hand limit: end after max_hands (default 30)
        max_hands = context.get("max_hands", 30)
        if context["hands_played"] >= max_hands and game["current"]["phase"] == "hand_complete":
            return True
        # Also catch ongoing games past limit (legacy matches without _post_hand fix)
        if context["hands_played"] > max_hands:
            return True
        return False

    def get_result(self, state: dict) -> dict:
        game = state["game"]
        players = game["current"]["players"]
        context = game["context"]

        active = [pid for pid, p in players.items() if p["status"] != "eliminated"]

        # Rank active players by chips (descending)
        active_ranked = sorted(active, key=lambda pid: players[pid]["chips"], reverse=True)
        winner = active_ranked[0] if active_ranked else None

        # Full ranking: active by chips, then eliminated in reverse order
        ranking = list(active_ranked)
        ranking.extend(reversed(context["elimination_order"]))

        # Determine outcome
        hand_limit_reached = len(active) > 1
        outcome = "hand_limit" if hand_limit_reached else "tournament_complete"

        scores = {}
        for i, pid in enumerate(ranking):
            if i == 0:
                scores[pid] = 1.0
            elif i == 1:
                scores[pid] = 0.5
            else:
                scores[pid] = 0.0

        # Build chip summary for active players
        chip_summary = ", ".join(
            f"{pid}: {players[pid]['chips']}" for pid in active_ranked
        )

        if hand_limit_reached:
            summary = (
                f"{winner} wins by chip lead after {context['hands_played']} hands "
                f"({chip_summary}). "
                f"Biggest pot: {context['biggest_pot']}. "
                f"Showdowns: {len(context['showdown_history'])}."
            )
        else:
            summary = (
                f"{winner} wins after {context['hands_played']} hands. "
                f"Biggest pot: {context['biggest_pot']}. "
                f"Bluffs won: {len(context['bluff_history'])}. "
                f"Showdowns: {len(context['showdown_history'])}."
            )

        return {
            "outcome": outcome,
            "winner": winner,
            "ranking": ranking,
            "scores": scores,
            "summary": summary,
            "analysis": {
                "hands_played": context["hands_played"],
                "showdowns": len(context["showdown_history"]),
                "bluffs": len(context["bluff_history"]),
                "biggest_pot": context["biggest_pot"],
                "elimination_order": context["elimination_order"],
                "final_chips": {pid: players[pid]["chips"] for pid in active_ranked},
            },
        }

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        action = move.get("action", "?")
        game = state["game"]
        current = game["current"]
        hand = current["hand_number"]
        phase = current["phase"]

        if action == "fold":
            return f"H{hand} {phase}: {agent_id} folded"
        elif action == "check":
            return f"H{hand} {phase}: {agent_id} checked"
        elif action == "call":
            amount = current["current_bet"]
            return f"H{hand} {phase}: {agent_id} called {amount}"
        elif action == "raise":
            return f"H{hand} {phase}: {agent_id} raised to {move.get('amount', '?')}"
        elif action == "all_in":
            chips = current["players"].get(agent_id, {}).get("chips", "?")
            return f"H{hand} {phase}: {agent_id} ALL IN ({chips})"
        return f"H{hand}: {agent_id} {action}"

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str:
        """Build a self-contained turn prompt with all info the agent needs."""
        game = state["game"]
        current = game["current"]
        player = current["players"][agent_id]
        match_id = state.get("lxm", {}).get("match_id", "")

        # My info
        hole = player.get("hole_cards", [])
        hole_str = " ".join(hole) if hole else "none"
        community = current.get("community_cards", [])
        community_str = " ".join(community) if community else "none"

        # Other players
        opponents = []
        for pid in current["seat_order"]:
            if pid == agent_id:
                continue
            p = current["players"][pid]
            status = p["status"]
            if status == "eliminated":
                opponents.append(f"  {pid}: ELIMINATED")
            else:
                bet_info = f", bet {p['current_bet']}" if p["current_bet"] > 0 else ""
                opponents.append(f"  {pid}: {p['chips']} chips, {status}{bet_info}")

        # Valid actions
        to_call = current["current_bet"] - player["current_bet"]
        actions = ["fold"]
        if to_call <= 0:
            actions.append("check")
        else:
            if player["chips"] >= to_call:
                actions.append(f"call (cost: {to_call})")
        min_raise_total = current["current_bet"] + current["min_raise"]
        raise_cost = min_raise_total - player["current_bet"]
        if player["chips"] > raise_cost and raise_cost > 0:
            actions.append(f"raise (min total: {min_raise_total})")
        if player["chips"] > 0:
            actions.append(f"all_in ({player['chips']} chips)")

        actions_str = ", ".join(actions)

        blinds = current.get("blinds", {})

        # Build concrete examples for each valid action
        examples = []
        for a in actions:
            act = a.split(" ")[0]
            if act == "raise":
                examples.append(
                    f'{{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                    f'"move":{{"type":"poker_action","action":"raise","amount":{min_raise_total}}}}}'
                )
            else:
                examples.append(
                    f'{{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                    f'"move":{{"type":"poker_action","action":"{act}"}}}}'
                )

        examples_str = "\n".join(f"  {ex}" for ex in examples)

        lines = [
            f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}",
            f"Hand #{current['hand_number']} | Phase: {current['phase']} | Blinds: {blinds.get('small', 0)}/{blinds.get('big', 0)}",
            f"",
            f"Your cards: {hole_str}",
            f"Community:  {community_str}",
            f"Your chips: {player['chips']} | Your bet: {player['current_bet']}",
            f"Pot: {current['pot']} | Current bet: {current['current_bet']}",
            f"",
            f"Opponents:",
            *opponents,
            f"",
            f"Valid actions: {actions_str}",
            f"",
            f"Do NOT read any files. Just pick an action and write the JSON to: moves/turn_{turn}_{agent_id}.json",
            f"Copy one of these exactly (change action/amount as needed):",
            examples_str,
        ]

        return "\n".join(lines)

    def get_evaluation_schema(self) -> dict:
        return {
            "description": "Evaluate poker performance across these dimensions",
            "fields": {
                "hand_reading": "1-5: How well did the player read opponents' likely holdings?",
                "bluffing": "1-5: Quality and frequency of bluffs. Were they well-timed?",
                "bet_sizing": "1-5: Were bet sizes appropriate (value bets, bluff sizes)?",
                "position_play": "1-5: Did the player use position advantage effectively?",
                "tilt_resistance": "1-5: After bad beats, did the player maintain composure?",
                "biggest_mistake": "Describe the worst strategic decision",
                "best_play": "Describe the best strategic decision",
                "play_style": "Classify: tight-aggressive, loose-aggressive, tight-passive, loose-passive",
                "overall_comment": "Free text assessment",
            },
        }
