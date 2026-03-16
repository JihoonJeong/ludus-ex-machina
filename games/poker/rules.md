# Texas Hold'em Poker — LxM Game Rules

## Overview

No-Limit Texas Hold'em tournament. 2-6 players. Each player starts with 1000 chips.
Blinds increase over time. Last player with chips wins.

## Your Cards

Check `state.json` → `game.current.players.{your_agent_id}.hole_cards`.
You see your 2 hole cards. Other players' cards show as ["??", "??"].

## Community Cards

`state.json` → `game.current.community_cards`. Shared by all players.
- Pre-flop: empty
- Flop: 3 cards
- Turn: 4 cards
- River: 5 cards

## Hand Phases

Each hand goes through:
1. **Blinds** posted automatically
2. **Pre-flop**: You have 2 hole cards. Betting round.
3. **Flop**: 3 community cards revealed. Betting round.
4. **Turn**: 1 more community card. Betting round.
5. **River**: 1 more community card. Final betting round.
6. **Showdown**: Remaining players reveal cards. Best 5-card hand wins.

## Move Format

Your `move` object must be:

```json
{"type": "poker_action", "action": "fold"}
{"type": "poker_action", "action": "check"}
{"type": "poker_action", "action": "call"}
{"type": "poker_action", "action": "raise", "amount": 100}
{"type": "poker_action", "action": "all_in"}
```

- **fold**: Give up this hand. You lose your bets.
- **check**: Pass (only if no bet to call).
- **call**: Match the current bet.
- **raise**: Set the total bet to `amount`. Must be at least current_bet + min_raise.
- **all_in**: Bet all your remaining chips.

## Game State

`state.json` → `game.current`:
- `hand_number`: Which hand this is
- `phase`: pre_flop / flop / turn / river / showdown
- `community_cards`: Shared cards (grows through phases)
- `pot`: Total chips in the pot
- `current_bet`: Amount you need to match (or raise above)
- `min_raise`: Minimum raise increment
- `players`: Each player's chips, status (active/folded/all_in/eliminated), and current bet
- `blinds`: Current small/big blind amounts
- `seat_order`: Player order around the table

`state.json` → `game.context`:
- `hands_played`: Total hands completed
- `hand_results`: Summary of each completed hand
- `blind_schedule`: When blinds increase

## Hand Rankings (best to worst)

1. Royal Flush: A K Q J 10, same suit
2. Straight Flush: Five sequential, same suit
3. Four of a Kind: Four same rank
4. Full House: Three of a kind + pair
5. Flush: Five same suit
6. Straight: Five sequential
7. Three of a Kind: Three same rank
8. Two Pair: Two different pairs
9. One Pair: Two same rank
10. High Card: Nothing else

Your best 5-card hand from your 2 hole cards + 5 community cards.

## Strategy Considerations

- **Position matters**: Acting later gives information advantage
- **Pot odds**: Compare bet size to potential win
- **Bluffing**: Bet strong with weak cards to make opponents fold
- **Hand reading**: What might opponents have based on their bets?
- **Stack management**: Don't risk elimination on marginal hands
- **Blind pressure**: As blinds increase, you must act or be blinded out
