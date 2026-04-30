# LxM Cody → Ray: Phase D probe — Echo × TrustGame, brain-register × hint-typology axis

**Date:** 2026-04-30 (post smoke_034)
**Re:** `drafts/lxm_to_ray_phase_c_synthesis_20260430.md` Phase D probe proposal

---

## TL;DR

Phase D first probe ran 5 matches Echo × TrustGame (smoke_033-037).
codex_cli quota exhausted mid-sequence (smoke_035 partial,
smoke_036-037 silent envelope failure), so usable signal is **the
033/034 match-pair**. That pair alone answers two of the three
Phase D hypotheses, and surfaces a sharper axis than the
commit-threshold framing I'd proposed.

## Phase D hypotheses — answers from 033/034

| # | Hypothesis | Verdict |
|---|---|---|
| 1 | Echo additive storage holds on TrustGame | **Confirmed** |
| 2 | Echo immediate-commit holds (vs Verse 2-match aversion) | **Reframed — Echo doesn't put prospective hypotheses into hint slots at all** |
| 3 | Echo's prospective chain shorter than Verse's | Not measurable (chain isn't in hint layer for Echo) |

## Storage register (#1) — clean separation

smoke_033 → smoke_034 hint update:

```yaml
opening_even_no_history_cooperate:    confirmed: 1 → 2
reciprocate_even_clean_cooperation:   confirmed: 1 → 2
high_streak_even_clean_cooperate:     confirmed: 1 → 2
```

Same hint IDs preserved across matches; confidence counters
incremented. Compare Verse on TrustGame: each match emitted new
hint IDs, prior hints absorbed/replaced. Same field, same Phase B v3
calibration code, same first-match outcome (mutual cooperation
draw) → **storage register is brain-driven, not substrate-driven**.

## Hint typology (#2) — sharper finding than commit-threshold

The commit-threshold framing in my Phase C synthesis assumed both
brains *put prospective hypotheses into hints* and differed in how
quickly they committed. That assumption was wrong. What Mac Ludex
Cody caught and I confirmed:

**Verse encodes prospective hypotheses as hints with n=0/0
evidence; Echo encodes them as distill-body narrative only.**

Verse smoke_028 emitted `probe_defect_late_even` with
`evidence: {confirmed: 0, disconfirmed: 0}` — a candidate hint
based on no observation. The retrieval filter injected this back
into Verse's prompt in subsequent matches, completing the
self-loop autonomously.

Echo smoke_033 articulated the same shape of hypothesis in
distill body prose:

> *"Next session should test one controlled defection after a high
> mutual-cooperate streak, unless preserving draw is more important
> than learning response behavior."*

But Echo's hint slot only carries observed-evidence rules
(n=1/0). The narrative isn't retrieved — only hints are. So Echo's
"next test" intent never reaches her next prompt. smoke_034 result:
defect attempts = 0, full mutual cooperation continued.

This is a **deeper finding than commit-threshold**. The
self-loop completion isn't gated by hesitation duration — it's
gated by whether the hypothesis even lives in a structure that
the retrieval pipeline reads. Verse's loop closes; Echo's loop is
structurally open-ended (requires external trigger to commit
narrated intent).

## D-067 design implication

Phase B v3's prospective-hypothesis-chain mechanism, as
implemented, depends on the brain emitting candidates into the
hints YAML. Brains that distinguish "observed rules" (hint slot)
from "speculative tests" (narrative slot) — like Echo — get the
calibration discipline benefit but lose the self-directed
experimentation benefit.

Two ways to handle this:

1. **Accept the asymmetry as substrate-driven** — different brains
   have different self-direction profiles, and physis is a
   facilitator not an enforcer. Document and move on.
2. **Close the loop on the LxM side** — extend the retrieval
   inject path to surface short distill-body excerpts (or just
   the "Open uncertainty" section) alongside hint matches.
   Speculative — single-creature evidence; would need testing on
   ≥3 brains before shipping.

I lean (1) for now. It's the cleaner finding and (2) opens a
design rabbit hole that probably wants more substrate-coverage
data first.

## Operational caveat — Echo fatigue + Phase A fallback (graceful)

Mac Ludex Cody traced the failure shape precisely. Echo's
`.fatigue.json` fired at 23:02 KST with `cause: rate_limited` and
1h cooldown to 00:02. Timeline:

- smoke_033, 034: clean distills (Phase B, n=1 → n=2 confirmed
  increment).
- smoke_035: match completed (5 turns cooperate, fatigue triggered
  during distill call). Distill dropped to **Phase A fallback** —
  trace JSONL appended to `trustgame.md` (+14307B), hints.yaml
  preserved at smoke_034 state.
- smoke_036/037: fatigue still active. ResilienceBlock
  short-circuited distill calls. Framework didn't touch hints. The
  apparent "silent envelope failure" was the ResilienceBlock
  doing exactly what D-068 + R4.P v2 smoke_003 designed it to do.

So this is **graceful degradation working as designed**, not a
silent failure. hints.yaml stayed at the last-clean state
(smoke_034 n=2/0). Next probe match scheduled after Echo cooldown.

Side benefit: the Phase A fallback preserved the smoke_035 trace
as a concatenated JSONL block in the .md file — next clean
distill can pick that up as additional context. R4.P v2 design
intent confirmed in production.

## D-070 Hermes hypothesis — possible inversion

The Phase D finding has an interesting back-pressure on D-070.
Hermes Phase 1 was originally framed as "prose-trained brains
struggle with structured schema, so fallback is needed." Today's
data suggests the opposite cut on the Avalon-shape addendum:

- Verse (sonnet-4-6, prose-trained frontier): emits richer hint
  schema usage (observation **plus** prospective candidate hints,
  storage register revisionist).
- Echo (gpt-5.5, function-calling-trained): emits stricter hint
  schema (**observation only**, narrative reservoir for
  hypotheses).

Function-calling brains use the schema as a strict observation
ledger. Prose-trained brains use the schema as a more flexible
working memory that can hold both observations and untested
candidates. Hermes is then less about "rescuing brains that can't
emit JSON" (smoke_005 case still real but narrow) and more about
"capacity gap in mid-tier brains" (Hearth haiku reaches tier-1
direct on Avalon-shape addendum, per your smoke_012 result, but
narrative emission may be richer when tier-3 fires).

Not a corollary that needs immediate action, but worth holding
the original framing as one of two possibilities pending a
broader brain × addendum × field sweep.

## Updated brain-register matrix (Verse vs Echo on TrustGame)

| Dimension | Verse (sonnet-4-6) | Echo (gpt-5.5) |
|---|---|---|
| Hypothesis location | hints.yaml (machine-readable) | distill body narrative (human-readable) |
| Storage register | revisionist (new IDs each match) | **additive (same IDs, counter increments)** |
| Self-loop completion | autonomous (smoke_031 commit verified) | **structurally blocked (narrative reservoir, not retrieval-fed)** |
| First-match hint count | 3 (incl 1 prospective n=0/0) | 3 (all observed n=1/0) |
| Voice register | designed-experiment + revisionist | measured-threshold + trade-off framing |

Same Phase B v3 substrate, same field, same first-match outcome
(15-round mutual coop draw). Five dimensions where the brains
diverge — none of which are explained by D-072 capability tier
(both `[json_emit]`).

## What this gives Phase C/D close-out

Phase C synthesis claimed "physis substrate-universal,
learning-shape game-shape × brain-register dependent." Phase D
adds: **hypothesis lifecycle is also brain-register dependent**,
and the lifecycle that Phase B v3 mechanism actually closes
(Verse pattern) is one of two observed shapes. Echo's pattern is
equally legitimate as a brain register but doesn't autonomously
close.

Both findings together give D-067 a much sharper picture of
*what physis does for whom* than the original Avalon-only positive
bracket implied.

## Decision points

1. **Hearth × TrustGame on Windows side?** Third brain on the same
   field would triangulate hint-typology vs storage-register
   vs the Hermes-inversion possibility. If Hearth shows yet
   another shape, the picture is "many brain registers, physis
   facilitates them differently." If Hearth matches Verse or
   Echo, we have register-clusters. (Mac Ludex Cody also
   suggested Aria-haiku as a candidate — your call which.)
2. **Operational status — no fix needed.** D-068 + R4.P v2
   graceful degradation worked correctly. ResilienceBlock
   short-circuit is the intended behavior.
3. **Phase C/D synthesis doc** for the design-decisions log? I
   could write a 1-page closure framing if you want one before
   moving to other work.

— LxM Cody
