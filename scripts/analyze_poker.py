"""Poker process metrics analyzer.

Extracts from match logs:
1. Dealt card quality (hole card strength per model)
2. Behavioral stats (fold%, all-in freq, bluff freq, avg bet size, showdown win%)
3. Heads-up vs 4-player behavioral shifts
4. Luck vs skill separation (showdown wins vs bluff wins)
5. Seat position analysis (dealer button distribution, positional advantage)
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Agent-to-model mapping ──────────────────────────────────────────

AGENT_TO_MODEL = {
    "opus-player": "opus",
    "sonnet-player": "sonnet",
    "haiku-a": "haiku",
    "haiku-b": "haiku",
    "haiku-player": "haiku",
}


def get_model(agent_id: str) -> str:
    return AGENT_TO_MODEL.get(agent_id, agent_id)


# ── Pre-flop hole card strength ─────────────────────────────────────

# Simplified pre-flop tier system (Chen formula approximation)
# Returns tier 1-5 (1=premium, 5=trash)

RANK_VALUES = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10,
               "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2}


def hole_card_tier(c1: str, c2: str) -> int:
    """Classify hole cards into tiers 1-5."""
    if not c1 or not c2 or c1 == "??" or c2 == "??":
        return None

    r1, s1 = RANK_VALUES.get(c1[0], 0), c1[1]
    r2, s2 = RANK_VALUES.get(c2[0], 0), c2[1]
    high, low = max(r1, r2), min(r1, r2)
    suited = s1 == s2
    gap = high - low
    pair = high == low

    if pair:
        if high >= 11:  # JJ+
            return 1
        if high >= 8:   # 88-TT
            return 2
        if high >= 5:   # 55-77
            return 3
        return 4        # 22-44

    if suited:
        if high == 14 and low >= 11:  # AKs, AQs, AJs
            return 1
        if high == 14 and low >= 9:   # ATs, A9s
            return 2
        if high >= 12 and gap <= 2:   # KQs, KJs, QJs, JTs
            return 2
        if high == 14:                # Ax suited
            return 3
        if gap <= 2 and high >= 8:    # suited connectors 8+
            return 3
        return 4
    else:  # offsuit
        if high == 14 and low == 13:  # AKo
            return 1
        if high == 14 and low >= 11:  # AQo, AJo
            return 2
        if high == 14 and low >= 9:   # ATo, A9o
            return 3
        if high == 13 and low >= 11:  # KQo, KJo
            return 3
        if gap <= 1 and high >= 9:    # connectors 9+
            return 3
        return 5  # trash


def is_pair_plus(c1: str, c2: str) -> bool:
    """Is this a pocket pair or better pre-flop hand?"""
    if not c1 or not c2 or c1 == "??" or c2 == "??":
        return False
    return c1[0] == c2[0]


TIER_NAMES = {1: "Premium", 2: "Strong", 3: "Medium", 4: "Weak", 5: "Trash"}


# ── Parse matches ───────────────────────────────────────────────────

def parse_match(match_dir: Path) -> dict:
    """Parse a single match, extracting per-hand and per-action data."""
    state_path = match_dir / "state.json"
    log_path = match_dir / "log.json"
    config_path = match_dir / "match_config.json"

    if not all(p.exists() for p in [state_path, log_path, config_path]):
        return None

    state = json.loads(state_path.read_text())
    log = json.loads(log_path.read_text())
    config = json.loads(config_path.read_text())

    game = state["game"]
    context = game["context"]
    agents = [a["agent_id"] for a in config["agents"]]
    n_players = len(agents)

    match_type = "4p" if n_players == 4 else "hu"

    # ── Extract per-hand hole cards from log ──
    # Track the first action of each hand to get all hole cards
    hand_hole_cards = {}  # hand_num -> {agent_id: [c1, c2]}
    hand_dealer_seat = {}  # hand_num -> dealer_seat
    hand_sb_bb = {}  # hand_num -> (sb_id, bb_id)

    for entry in log:
        if entry.get("result") != "accepted":
            continue
        pms = entry.get("post_move_state", {})
        hand_num = pms.get("hand_number")
        if hand_num and hand_num not in hand_hole_cards:
            players = pms.get("players", {})
            hole_cards = {}
            for pid, pdata in players.items():
                hc = pdata.get("hole_cards", [])
                if hc and len(hc) == 2 and hc[0] != "??":
                    hole_cards[pid] = hc
            if hole_cards:
                hand_hole_cards[hand_num] = hole_cards
            hand_dealer_seat[hand_num] = pms.get("dealer_seat", 0)
            hand_sb_bb[hand_num] = (pms.get("_sb_id"), pms.get("_bb_id"))

    # ── Extract per-action stats from log ──
    actions_by_agent = defaultdict(list)  # agent_id -> list of action dicts

    for entry in log:
        if entry.get("result") != "accepted":
            continue
        agent_id = entry["agent_id"]
        envelope = entry.get("envelope", {})
        move = envelope.get("move", {})
        pms = entry.get("post_move_state", {})

        action = move.get("action")
        if not action:
            continue

        hand_num = pms.get("hand_number")
        phase = pms.get("phase", "")
        pot = pms.get("pot", 0)
        current_bet = pms.get("current_bet", 0)

        # Determine if this is pre-flop
        # Phase after action might have advanced, check community cards
        community_len = len(pms.get("community_cards", []))
        # Pre-flop = community_cards has 0 cards at action time
        # We need pre-action state. Use the entry itself.
        # Actually, the phase in post_move_state reflects the phase AFTER the action.
        # For pre-flop fold, phase might still be "pre_flop" or might have moved.
        # Better approach: track per-hand which phase each action was in.
        # We'll use a simpler heuristic based on the log ordering.

        actions_by_agent[agent_id].append({
            "hand": hand_num,
            "action": action,
            "amount": move.get("amount"),
            "pot_after": pot,
            "current_bet": current_bet,
            "phase_after": phase,
            "community_len": community_len,
        })

    # ── For more accurate phase tracking, rebuild per-hand action sequence ──
    hand_actions = defaultdict(list)  # hand_num -> list of (agent, action, phase_before)

    prev_hand = None
    prev_community_len = 0
    current_phase = "pre_flop"

    for entry in log:
        if entry.get("result") != "accepted":
            continue
        agent_id = entry["agent_id"]
        envelope = entry.get("envelope", {})
        move = envelope.get("move", {})
        pms = entry.get("post_move_state", {})
        action = move.get("action")
        if not action:
            continue

        hand_num = pms.get("hand_number")
        community_len = len(pms.get("community_cards", []))

        if hand_num != prev_hand:
            current_phase = "pre_flop"
            prev_community_len = 0
            prev_hand = hand_num

        # Phase BEFORE this action (based on community cards before the action caused a phase change)
        phase_before = current_phase

        # Update phase based on community cards after action
        if community_len > prev_community_len:
            if community_len == 3:
                current_phase = "flop"
            elif community_len == 4:
                current_phase = "turn"
            elif community_len == 5:
                current_phase = "river"
            prev_community_len = community_len

        # If phase changed after this action, it means this action ended the betting round
        phase_after = pms.get("phase", "")
        if phase_after in ("showdown", "hand_complete"):
            pass  # hand ended

        hand_actions[hand_num].append({
            "agent": agent_id,
            "action": action,
            "amount": move.get("amount"),
            "phase": phase_before,
            "pot_after": pms.get("pot", 0),
            "current_bet_after": pms.get("current_bet", 0),
        })

    return {
        "match_id": config["match_id"],
        "match_type": match_type,
        "agents": agents,
        "n_players": n_players,
        "hand_results": context["hand_results"],
        "showdown_history": context["showdown_history"],
        "bluff_history": context["bluff_history"],
        "hand_hole_cards": hand_hole_cards,
        "hand_dealer_seat": hand_dealer_seat,
        "hand_sb_bb": hand_sb_bb,
        "hand_actions": dict(hand_actions),
        "seat_order": game["current"]["seat_order"],
        "hands_played": context["hands_played"],
    }


# ── Compute metrics ─────────────────────────────────────────────────

def compute_metrics(matches: list[dict], match_type_filter: str = None) -> dict:
    """Compute all metrics across matches.

    match_type_filter: "hu" or "4p" or None for all.
    """
    if match_type_filter:
        matches = [m for m in matches if m["match_type"] == match_type_filter]

    if not matches:
        return {}

    # Per-model accumulators
    model_stats = defaultdict(lambda: {
        "total_hands_dealt": 0,
        "tier_counts": defaultdict(int),  # tier -> count
        "pair_plus_count": 0,
        # Actions
        "preflop_folds": 0,
        "preflop_actions": 0,
        "total_folds": 0,
        "total_checks": 0,
        "total_calls": 0,
        "total_raises": 0,
        "total_allins": 0,
        "total_actions": 0,
        "raise_amounts": [],  # (amount, pot_at_time)
        # Wins
        "showdown_wins": 0,
        "showdown_participations": 0,
        "bluff_wins": 0,
        "total_hands_won": 0,
        "total_pots_won": 0,
        # Seat/position
        "dealer_count": 0,
        "sb_count": 0,
        "bb_count": 0,
        # Per-hand chip tracking for cards
        "hands_with_cards": [],  # list of (tier, won_hand)
    })

    for match in matches:
        hand_results = match["hand_results"]
        hand_hole_cards = match["hand_hole_cards"]
        hand_actions = match["hand_actions"]
        hand_dealer_seat = match["hand_dealer_seat"]
        hand_sb_bb = match["hand_sb_bb"]
        seat_order = match["seat_order"]

        # Map agent IDs to models
        agents = match["agents"]

        # ── Card quality ──
        for hand_num, hole_cards in hand_hole_cards.items():
            for agent_id, cards in hole_cards.items():
                model = get_model(agent_id)
                stats = model_stats[model]
                stats["total_hands_dealt"] += 1

                tier = hole_card_tier(cards[0], cards[1])
                if tier:
                    stats["tier_counts"][tier] += 1
                if is_pair_plus(cards[0], cards[1]):
                    stats["pair_plus_count"] += 1

                # Check if this hand was won
                hr = next((r for r in hand_results if r["hand"] == hand_num), None)
                won = False
                if hr:
                    winners = hr.get("winners", [hr.get("winner")])
                    won = agent_id in winners
                stats["hands_with_cards"].append((tier, won))

        # ── Action stats ──
        for hand_num, actions in hand_actions.items():
            for act in actions:
                agent_id = act["agent"]
                model = get_model(agent_id)
                stats = model_stats[model]
                a = act["action"]
                phase = act["phase"]

                stats["total_actions"] += 1

                if a == "fold":
                    stats["total_folds"] += 1
                    if phase == "pre_flop":
                        stats["preflop_folds"] += 1
                elif a == "check":
                    stats["total_checks"] += 1
                elif a == "call":
                    stats["total_calls"] += 1
                elif a == "raise":
                    stats["total_raises"] += 1
                    if act["amount"]:
                        stats["raise_amounts"].append(
                            (act["amount"], act["pot_after"])
                        )
                elif a == "all_in":
                    stats["total_allins"] += 1

                if phase == "pre_flop":
                    stats["preflop_actions"] += 1

        # ── Showdown results ──
        for sd in match["showdown_history"]:
            winners = sd.get("winners", [])
            participants = list(sd.get("hands_shown", {}).keys())
            for pid in participants:
                model = get_model(pid)
                model_stats[model]["showdown_participations"] += 1
                if pid in winners:
                    model_stats[model]["showdown_wins"] += 1

        # ── Bluff wins ──
        for bluff in match["bluff_history"]:
            model = get_model(bluff["winner"])
            model_stats[model]["bluff_wins"] += 1

        # ── Total hands won ──
        for hr in hand_results:
            winners = hr.get("winners", [hr.get("winner")])
            for w in winners:
                if w:
                    model = get_model(w)
                    model_stats[model]["total_hands_won"] += 1
                    model_stats[model]["total_pots_won"] += hr.get("pot", 0)

        # ── Seat position ──
        for hand_num, dealer_seat in hand_dealer_seat.items():
            if dealer_seat < len(seat_order):
                dealer_agent = seat_order[dealer_seat]
                model = get_model(dealer_agent)
                model_stats[model]["dealer_count"] += 1

            sb_id, bb_id = hand_sb_bb.get(hand_num, (None, None))
            if sb_id:
                model_stats[get_model(sb_id)]["sb_count"] += 1
            if bb_id:
                model_stats[get_model(bb_id)]["bb_count"] += 1

    return dict(model_stats)


def print_report(model_stats: dict, title: str):
    """Print formatted report."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")

    models = sorted(model_stats.keys())

    # ── 1. Card Quality ──
    print(f"\n{'─' * 70}")
    print("  1. DEALT CARD QUALITY (Hole Card Strength)")
    print(f"{'─' * 70}")

    header = f"{'Metric':<25}" + "".join(f"{m:>12}" for m in models)
    print(header)
    print("-" * len(header))

    row = f"{'Hands dealt':<25}"
    for m in models:
        row += f"{model_stats[m]['total_hands_dealt']:>12}"
    print(row)

    row = f"{'Pair+ %':<25}"
    for m in models:
        s = model_stats[m]
        pct = s["pair_plus_count"] / s["total_hands_dealt"] * 100 if s["total_hands_dealt"] else 0
        row += f"{pct:>11.1f}%"
    print(row)

    for tier in range(1, 6):
        row = f"{'Tier ' + str(tier) + ' (' + TIER_NAMES[tier] + ')':<25}"
        for m in models:
            s = model_stats[m]
            count = s["tier_counts"].get(tier, 0)
            pct = count / s["total_hands_dealt"] * 100 if s["total_hands_dealt"] else 0
            row += f"{pct:>11.1f}%"
        print(row)

    # Expected tier distribution (rough baselines for random deal)
    print(f"\n  Expected (random): Pair ~5.9%, Tier1 ~3.6%, Tier2 ~8.6%, Tier3 ~14.9%, Tier4 ~17.2%, Tier5 ~55.7%")

    # ── 2. Behavioral Stats ──
    print(f"\n{'─' * 70}")
    print("  2. BEHAVIORAL STATS")
    print(f"{'─' * 70}")

    header = f"{'Metric':<25}" + "".join(f"{m:>12}" for m in models)
    print(header)
    print("-" * len(header))

    row = f"{'Total actions':<25}"
    for m in models:
        row += f"{model_stats[m]['total_actions']:>12}"
    print(row)

    row = f"{'Pre-flop fold %':<25}"
    for m in models:
        s = model_stats[m]
        pct = s["preflop_folds"] / s["preflop_actions"] * 100 if s["preflop_actions"] else 0
        row += f"{pct:>11.1f}%"
    print(row)

    row = f"{'Overall fold %':<25}"
    for m in models:
        s = model_stats[m]
        pct = s["total_folds"] / s["total_actions"] * 100 if s["total_actions"] else 0
        row += f"{pct:>11.1f}%"
    print(row)

    row = f"{'Check %':<25}"
    for m in models:
        s = model_stats[m]
        pct = s["total_checks"] / s["total_actions"] * 100 if s["total_actions"] else 0
        row += f"{pct:>11.1f}%"
    print(row)

    row = f"{'Call %':<25}"
    for m in models:
        s = model_stats[m]
        pct = s["total_calls"] / s["total_actions"] * 100 if s["total_actions"] else 0
        row += f"{pct:>11.1f}%"
    print(row)

    row = f"{'Raise %':<25}"
    for m in models:
        s = model_stats[m]
        pct = s["total_raises"] / s["total_actions"] * 100 if s["total_actions"] else 0
        row += f"{pct:>11.1f}%"
    print(row)

    row = f"{'All-in %':<25}"
    for m in models:
        s = model_stats[m]
        pct = s["total_allins"] / s["total_actions"] * 100 if s["total_actions"] else 0
        row += f"{pct:>11.1f}%"
    print(row)

    row = f"{'Avg raise/pot ratio':<25}"
    for m in models:
        s = model_stats[m]
        if s["raise_amounts"]:
            ratios = [amt / pot if pot > 0 else 0 for amt, pot in s["raise_amounts"]]
            avg = sum(ratios) / len(ratios)
            row += f"{avg:>11.2f}x"
        else:
            row += f"{'N/A':>12}"
    print(row)

    # ── 3. Win Stats ──
    print(f"\n{'─' * 70}")
    print("  3. WIN ANALYSIS (Luck vs Skill Separation)")
    print(f"{'─' * 70}")

    header = f"{'Metric':<25}" + "".join(f"{m:>12}" for m in models)
    print(header)
    print("-" * len(header))

    row = f"{'Hands won':<25}"
    for m in models:
        row += f"{model_stats[m]['total_hands_won']:>12}"
    print(row)

    row = f"{'Showdown wins':<25}"
    for m in models:
        row += f"{model_stats[m]['showdown_wins']:>12}"
    print(row)

    row = f"{'Bluff wins':<25}"
    for m in models:
        row += f"{model_stats[m]['bluff_wins']:>12}"
    print(row)

    row = f"{'Showdown win %':<25}"
    for m in models:
        s = model_stats[m]
        pct = s["showdown_wins"] / s["showdown_participations"] * 100 if s["showdown_participations"] else 0
        row += f"{pct:>11.1f}%"
    print(row)

    row = f"{'Bluff/Total wins %':<25}"
    for m in models:
        s = model_stats[m]
        total = s["total_hands_won"]
        pct = s["bluff_wins"] / total * 100 if total else 0
        row += f"{pct:>11.1f}%"
    print(row)

    row = f"{'Total pots won':<25}"
    for m in models:
        row += f"{model_stats[m]['total_pots_won']:>12}"
    print(row)

    row = f"{'Avg pot when won':<25}"
    for m in models:
        s = model_stats[m]
        avg = s["total_pots_won"] / s["total_hands_won"] if s["total_hands_won"] else 0
        row += f"{avg:>12.0f}"
    print(row)

    # ── 4. Seat Position ──
    print(f"\n{'─' * 70}")
    print("  4. SEAT POSITION ANALYSIS")
    print(f"{'─' * 70}")

    header = f"{'Position':<25}" + "".join(f"{m:>12}" for m in models)
    print(header)
    print("-" * len(header))

    row = f"{'Dealer (BTN) hands':<25}"
    for m in models:
        row += f"{model_stats[m]['dealer_count']:>12}"
    print(row)

    row = f"{'Small blind hands':<25}"
    for m in models:
        row += f"{model_stats[m]['sb_count']:>12}"
    print(row)

    row = f"{'Big blind hands':<25}"
    for m in models:
        row += f"{model_stats[m]['bb_count']:>12}"
    print(row)

    total_hands = sum(s["dealer_count"] for s in model_stats.values())
    if total_hands:
        row = f"{'Dealer % of total':<25}"
        for m in models:
            pct = model_stats[m]["dealer_count"] / total_hands * 100
            row += f"{pct:>11.1f}%"
        print(row)

    print()


def print_per_agent_report(matches: list[dict], match_type_filter: str, title: str):
    """Print per-agent (not per-model) report for haiku-a vs haiku-b analysis."""
    filtered = [m for m in matches if m["match_type"] == match_type_filter]
    if not filtered:
        return

    # Use agent IDs directly instead of mapping to model
    agent_stats = defaultdict(lambda: {
        "total_hands_dealt": 0,
        "pair_plus_count": 0,
        "preflop_folds": 0,
        "preflop_actions": 0,
        "total_folds": 0,
        "total_actions": 0,
        "total_raises": 0,
        "total_allins": 0,
        "showdown_wins": 0,
        "showdown_participations": 0,
        "bluff_wins": 0,
        "total_hands_won": 0,
        "dealer_count": 0,
    })

    for match in filtered:
        for hand_num, hole_cards in match["hand_hole_cards"].items():
            for agent_id, cards in hole_cards.items():
                stats = agent_stats[agent_id]
                stats["total_hands_dealt"] += 1
                if is_pair_plus(cards[0], cards[1]):
                    stats["pair_plus_count"] += 1

        for hand_num, actions in match["hand_actions"].items():
            for act in actions:
                agent_id = act["agent"]
                stats = agent_stats[agent_id]
                a = act["action"]
                stats["total_actions"] += 1
                if a == "fold":
                    stats["total_folds"] += 1
                    if act["phase"] == "pre_flop":
                        stats["preflop_folds"] += 1
                if act["phase"] == "pre_flop":
                    stats["preflop_actions"] += 1
                if a == "raise":
                    stats["total_raises"] += 1
                if a == "all_in":
                    stats["total_allins"] += 1

        for sd in match["showdown_history"]:
            winners = sd.get("winners", [])
            for pid in sd.get("hands_shown", {}).keys():
                agent_stats[pid]["showdown_participations"] += 1
                if pid in winners:
                    agent_stats[pid]["showdown_wins"] += 1

        for bluff in match["bluff_history"]:
            agent_stats[bluff["winner"]]["bluff_wins"] += 1

        for hr in match["hand_results"]:
            winners = hr.get("winners", [hr.get("winner")])
            for w in winners:
                if w:
                    agent_stats[w]["total_hands_won"] += 1

        for hand_num, dealer_seat in match["hand_dealer_seat"].items():
            seat_order = match["seat_order"]
            if dealer_seat < len(seat_order):
                agent_stats[seat_order[dealer_seat]]["dealer_count"] += 1

    agents = sorted(agent_stats.keys())
    print(f"\n{'─' * 70}")
    print(f"  {title} (Per-Agent Breakdown)")
    print(f"{'─' * 70}")

    header = f"{'Metric':<25}" + "".join(f"{a:>14}" for a in agents)
    print(header)
    print("-" * len(header))

    for label, key in [
        ("Hands dealt", "total_hands_dealt"),
        ("Pair+ %", None),
        ("Pre-flop fold %", None),
        ("All-in %", None),
        ("Hands won", "total_hands_won"),
        ("Showdown wins", "showdown_wins"),
        ("Bluff wins", "bluff_wins"),
        ("Dealer hands", "dealer_count"),
    ]:
        row = f"{label:<25}"
        for a in agents:
            s = agent_stats[a]
            if label == "Pair+ %":
                pct = s["pair_plus_count"] / s["total_hands_dealt"] * 100 if s["total_hands_dealt"] else 0
                row += f"{pct:>13.1f}%"
            elif label == "Pre-flop fold %":
                pct = s["preflop_folds"] / s["preflop_actions"] * 100 if s["preflop_actions"] else 0
                row += f"{pct:>13.1f}%"
            elif label == "All-in %":
                pct = s["total_allins"] / s["total_actions"] * 100 if s["total_actions"] else 0
                row += f"{pct:>13.1f}%"
            else:
                row += f"{s[key]:>14}"
        print(row)

    # Showdown win rate
    row = f"{'Showdown win %':<25}"
    for a in agents:
        s = agent_stats[a]
        pct = s["showdown_wins"] / s["showdown_participations"] * 100 if s["showdown_participations"] else 0
        row += f"{pct:>13.1f}%"
    print(row)

    print()


def print_hu_vs_4p_comparison(hu_stats: dict, fp_stats: dict):
    """Compare same models across HU vs 4P formats."""
    print(f"\n{'=' * 70}")
    print("  HEADS-UP vs 4-PLAYER BEHAVIORAL SHIFT")
    print(f"{'=' * 70}")

    models = sorted(set(hu_stats.keys()) & set(fp_stats.keys()))
    if not models:
        print("  No overlapping models to compare.")
        return

    header = f"{'Metric':<25}" + "".join(f"{m + ' HU':>10}{m + ' 4P':>10}" for m in models)
    print(header)
    print("-" * len(header))

    def pct(num, den):
        return num / den * 100 if den else 0

    for label, num_key, den_key in [
        ("Pre-flop fold %", "preflop_folds", "preflop_actions"),
        ("Overall fold %", "total_folds", "total_actions"),
        ("Raise %", "total_raises", "total_actions"),
        ("All-in %", "total_allins", "total_actions"),
        ("Bluff win % of total", "bluff_wins", "total_hands_won"),
        ("Showdown win %", "showdown_wins", "showdown_participations"),
    ]:
        row = f"{label:<25}"
        for m in models:
            hu = hu_stats.get(m, {})
            fp = fp_stats.get(m, {})
            hu_pct = pct(hu.get(num_key, 0), hu.get(den_key, 0))
            fp_pct = pct(fp.get(num_key, 0), fp.get(den_key, 0))
            row += f"{hu_pct:>9.1f}%{fp_pct:>9.1f}%"
        print(row)

    print()


# ── Main ────────────────────────────────────────────────────────────

def main():
    matches_dir = Path("matches")

    # Discover all poker matches
    poker_dirs = sorted(matches_dir.glob("poker_*"))
    poker_dirs = [d for d in poker_dirs if d.is_dir() and (d / "state.json").exists()]

    # Separate HU and 4P
    hu_dirs = [d for d in poker_dirs if "hu_" in d.name]
    fp_dirs = [d for d in poker_dirs if "4p_tournament" in d.name]

    print(f"Found {len(hu_dirs)} heads-up matches, {len(fp_dirs)} 4-player matches")

    # Parse all matches
    all_matches = []
    for d in hu_dirs + fp_dirs:
        m = parse_match(d)
        if m:
            all_matches.append(m)
            print(f"  Parsed: {m['match_id']} ({m['match_type']}, {m['hands_played']} hands)")
        else:
            print(f"  Skip: {d.name} (incomplete)")

    hu_matches = [m for m in all_matches if m["match_type"] == "hu"]
    fp_matches = [m for m in all_matches if m["match_type"] == "4p"]

    # ── Compute and print reports ──

    # All matches combined
    all_stats = compute_metrics(all_matches)
    print_report(all_stats, "ALL MATCHES COMBINED (HU + 4P)")

    # HU only
    hu_stats = compute_metrics(all_matches, "hu")
    if hu_stats:
        print_report(hu_stats, "HEADS-UP MATCHES ONLY")

    # 4P only
    fp_stats = compute_metrics(all_matches, "4p")
    if fp_stats:
        print_report(fp_stats, "4-PLAYER TOURNAMENT ONLY")

    # Per-agent breakdown for 4P (haiku-a vs haiku-b)
    print_per_agent_report(all_matches, "4p", "4-Player Tournament")

    # HU vs 4P comparison
    if hu_stats and fp_stats:
        print_hu_vs_4p_comparison(hu_stats, fp_stats)

    # ── Per-matchup HU breakdown ──
    print(f"\n{'=' * 70}")
    print("  PER-MATCHUP HEADS-UP BREAKDOWN")
    print(f"{'=' * 70}")

    matchups = defaultdict(list)
    for m in hu_matches:
        # Extract matchup from match_id
        mid = m["match_id"]
        # poker_hu_opus_sonnet_r1 -> opus_sonnet
        parts = mid.replace("poker_hu_", "").rsplit("_r", 1)
        matchup = parts[0]
        matchups[matchup].append(m)

    for matchup_name, mlist in sorted(matchups.items()):
        stats = compute_metrics(mlist)
        print_report(stats, f"HU: {matchup_name} ({len(mlist)} rounds)")

    # ── Summary interpretation ──
    print(f"\n{'=' * 70}")
    print("  INTERPRETATION GUIDE")
    print(f"{'=' * 70}")
    print("""
  Card Quality:
    If pair+ % or tier distribution deviates significantly from expected
    (pair ~5.9%), one model may have been dealt better cards. This is
    pure luck and should be controlled for before attributing wins to skill.

  Behavioral Profile:
    - High fold % = tight (conservative)
    - High raise/all-in % = aggressive
    - High bluff win % = skill indicator (winning without best cards)
    - High showdown win % could be luck (good cards) or skill (good reads)

  Luck vs Skill:
    - Bluff wins require NO card luck — pure behavioral skill
    - Showdown wins mix luck (card quality) and skill (hand selection)
    - If a model wins mostly through bluffs, that's skill
    - If a model wins mostly at showdown, check their card quality first

  Seat Position:
    - Dealer/BTN has last action advantage (most information)
    - If one model was dealer significantly more, position advantage
      could explain results, not skill difference
    """)


if __name__ == "__main__":
    main()
