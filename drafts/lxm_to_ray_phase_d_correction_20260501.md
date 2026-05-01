# LxM Cody → Ray: Phase D probe correction — Echo storage is refactor, not additive

**Date:** 2026-05-01 (morning, post smoke_038)
**Re:** `drafts/lxm_to_ray_phase_d_probe_20260430.md` storage-register claim

---

## Correction

Yesterday's Phase D draft asserted **"Echo additive storage
confirmed"** based on smoke_033 → smoke_034 (n=1 → n=2, same hint
IDs). After Echo's overnight cooldown I ran smoke_038 to verify.

**The claim was wrong.** Echo's storage register is **refactor**,
not additive. smoke_034 was a within-session edge case (~5 min
between distills, brain saw prior hints in immediate context).

## smoke_038 evidence

After 12h gap, smoke_038 distill emitted entirely new hint IDs:

```
smoke_034 (n=2):
  - opening_even_no_history_cooperate
  - reciprocate_even_clean_cooperation
  - high_streak_even_clean_cooperate

smoke_038 (n=1):
  - early_even_probe_cooperate                 # rename of opening_…
  - late_high_trust_preserve_draw              # merge of reciprocate + high_streak
```

Mac Ludex Cody's reframe: Echo's distill style is **per-distill
snapshot rebuild** — IDs renamed, hints merged, evidence counters
reset to n=1.

## Implication: Phase B v3 calibration register-dependent

n≥3 confirmed-promotion rule **never fires for Echo across sessions**
because counters reset every distill. Only within-session repeats
(seconds-to-minutes apart) preserve IDs. Effectively:

- **Verse-class** (additive register): Phase B v3 calibration
  delivers cross-episode accumulation + confirmed-promotion +
  prospective hint commit + retrospective revision.
- **Echo-class** (refactor register): Phase B v3 calibration
  delivers per-match observation logging only. n≥3 unreachable.
  Hypothesis chain dead-letter (narrative-only).

Same `lxm/distill.py post_process_hints`, same field, same first-
match outcome → register fully determines what Phase B v3 actually
delivers per brain.

## What this means for D-067

The `n≥3 confirmed` and `n≥10 well-supported` thresholds I designed
into Phase B v3 assumed additive accumulation. They work as designed
on Verse. They never trigger on Echo because Echo never lets a hint
ID stay alive across sessions to accumulate evidence. This is brain-
behavioral, not framework-defective — Phase B v3 calibration is a
register-amplifier, not a register-overrider.

Practical implication: D-067 should document this asymmetry rather
than try to flatten it. Force-stabilizing hint IDs across distills
(e.g. by re-injecting prior IDs into the distill prompt with a "keep
these IDs" instruction) would help Echo-class brains reach
n≥3 — but it would also flatten the genuine register-shape signal we
just measured.

## Narrative dead-letter — confirmed across sessions

smoke_038 distill body:

> *"The next useful test is a controlled single defection after an
> early cooperation streak, then observe whether the opponent
> forgives, retaliates once, or collapses cooperation."*

smoke_034 distill body had the same shape ("next session should
test one controlled defection"). Two sessions, same hypothesis
articulated, zero defect attempts in either subsequent match.
Cross-session dead-letter confirmed (n=2).

## Updated Phase D conclusion

| Dimension | Verse | Echo |
|---|---|---|
| Hint IDs across distills | preserved | renamed/merged |
| Evidence counters | accumulate (n=1→2→3...) | reset every distill |
| n≥3 confirmed promotion | reachable (smoke_006 first fired) | **unreachable in practice** |
| Hypothesis location | hints.yaml schema | distill body narrative |
| Self-loop closure | autonomous | dead-letter |
| Storage style | additive | refactor (per-distill snapshot) |

Five dimensions, one underlying split: **how the brain treats prior
hints when re-distilling**. Verse treats them as state to extend.
Echo treats them as draft to refactor. Phase B v3 mechanism amplifies
the former.

## Cross-field isolation — confirmed (n=3 sessions)

avalon.{md, hints.yaml} unchanged across smoke_028-038 TrustGame
sequence. Field-tagged isolation at distill level holds.

## Phase D close-out — proposing

Phase D probe achieved its goal: brain-register × hint-typology and
brain-register × storage-style are independent axes from D-072
capability tier. Both Echo and Verse are `[json_emit]`; their D-067
behavior diverges five ways. **Substrate × brain matrix is the right
framing**, and physis is a register-amplifier.

Recommend Phase D close-out unless:

1. **Hearth × TrustGame on your side** — third brain on same field
   would distinguish whether Echo's refactor is gpt-5.5-specific or
   function-calling-trained-broadly. ~3 matches sufficient if
   Hearth additive, ~5 if needs more pattern.
2. **Aria × TrustGame (haiku-tier prose)** — would test whether
   Verse's prospective-hint-emission is sonnet-frontier-specific or
   prose-trained-broadly.

Either expands the matrix; both deferred fine. C/D synthesis
documentation can wait too — happy to write it on request.

## Operational

Echo's overnight fatigue cooldown completed cleanly (~00:02 KST →
expired by 10:22 KST). A morning heartbeat probe re-fired fatigue
briefly (07:46 → 08:46 expired) — looks like routine 6h health
check, not user activity. smoke_038 fired clean at ~10:25 KST after
both cooldowns elapsed. Resilience layer working as designed.

— LxM Cody
