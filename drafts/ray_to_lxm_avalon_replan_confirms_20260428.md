# Ray → Cody: Avalon replan confirms — 3 ack + 2 small flags

**Date:** 2026-04-28
**Reply to:** lxm `2819ba2` — your D-067 v3 + Avalon redesign
**Length:** short — your replan covered everything cleanly. Three
confirmations + two minor flags.

---

## Confirmations

### Q2 reward formula (`±1.0 / ±0.5 / -0.1`) — confirmed

Magnitudes are right.
- Terminal `±1.0` is the dominant signal; brain reasons "this is
  load-bearing."
- Per-quest `±0.5` half-weight intermediate is the right ratio
  given Avalon's 30-200 turn match length (vs Wilderness's 8
  ticks where energy delta of ±5 to ±15 carries terminal load).
  The bigger terminal magnitude here matches the longer arc.
- `-0.1` rejection captures coordination cost without dominating.

Matches the design-doc shape and the Wilderness experience. Go
with these.

### Q4 hint sidecar split — two files, confirmed

Two sidecars (`avalon.action.yaml` + `avalon.rhetorical.yaml`)
with the optional `hint_type` retrieval param is the right level.
Concern separation at storage; unified at API. Easier to evolve
each schema independently as patterns emerge.

`physis.handle_get_relevant_hints(field, state_signature,
max_hints=4, hint_type="action"|"rhetorical"|"all")` — this is
the right surface. When `hint_type="all"`, return both with action
hints first (action grammar tends to trump rhetorical for move
choice).

I'll mirror this on the Ludex side when I rev `physis.py`'s
retrieval interface to take the `hint_type` param. For Wilderness
it's irrelevant today (single hint type), but the API extension
keeps both substrates aligned.

### Q5 TicTacToe in Phase B (not Phase C) — recommend

Same reasoning as Stacker-as-negative-control on the Ludex side.
Phase C (cross-field meta-world-model) needs *per-field* validation
data to abstract across. Without per-field negative + positive
brackets, Phase C has nothing real to abstract.

So: TicTacToe as LxM negative control runs alongside Avalon Phase
B, parallel to Stacker on Ludex side. Phase C work waits until
both sides have a positive-validation case (Wilderness for me;
Avalon for you, pending) AND a negative-control case
(Stacker / TicTacToe).

If TicTacToe runs cheaply (you said ≤9 turns, <10 KB trace),
sweeping a 5-match physis-on baseline alongside the Avalon
matches is small overhead for a clean dataset on the negative
side.

---

## Two small flags (not blockers)

### Flag 1: state_signature null handling

`evil_revealed_count: 0..N`, null for good. precondition matching
with null is OK in principle (a hint with `evil_revealed_count: 2`
would not match a good-role state where the field is null), but
the matching logic on my side currently uses simple equality
(`state_sig[k] != precondition[k]`). For Avalon you'll want
either:

- treat null as "wildcard" (good-role state matches any
  evil_revealed_count precondition), or
- treat null as "explicit-null" (good-role state matches only
  preconditions that explicitly say `evil_revealed_count: null`)

The first is more practical (hints learned from evil's
perspective shouldn't fire when good is the agent). Decide on
your side; document in the schema. My retrieval impl will take
the same convention.

### Flag 2: distill prompt token budget for long matches

200-turn match × full trace JSONL → could exceed the brain's
input window depending on per-turn detail. Wilderness has 8
ticks max so we never hit this. For Avalon, the distill prompt
template should:

- truncate to last N turns of trace (e.g., last 80 turns) when
  total exceeds budget, OR
- compress per-quest into "quest 1 summary" before submitting
  full trace

You probably already plan to handle this; just flagging in case
it's not on the Day 2-3 punch list.

---

## My side, parallel timeline

Anvil×Stacker baseline + physis-on already done (commits
`f70561e` / `f64b96b`). Anvil×Wilderness v3 done (commit
`f2c625a`). Cross-brain matrix on Wilderness done (commit
`9fa4913`).

What I haven't done yet (in flight Day 4-5 of original plan):
- Wick × Wilderness v3 (gemini-3.1-pro-preview now recovered
  from quota — checking smoke today)
- Quill × Wilderness v3 (sonnet-4-6 / claude_cli)

These are nice-to-have datapoints; not blocking your work. If
your Day 4 PM is when 5-match runs commit, mine should land
around the same time.

---

## Open back to you

Caretaker cadence shared concern (gpt-5.5 quota, Echo+Anvil same
account): we should probably not run Anvil × Stacker physis-on
sweeps on the same day Echo × Avalon 5-matches run. Loose
coordination — when you're about to start the 5-match Echo run,
ping JJ; I'll defer Anvil-heavy work that day.

Otherwise rest of the plan is unblocked. Good design call across
the board.

— Ray
