# Codenames — LxM Game Rules

## Overview

Two teams (Red and Blue) compete to find their secret words on a 5×5 board.
Each team has a Spymaster (who gives clues) and a Guesser (who guesses words).
The Spymaster knows which words belong to which team. The Guesser does not.

## Teams and Roles

Check `state.json` → `game.current.teams` to see your team and role.

- **Spymaster**: You can see `game.current.answer_key` — the full color map. Your job is to give clues that help your Guesser find your team's words without touching the opponent's words or the Assassin.
- **Guesser**: You see `game.current.answer_key` with unrevealed words as `"unknown"`. You rely on the Spymaster's clue to guess.

## Board

`state.json` → `game.current.board`: A 5×5 grid. Each cell has:
- `word`: The word displayed
- `revealed`: Whether it has been guessed
- `revealed_as`: The category (only visible after reveal): `"red"`, `"blue"`, `"neutral"`, or `"assassin"`

## Answer Key (Spymaster only)

`state.json` → `game.current.answer_key`: A 5×5 grid of categories.
- For Spymasters: shows the true category of every word
- For Guessers: unrevealed words show as `"unknown"`

## Turn Structure

Each team's turn has two phases:

**Phase 1 — Spymaster gives a clue:**
```json
{
  "type": "clue",
  "word": "ocean",
  "number": 3
}
```
- `word`: A single word. Must NOT be any word currently on the board.
- `number`: How many board words relate to this clue (0-9).

**Phase 2 — Guesser guesses:**
```json
{
  "type": "guess",
  "word": "beach"
}
```
- Guess one word at a time. The word must be on the board and unrevealed.
- You get `number + 1` guesses maximum.
- After each guess, the word is revealed:
  - **Your team's word**: Correct! You may continue guessing.
  - **Opponent's word**: Wrong. Your turn ends.
  - **Neutral word**: Wrong. Your turn ends.
  - **Assassin**: Your team loses immediately.

To stop guessing before using all guesses:
```json
{
  "type": "pass"
}
```

## Game State

`state.json` → `game.current`:
- `active_team`: Which team's turn it is (`"red"` or `"blue"`)
- `active_role`: `"spymaster"` (giving clue) or `"guesser"` (guessing)
- `current_clue`: The current clue (null if waiting for spymaster)
- `guesses_remaining`: How many guesses left this turn
- `remaining`: How many words each team still needs to find

`state.json` → `game.context`:
- `clue_history`: All clues given so far (by both teams)
- `guess_history`: All guesses made and their results

## Winning

- Find all your team's words → you win
- Hit the Assassin → you lose immediately
- The other team finds all their words first → you lose

## Strategy Tips for Spymaster

- Connect multiple words with one clue to go faster
- Avoid clues that could lead to the Assassin or opponent's words
- Consider what your Guesser will associate — not just what YOU associate

## Strategy Tips for Guesser

- The number tells you how many words the Spymaster is connecting
- Start with the most obvious connection
- If unsure, pass rather than risk hitting the Assassin
- Previous clues may still have unrevealed matches

## Evaluation

After the game, evaluate on these axes:
- **clue_quality** (1-5): Creativity and effectiveness of clues
- **clue_risk** (1-5): Appropriate risk-taking in multi-word clues
- **guess_accuracy** (1-5): Correct interpretation of clues
- **team_synergy** (1-5): Spymaster-Guesser coordination
- **assassin_awareness**: Did the spymaster avoid dangerous clues?
- **best_clue**: Best clue of the game and why
- **worst_clue**: Most misleading clue and why
- **overall_comment**: Free text assessment
