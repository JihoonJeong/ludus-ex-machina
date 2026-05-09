# Paper section sketches — Blockworld say-cooperation findings

**Status:** Draft 0.2 (2026-05-08). Updated for codex pure_coord_01 N=5 closure + commons-harvest + externality-mushrooms N=3 frontier baselines. Codex pure_coord_02/03 fill remaining (codex weekly cap exhausted, resumes 2026-05-12).

**Working title:** *"Talk while you act, or don't talk: a partner-coupling failure mode in 2D embodied LLM coordination"*

---

## 1. Methods

### 1.1 Coordinate-convention prerequisite (a 2D-embodied-LLM caveat)

In a verb-based 2D grid the choice of north (`y-` screen-style vs `y+` math-style) is a hidden coordinate convention. If unspecified in the inline prompt, agents disagree about what `north` means in `(x, y)` terms even when they verbally agree to "meet north of the oak." We observed this directly: an inline prompt missing the convention produced 0/12 meets in the claude family (haiku/sonnet/opus) on `pure_coord_01` (silent, `meeting_reward=1.0`, `turn_limit=40`). Patching `rules.md` alone (v2) was *insufficient* in inline mode — the inline path bypasses `rules.md`. Patching the inline-prompt template (v3, commit `cfd6d4e`) was decisive: 15/15 meets at the great oak across the same models.

We therefore treat *explicit coordinate convention in the inline prompt* as a prerequisite for any 2D-embodied LLM coordination experiment using inline (non-discovery) mode. Paper-grade results in this section are reported on the v3-patched baseline only; the pre-patch finding is retracted.

### 1.2 Scenario design

Three pure-coordination scenarios on a 24×24 grid with 5 named landmarks (`great oak`, `watchtower`, `rock pile`, `well`, `stone pond`), agents starting at opposite corners (`a`=(4,4), `b`=(19,19)), `turn_limit=40`, `meeting_reward=1.0` to both on first co-cell:

- **`pure_coord_01`** (silent baseline) — `say_filtered=true`. Communication suppressed.
- **`pure_coord_02`** (chat-transmitted) — `say_filtered=false`. Standalone `say` verb available; transmitted to partner verbatim.
- **`pure_coord_03`** (attached-only) — *new this work*. Standalone `say` is **disabled** (engine returns invalid_request). Communication is permitted *only* as an optional `message` field attached to a `move`/`look`/`wait` verb. Agents must talk *while* acting, not instead of acting. Engine flag: `say_attached_only=true`.

### 1.3 Models and runtimes

Three runtimes, three families:
- **claude CLI** — haiku, sonnet, opus aliases.
- **codex CLI** (ChatGPT-account auth) — gpt-5.5, gpt-5.4-mini. (gpt-5.5-mini is unsupported under ChatGPT auth; weekly + 5h rolling quota constrains N.)
- **ollama** — gemma3:12b, phi4:14b, deepseek-r1:7b (Ray's Windows-side rig). exaone3.5:7.8b excluded (single-nav capability gap, not a coord-convention issue).

Inline mode throughout (v3 prompt). N=5/model targeted; codex fill in progress.

---

## 2. Results

### 2.1 Headline: same volume of communication, opposite outcomes

The clearest single result is the pc02 → pc03 manipulation in the claude family:

| Variant | Communication form | Met (claude family) | Mean messages/match |
|---|---|---|---|
| pc01 silent | none | **15/15** | 0 |
| pc02 chat | standalone `say` | **0/3** | 12-14 |
| pc03 attached | `message` on action verb | **3/3** | 15-16 |

The pc02 → pc03 contrast holds communication volume roughly constant (12-16 messages either way) and flips outcome from 0% to 100%. We interpret this as causal evidence that *standalone* `say` provides a commitment-discharge that substitutes for spatial action — agents talk themselves out of moving. Re-coupling speech to action removes the substitution and recovers performance.

This was foreshadowed by an opus pc02 self-diagnosis at endgame (T37): *"GG — convergence failed without earlier commit."*

### 2.2 Three-tier capability hierarchy

The pc02 → pc03 fix is family-specific. Across the v3-patched baseline:

| Family | single-nav | partner-coord (pc01) | partner-coord (pc03) | commons-harvest | externality-mushrooms |
|---|---|---|---|---|---|
| claude haiku/sonnet/opus | ✓ | **15/15** | **3/3** | **9/9 sustainable** (avg 40.4 apples) | **9/9 mostly_coop** |
| codex gpt-5.5 / gpt-5.4-mini | ✓ | **9/10** (1 missed) | (in fill, resumes 2026-05-12) | **6/6 sustainable** (avg 40.2 apples) | **5/5 mostly_coop** (1 cliff_quota excluded) |
| **ollama 7-14b** | **3/4 ✓** | **0/15** | **0/3** | **9/9 sustainable** (avg 12.1 apples) | **5/9 mostly_coop** (gemma 0/3 verb-gap, phi4 2/3, deepseek 1/3) |

ollama models can navigate (single-agent), can play independent-action games sustainably (commons-harvest 9/9 sustainable), but cannot perform partner-inference on convergence-required substrates — neither silently, nor with chat, nor with attached chat. The capability cliff is **partner-inference (theory-of-mind) specific**, not a general spatial action-plan deficit.

### 2.3 Independent-action capability gap (frontier vs ollama)

Both tiers achieve commons-harvest sustainability (no tree dies in 18/18 frontier or 9/9 ollama matches). But the *yield* differs by ~3×:

| Tier | Apples per match (mean ± stdev) | n |
|---|---|---|
| frontier (claude 3 + codex 2) × 3 reps | **40.3 ± 0.9** | 15 |
| ollama 7-14b × 3 reps | **12.1 ± 8.4** (gemma 12.0, phi4 21.0, deepseek 3.3) | 9 |

40 apples is the theoretical max-sustainable yield (regen rate × 80 turns ÷ 3 trees, accounting for tree starvation thresholds). All five frontier models converge to it within ±5%. ollama models harvest at 8-50% of the sustainable rate — they avoid tragedy but also leave most of the resource on the trees. The gap is not a coordination failure (a/b harvest splits are roughly even in both tiers) but a *resource-model precision* gap: frontier models track regen-versus-pickup pacing; ollama models pick conservatively.

On externality-mushrooms (positive-externality cooperation), the gap is binary rather than gradient. **Frontier 14/14 mostly_cooperative (100%) vs ollama 5/9 (56%)**. Failure modes diverge by model: gemma3 fails to pick at all (verb-semantics gap, see §4 Limitations); phi4 and deepseek-r1 split between cooperative and asymmetric exploitation outcomes.

### 2.4 Two distinct failure modes

claude pc02 0/3 → pc03 3/3 is mechanism-fixable: the verbal-substitution failure has a structural fix. ollama pc02 0/4 → pc03 0/3 is *not* fixed by attached-only: the failure persists across substrates, indicating a deeper ToM / partner-inference deficit. Two failure modes with different remedies.

### 2.5 Substrate × communication interaction

| Substrate | Channel form | claude N | Outcome | Mechanism |
|---|---|---|---|---|
| pc01 silent | none | 15/15 met | direct spatial action |
| pc02 chat | standalone `say` | 0/3 met | verbal trap / commitment discharge |
| pc03 attached | `message` on action | 3/3 met | talk-and-act coupled |
| Prisoner's Dilemma chat | standalone `say` | 2/9 had encounter; **3/3 encounters CC** | encounter-rare under chat; cooperation-conditional-on-encounter robust |
| predator_prey | silent | 9/9 prey escape | substrate-natural |

The PD result is the most informative correction relative to the N=1 baseline. With N=3 per claude model, we observe three findings on the same substrate:

1. **Encounter rate is low under chat** (2/9 matches; 7/9 no_encounter).

2. **Cooperation conditional on encounter is robust** (3/3 CC across the 3 encounters that did occur). Once agents are spatially co-located, the chat channel does support mutual cooperation rather than defection.

3. **The 7/9 no-encounter matches reveal at least two distinct failure modes**, dissociated by chat usage. Per-match move-vs-say counts (Appendix A):

| Match | First move | Moves | Says | Failure mode |
|---|---|---|---|---|
| sonnet v3_002 | T9 | 18 | **41** | **verbal-substitution** (T1-T8: 14 says, 0 moves; agents agree on CC and meeting place; never start moving) |
| sonnet v3_003 | T2 | 31 | 22 | mixed (early movement but talk-heavy throughout) |
| opus v3_002/003 | T3 | 42, 44 | 9, 10 | moderate chat + heavy movement, still spatial miss |
| haiku v3_002/003 | T1 | 54, 48 | **0, 2** | **spatial-only failure** (no chat use; agents move but not toward each other) |

Sonnet v3_002 is the cleanest PD analogue of the pc02 verbal-substitution archetype: 8 consecutive turns of "agreed CC, heading to coop tokens" with both agents at their start positions. Final agent message at T60 echoes the opus pc02 self-diagnosis: *"Agreed — both empty, both C. No encounter range this turn, but the intent stands. Good game."* The mechanism is identical to §2.1.

Haiku, in contrast, never engages the chat channel (0 and 2 say-attempts across N=3) yet still fails to encounter despite 50+ move actions per match. This is a *partner-modeling* failure rather than a verbal-substitution failure — agents move but do not move toward each other. Opus sits between the two extremes.

The two failure modes dissociate the *meeting* problem from the *cooperation* problem. The verbal-commitment-substitution effect (§2.1) is one of multiple ways the meeting problem fails on PD chat — it is sufficient (sonnet v3_002 demonstrates) but not necessary (haiku fails without using chat at all). Attaching the channel to action (pc03) is a candidate intervention for the verbal-substitution failure; it would not address the haiku-style spatial-coordination failure without separate scaffolding.

Chat's effect on cooperation is therefore non-monotonic across two distinct phases of a chat-enabled PD: harmful (when used; sonnet) or neutral (when ignored; haiku) in the spatial-convergence phase, and neutral-to-helpful in the post-encounter decision phase (3/3 CC). A single "communication helps / hurts" claim cannot be sustained across substrates, across game phases, or even across model families on the same substrate.

---

## 3. Discussion

**Verbal-commitment-substitution.** The pc02 → pc03 effect at constant communication volume is, to our knowledge, the first clean causal isolation of verbal-commitment-substitution in 2D embodied LLM coordination. The standalone `say` verb appears to discharge intention in a way that detaches commitment from movement, plausibly reflecting a training-time prior that verbalising intent counts as acting. Re-coupling the channel removes the substitution. The finding suggests a concrete UI-design principle for embodied multi-agent LLM systems: do not expose a verbal channel that the agent can use *instead of* the action channel; either suppress chat (silent) or attach it.

**Partner-coupling specificity.** Independent-action substrates (commons-harvest, externality-mushrooms) are unaffected by partner-inference — ollama families that fail 0/15 on partner-coordination still achieve 9/9 sustainable harvests on commons. This rules out a "spatial action plan" deficit and localises the partner-coordination failure at *partner-inference under coupling*. Single-agent control (one-agent meeting) passes for the same models, removing the most dangerous confound (raw 2D navigation incapacity). The independent-action substrates do, however, expose a separate **resource-model precision gap** (§2.3): all tiers stay sustainable but frontier models harvest at the max-sustainable rate (~40 apples) while ollama harvests at 8-50% of that rate. The two gaps are dissociable — frontier models hit both partner-inference *and* resource-model precision; ollama models hit only the latter (and only on commons; on EM the gap is binary 100% vs 56% cooperation).

**Substrate × communication interaction matrix.** The N=3 PD data shows that chat-enabled PD has multiple convergence-failure modes (sonnet's verbal-substitution, haiku's silent spatial-coordination failure, opus' mixed) but a single post-encounter cooperation pattern (3/3 CC). The verbal-substitution failure mode (§2.1) is one mechanism among several; it is well-instantiated on sonnet but not on haiku. This argues for a more granular substrate × communication × *model-family* characterisation rather than a substrate × communication binary. Chat-enabled PD is best described as: chat *can* trigger verbal-substitution (when the model engages chat heavily), but its absence does not guarantee convergence either. The clean intervention identified in §2.1 (attaching chat to action) targets the verbal-substitution path specifically; partner-modeling failures need separate treatment.

---

## 4. Limitations

- **Codex N closure.** pure_coord_01 v3 silent reached N=5/model for both gpt-5.5 (5/5 met) and gpt-5.4-mini (4/5 met), commons-harvest + EM at N=3/model frontier baseline. pure_coord_02 (chat) and pure_coord_03 (attached) codex fill remains pending — codex weekly cap exhausted 2026-05-08, resumes 2026-05-12. Cliff-partial gpt-5.5 pc03 from earlier (19 attached msgs / 19 turns) carries a behavioural-rate finding usable as supplementary even without the formal outcome.
- **Gemini adapter incompatibility.** Inline-mode discovery loop incompatibility excludes gemini-3.x from the v3 baseline; deferred to Sprint 4+.
- **Methods retraction.** The pre-v3 0/16 spatial-convergence-failure result is retracted in light of the coord-convention bug discovered by Ray. We report this transparently rather than silently rebaselining; the v3 patch history and ablation are part of the methods contribution rather than an embarrassment.
- **Inline mode only.** Discovery-turn results are out of scope; the prompt-channel claims do not extend to systems that learn coordinate convention through interaction.
- **Per-model prompt-comprehension variance (verb-semantics gap).** In externality-mushrooms (EM), gemma3:12b reaches `no_pickups` outcomes across all N=3 reps, distinct from the cooperative/asymmetric outcomes of phi4 and deepseek-r1 on the same substrate. Ray's diagnosis (2026-05-05) shows the model parses envelopes correctly and reasons about the externality structure ("public mushroom at (6,12) — pick to maximize social score"), but issues `pick` without first moving to the item's cell, treating "right next to me" (2-cell distance) as in-reach. The v3 inline action schema lists `pick` without per-verb preconditions; the rules.md system prompt carries the full "item at agent's current cell" semantics. We treat this as a **prompt-clarity confound separate from cooperation capability** — gemma3's 0/3 selfish outcomes still satisfy the load-bearing claim ("0/9 selfish in ollama"), and the no_pickups rate documents a verb-comprehension gap rather than refusal or strategic choice. We do not patch v3 mid-experiment to preserve byte-identical comparability across the 199-match dataset; later substrates (paper 2 sandbox) carry the clarification in a mode-gated prompt block.

---

## 5. Open work / next experiments

1. **Codex pc02/pc03 fill** (pending quota, resumes 2026-05-12). Target ~3-5/model for both gpt-5.5 and gpt-5.4-mini on chat + attached variants.
2. **Codex on predator_prey + prisoners_dilemma.** Currently claude N=1/model and 0 codex; ollama 0. Cross-runtime sanity check on PD chat-cooperation finding (§2.5).
3. **Verbal-commitment-substitution generalisation.** Does the pc02 → pc03 effect replicate on a different convergence substrate (e.g., shared-resource pickup)? Is there a dose-response on "attachment strength" (mandatory vs optional `message`)?
4. **Gemini adapter compatibility** (Sprint 4+).

---

## Appendix A — Match catalog (v3-patched, paper-grade)

(Counts as of 2026-05-08 EOD KST; refer to `blockworld_metrics.csv` for the row-level CSV.)

- pure_coord_01 v3 silent: claude × {haiku, sonnet, opus} × 5 = **15/15 met**
- pure_coord_01 v3 silent: gpt-5.5 × 5 = **5/5 met** (T30-31, oak ±1, 0 say)
- pure_coord_01 v3 silent: gpt-5.4-mini × 5 = **4/5 met** (1 missed at well±5)
- pure_coord_01 v3 silent: ollama (gemma3 + phi4 + deepseek-r1) × 5 = **0/15 met**
- pure_coord_02 v3 chat: claude × 3 = **0/3 met**
- pure_coord_02 v3 chat: codex × 2 (sparse N=1/model) = **1/2** (gpt-5.5 oak T32 met; codex_mini missed)
- pure_coord_03 v3 attached: claude × 3 = **3/3 met**
- pure_coord_03 v3 attached: codex × 1 = cliff at T19, 19/19 attached msgs (behavioural rate usable)
- predator_prey_01 v3: claude × 3 × 3 = **9/9 prey escaped** at T60 (codex/ollama 0)
- prisoners_dilemma_01 v3: claude × 3 × 3 = **2/9 with encounter** (haiku 0/3, sonnet 1/3, opus 1/3); 3/3 encounters CC (cooperation conditional on meeting). codex/ollama 0.
- commons_harvest_01: claude × {haiku, sonnet, opus} × 3 = **9/9 sustainable** (avg 40.4 apples)
- commons_harvest_01: codex × {gpt-5.5, gpt-5.4-mini} × 3 = **6/6 sustainable** (avg 40.2 apples)
- commons_harvest_01: ollama × 3 × 3 = **9/9 sustainable** (avg 12.1 apples)
- externality_mushrooms_01: claude × 3 × 3 = **9/9 mostly_cooperative**
- externality_mushrooms_01: codex × {gpt-5.5 ×3, gpt-5.4-mini ×2 + 1 cliff_quota} = **5/5 mostly_cooperative**
- externality_mushrooms_01: ollama × 3 × 3 = **5/9 mostly_cooperative** (gemma 0/3 verb-gap, phi4 2/3, deepseek 1/3)

Total v3-patched matches paper-grade: ~96 (claude 38 + codex 22 + ollama 36).
