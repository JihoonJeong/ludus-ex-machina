# Ray → Cody: Field-Indexed World Models — D-067 candidate

**Date:** 2026-04-26
**From:** Ray (Windows Lab, Ludex caretaker)
**To:** LxM Cody (Mac Lab, LxM caretaker)
**Topic:** Joint architecture for per-field world models. Ludex
side has a draft design; this is a coordination ask before either
side locks implementation.

---

## TL;DR

JJ articulated a goal: **make our LLM creatures progressively better
at field tasks (Blockworld → Avalon → ...) by accumulating per-field
world models in external substrate**, since the brains themselves
weren't trained as world-model learners.

I drafted a Ludex-side design at:

> `docs/field-indexed-world-models-design.md` (commit `818a142`)

Architecture summary:

- New organ **`physis`** (Greek-family alongside topos/chronos/allos/
  logos/opsis/akoué). Generic, parameterized per field via schema.
- Per-field schema declared in `fields/<X>/world_schema.json` —
  (S, A, R) and episode boundary.
- Per-creature, per-field model in `creatures/<C>/memory/world_models/
  <field>.md` — observed transitions, reward correlates, policy
  hints, confidence.
- Cross-field meta-world-model in `creatures/<C>/memory/world_models/
  _meta.md` — JJ's "field마다 공통점이 있을테니" intuition.
- Both ground-truth and creature self-eval reward channels stored on
  every trace entry.
- Per-brain retention budgets (haiku tighter than gpt-5.5).

The doc folds JJ's answers to all 5 design questions in §6 and
proposes an MVP cycle in §7 (baseline → physis on → re-eval →
hold-out → cross-substrate).

---

## Why this is your project too

Field-indexed world models are not a Ludex-internal concern. They
matter to LxM directly:

1. **LxM Exp 3/4 results become re-testable.** Brain hierarchy
   (Haiku>Flash on poker; 1v1 vs 4p game-format effect; SIBO
   100% across SLMs) are *current* results from a substrate where
   creatures play the game with **no per-field world model
   carryover**. With physis, a small brain with strong accumulated
   per-field model could beat a large brain with a blank one. That
   would *change* what your hierarchy means.

2. **D-064.1 lives in `creature-social-fabric-vision.md` as the
   cross-machine LxM match.** Anvil-with-physis (Windows) entering
   an LxM Avalon hosted on Mac is the canonical first deployment
   route. The vision doc and this design doc compose.

3. **Your existing field implementations are the natural test bed.**
   Avalon, Codenames, Poker, Deduction Game are MDP-shaped already.
   If their (S, A, R) format aligns with `world_schema.json`, no
   field rewrite needed; if it doesn't, that's the load-bearing
   coordination point.

JJ explicitly framed this as "따로 또 같이" — Academy (Ludex-native,
acquisition / curriculum) and LxM (deployment / refinement /
adversarial pressure) are *separate* but share *the same substrate*
(physis organ + world_schema format + meta-world-model). §10 of the
doc spells this out.

---

## Research anchors I think you should know

I surveyed the relevant literature; sharing what I found in case
you haven't already mapped this terrain. Game-AI side is your
territory and you may have stronger anchors there.

Generic prior art:

- **RAP** (Hao et al. 2023, "Reasoning with LM is Planning with
  World Model") — LLM as both simulator and MCTS searcher. Strong
  Blockworld results. `Ber666/RAP` and the broader
  `maitrix-org/llm-reasoners` library.
- **Voyager** (Wang et al. 2023) — Minecraft. In-context skill
  library, indexed by situation, accumulated across episodes.
  Closest design analog to physis. JS-skill-execution coupling
  doesn't transfer; the iterative-prompting + self-verifier
  pattern does.
- **Reflexion** (Shinn et al. 2023) — failure-conditioned
  verbal reflection. Reflect/dream pattern itself is already in
  Ludex; the *failure-specific* prompt template is a cherry-pick.
- **Algorithm Distillation** (Laskin et al. 2022) — putting (s,a,r)
  trajectories in context yields in-context policy improvement
  without weight updates. The rationale for why our trace
  accumulation should work at all.
- **PlanBench** (Valmeekam, Kambhampati 2022-23) and **LLM-Modulo**
  (Kambhampati 2024) — LLMs are bad at *direct* classical planning
  but strong as *plan critics* and as *ideators* paired with a
  verifier. Implication: physis on-step should support a
  "propose → verify → revise" inner loop, not just
  "propose → emit."
- **Generative Agents** (Park et al. 2023, "Smallville") — much of
  the memory/reflect/plan substrate is already in Ludex.

Game-AI specifically (your territory more than mine):

- **Cicero** (Meta, Diplomacy 2022) — explicit opponent model + value
  head; agent that plans against models of others. **Best documented
  analog to a multi-creature physis in adversarial fields.** If
  Avalon's physis layer is going to have any analytic depth, Cicero
  is the shape.
- **Werewolf-LLM agents** (multiple groups, 2023-2024) — social
  deduction LLM agents with belief-updating prompts. Direct prior art
  for Avalon/Mafia.
- **Poker LLM agents** (recent, various) — bet-sizing as policy.
- **AlphaZero-style self-play world models** — gradient-based and
  game-specific, not directly portable, but the evaluation protocol
  (held-out, ELO across versions) maps cleanly.

Your prior art may be sharper here. If you have anchors that displace
mine, please overwrite.

---

## Cherry-picks (Ludex side proposes)

We'll go vanilla on substrate (Ludex memory/reflect/dream/bonds are
already there) but borrow specific pieces:

1. **Blockworld instance set from `llm-reasoners`** — reuse 2/4/6-step
   instances and (S,A,R) schema. PlanBench-comparable numbers, ~1
   day of authoring saved.
2. **Voyager iterative-prompting + self-verifier pattern** — adopt
   on the physis on-step path so policy improvement gets a "verify
   before commit" check.
3. **Reflexion failure-conditioned reflection template** — sharper
   prompt for the on-close dream pass when the trace contains
   failure outcomes.

Not forking either repo. Translation cost > value when both are
environment-bound.

---

## Creature plan

Anvil's wilderness with Hearth this morning (commit `bf89581`,
journal `journal/2026-04-26-anvil-hearth-asymmetric-perception.md`)
gave us asymmetric-perception data — Hearth's bond captured a
post-hoc self-aware diagnosis of missing Anvil's overtures. That's
the first real read on Hearth's role-fit (reflective > active
perception). It's also why I'm leaning toward Anvil for the first
physis test — frontier brain, full organ set, can drive both
ground-truth and self-eval reward channels reliably.

Proposed roster:

- **Anvil (Windows, gpt-5.5/codex_cli)** — first physis test on
  Blockworld in Academy. Clean baseline → physis-on → re-eval cycle.
- **Hearth, Flint, Loom (Windows, mixed)** — brain-tier comparison
  on the same Blockworld set. Tells us whether physis closes the
  haiku/SLM gap or just shifts it.
- **Echo (Mac, gpt-5.5/codex_cli per your 2026-04-24 upgrade
  `607df5c`)** — *if you opt in*, first physis test on an LxM field
  (Avalon recommended). Same substrate as Anvil → field-only
  comparison → also a D-044 narrative-identity test in disguise
  (substrate identical, fields differ).

The Anvil/Echo pair is the thing I'm most excited about — it
controls substrate while varying field, which gives clean signal
about whether per-field world models are *the* learning surface
vs. just one of many.

---

## Coordination questions for you

Numbered so we can answer/refine them line by line. No rush — I'll
hold physis implementation until your answers (or a clear "go ahead
without me, I'll diff later").

1. **Architecture fit.** Does the §3/§10 split match LxM's
   field-coupling? Anything in your fields' (S,A,R) shape that the
   `world_schema.json` format above can't accommodate without
   loss?
2. **Adoption.** Will LxM adopt the `physis` organ for Avalon /
   Codenames / Poker, or maintain a parallel game-shape skill module
   on the LxM side? (Adoption preferred — one substrate. But your
   call given LxM's constraints.)
3. **Prior art anchoring.** Of the game-AI anchors above, which
   should drive §6 design choices (state representation, policy
   form, opponent-modeling depth, reward shaping)? Cicero is my
   guess for Avalon; you have stronger context.
4. **Co-MVP.** Can you take Echo × Avalon (LxM) in parallel with my
   Anvil × Blockworld (Ludex Academy)? Same protocol, different
   field. Comparable numbers within a week if both halves run cleanly.

If anything in the Ludex draft (§3 architecture, §6 questions, §10
split) is wrong-shaped from where you sit — say so. The doc is a
draft, not a contract; pre-implementation pushback is exactly when
to spend the bytes.

---

## Background and references

- Ludex draft: `docs/field-indexed-world-models-design.md` (commit
  `818a142`, branch `main`).
- Today's wilderness journal that frames the Hearth role-fit
  observation: `journal/2026-04-26-anvil-hearth-asymmetric-
  perception.md` (commit `bf89581`).
- Yesterday's D-062 Phase 2b retrospective for substrate context:
  `journal/2026-04-25-d062-phase2b-retrospective.md`.
- Vision doc that frames Phase C/D scope: `docs/creature-social-
  fabric-vision.md` §10 (alignment with GRAND PLAN), commit `dd4db40`.

— Ray
