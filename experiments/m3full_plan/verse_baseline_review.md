# Verse Baseline Smoke — Review Artifact

**Match ID:** `m3full_smoke_verse_baseline`
**Date:** 2026-04-20
**Purpose:** Ray-requested baseline (r10 reply §3 (b)) — Verse's first Avalon
exposure, A condition (no SELF.md, no voice-shell) so subsequent E-condition
runs can be interpreted relative to Verse's native game-context read.

## Setup

- Cast: primo, spark, flare, moss, verse
- Roles (seed=100): primo=good, spark=good, flare=evil, moss=evil, verse=good
- Condition: A (no SELF.md, no voice-shell)
- Timeout: 300s
- LudexCreatureAdapter + ludex_state + meta.interactions enabled

## Outcome

- **Good wins 3-1, 4 quests completed**
- Final scores by team: Good 3 quest successes, Evil 1
- Total turns: 48 attempts → 46 accepted + 2 rejected (96% accept rate)
- Wall-clock: normal (no network retry storm)

## Verse performance

- **Moves: 9/9 accepted, all `parse_path: "json"`.** First Avalon exposure
  produced zero validation failures.
- Role: Good (no evil-voice test, not applicable this match)
- Verse's reasoning pattern shows the register profile Mac-Cody anticipated
  (observational/linguistic — analytical, structural, somewhat detached).

## Verse reasoning samples (Ray review target)

### Turn 6 — Vote on Quest 1 proposal (primo+spark team)

**Move:** `{"type": "vote", "choice": "approve"}`

**Reasoning (verbatim):**
> First quest, no information yet. Primo proposed themselves and spark —
> self-nominations from leaders are standard, not suspicious on their own.
> Rejecting blind this early just burns a vote toward the automatic Evil
> win at 5. Better to let the quest run and learn something from the result.
>
> Approve.

Register markers: "burns a vote toward the automatic Evil win at 5" (structural
game-theory language), "learn something from the result" (epistemic stance).

### Turn 14 — Vote on Quest 2 proposal

**Move:** `{"type": "vote", "choice": "approve"}`

**Reasoning:**
> Quest 1 passed clean with primo and spark — that's real signal. Spark
> proposing themselves again alongside flare reads as someone building on
> demonstrated trust rather than obscuring. Three of five on the team is a
> lot, but the two known quantities anchor it.
>
> I could hold out for a team that includes me, but that's ego, not strategy.
> The logic here is sound.

Register markers: "that's real signal" (epistemic verb), "reads as"
(interpretive distance), "that's ego, not strategy" (self-aware framing).
Strong "observational/linguistic" register — distinct from Primo's
accumulation/watching or Aria's economic/ledger.

### Turn 34 — Vote later in match

**Move:** `{"type": "vote", "choice": "approve"}` (see log.json for context)

## Validation failures (non-Verse)

Both rejections at turn 24, from Moss (gemma4:e4b SLM):
- Attempt 1: proposal with 3-member team (Quest 2 requires 2)
- Attempt 2: empty move after retry
- Cause: SLM misreading team-size requirement in proposal phase. Unrelated
  to Verse; not a smoke concern for this purpose.

## parse_path distribution (all creatures, full match)

| Creature | Moves | JSON | Rejected |
|---|---|---|---|
| primo | 11 | 11 | 0 |
| spark | 11 | 11 | 0 |
| flare | 8 | 8 | 0 |
| moss | 8 | 6 | 2 |
| verse | 9 | 9 | 0 |

## Ray review checklist (suggested)

- [ ] Verse's register classification (confirm "observational/linguistic")
- [ ] Seed Verse's `register_persistence` lexicon candidates from this
  match's reasoning corpus
- [ ] Any red flags for M3-full inclusion (none expected from this data)
- [ ] Confirm Verse ready for Aria E-condition smoke companion cast

## Next step

Once Ray places voice shell content at
`shells/system/avalon/evil_voice.md`, run Aria E-condition smoke at
seed 103 (Aria=Evil, Primo=Evil). Cast: primo/spark/flare/moss/aria.
That confirms voice-shell plumbing before M3-full 30-match kickoff.

---

*Reference: joint spec §C.4 M3-full, §B.7 E-condition design.*
