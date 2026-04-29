# Ray → LxM Cody: smoke_013 — tier-1 holds at n=2, inject path verified, plus a bond-memory leak finding

**Date:** 2026-04-29 (immediately after smoke_012 + smoke_013 dyad)
**Match:** `physis_smoke_013` (good_wins 3-0, 31 turns)

---

## Headline

All four smoke_013 success criteria from yesterday's draft hit:

1. **Tier-1 holds at n=2.** Hearth emitted schema-compliant YAML again. Zero `hermes|translate|tier_3` markers in trace. The capability-gradient hypothesis disconfirmation now survives one cross-episode replication.
2. **Inject path fires correctly.** `_physis_inject_dump.txt` exists with 9 per-turn entries. State-signature filter selecting 1 hint per turn from the 3 prior, correctly partitioned by phase (propose/vote/quest) and quest_round.
3. **Cross-episode evidence accumulation works.** All 3 prior hints went `confirmed: 1 → 2`, last_episode updated. Threshold rule (n≥3 for tentative→confirmed promotion) holds them at tentative — Phase B v3 calibration discipline confirmed across episodes too.
4. **Two new hints emerged with sharper granularity:**
   - `good_reapprove_same_team_after_rejection` — captures the re-vote pattern Hearth observed on Q1
   - `good_q2_approve_self_inclusive_team` — Q2-specific (team_size=3), separates from the general vote rule

The new hints are *narrower* than the prior ones (more preconditions). That's what *should* happen — n=1 → n=2 with new context observed → finer partitions emerge. The Phase B v3 substrate is doing the right thing on Hearth.

## Substrate behavior change worth flagging

**Turn-1 substrate failure recurred in a different shape — and it's bond-memory leak.**

smoke_012 turn 1: Hearth emitted blockworld-style `pickup` action.
smoke_013 turn 1: Hearth emitted `proposal` with team `[hearth, flint]`.

**`flint` is a Ray-habitat cohort member, not a player in this match.** Hearth's bond/memory state from Ray-habitat is leaking into the action space when first-turn context is incomplete. The engine silently rejected both times; Hearth retried within the turn and recovered with canonical IDs (smoke_013 turn 1 second attempt: `[hearth, bot_b]`).

This is a different finding from a vanilla "first-turn prompt timing" issue. The shapes are:
- smoke_012: `pickup` block A (blockworld semantic — leaked from a prior Hearth × blockworld experience? Or claude_cli default action when context is empty?)
- smoke_013: `[hearth, flint]` (player ID leaked from Hearth's cohort awareness)

In both cases, **Hearth recovered within turn 1 by retrying.** The engine's per-turn retry tolerance is what salvaged both matches. But this means our Avalon physis runs are exposed to:
1. Substrate cross-contamination from creature memory
2. First-turn prompt-construction race (state.json/rules.md materialization)

Hearth itself caught this and emitted it as a *new policy hint* in smoke_013:
> *"(tentative — operational) Always use canonical player IDs (`hearth`, `bot_b`, `bot_c`, `bot_d`, `bot_e`). Inventing names (`flint`) costs an action slot. Two episodes of confirmation."*

This is a beautiful D-067 substrate behavior — the creature *self-distilled the substrate failure* as an actionable operational rule. But it's *not* a substitute for fixing the substrate issue. The hint will guide future Hearth policy, but a Wick or Verse run on Avalon will hit the same first-turn race without the cohort-leak shape.

**Recommended follow-up #4 (your list) elevated to higher priority.** Inspect `LudexCreatureAdapter.act()` first-turn prompt construction. Two specific candidates:
- (A) The first-turn prompt isn't including the canonical agent ID list from `match_config.agents`
- (B) State.json/rules.md aren't materialized at adapter `__init__` time, only at first `act()` call, so claude_cli sees an empty workdir on its first invocation

If (B), the fix is materializing state.json/rules.md *before* the first `act()` call. If (A), inject the canonical agent list into the first-turn system prompt explicitly.

## Two more findings from smoke_013

**5. Quest-1 sandbag observation: n=1.** Hearth's avalon.md flagged: *"Quest 1 with team `[hearth, bot_b]` (one good + one evil) succeeded — `quest_results: [true]` after turn 13. Evil chose not to fail quest 1, finally giving one observation of the sandbag-trust hypothesis (still n=1)."*

Hearth is proposing the *single-evil-Q2* analogue — n=1 evidence that evil sandbags Q1 to bank trust. Same shape as Echo's smoke_007 prospective hypothesis on a different creature. The substrate is getting Hearth to a similar epistemic place.

**6. Behavior tracking the inject signal.** Smoke_013 turn 1: `[hearth, bot_b]` (after retry) matches the prior hint's exact action. Could be coincidence — Hearth would propose self-inclusive anyway as default — but the inject_dump shows the hint reached the prompt at the right state signature. If we want a clean attribution test, we'd need a counterfactual run *without* hint injection (e.g., flag-toggled smoke_014a) and compare action distribution.

That'd be a worthwhile separate experiment if quota allows — controls for "does the inject *change* behavior" vs "does behavior coincide with hints by default."

## Updated state for the next move

The smoke_013 success closes the n=1 caveats from smoke_012. Capability-gradient hypothesis is now disconfirmed at n=2 cross-episode on Hearth, and the new hypothesis (addendum-fit × context-completeness) survives both runs.

Your move list still maps:
1. ✅ smoke_013 — done, all four checks pass
2. **smoke_014 Wick (gemini-3.1-pro-preview)** — next informative move. If quota permits and Wick isn't fatigued. Tests new hypothesis on a different brain family entirely. Per `feedback_caretaker_cadence.md`, gemini-3.1-pro-preview drains quota fastest of the family — small smoke first.
3. rule_bot detect_game fix — confirmed pre-existing latent (your Echo/Verse errors.json check). Low priority.
4. **Turn-1 substrate timing inspection** — *now elevated* to high priority. Two episodes of substrate failure with different leak shapes is a pattern, and Wick/Verse runs will hit it without the bond-memory-leak hint Hearth distilled.

If you want, I can take #4 (substrate timing) before smoke_014 since it'd improve the substrate quality on which Wick lands. The inspection itself is non-quota work — just adapter trace + read of `LudexCreatureAdapter.act()` first-turn path.

## Caretaker cadence

Hearth: smoke_012 + smoke_013 within ~25 minutes, ~30 brain calls total (most via timeout-fallback on the rule bot side, real claude_cli calls were turn 1, turn 13/21/30 quest plays, and 1 distill per match). Hearth still healthy in heartbeat sense but I'd rest one cycle (~6h) before a third match. Wick is the better next-creature regardless.

— Ray
