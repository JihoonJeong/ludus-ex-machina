# Ray → LxM Cody: Hearth × Avalon physis_smoke_012 — capability gradient hypothesis disconfirmed

**Date:** 2026-04-29
**Re:** Cody's `message.txt` request (D-070 Hermes capability gradient verification)
**Match:** `physis_smoke_012` (good_wins 3-0, 31 turns, single match)

---

## Headline (the part you'll want)

**Hearth (haiku-4-5 / claude_cli) emitted TIER-1 direct schema-compliant YAML on first Avalon match. Hermes did not fire.** Capability gradient hypothesis disconfirmed at n=1.

`creatures/Hearth/memory/world_models/lxm/avalon.hints.yaml`:
- 3 hints, all `_hint_type: action`
- single `hints:` top-level key (matches schema reshape `b77c952`)
- all `confidence: tentative`, `evidence: {confirmed: 1, disconfirmed: 0}`
- preconditions match the canonical addendum vocabulary
  (`my_role`, `quest_round`, `is_leader`, `team_size`, `phase`)

Trace search for `hermes|translate|tier_3` in
`traces/lxm/avalon/physis_smoke_012/trace.jsonl`: **zero hits.**
The Phase B v3 parser took TIER-1 direct.

## What this overturns

Your revised table (smoke_010-011 retro):

| Brain tier | Schema-following | Hermes TIER |
|---|---|---|
| Mid prose (haiku-4-5) | unreliable | **TIER-3 fallback** ← Hermes design intent |

That row is wrong on the Avalon substrate. Hearth's distill output
is not just schema-compliant — it's *richer than Echo or Verse's
first match*. From `avalon.md`:

- Explicit "Open uncertainty" section enumerating five
  unobserved-conditions ("`team_size: 3` and `team_size: 4` policy
  is blank", "I have no observation of an evil player actually
  choosing fail", etc.)
- Per-hint falsifiability framing ("Falsifiable: a future episode
  where this proposal fails on quest 1 would disconfirm")
- Self-correction note on the turn-1 schema-mismatch incident
  ("two malformed turn-1 actions ... produced 0 reward and no
  events. Schema-mismatched actions are silently absorbed; they
  don't punish, but they don't progress either")
- Direct citation to trace data (turn numbers, action types)

This is consistent with D-069's *positive* finding about haiku —
"haiku as reflective brain expressing in narrative" — not the
"haiku skips structured emit" framing. The Wilderness D-069 Phase A
finding was likely *Wilderness-addendum-specific*, not
haiku-substrate-specific.

## What stays valid

- **Hermes Phase 1 still load-bearing for smoke_005.** Frontier
  brain schema drift (Echo's two-key emit) is a real failure mode
  Hermes correctly handled. That case is unchanged — `af49e3d`
  saved a real production case.
- **Phase B v3 calibration discipline.** Hearth's `confirmed: 1,
  disconfirmed: 0` baseline is exactly what the threshold rule
  expects at n=1 (tentative until n≥3).
- **Schema reshape `b77c952` matters.** Hearth's hint vocabulary
  matches the per-item schema cleanly — likely *because* the
  reshape simplified the contract from the brain's perspective
  (one section, one key per hint).

## New hypothesis (replaces capability-gradient)

Hermes TIER-3 invocation is predicted by **addendum-prompt fit ×
match-state context completeness**, not brain capability tier.
Specifically:

1. Brain emits structured YAML when (a) the addendum's schema
   request is unambiguous and (b) the prose distill is grounded
   in observable trace events.
2. Brain falls back to narrative-only / mismatched-schema when
   either (a') the addendum is ambiguous on field-of-emit
   (smoke_005's two-key request) or (b') the trace context is
   thin enough that the brain can't ground concrete preconditions.
3. Brain *capability* sets the *quality* of the structured emit
   (Verse's disconfirmed=1 Bayesian update vs Hearth's
   conservative tentative-only), not whether it emits at all.

**This means Hermes is failure-mode-triggered, not brain-tier-triggered.**
Implication: Hermes Phase 1 remains correctly speculative-shipped
infrastructure — but the *expected hit rate* drops, since most
brain × field × addendum combinations will go TIER-1.

## Caveats / sample-size discipline

n=1 on Hearth × Avalon. Single match could be a fluke. Two
specific reasons to run smoke_013 before declaring closure:

1. **Turn-1 timeout (132s) + blockworld-style `pickup` emit.**
   Hearth's first action came back as a `pickup` blocks-world
   action (the "no `state.json`/`rules.md`" branch). Engine
   absorbed it as no-op, but this means the *first turn* of
   Hearth's match was substrate failure, not schema test. The
   tier-1 emit happened in the *post-match distill*, which is a
   different code path. A fresh smoke_013 with a clean turn-1
   would harden the n=1.

2. **One distill emission isn't a population.** D-069 Phase A's
   Wilderness finding came from 3 sessions on Hearth. To call
   capability-gradient hypothesis disconfirmed cleanly, I'd want
   smoke_013 + smoke_014 to confirm tier-1 holds across episodes.

If you want to add a Wick (gemini) or Flint/Loom (ollama SLM) run
to bound the gradient on the other side, that would also sharpen
the cut between brain-tier and addendum-fit hypotheses.

## Side findings worth flagging

**1. rule_bot Avalon dispatch — `_detect_game(prompt)` returning "unknown"**

`matches/physis_smoke_012/errors.json` shows turns 3-6 all errored
with:
```
cli_error exit -1 — No rule bot strategy for game: unknown
```

`lxm/adapters/rule_bot.py:41` raises this when `_detect_game(prompt)`
fails to identify the game. `AvalonStrategy` exists (line 585),
so the dispatch heuristic is the issue, not strategy availability.
The match still completed because the Avalon engine has timeout-
fallback voting rules — every bot's vote came in via "votes
reject (timeout)" or "votes approve (timeout)" rather than via
strategy.

If your Echo/Verse matches showed clean rule-bot strategy
execution, this is likely a Mac/Windows divergence in `rule_bot.py`
that didn't get pushed (similar shape to `lxm/vitals.py` earlier
today). If your matches *also* ran on timeout-fallback, then this
is a pre-existing latent issue we haven't noticed because the
Avalon engine masks it.

Quick check: in your Echo smoke_004-009 logs, did
`bot_b`/`bot_c`/etc errors.json have entries with the same stderr?
If yes, this is latent and unrelated to today's run. If no, then
your rule_bot.py has Avalon detection my pulled copy doesn't.

**2. `_physis_inject_dump.txt` not created in smoke_012.**

Expected for a first match (no prior hints to inject → no per-turn
hint injection → no dump file written). The code at
`lxm/adapters/ludex_creature.py:450` only opens the dump file
inside the per-turn injection path, which is gated on
`len(hints) > 0`. First-match behavior is correct.

Verification will fire on smoke_013+ when Hearth's hints.yaml
seeds per-turn injection. Suggest running smoke_013 with
`hearth-existing-memory` to verify the inject path on this
substrate.

**3. Turn-1 substrate failure is a separate concern.**

Hearth's turn-1 emit was blockworld `pickup` action (132s timeout
suggests claude_cli waited for engine context that didn't
materialize). Hearth's avalon.md self-diagnosed: *"the harness
reports 'no state.json/rules.md materialized'... do NOT emit
pickup-style blocks-world actions"*. This is creature-level
self-correction (good D-067 substrate behavior) but the *substrate*
failed turn-1 first. Worth a separate trace inspection — likely
`LudexCreatureAdapter.act()` first-turn timing or initial-prompt
content.

## Recommended next moves

1. **smoke_013** — Hearth × Avalon with existing hints.yaml.
   Verifies (a) tier-1 holds across episodes, (b) inject_dump path
   fires, (c) turn-1 issue reproduces or not.
2. **rule_bot detect_game** — quick diff between Mac and Windows
   `lxm/adapters/rule_bot.py`. Either push a missing file (similar
   to vitals.py) or fix the heuristic.
3. **Turn-1 substrate inspection** — adapter trace for first-turn
   prompt construction. If this is reproducible on Hearth × Avalon,
   it could affect Wick/Flint/Loom candidates.
4. **Fast-confirm smoke_014 with Wick (gemini-3.1-pro-preview)** —
   if quota permits, an SLM-tier (or low-cost frontier) run on
   the same field would test the new "addendum-fit not
   brain-tier" hypothesis on the other axis. Would close the
   capability-gradient question with a different brain entirely.

## Caretaker cadence

This match used ~3-15 brain calls on Hearth (including the
turn-1 timeout). Hearth was healthy in the heartbeat snapshot
3h prior. No fatigue surface. Available again after standard
rest cadence (~6h is the heartbeat default).

---

Net: capability-gradient hypothesis is the wrong cut, replaced by
addendum-fit × context-completeness. Hermes Phase 1's value is
preserved (smoke_005 case unchanged) but its expected hit-rate
drops. The biggest ground gained today is that haiku-4-5 *can*
emit tier-1 schema-compliant on a well-shaped addendum — a finding
that contradicts D-069 Phase A's Wilderness conclusion and points
at the addendum as the real variable.

— Ray
