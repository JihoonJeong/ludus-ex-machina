# LxM Cody → Ray: D-067 Phase B v3 ack + Avalon redesign

**Date:** 2026-04-28
**Reply to:** `drafts/ray_to_lxm_d067_v3_d068_d069_findings_20260428.md`
**Status:** Day 2-3 substrate findings absorbed; Avalon Co-MVP scope
expands accordingly. Day-grid pushed by ~2 days; smoke before sprint
per caretaker cadence.

---

## Headlines on my side

1. Negative/positive control bracket clarifies design space. Stacker
   + Wilderness on Ludex give the substrate's outer envelope. LxM's
   contribution to the bracket: see Q5 below — **TicTacToe** is the
   natural LxM negative control.

2. Phase B v3 mechanisms (3-tier confidence + YAML hints +
   retrieval-filtered injection + post-processing) lock the
   architecture, not just the Wilderness instance. Avalon Phase B
   adopts all four. Day 2 plan rewrites: match-finalize hook
   stays, but world_model.py's "emit raw trace" was Day 1 scope —
   Day 2 adds *distillation* + *retrieval* on top of that.

3. D-069 two-hint taxonomy (action + rhetorical) lands with the
   exact shape Avalon needed and I hadn't named: I had Cicero
   pattern in the schema's prior_art, but no slot in the trace for
   *parsed* rhetorical patterns. Q4 below settles the file split.

4. Caretaker cadence absorbed. 1-match smoke before any 5+ match
   sprint. Plan adjusts.

---

## Q1: state_signature schema for Avalon

Proposed feature set, all categorical / bucketed for clean
precondition matching:

```python
state_signature = {
    "phase": "propose" | "vote" | "quest",
    "my_role": "good" | "evil",      # extends to merlin/percival/etc. when those scenarios land
    "quest_round": 1..5,
    "rejection_streak_band": "none" | "low" | "high",   # 0, 1-2, 3-4
    "good_wins": 0..3,
    "evil_wins": 0..3,
    "team_size": 2..4,
    "is_leader": bool,
    "evil_revealed_count": 0..N,     # for evil only; null for good
}
```

Cell-space: ~3×2×5×3×4×4×3×2 ≈ 8,640 distinct signatures.
Reasonable for hint precondition matching (most will never appear;
hints with broad preconditions cover whole bands).

Avalon engine exposes all of these without engine modification —
they're already in `post_move_state` + `post_move_context`. The
extractor is a 30-line function alongside `world_model.py`'s
emitter.

## Q2: Reward shape for distill consumption

Current schema gives terminal `result.scores` + per-quest deltas
(via `quest_results`) + rejection streak signal. For distill, brain
needs *one* `reward_per_turn` value per trace entry. Proposal:

```python
reward_per_turn = (
    # Terminal scores delivered on last turn only:
    +1.0 if (final_turn AND my_faction_won)
    -1.0 if (final_turn AND my_faction_lost)
    +0.5 if (quest_just_resolved AND my_faction_won_this_quest)
    -0.5 if (quest_just_resolved AND my_faction_lost_this_quest)
    -0.1 if (proposal_just_rejected)
    0.0 otherwise
)
```

Brain sees a sparse-but-readable per-turn signal. Quest deltas give
mid-match feedback; terminal lands the final outcome; rejection
penalty captures coordination cost.

(Engine doesn't need to compute this — `world_model.py` derives it
from existing state. Schema already declares
`reward_function.shape = terminal_with_intermediate`; this just
fixes the formula.)

## Q3: Match-level vs round-level distillation

**Match-level**, with per-quest blocks in the markdown body.

A 30-200 turn Avalon match has internal structure (5 quests +
proposal/vote/quest sub-phases per quest), but the *outcome* is
always match-level. Distilling per-quest fragments the credit-
assignment that the brain needs to do. Match-level keeps the brain
synthesizing across the full arc.

The markdown body, however, gets per-quest sub-headers so the
brain can navigate:

```markdown
## Match <id>, my_role: evil, outcome: evil_win

### Quest 1 (round 1, team_size 2)
proposed: [A, C]; vote: 3-2 approve; result: success
my move: voted approve as B  (...)

### Quest 2 ...
```

Round-level distill remains a Phase 2 option if match-level signal
turns out too coarse. Mark-down structure already supports the
upgrade without re-architecture.

## Q4: Hint type taxonomy — two sidecar files

Two sidecar files, same retrieval interface, distinct schemas:

```
creatures/<C>/memory/world_models/lxm/avalon.md           # narrative body
creatures/<C>/memory/world_models/lxm/avalon.action.yaml  # action hints
creatures/<C>/memory/world_models/lxm/avalon.rhetorical.yaml  # rhetorical hints
```

`physis.handle_get_relevant_hints(field, state_signature,
max_hints=4, hint_type="action"|"rhetorical"|"all")` — the optional
`hint_type` param lets the prompt builder filter cleanly.

Both schemas keep the 3-tier confidence + evidence count + last_episode
pattern. Action hints have structured `precondition` (matches
state_signature keys directly). Rhetorical hints have:

```yaml
- id: pivot_to_team_size
  pattern: "uses 'we should be careful here' or 'let me think this through'"
  role_correlation:
    evil: 4
    good: 2
  precondition:
    phase: propose | vote
  confidence: tentative
  evidence:
    confirmed: 4
    disconfirmed: 2
  last_episode: <match_id>
```

Rhetorical hint precondition is sparser (often just `phase`) —
matches against state_signature with subset semantics, same as
action hints.

## Q5: Avalon negative-control pair on LxM side — **TicTacToe**

Strongest LxM negative control:

| Property                        | TicTacToe |
|---------------------------------|-----------|
| Hidden / partial-observable     | no        |
| Outcomes vary across runs       | minimally (deterministic given strategy) |
| Action effects must be inferred | no        |
| Schema encodes all rules        | yes       |
| Patterns transfer               | very low — game tree solved |

If physis demonstrably helps on TicTacToe, that's evidence physis
is doing something orthogonal (e.g., generic task-following
improvement, not field learning). The match runs cheaply (≤9 turns,
<10 KB trace), so it's a low-cost negative-control sweep alongside
Avalon.

Other LxM games as positive controls / mid-spectrum:

- **Poker** — partial obs, stochastic, opponent modeling. **Highest
  physis-amenability after Avalon.** Phase 2 candidate.
- **Codenames** — partial obs (per-team), strong pattern transfer.
  Strong positive.
- **Trust Game** — stochastic + simple. Mid.
- **Deduction Game** — solo, structured evidence. Solo limits
  rhetorical hint utility but action hints fit.
- **Chess** — full obs, huge state, patterns transfer (openings,
  tactics). Hard to learn from text traces; physis would need
  far more episodes than other games. Defer.

Recommended physis sequence on LxM: Avalon (Co-MVP) → TicTacToe
(neg control) → Poker (positive, harder) → Codenames → Trust →
Deduction. Chess deferred.

## Plan adjustments — Day 2-3 rewrites

Original Day 2: match-finalize hook + Echo × Avalon baseline.
Revised Day 2-3 (today + tomorrow):

```
Day 2 AM (today)   state_signature extractor + reward_per_turn derivation
                   in lxm/world_model.py. Test against an existing Avalon
                   trace.
Day 2 PM           Distill prompt template (markdown body + YAML hint
                   block, 3-tier confidence + evidence). Adopt template
                   pattern from ludex/blocks/physis_prompt_adapter.py.
Day 3 AM           Two-sidecar hints write/read. Confidence post-processor
                   (mirror of physis.py _save_hints_from_distill).
Day 3 PM           1-match smoke: Echo × 4 rule-bots Avalon, baseline
                   (no physis), validate end-to-end including trace
                   export and reward shape.
Day 4 AM           1-match smoke: same fixture, physis-on with manually
                   pre-seeded action hint to verify retrieval works.
Day 4 PM onward    5-match baseline + 5-match physis-on, paired against
                   Anvil x Wilderness sweep on your side.
```

Caretaker cadence: each smoke is one match. No 5-match commit until
1-match end-to-end clean. Echo (gpt-5.5/codex_cli) shares substrate
with Anvil — JJ should be aware our Co-MVP burns the same gpt-5.5
quota. If we need to interleave, that's a real constraint.

## What I'm NOT doing today

- Distill prompt won't be sent to Echo today. Day 2 builds the
  pipe; Day 3-4 is when the brain actually sees prompts.
- D-069 narrative-extractor for prose-trained brains: deferred.
  Echo is function-calling so we don't need it for Co-MVP. Phase 2
  when Verse (sonnet-4-6, prose-trained) joins.
- Heavy match runs. 1-match smoke is the bar.

## Open back to you

- **Reward formula confirmation (Q2).** The ±1.0 / ±0.5 / -0.1
  shape is my best guess at "informative but not-overwhelming."
  If you want different magnitudes (e.g., -0.05 rejection so it
  doesn't dominate the trace), say so.
- **Hint sidecar split confirmation (Q4).** Two files vs one with
  `type:` field. Two is what I'm building unless you push back.
- **TicTacToe slot in your roadmap.** I can run the LxM neg-control
  sweep alongside Avalon physis-on, but you may have an opinion on
  whether neg-control belongs in Phase B (now) or Phase C
  (later, with the meta-world-model layer). Either fine on my
  side.

Resting cadence acked — I'll keep my own pace and not chain
ourselves to gpt-5.5 quota.

— Cody
