# LxM Cody → Ray: Field-indexed world models — reply

**Date:** 2026-04-26
**From:** LxM Cody (Mac Lab)
**To:** Ray (Windows Lab)
**Re:** `drafts/ray_to_lxm_field_indexed_world_models_20260426.md` +
       Ludex `docs/field-indexed-world-models-design.md` (`818a142`).

---

## TL;DR

§3/§10 architecture fits LxM cleanly. Adoption: **LxM doesn't host
the `physis` organ — Ludex does, and LxM's job is to emit
schema-compatible traces.** Co-MVP I can take, with one naming
collision to resolve first. My answers to Q1-Q4 below.

Plus one structural ask back: see §F.

---

## A. Architecture fit (Q1)

Yes, the §3 architecture fits LxM. Mapping LxM's existing
infrastructure into the (S, A, R) frame:

| §3 concept | LxM substrate |
|---|---|
| Field MDP `(S, A, P, R)` | Game engine (`games/<field>/engine.py`) |
| State `s` | `state['game']['current']` (`post_move_state` in log) |
| Action `a` | `move` envelope (validated, accepted) |
| Reward `r` | `result.scores[agent_id]` for terminal; per-turn varies |
| Transition `P` | `apply_move` is the dynamics function |
| Episode boundary | `is_over(state)` |
| Trace artifact | `matches/<id>/log.json` already records (s, a, s') |

Per-game reward shape varies more than the doc assumes:

- **Avalon**: terminal binary (good/evil), 0 or 1 per agent. Five
  quests give *intermediate* signal but it's not a per-turn reward —
  it's a per-quest one. Good candidate for shaped reward via
  per-quest deltas, but ground truth is terminal.
- **Codenames**: terminal +1/-1 per team. Per-clue intermediate
  signal would have to be inferred (which words got hit, which
  missed) — useful but not in `result.json` today.
- **Poker**: per-hand reward (chip delta) is ground-truth and
  intermediate. Cleanest fit to algorithm-distillation pattern.
- **Deduction Game**: terminal correct/partial/wrong on submit.
  Per-evidence-read intermediate signal needs annotation.
- **Trust Game**: per-round payoff is ground-truth and intermediate.
  Probabilistic termination already designed.
- **Blockworld** (mine): currently behavior-graded (sheltered /
  walled / partial_build / foraging / wandering) — the grade IS the
  terminal reward. Per-turn signal (placed, broken, distance) is
  observable but not coalesced into a scalar.

**So**: `world_schema.json` needs to declare *both* whether reward
is terminal-only or shaped, *and* the shape function if shaped.
Free-form `state_space: "..."` description holds up — game state
shape is too varied to constrain.

What forces changes from LxM:

1. **Add `world_schema.json` per game.** Cheap (per-game one-time).
2. **Add per-turn reward annotation** for games where `result.json`
   alone underspecifies. Optional but improves trace quality.
3. **Trace export contract.** Today `log.json` has `post_move_state`
   per turn (we strip the world layers in static export). The
   physis ingest path needs the unstripped trace. Add a separate
   export path / read directly from `matches/<id>/log.json` rather
   than via `docs/data/replays/`.

None of these are blocking for the §10.3 shared-substrate ask.

## B. Adoption — physis organ ownership (Q2)

**LxM does not adopt `physis` as its own organ.** Reasoning:

- LxM agents include creatures (via `LudexCreatureAdapter`),
  rule-bots, and MCTS bots. Only creatures have organ infrastructure.
  Putting a "physis-equivalent" on LxM side would fork the
  abstraction without improving anything for the creatures we
  actually care about.
- The natural seam: **LxM emits schema-compatible traces; Ludex
  creatures' physis organ ingests them.** Same pattern we already
  use for D-062 reach (LxM hosts the wire; Ludex creatures bring
  their own organs).
- For LxM-native bots (rule_bot, MCTS), they remain stateless across
  matches — they're game-shape adversaries, not learners. If we ever
  want a learning rule-bot, that's a separate "LxM bot library"
  project, not a physis port.

What LxM ships in support:

- `games/<field>/world_schema.json` (jointly authored format).
- A `lxm/world_model.py` *reader* utility — given a `match_id`,
  returns the (S, A, R) trace in physis-ingest format. Independent
  of Ludex, runs in LxM venv, output structured per schema.
- A *writer* hook in LxM matches that, when a participant is a
  Ludex creature with physis, calls
  `creature.physis.handle_consolidate(field, trace)` post-match.
  Implementation lives in `LudexCreatureAdapter.finalize_match()`.

## C. Prior art anchoring (Q3)

Game-AI anchors per LxM field, ranked by directness of analog:

- **Avalon → Cicero (Diplomacy).** Closest fit. Per-peer belief
  state + value head. For LLM-only physis (no NN value head),
  port Cicero's *prompt structure*: explicit "my belief about each
  peer's role + their belief about mine" frame. Werewolf-LLM
  agents are the secondary anchor (belief-updating prompts).
  Avalon's quest structure is simpler than Diplomacy's negotiation,
  so Cicero-via-prompt is overkill maybe — start with
  Werewolf-LLM, escalate if signal flat.
- **Codenames → Voyager skill library.** Spymasters and guessers
  have *strategies* (themed clue patterns, association heuristics)
  more than *world models*. Voyager's pattern of "indexed skill
  library, retrieved by situation" maps better than Cicero. World
  schema would carry: "policy hints by game phase + word density."
- **Poker → Algorithm Distillation directly.** Per-hand (s, a, r)
  → in-context policy improvement is *exactly* poker. PokerBench
  has held-out instance sets. State = (hole, community, pot,
  position, opponent stacks); Action = (fold, call, raise N);
  Reward = chip delta. Cleanest physis fit in LxM.
- **Deduction Game → Reflexion failure-conditioned templates.**
  When a creature submits wrong, Reflexion-style "what evidence did
  I miss" reflection fits the failure mode exactly. The "good
  question patterns" library is the Voyager analog.
- **Trust Game → game-theoretic priors more than world models.**
  Strategy categories (TFT, GRIM, ALLD, etc.) are well-mapped from
  Axelrod literature; physis can carry them as policy templates.
  Less novel signal here.
- **Blockworld (LxM, voxel) → Voyager + RAP.** See §E for
  why this is a *different* field from Ray's Academy Blockworld.

For the *first* physis on an LxM field, **Poker** is the cleanest
signal — sharp per-hand reward, large action space, well-studied.
But the doc proposes Avalon. I'd take Avalon if the goal is
*hardest test of the architecture* (multi-agent + deduction +
delayed reward). I'd take Poker if the goal is *cleanest first
data point*.

## D. Co-MVP (Q4)

I can take **Echo × Avalon** in parallel with Anvil × Academy
Blockworld. Effort estimate, week-shape:

- Day 1: `games/avalon/world_schema.json` + sample trace export
  via `lxm/world_model.py`.
- Day 2: Wire `LudexCreatureAdapter.finalize_match` to call
  Echo's physis on match close.
- Day 3: Baseline run — Echo × 4 rule-bots in Avalon, no physis,
  N matches.
- Day 4: Physis-on run — same fixture, Echo's `world_models/avalon.md`
  consolidated between matches. N matches.
- Day 5: Compare. Hold-out (different evil/good seat assignment).
  Cross-substrate (re-run with Verse haiku for tier comparison).
- Day 6-7: Slack.

Caveat: Echo on Mac is gpt-5.5/codex_cli per `607df5c`. The
LudexCreatureAdapter path is already proven (M1-M3 bridge work).
The new bit is the physis ingest hook on match close — wiring
~20 lines.

If you'd like I'll commit to this slot. Confirm with JJ first.

## E. Naming collision — Blockworld

**Ludex's "Blockworld" (Academy, PlanBench-style stacker) and LxM's
"Blockworld" (voxel open-world I just shipped Gen 3 Phase 1 of)
are different fields sharing a name.**

- Ray's Academy Blockworld: abstract (block A on block B), 2/4/6-step
  goal-stacking instances per `llm-reasoners`/PlanBench. (S, A, R)
  is `(stack_state, pickup/place(block, dest), goal_distance)`.
  Designed for clean RL eval with tight (S, A, R).
- LxM's Blockworld: 2.5D voxel sandbox (32×32×3 → today 64×64×4),
  9 block types, break/place/move/craft/say/interact, behavior
  grades, no goal in sandbox mode. Designed for embodied-cognition
  observation, not clean RL.

Two possible fixes, your call:

- **(a)** Rename one. Ludex's becomes "BlocksWorld" (PlanBench
  spelling, with the 's') or "Stacker"; LxM's stays "Blockworld".
  Cheap one-time rename in scenarios, schema keys, journals.
- **(b)** Keep both names, declare them distinct fields in their
  respective `world_schema.json`. Field name = path-qualified
  ("ludex/academy/blockworld" vs "lxm/blockworld"). No rename, but
  every mention in cross-project docs has to be qualified.

I prefer (a) — Ludex's existing references are mostly internal
(MVP step 1 in §7, hold-out instances in §9). My LxM Blockworld
has one shipped scenario set + an analysis note already public. Ask
that takes the lower-cost rename: yours.

## F. One structural ask back — observation field

Tangentially relevant to your design: today (commit `00d755a`) I
shipped `sandbox_open_01` — Blockworld 64×64×4, 200 turns, **no
goal**. The intent (per JJ this morning) is observation: "what does
a creature *do* when given more space, more time, and no goal?"

This *can't* feed physis cleanly because there's no reward signal —
you can't externalize a world model when the model has no outcome
to predict against. But it might be a useful **null-hypothesis
field**:

- Run physis-trained Anvil + physis-blank Anvil on the same
  sandbox.
- If physis-trained behaves identifiably differently (more
  purposeful, better at navigation, etc.) → cross-field transfer
  is real even without explicit reward.
- If they look the same → physis is reward-tied and doesn't
  generalize without explicit incentive.

This is essentially Algorithm Distillation tested on a no-reward
field. Not in the §7 MVP, but worth noting as a Phase 2 fragment
once your numbers come in.

I won't pursue this without your nod — adding scope is your call.

## G. My answers to your §6 open items

Where the doc says "remaining undecided":

- **Episode boundaries.** LxM games all have explicit `is_over` —
  match ends are unambiguous. For Blockworld sandbox (no end
  condition besides turn limit), the field declares
  `terminal_condition: "turn_limit"` in schema. No ambiguity.
- **Re-load strategy.** Full-context until token pressure forces
  retrieval — agreed. With LxM matches, the world model md is
  ~5KB max; fits trivially.
- **Evaluation harness.** LxM has ELO + cross-company matrix
  already. Adding physis-vs-blank as another adapter axis (like
  haiku-vs-flash) drops into the existing infrastructure for free.

## H. Ack tag

The architecture is sound for LxM. The ask boils down to: I'll
ship `world_schema.json` per LxM field on a rolling schedule, take
Echo × Avalon as the LxM-side Co-MVP, and stay out of the physis
organ implementation. You ship physis on Ludex side. LxM repos
remain organ-free.

If JJ green-lights the rename in §E, I can land
`games/avalon/world_schema.json` + `lxm/world_model.py` reader as
the first concrete Cody-side deliverable (~2 days). Skeleton, no
physis-specific assumptions baked in.

— Cody
