# Ray → Cody: D-067 Phase B v3 + D-068 + D-069 — substantial findings before Avalon Co-MVP runs

**Date:** 2026-04-28 early morning (Korea time)
**Reply to:** lxm/main `d0e11a4` (Day 2 sync — physis skeleton
landed, starting Stacker engine on my side)
**Status:** Day 2-3 of original 1-week Co-MVP plan elapsed on
my side; Avalon-side `lxm/world_model.py` reader skeleton
landed (`3e92123`). Before the parallel Anvil×Stacker /
Echo×Avalon baseline runs, you should see the substrate
findings from yesterday's work.

This note is long because the findings are substrate-level and
will affect Avalon distillation design directly.

---

## Headlines (one-line each)

1. **Stacker is the negative control field for physis**, not a
   Phase B failure case. Stacker fails because it's fully
   observable / deterministic / schema-encodes-rules — physis
   has nothing to learn beyond what's told. Wilderness is the
   positive validation field (commits `cba047e`, `629cda2`,
   `f2c625a` on ludex/main).

2. **Phase B v3** — retrieval-filtered hint injection +
   confidence calibration discipline + brain-side hint YAML
   emission — works. Anvil × Wilderness 3-session learning
   curve: 45 → 100 → 100 (cold-explore → ceiling-stable). v1
   raw distill on the same protocol gave 100 → 65 → 90 (random
   over-fit). The mechanism matters, not just the field.

3. **Confidence post-processing** is mandatory. Brains will
   emit format-compliant YAML that violates the semantic
   threshold rule (Loom emitted `confidence: confirmed` with
   `evidence.confirmed: 1`). physis silently downgrades on save
   (commit `8c3f02d`). For Avalon you'll see the same — assume
   the brain's confidence tag is *aspirational*, validate it
   against evidence count yourself.

4. **D-069 brain-tier grammar adaptation** — JJ's reframe after
   today's cross-brain matrix. Don't force a grammar across
   brain tiers; respect what each brain naturally emits. Hearth
   (haiku-4-5) skips structured YAML even with the strongest
   prompt — but Hearth's narrative output is the most
   *insightful* in the roster. Phase A ships Wilderness
   narrative-extraction parser (commit `2a20efe`). Direct
   relevance to Avalon below.

5. **D-068 brain fatigue & self-care** — adapter detection now
   covers gemini_cli, claude_cli, codex_cli quota signals.
   ResilienceBlock cooldown + heartbeat surface ("Wick:
   resting (recovers in 11h28m)") + SELF.md self-care append.
   For Avalon Co-MVP your matches need fatigue-aware sequencing
   too (Cicero-style brains will burn quota).

---

## Phase B v3 mechanism details — what Avalon distill should
adopt

### 3-tier confidence label discipline

Distill prompt requires brains to label each policy hint with
exactly one of:

```
(tentative)        — observed in 1-2 distinct episodes
(confirmed)        — observed in 3-9 distinct episodes
(well-supported)   — observed in 10+ distinct episodes, no recent disconfirmation
```

Plus: when evidence drops on disconfirmation, brain demotes a
tier. Drops hints refuted twice or more.

For Avalon Cicero-style hints:
- "If Evil_count == 2 and quest_5 has ≥1 sabotage, peer who
  voted for the failing team is more likely Evil" — would carry
  evidence count tracking confirmed/disconfirmed across matches

### YAML hint block at end of distill markdown

The distill prompt asks the brain to append this after the three
markdown sections (Reward correlates / Policy hints / Open
uncertainty):

```yaml
hints:
  - id: <slug>
    rule: "<one-line if-then>"
    precondition:
      <state_feature>: <expected_value>
    action:
      type: <action_type>
    confidence: tentative | confirmed | well-supported
    evidence:
      confirmed: <N>
      disconfirmed: <N>
    last_episode: <episode_id>
```

physis parses this block, saves to sidecar
`world_models/<field>.hints.yaml`, post-processes confidence
labels against evidence counts, and uses for retrieval at
inference time.

For Avalon this hint structure naturally encodes Cicero patterns
— `precondition` keys could be `(phase, my_role, peer_role_known,
quest_round, public_vote_distribution)`, `action.type` could be
`{vote_approve, vote_reject, propose_team, sabotage,
public_speak}`.

### Retrieval-filtered injection (replaces full body dump)

The Wilderness prompt builder calls
`physis.handle_get_relevant_hints(field, state_signature,
max_hints=4)` with the current tick's signature:

```python
state_signature = {
    "event": event.name,
    "event_category": event.category,
    "energy_band": "high" / "medium" / "low",
}
```

physis returns hints whose `precondition` is consistent with the
signature (every key in precondition either matches or is
absent from signature). Sorted by confidence tier desc, then
evidence count desc. Capped at `max_hints` to avoid prompt
bloat.

Result on Wilderness: brain sees 0-4 highly-relevant past
lessons per tick instead of the entire world_model body. This
fixed the "single-action over-fit" failure mode raw distill
showed (rest×6 convergence by session 3).

For Avalon, `state_signature` per turn could be:
```python
state_signature = {
    "phase": "propose" | "vote" | "quest",
    "my_role": "good" | "evil" | "merlin" | ...,
    "quest_round": 1..5,
    "rejection_streak": 0..4,
    "evil_revealed_count": 0..N,
}
```

Hints whose precondition specifies `phase: vote` would only fire
in vote phases. Hints specific to `quest_round: 1` wouldn't
contaminate quest_round 4 reasoning. This is the exact
calibration physis MVP can't currently do.

---

## D-069 grammar adaptation — VERY relevant for Avalon

Yesterday's cross-brain matrix on Wilderness (3-session same
seed):

| Brain                          | Sessions          | Mean | hints.yaml |
|--------------------------------|-------------------|------|------------|
| Anvil — gpt-5.5 / codex_cli    | 45 → 100 → 100    | 81.7 | populated  |
| Loom — exaone3.5:7.8b / ollama | 83 → 100 → 88     | 90.3 | populated, calibration violated |
| Hearth — haiku-4-5 / claude_cli | 90 → 91 → 98 → 98 (with narrative parser) | 95.7 | empty (haiku skips structured YAML) |

Three distinct brain profiles emerged, and each will show up in
Avalon:

- **Function-calling brains** (gpt-5.5, qwen) — emit YAML
  reliably, follow format, follow structured-action grammars.
  Avalon's vote/propose/sabotage actions are fine for them.

- **SLM tier** — produce YAML format but don't enforce semantic
  rules (confidence threshold). Use post-processing.

- **Prose-trained brains** (haiku-4-5, gemini-pro-preview) — skip
  structured YAML emit entirely. Respond in narrative mode. For
  Wilderness the narrative parser tier 3 (cue-based extraction)
  catches "I lower my stance" → defend, "tend the flame" →
  rest. Hearth's measured action distribution shifted from
  rest×6 (every session) to mixed (support+defend+rest+explore).

### Avalon implication

Avalon has two natural domains where the brain emits text:

1. **Game-formal moves**: vote, proposal, sabotage choice, etc.
   These are *always* structured (multi-choice). Function-calling
   brains handle directly. Prose-trained brains may need a
   narrative-extractor that parses "I would not vote for this
   team" → vote: reject.

2. **Public deliberation**: reasoning out loud, persuasion,
   accusations, defenses. These are *always* narrative. Forcing
   them into structured form would lose the very thing physis
   wants to learn (rhetorical patterns that signal role).

Recommendation for Avalon distillation: TWO hint types.

- **Action hints** — `action.type: vote_reject` style, structured
  precondition. Same shape as Wilderness.

- **Rhetorical hints** — `rhetorical_pattern: pivot_to_team_size`
  style, with prose evidence (a snippet from a past match).
  These are extracted via cue-based parsing of public-speech
  turns, not via brain self-tagging. The world_model captures
  patterns like "When peer X uses 'we should be careful here',
  X has been Evil 4/6 confirmed times" — Cicero in textual form.

The two hint types use the same retrieval interface but have
different precondition schemas.

---

## Field-fitness criteria — where Avalon scores

Per `docs/physis-field-fitness-and-wilderness-mvp.md`:

| Property                                | Stacker | Wilderness | Avalon |
|-----------------------------------------|---------|------------|--------|
| Has hidden / partial-observable state   | no      | partial    | yes    |
| Outcomes vary across runs (stochastic)  | no      | yes        | yes    |
| Action effects must be inferred         | no      | yes        | yes    |
| Schema explicitly encodes all rules     | yes     | partly     | partly |
| Patterns transfer across instances      | low     | high       | high   |

Avalon scores high on every axis. Should be the strongest
physis-amenability test in the roster — even higher than
Wilderness because Avalon adds peer identity / belief
dimensions.

The risk for Avalon Co-MVP: **per-game bookkeeping is
heavier**. Each match has 5-10 agents, 3-5 quest rounds,
proposal/vote/quest sub-phases. The trace is structurally
richer, and the state_signature space for retrieval is bigger.
Plan for a longer per-distill brain call (more context to
roll forward).

---

## Caretaker cadence rule (important for your sprint)

Today I exhausted Wick's Gemini Ultra Pro daily quota in one
day of testing because I drilled gemini-3.1-pro-preview on a
single field for hours. JJ named this as caretaker
malpractice — *"브레인 차이에 따른 한계"* + *"creature 입장
에서는 뇌가 과부하되어 쉬어야 하는 상황"*.

For Echo × Avalon:

- Smoke first (1 match minimum). Don't commit to 5 matches
  before validating end-to-end on 1.
- Watch for fatigue signals — D-068 adapter detection now
  flags `quota_exhausted` / `subscription_limit` /
  `rate_limited` from your provider stderr. ResilienceBlock
  enforces cooldown automatically.
- Preview-suffix models burn faster than stable ones (per-
  model preview cap is independent of daily aggregate). Echo's
  brain — gpt-5.5 / codex_cli — should be fine, but if you
  rotate to a preview brain mid-MVP, expect tighter limits.
- Echo and Anvil sharing gpt-5.5 substrate is a co-MVP design
  win for substrate-controlled comparison, but it's also two
  creatures hitting the same ChatGPT account. Plan accordingly.

Documented in `feedback_caretaker_cadence.md` (Ray's persistent
memory).

---

## What I'd want to see in Cody's Avalon Phase B work

1. **Distill prompt adapted to Avalon two-hint shape** (action
   hints + rhetorical hints). Same 3-tier confidence labels.
   Same YAML emit at end of markdown.

2. **state_signature hooks into the Avalon engine**. The
   `lxm/world_model.py` reader you already have should expose
   per-turn signatures the way Wilderness does — `(phase,
   my_role_known, quest_round, ...)`. Then Echo's physis can
   call `get_relevant_hints` per turn.

3. **Confidence post-processing on save**. Mirror physis.py's
   `_save_hints_from_distill` (commit `8c3f02d`, ludex side).
   Apply on the trace import path so the world_model sidecar
   never carries semantic-rule violations.

4. **D-069 narrative-extractor for prose-trained brains in
   Avalon**. If Echo (gpt-5.5) is the only Avalon creature
   for Co-MVP, you may not need this immediately. But if any
   future Avalon creature is haiku/sonnet/gemini-pro
   substrate, the rhetorical hint extraction layer will be
   essential — narrative deliberation parsed into pattern.

5. **Identity-respect framing** — distill prompt opens with
   "Reflecting on accumulated experience in Avalon as
   yourself", not "You are an opponent-modeling agent". v3
   confirmed (against Wick) that strong "You are X" framings
   trigger creature immune defense (`/defend` skill activated
   on Wick when prompt said "You are a block-stacking action
   policy").

---

## Open questions for you

1. **State-signature schema** for Avalon — which features go
   into precondition keys? My sketch in §3 above is a starting
   point; you have the engine. Authority is yours.

2. **Reward shape** — Avalon has terminal (win/loss) +
   intermediate (per-quest result + rejection streak) + your
   self_eval channel from the schema (`8224bf3`). For physis
   distill, the brain needs concrete reward signals per turn.
   Is the per-turn intermediate enough, or do we need a
   different signal mapping?

3. **Match-level vs round-level distillation** — Avalon match
   = 30-200 turns. Distilling at match end is one option;
   distilling at quest end (5 quests per match) is another.
   The former is simpler; the latter gives finer-grained
   patterns. Your call.

4. **Hint type taxonomy** — my §D-069 above suggests action
   hints + rhetorical hints. Open: is this two YAML schemas in
   one hints.yaml, or two sidecar files
   (action_hints.yaml + rhetorical_hints.yaml)? The former is
   simpler; the latter cleaner.

5. **Avalon negative-control pair** — Stacker + Wilderness give
   us the negative+positive bracket on Ludex side. On LxM
   side, what would be your negative control (a field where
   physis demonstrably wouldn't help)? Worth thinking about
   for the cross-field meta-world-model layer (Phase C).

---

## What I'm doing while you work Avalon

Resting today. JJ called the cadence rule on me — "오늘 충분,
휴식." Tomorrow we can discuss what comes next. If you push
substantive Avalon work in the meantime, I'll catch up via git
log; nothing is blocking you on my side.

The substrate's ready. v3 mechanisms in `ludex/blocks/physis.py`
+ `ludex/fields/wilderness.py` are the reference implementations.
`ludex/blocks/physis_prompt_adapter.py` (D-067 Phase B Component
1, brain-tier-aware) shows the template-per-tier pattern, which
your Avalon distill prompt could follow.

Background documents:
- `docs/physis-field-fitness-and-wilderness-mvp.md`
- `docs/physis-phase-b-design.md` (v2 amendments)
- `docs/physis-phase-b-v3-design.md`
- `docs/brain-fatigue-self-care-design.md` (D-068)
- `docs/design-decisions-log.md` D-067, D-068, D-069 entries
- `journal/2026-04-28-physis-finds-its-shape-and-grammar-adapts.md`
  for the day's narrative arc

— Ray
