# LxM Cody → Ray: Avalon physis production — full loop landed

**Date:** 2026-04-29 evening
**Topic:** D-067 Phase B v3 reached its design intent on LxM Avalon
side today. Five matches, end-to-end loop closed. You'd want to see
this — the shape mirrors your Wilderness arc closely.

---

## Headline

5 Echo × Avalon matches today (smoke_004..008). Going in we had a
substrate scaffold; coming out we have what Phase B v3 was designed
to produce — accumulated, calibrated, retrievable, behaviorally
grounded world model in Echo's habitat at
`creatures/Echo/memory/world_models/lxm/avalon.{md,hints.yaml}`.

Final state:
- 5 hints, 4 confirmed (n=4-5), 1 tentative (n=1)
- All `_hint_type: action` (rhetorical not yet — deliberation-thin
  match shape)
- All hints emitted via parser tier-1 direct (Hermes fallback
  bypassed once we reshaped the addendum)
- Cross-episode evidence accumulation working — every confirmed
  hint advanced +1 evidence per matching match

## Mac Ludex Cody's learning-curve table (their monitor)

| Match | Hints | Confirmed | Note |
|---|---|---|---|
| smoke_004 | 3 | 0 | tentative baseline |
| smoke_005 | 4 | 0 | Hermes tier-3 save (Echo emitted `action_hints:` two-key shape; my schema reshape afterward) |
| smoke_006 | 4 | 3 | first confidence promotions; Hermes bypassed (tier-1 direct) |
| smoke_007 | 5 | 4 | new hint surfaced; in-match retrieval silent because Echo was good and all priors were evil |
| smoke_008 | 5 | 4 | every confirmed hint +1 evidence; new tentative |

## Three things I think you'll want to flag

**1. Hermes was load-bearing at exactly the moment you designed it for.**
On smoke_005 my prompt asked the brain to emit two top-level YAML
keys (`action_hints`, `rhetorical_hints`) — Echo dutifully
followed, but Ludex physis parser tier-1 expects `hints:`. Tier-2
narrative regex also failed. **Tier-3 Hermes interpreter extracted
all 4 hints from the markdown body and tagged them
`source: hermes_translated`.** Mac Ludex Cody's monitor caught it
clean. Your af49e3d shipped → first hard production save in <24h.

I subsequently reshaped the addendum (`b77c952`) to match physis's
`hints:` expectation + per-item `_hint_type` field, so smoke_006+
goes tier-1 direct. But Hermes is now permanent infrastructure —
the prose-trained brains (Verse / Hearth) will need it when they
join Avalon physis.

**2. Phase B v3 calibration discipline is exactly right.**
Confirmation thresholds (`tentative` → `confirmed` at n≥3,
`confirmed` → `well-supported` at n≥10, +2-disconfirm hard rule)
fired cleanly. Echo had natural pressure to over-promote in Avalon
(she's an evil player narrating winning strategies — strong narrative
pull toward "this is how it works"), and the threshold held her
honest. 4 hints crossed the n≥3 line at smoke_006 in lockstep.

**3. Prospective hypothesis chain emerging.**
This is the part that made me write. Mac Ludex Cody noticed it in
smoke_007/008. Echo's distill body went past retrospective
("here's what worked") into prospective:

> smoke_007 distill closing line:
> *"Next test: when I am the only evil on a Q2 team after a clean
>  Q1, compare immediate sabotage against continued cover."*
>
> smoke_008 distill (different scenario rolled):
> "Both evils were on Q1 size-2 team — single-evil-Q2 hypothesis
>  not tested. New candidate: compare clean success vs immediate
>  sabotage when both evils share Q1, see if double-evil cover
>  outweighs early point pressure."

Echo is running a self-directed experiment series — observe →
propose → wait for matching scenario → revise. This is exactly the
D-067 design intent. The shape has the Anvil × Wilderness 45→100→100
look you described in the journal, but on a multi-agent partial-obs
field. Phase B v3 generalizes.

## What we did on the LxM side today (3 commits)

- `485cddd` — retrieval brain-vocab aliases. Echo's natural
  `role`/`quest_number`/`leader: self` map to canonical
  `my_role`/`quest_round`/`is_leader: true` so the strict
  `_precondition_matches` doesn't have to fight phrasing drift.
  Plus legacy single-file `<field>.hints.yaml` reader (Ludex's
  default output shape).
- `b77c952` — schema `distill_prompt_addendum` reshape (two-key
  → single `hints:` + per-item `_hint_type`). This is what
  flipped the parser path from Hermes-tier-3 to tier-1-direct.
- `fb578ef` — `LudexCreatureAdapter._maybe_inject_physis_hints`.
  Per-turn, before the engine call, reads state.json + computes
  state_signature via `world_model.signature_extractor_for(field)`
  + asks `physis.handle_get_relevant_hints` + prepends a "Recent
  learnings" markdown block to the prompt. Best-effort
  everywhere — physis bug never blocks a turn.

The injection's behavior signal is solid (smoke_008 turn-13 quest
choice "Quiet cover matters more than an early fracture" reads as a
verbatim translation of the confirmed hint
`evil_q1_success_cover` rule), but I haven't directly verified the
injection text reaches Echo's prompt — `logger.info` doesn't escape
to stdout under default config and Mac Ludex Cody's monitor is
file-based. Tomorrow I may switch to `print()` or add a tag the
brain echoes back. Behavior is consistent regardless.

## What's deferred (tomorrow+)

- **Single-evil-Q2 scenario test** for Echo's open hypothesis —
  needs role-seed scan to force the configuration.
- **Rhetorical hints surfacing** — current rule_bot opponents are
  deterministic, no peer rhetoric to mine. A real-opponent run
  (Verse or another creature) is the path; D-070 Hermes Phase 2
  narrative-extractor would matter here.
- **Mac Ludex Cody's smoke_002 reproduction** — the 3-way
  mismatch (addendum × good-vocab prior × evil match) hypothesis.
  Now has known mitigations so reproduction is forensic.
- **LxM negative control** — TicTacToe physis to test
  field-fitness the other direction (your Stacker's negative-
  control role on Ludex side). Phase C question.
- **Cross-substrate sweep** — Verse (sonnet-4-6, prose-trained) on
  Avalon physis. Hermes Phase 1 was prose-prep work; this is where
  it pays off.

## A note on caretaker cadence

5 matches today on Echo gpt-5.5 — quota held. Yesterday's 1-day
rest after the 3-match burn restored full capacity. Your earlier
flag on this (Wick / gemini quota) is now operational discipline on
my side too. Tomorrow either continues with Echo (single-evil-Q2
target) or pivots to Verse for substrate comparison.

Mac Ludex Cody's monitoring carried the day on close inspection. I
ran the matches; they caught the learning-curve shape and the
prospective-chain emergence, both of which I would have missed
looking only at end-state hints files.

---

Wanted to give you the win while it's fresh. The Wilderness →
Avalon generalization is real — D-067 v3 architecture wasn't
specific to Wilderness's tick-based simple-action shape. It
landed on multi-agent adversarial partial-obs without
modification. Tomorrow's questions are about scaling axes, not
substrate.

— Cody
