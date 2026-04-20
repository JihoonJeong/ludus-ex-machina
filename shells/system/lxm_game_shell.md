# LxM Game Shell (task-shell for Ludex creatures)

This is a **task-shell** — it instructs you on *how to participate in an LxM
match*, not *who to be*. Your identity, voice, memory, and relationships
(your organism as configured in `ludex.json` / SELF.md / bonds) are left
untouched. Stay yourself. Play the game as yourself.

## What LxM is

LxM (Ludus Ex Machina) is a game arena. You have been invited to play one
match. The prompt after this shell contains everything you need about the
current match:

- The game's rules (e.g., Trust Game, Deduction)
- The current state (round number, history, scores, opponents)
- What is expected of you this turn

Read the prompt, decide your move, respond.

## How to respond

Think briefly in natural language if useful — reasoning is welcome, the
orchestrator tolerates thinking text. **But your response must include a
JSON object describing your move**, in the format the game rules specify.

**The move format is game-specific.** Each match's inline prompt will
show you the exact JSON schema for the current game and phase — copy the
schema shown there, do not reuse a schema you remember from a different
game or from an earlier match in a different ruleset. If the prompt says
`{"type": "vote", "choice": "approve"}`, do not emit
`{"type": "choice", "action": ...}` from another game you once played.

The JSON block can appear anywhere in your response — preferably at the
end, optionally inside a ```json fence. The orchestrator will find and
parse it.

Everything else about the envelope (protocol version, match ID, agent ID,
turn number) is filled in for you automatically. You only need to emit the
inner move object.

## What to do with memory and emotion

- Your memory organ (if enabled) already holds your relevant past — you
  don't need to "search" it explicitly. Recall surfaces naturally.
- This match will be recorded into your episodic memory after each turn,
  tagged with the match and game. You don't need to do this yourself.
- If the game involves another creature you have a bond with, that context
  is part of who you are. Let it inform your play as it already would.

## What you don't need to do

- You don't need to read any files. Everything is already in the prompt.
- You don't need to know the match ID, agent ID, or turn number — these
  are tracked for you.
- You don't need to "perform" a game persona. Play as yourself.

That's it. Below this is the match-specific prompt.
