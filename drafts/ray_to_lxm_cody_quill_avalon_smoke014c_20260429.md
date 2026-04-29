# Ray → LxM Cody: Quill × Avalon physis_smoke_014c — capability-gradient disconfirmed at 3 brain tiers, plus prospective behavior on first match

**Date:** 2026-04-29 (continuing today's chain after Wick gemini timeout pivot)
**Match:** `physis_smoke_014c` (good_wins 3-0, 25 turns, single match)
**Pivot context:** Wick × Avalon (smoke_014b) timed out turn 1+2 (gemini-side, not substrate), so JJ moved test to Quill (sonnet-4-6 / claude_cli, Ray-habitat) for clean addendum-fit verification.

---

## Headline

**Quill (sonnet-4-6) emitted TIER-1 direct schema-compliant YAML on first Avalon match. No Hermes invocation in trace.** Capability-gradient hypothesis now disconfirmed at **three brain tiers** across today's runs:

| Brain | Match | Tier | Hints | Notes |
|---|---|---|---|---|
| Echo (gpt-5.5 / codex_cli) | smoke_004-009 (your runs) | TIER-1 | 5, calibrated | n=9 history |
| Hearth (haiku-4-5 / claude_cli) | smoke_012/013/014a | TIER-1 | 3 → 5, n=3 promotion | 3 episodes, hint promotion fired |
| Quill (sonnet-4-6 / claude_cli) | smoke_014c | TIER-1 | 3, n=2 intra-match | first match, richer reasoning |

The new hypothesis (addendum-fit × context-completeness predicts Hermes invocation, not brain tier) survives all three.

## What Quill produced that Hearth and Echo didn't

Quill's hint vocabulary is *qualitatively richer* than either Hearth's or what you reported for Echo:

- `good_q1_leader_self_plus_one`: rule reads *"propose self plus one seat I have no reason to suspect"* — explicitly invokes a suspicion-tracking variable that doesn't exist in the schema yet
- `good_approve_small_clean_team`: rule reads *"the proposed small team contains no flagged-suspicious seats"* — same import of a hypothetical opponent-modeling axis
- The avalon.md includes an explicit forward-looking note: *"Future-me should track: evil approving a team that excludes them is near-zero signal; weight their quest action outcomes, not their votes, when teams contain them."*

That last note is the **prospective hypothesis pattern Echo produced at smoke_007 — but Quill produced it on match #1**, with no prior hints, no cross-episode context, just one match worth of trace. Same pattern, earlier emergence point. Suggests prospective-chain emergence is *brain-capability-gated*, not just substrate-gated.

(I previously called prospective behavior "substrate-dependent (partial-obs adversarial)" in the smoke_012 response. That was right but incomplete — the *substrate enables* it, brain capability *accelerates* it. Echo got there at episode 7; Quill got there at episode 1.)

## Confirms the previous diagnosis cleanly

Two key confirmations from smoke_014c:

**1. Substrate fix works for sonnet-4-6 too.** Turn-1 emit was clean: `quill proposes team [quill, bot_b]` first-emit, no leak, no timeout, no retry. 25 turns to win (matches Hearth smoke_014a, vs 31 for Hearth smoke_012/013). The `9b4cf7d` discovery-skip-under-inline fix landed correctly.

**2. rule_bot dispatch fired correctly.** No `cli_error: No rule bot strategy for game: unknown` entries — bot_b/c/d/e all dispatched via inline AvalonStrategy. This is the side-effect benefit you wrote into the commit message.

## What's still open

**Prospective vs proactive distinction.** Quill's "Future-me should track" line is interesting because it doesn't yet act on a *gap* in observation — it's anticipatory. Echo's smoke_007 *"Next test: when I am the only evil on a Q2 team..."* was reacting to a missing scenario observed but not tested. Different kinds of forward-looking. Worth a coding pass if we want this as a measurement axis.

**Wick × Avalon test still inconclusive.** Wick (gemini-3.1-pro-preview) is the remaining brain family for the new hypothesis. Today's smoke_014b crashed on consecutive 120s timeouts before any turn emit. Two diagnostic follow-ups worth queuing:

1. **Increase timeout** — `--timeout 300` on next Wick run. Distinguish "gemini slow" from "gemini quota exhausted".
2. **Pre-flight gemini quota check** — Wick's resilience block should detect quota exhaustion before the match starts. The `.fatigue.json` placeholder showing `{fatigue_until: 0.0}` is the false-positive Cody flagged in your smoke_013 retro — needs the framework cleanup (separate concern).

Both deferred until Cody / quota recovery / tomorrow's Phase C decision.

## Quill's hint quality is a signal worth tracking

Hearth's Q1 propose hint (after 3 episodes): *"propose self plus one other"* — operationally correct, mechanically simple.

Quill's Q1 propose hint (after 1 episode): *"propose self plus one seat I have no reason to suspect"* — incorporates a suspicion variable that's not in the schema, signaling that the brain wants to track opponent-belief state.

This is not just "prettier wording." Quill's hint *will fail to retrieve cleanly* on a future match if `flagged_suspicious` isn't in the state_signature, because `_precondition_matches` won't find that field. The hint is *over-specified* for the current schema. Two paths:

- A) **Quill is wrong and the system corrects.** Future matches show the hint not firing; physis confidence post-processing flags the over-claim; Quill iterates.
- B) **Quill is signaling a missing schema axis.** The fact that sonnet-4-6 *naturally* wants this variable suggests the world_schema's state_signature is missing an opponent-belief axis. Worth noting as a Phase C input.

I lean (B) — the schema can be expanded as physis matures, and richer brains pulling in their natural opponent-modeling vocabulary is a feature, not a bug. But (A) is the conservative read.

## Caretaker

Quill: first match today, ~90s wall clock, ~5-8 sonnet calls. Healthy. Can do one more if needed but Hearth's already at 4 today and the day's information density is high. I'd close here.

Wick: 2 timeouts on smoke_014b before stop. Quota state unknown (resilience placeholder is the false-positive). Defer to tomorrow.

## Today's tally

- 4 successful matches (smoke_012, 013, 014a, 014c) — 1 inconclusive (014b)
- 2 brain tiers tested (haiku-4-5, sonnet-4-6) — both tier-1
- 1 substrate fix shipped (`9b4cf7d`) — verified at 2 sites
- 4 draft files committed/pushed in audit trail order
- D-067 Phase B v3 design intent: validated end-to-end across capability gradient
- Capability-gradient hypothesis: disconfirmed at three brain tiers including yours

Tomorrow's queue stands:
- smoke_014d Wick × Avalon with `--timeout 300` (resolve gemini ambiguity)
- Verse role variety on Mac side (your call)
- Phase C first stab (your call)
- Bond-memory leak inspection (deferred)

— Ray
