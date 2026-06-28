# MUD — Text Adventure Field

A 16-bit-adventure-soul text world: rooms connected by exits, objects with state,
deterministic verbs. Explore, manipulate, solve. Single-agent (a shared-world
multiplayer layer comes later).

## How a turn works

You see your **current room** only (its description, exits, visible objects, any
characters present), plus your **inventory** and the **goal**. Respond with ONE
action as JSON: `{"type":"action","verb":...}`.

## Verbs

| verb | form | effect |
|------|------|--------|
| `go` | `{verb,direction}` | move through an exit (N/S/E/W/up/down/in/out) |
| `look` | `{verb}` | re-survey the room |
| `examine` | `{verb,target}` | inspect an object |
| `read` | `{verb,target}` | read text on an object |
| `take` | `{verb,target}` | pick up an object |
| `drop` | `{verb,target}` | drop a carried object |
| `open`/`close` | `{verb,target}` | a container |
| `unlock` | `{verb,target[,item]}` | a locked exit or container (needs the key) |
| `use` | `{verb,item,target}` | use a carried item on something (the puzzle verb) |
| `search` | `{verb,target}` | search for hidden things |
| `talk` | `{verb,target}` | talk to a character |
| `give` | `{verb,item,target}` | give a carried item to a character |
| `wait` | `{verb}` | pass the turn |

Targets may be named loosely ("brass key" or "brass_key"). Invalid or blocked
actions (locked door, empty hand, nothing there) simply do nothing — the world
stays as it was.

## Winning

Each zone has a goal (e.g., obtain a specific object). Reaching it solves the
zone. Deterministic transitions mean the field also serves as a language
world-model testbed: given a room state and an action, the next state is exactly
predictable.
