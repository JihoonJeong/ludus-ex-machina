"""Pot management for Texas Hold'em — main pot and side pots."""


def calculate_side_pots(players: dict) -> list[dict]:
    """Calculate main pot and side pots from player bets.

    Call this after all betting in a hand is complete (at showdown or
    when all but one player has folded).

    Args:
        players: {agent_id: {"total_bet_this_hand": int, "status": str}}
                 status is "active", "all_in", "folded", or "eliminated"

    Returns:
        List of pot dicts, ordered from main pot to smallest side pot:
        [{"amount": int, "eligible": [agent_ids]}, ...]
    """
    # Collect bets from non-folded, non-eliminated players who put money in
    bets = []
    for pid, p in players.items():
        bet = p.get("total_bet_this_hand", 0)
        if bet > 0:
            bets.append((pid, bet, p["status"]))

    if not bets:
        return []

    # All players who contributed (including folded — their money is in the pot)
    all_contributors = [(pid, bet) for pid, bet, _ in bets]

    # Eligible = not folded (active or all_in)
    eligible_players = {pid for pid, bet, status in bets if status != "folded"}

    # Sort by bet amount to build pots layer by layer
    all_contributors.sort(key=lambda x: x[1])

    pots = []
    prev_level = 0

    # Get unique bet levels from all-in players (these create pot boundaries)
    bet_levels = sorted(set(bet for _, bet in all_contributors))

    for level in bet_levels:
        # How many players contributed at least this level?
        pot_amount = 0
        pot_eligible = []

        for pid, bet in all_contributors:
            contribution = min(bet, level) - min(bet, prev_level)
            if contribution > 0:
                pot_amount += contribution
            # Eligible if they bet at least this level AND not folded
            if bet >= level and pid in eligible_players:
                pot_eligible.append(pid)

        if pot_amount > 0 and pot_eligible:
            pots.append({"amount": pot_amount, "eligible": pot_eligible})

        prev_level = level

    return pots


def distribute_pots(
    pots: list[dict], winners_by_pot: list[list[str]]
) -> dict[str, int]:
    """Distribute pot winnings.

    Args:
        pots: From calculate_side_pots()
        winners_by_pot: For each pot, list of winner agent_ids.
                        If multiple winners, pot is split evenly.

    Returns:
        {agent_id: chips_won}
    """
    winnings = {}

    for pot, winners in zip(pots, winners_by_pot):
        if not winners:
            continue
        share = pot["amount"] // len(winners)
        remainder = pot["amount"] % len(winners)

        for i, w in enumerate(winners):
            # First winner gets remainder (standard poker rule)
            award = share + (1 if i < remainder else 0)
            winnings[w] = winnings.get(w, 0) + award

    return winnings
