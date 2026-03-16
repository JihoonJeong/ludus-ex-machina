"""Hand evaluation for Texas Hold'em using treys library."""

from treys import Card, Evaluator, Deck

_evaluator = Evaluator()

# Hand rank classes (treys uses 0-9, lower is better)
HAND_RANK_NAMES = {
    0: "Royal Flush",
    1: "Straight Flush",
    2: "Four of a Kind",
    3: "Full House",
    4: "Flush",
    5: "Straight",
    6: "Three of a Kind",
    7: "Two Pair",
    8: "Pair",
    9: "High Card",
}


def card_to_treys(card_str: str) -> int:
    """Convert 2-char card string (e.g. 'Ah', 'Tc') to treys int."""
    return Card.new(card_str)


def cards_to_treys(card_strs: list[str]) -> list[int]:
    """Convert list of card strings to treys ints."""
    return [Card.new(c) for c in card_strs]


def evaluate_hand(hole_cards: list[str], community_cards: list[str]) -> dict:
    """Evaluate a poker hand.

    Args:
        hole_cards: 2 card strings (e.g. ['Ah', 'Kd'])
        community_cards: 3-5 card strings

    Returns:
        {"score": int (lower=better), "rank_class": int, "rank_name": str, "description": str}
    """
    hand = cards_to_treys(hole_cards)
    board = cards_to_treys(community_cards)

    score = _evaluator.evaluate(board, hand)
    rank_class = _evaluator.get_rank_class(score)
    rank_name = HAND_RANK_NAMES.get(rank_class, "Unknown")
    description = _evaluator.class_to_string(rank_class)

    return {
        "score": score,
        "rank_class": rank_class,
        "rank_name": rank_name,
        "description": description,
    }


def compare_hands(
    hands: dict[str, list[str]], community_cards: list[str]
) -> list[tuple[str, dict]]:
    """Compare multiple hands against the same community cards.

    Args:
        hands: {agent_id: [hole_card1, hole_card2]}
        community_cards: 5 community cards

    Returns:
        List of (agent_id, eval_result) sorted best to worst.
    """
    results = []
    for agent_id, hole in hands.items():
        ev = evaluate_hand(hole, community_cards)
        results.append((agent_id, ev))

    # Sort by score (lower = better)
    results.sort(key=lambda x: x[1]["score"])
    return results


def find_winners(
    hands: dict[str, list[str]], community_cards: list[str]
) -> list[str]:
    """Find the winner(s) — may be multiple in case of a tie.

    Returns:
        List of agent_ids with the best hand (usually length 1).
    """
    ranked = compare_hands(hands, community_cards)
    if not ranked:
        return []

    best_score = ranked[0][1]["score"]
    return [aid for aid, ev in ranked if ev["score"] == best_score]


def make_deck() -> list[str]:
    """Create a shuffled 52-card deck as string representations."""
    ranks = "23456789TJQKA"
    suits = "hdcs"
    deck = [f"{r}{s}" for r in ranks for s in suits]
    import random
    random.shuffle(deck)
    return deck
