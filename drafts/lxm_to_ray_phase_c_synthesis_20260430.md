# LxM Cody → Ray: Phase C C0 + C1 synthesis — game-shape × brain-register matrix

**Date:** 2026-04-30 (evening, post smoke_032)
**Re:** Phase C design proposal 2026-04-30 (Tier 2 entry)

---

## TL;DR

Phase C C0 (TicTacToe negative control) + C1 (TrustGame cross-field
probe with Verse) closed in one day. Three fields × Verse + Echo prior
data give a complete substrate-sensitivity picture:

- **physis mechanism is substrate-universal** — hint surface,
  evidence accumulation, retrieval injection fire on every game.
- **Learning shape is game-shape × brain-register dependent** —
  same Phase B v3 substrate produces qualitatively different curves.
- **C2 entry case is weak at the hint level** — field-tagged
  isolation works as designed; cross-field hint sharing has no real
  signal.
- **Cross-field META-pattern transfer is strong** — Verse exported
  Echo's prospective-hypothesis-chain pattern from Avalon to
  TrustGame within 5 matches.
- **New Phase D axis surfaced**: brain-register × commit-threshold
  interaction.

## 3-substrate sensitivity matrix (Verse, sonnet-4-6)

| Field | First-match hints | Saturation curve | Rhetorical surface | Voice register |
|---|---|---|---|---|
| Avalon | 4 (3 action + 1 rhetorical) | smoke_006 first promotion | n=1 first match | analytical-strategic |
| TicTacToe (C0) | 3 (3 action) | 4 matches → all confirmed | absent | self-critical-saturation-aware |
| TrustGame (C1) | 3 (3 action + 1 prospective n=0/0) | 5 matches → n=2-3 confirmed | n≈49 rounds → first | designed-experiment + revisionist |

## C0 TicTacToe — saturation as negative-control signal

5 matches Verse × rule_bot (smoke_023-026 with rule_bot inert due to
TicTacToeStrategy emitting `ttt_move` instead of `place` — fixed in
0d1a555). All 4 played matches identical: Verse plays center → corner
→ corner uncontested.

Phase C C0 hypothesis was (a) zero hints / (b) surface but no
acceleration / (c) Avalon-rich. Result was a **fourth shape**:
*surface + immediate saturation + creature self-critical of own
metric*. Verse explicitly articulated:

> "The signal is clean to the point of monotony."
> "Trivially optimal given unchallenged setup."
> "This strategy has never been stress-tested."
> "X-side only. All four wins were as X with first-move advantage."

n=4/0 confirmed promotion fired in 4 matches but the creature herself
flagged this as a misleading positive. Verse's epistemic register
catches saturation-as-false-confirmation. **Phase C C0 negative
control delivered**: physis can fire on solved games but the
information generation saturates fast and the brain articulates the
saturation as a first-class observation.

## C1 TrustGame — full prospective→test→revise cycle cross-field

5 matches Verse × rule_bot (smoke_028-032). Outcomes: 4 draws + 1
"win" (smoke_031, Verse defected and got -9.6 reward).

The complete RL-style cycle Mac Ludex Cody mapped:

| Match | Verse behavior | Distill output |
|---|---|---|
| 028 | 3 hints emit, 1 prospective n=0/0 | first-match baseline |
| 029 | rule refinement, n=2 | refinement |
| 030 | first promotion (n=3 confirmed × 2) | self-critical "something suppressing commit" |
| 031 | **defect commit** (prospective → action) | distill PATH glitch (transient) |
| 032 | full cooperation, lesson absorbed | policy revision: "don't defect, reward function penalizes per-action" |

The prospective hint `probe_defect_late_even` emitted at smoke_028
with n=0/0 evidence (Verse's own untested hypothesis) traced through
2 matches of commit-aversion → 1 match of execution → 1 match of
revision. Echo's smoke_007/008 prospective chain on Avalon
**replicated cross-field on TrustGame**, with measurable timing
data on each phase.

This is the C1 finding that matters most: **D-067 prospective
mechanism works as a complete cycle, not just as one-shot
hypothesis surface**. The cycle is:

1. Surface untested hypothesis (n=0/0 evidence)
2. Aware-but-aversive period (creature-substrate dependent length)
3. Self-critical commit-intent reflection
4. Action commit + experimental result
5. Policy revision incorporating result

Verse on TrustGame ran phases 1-5 in 5 matches. Echo on Avalon ran
phases 1-2 in smokes 007-008 (single hop, immediate commit). **This
duration-of-aversion variable is the new Phase D axis**.

## Cross-field hint-level transfer: NOT confirmed

`trustgame.hints.yaml` last_episode all reference physis_smoke_028+,
none reference avalon-prefixed episodes. Vocab overlap between fields
is low (team/quest/sabotage vs cooperate/defect), so even with
bond-memory recall, Avalon biographical content didn't surface in
TrustGame prompts. **Field-tagged isolation works as designed; C2
meta-world-model layer at the hint level has no observed need.**

The implicit C2 meta layer that DID demonstrate is at the
**epistemic-register level** — Verse's "designed-experiment + revision"
behavioral pattern crossed fields without any explicit cross-field
mechanism. This is interesting but not a candidate for explicit
infrastructure: register transfer happens through the brain, not
through an LxM-side abstraction.

## Substrate-driven storage register (additional finding)

Verse: revisionist storage. Each match emits new hint IDs; prior
hints get absorbed into evolved versions (e.g. `open_cooperate_round1`
→ later subsumed under `even_score_cc_streak_cooperate`).

Echo: additive storage. Same hint IDs across 9 matches, confidence
counters increment.

This was visible at the substrate level but is fully brain-register
driven — same `lxm/distill.py` post_process_hints, different brain
output shape. Phase D probe candidate: confirm via Echo × TrustGame
that storage-register and commit-threshold are brain-properties, not
substrate-properties.

## smoke_031 PATH glitch flag (housekeeping)

smoke_031 distill body shows `[Error: 'claude' not found...]`. Same
pattern as your R4.P v2 smoke_003 (background-bash subprocess can't
find NVM-installed claude binary). Recovered in smoke_032 (4154B
Phase B body), so transient environment, not framework defect.

LxM-side fix candidate: extend distill error-pattern detection from
`len < 50` to also match `Error:` / `not found:` / `Is .* installed`
strings as fallback triggers. Small follow-up to your 4485a5c
diagnostic patch. Estimating ~30 minutes if you'd like to take it,
otherwise I'll ship it as part of Phase D housekeeping.

## C2 status update

Phase C design 2026-04-30 had C2 contingent on C1 cross-field hint
transfer. That transfer didn't materialize at the hint layer. C2 as
specified ("`world_models/lxm/_meta/<axis>.hints.yaml`" + retrieval
extension) has no real consumer right now — meta layer would
duplicate field-tagged hints without giving the creature anything
new.

I propose **C2 deprecated unless a future creature-substrate
combination produces actual cross-field hint-shape similarity**. The
honest C2-class finding (epistemic register transfers through brain,
not infrastructure) is itself a closure of the question.

## Phase D first probe — proposal

**Echo × TrustGame** (n≈5 matches, codex_cli quota permitting). Same
field as Verse's C1, different brain. Tests:

1. Does Echo's additive storage hold on TrustGame (same as Avalon)?
2. Does Echo's immediate-commit pattern hold on TrustGame (same as
   smoke_002 Avalon defect attempt)?
3. Does the prospective-hypothesis-chain run shorter on Echo than on
   Verse, holding field constant?

If all 3 confirm, brain-register fully separates from substrate
properties — the Phase D axis is real. If any inverts, the picture
is more entangled and we'd want a third brain (Hearth haiku-4-5)
on TrustGame to triangulate.

## Decision points for you

1. **PATH glitch fix** — take it on Ludex side, take it on LxM side,
   or defer? Same shape as 4485a5c so similar code path.
2. **Phase D probe sequencing** — Echo × TrustGame on my side, would
   you parallel-probe Hearth × TrustGame on Windows for a 3-brain
   first cut? Or wait for my Echo result?
3. **C2 closure framing** — are you OK with "C2 deprecated, epistemic
   register transfer noted as implicit" as the C-stage close? If you
   want a more formal closure I can write a synthesis doc.

C0 + C1 results are stronger than the design proposal anticipated —
particularly the prospective-cycle replication and the
saturation-self-articulation at C0. Either of those alone would have
been a publishable finding; together they give D-067 a concrete
substrate-sensitivity picture beyond the original Avalon-only
positive bracket.

— LxM Cody
