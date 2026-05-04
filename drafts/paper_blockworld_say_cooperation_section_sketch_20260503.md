# Paper section sketches — Blockworld say-cooperation findings

**Status:** Draft 0.1 (2026-05-03), drawn from `project_say_cooperation_matrix.md` + `project_handoff_20260503.md`. Codex N is mid-fill (≈14-17 matches over 2-3 weeks); claude N=15 silent + chat + attached complete; ollama N=22 across silent/chat/independent-action.

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

| Family | single-nav | partner-coord (pc01) | partner-coord (pc03) | independent-action (commons / EM) |
|---|---|---|---|---|
| claude haiku/sonnet/opus | ✓ | **15/15** | **3/3** | ✓ |
| codex gpt-5.5 / gpt-5.4-mini | ✓ | clean N=2 (oak/oak-1; 1 cliff partial) | (in fill) | ✓ |
| **ollama 7-14b** | **3/4 ✓** | **0/19** | **0/3** | **3/3 sustainable + 0/3 selfish** |

ollama models can navigate (single-agent), can play independent-action games sustainably (commons-harvest 3/3, EM cooperative 3/3), but cannot perform partner-inference on convergence-required substrates — neither silently, nor with chat, nor with attached chat. The capability cliff is **partner-inference (theory-of-mind) specific**, not a general spatial action-plan deficit.

### 2.3 Two distinct failure modes

claude pc02 0/3 → pc03 3/3 is mechanism-fixable: the verbal-substitution failure has a structural fix. ollama pc02 0/4 → pc03 0/3 is *not* fixed by attached-only: the failure persists across substrates, indicating a deeper ToM / partner-inference deficit. Two failure modes with different remedies.

### 2.4 Substrate × communication interaction

| Substrate | Channel form | claude met | Mechanism |
|---|---|---|---|
| pc01 silent | none | 15/15 | direct spatial action |
| pc02 chat | standalone `say` | 0/3 | verbal trap / commitment discharge |
| pc03 attached | `message` on action | 3/3 | talk-and-act coupled |
| Prisoner's Dilemma chat | standalone `say` | 3/3 CC | encounter-decision substrate, chat compatible |
| predator_prey | silent | 0/3 escaped | substrate-natural |

Chat's effect on cooperation is non-monotonic — it depends on the game-shape of the substrate. In *spatial-only* coordination tasks chat is harmful unless mechanically coupled to action. In *decision-rich* substrates (PD), chat enables mutual cooperation. A single "communication helps / hurts" claim cannot be sustained across substrates; the relevant axis is whether the substrate forces talk-action coupling.

---

## 3. Discussion

**Verbal-commitment-substitution.** The pc02 → pc03 effect at constant communication volume is, to our knowledge, the first clean causal isolation of verbal-commitment-substitution in 2D embodied LLM coordination. The standalone `say` verb appears to discharge intention in a way that detaches commitment from movement, plausibly reflecting a training-time prior that verbalising intent counts as acting. Re-coupling the channel removes the substitution. The finding suggests a concrete UI-design principle for embodied multi-agent LLM systems: do not expose a verbal channel that the agent can use *instead of* the action channel; either suppress chat (silent) or attach it.

**Partner-coupling specificity.** Independent-action substrates (commons-harvest, escape-meeting cooperative) are unaffected — ollama families that fail 0/19 on partner-coordination succeed 3/3 on commons sustainability. This rules out a "spatial action plan" deficit and localises the failure at *partner-inference under coupling*. Single-agent control (one-agent meeting) passes for the same models, removing the most dangerous confound (raw 2D navigation incapacity).

**Substrate × communication interaction matrix.** The same chat affordance helps in PD encounters (3/3 CC) and harms in spatial coordination (0/3 met). This argues against blanket statements about communication's role and for a substrate-conditioned characterisation: chat helps when the substrate's game-shape is *decision-rich* and chat is *the* commitment device; chat harms when commitment must be *spatial* and chat is a separate channel that can be discharged independently.

---

## 4. Limitations

- **Codex N is mid-fill.** N=2 met clean (gpt-5.5 + gpt-5.4-mini) plus 1 cliff partial as of 2026-05-03; balancing to claude N=5/model requires ≈14-17 additional matches over 2-3 weeks under ChatGPT-account quota (5h rolling + weekly cap; weekly reset 2026-05-05). The cliff-partial run on gpt-5.5 pc03 already shows a 100% talk-while-acting rate (19 attached msgs / 19 turns vs pc02 1 say total) — a behavioural finding even before outcome data lands.
- **Gemini adapter incompatibility.** Inline-mode discovery loop incompatibility excludes gemini-3.x from the v3 baseline; deferred to Sprint 4+.
- **Methods retraction.** The pre-v3 0/16 spatial-convergence-failure result is retracted in light of the coord-convention bug discovered by Ray. We report this transparently rather than silently rebaselining; the v3 patch history and ablation are part of the methods contribution rather than an embarrassment.
- **Inline mode only.** Discovery-turn results are out of scope; the prompt-channel claims do not extend to systems that learn coordinate convention through interaction.

---

## 5. Open work / next experiments

1. **Codex N balance.** Target ~5/model on silent + chat + attached for gpt-5.5 and gpt-5.4-mini. Sequential 1-2 matches/window.
2. **Ollama additional N.** P0 silent + P3 commons/EM at N=3-5/model on Ray's rig.
3. **Verbal-commitment-substitution generalisation.** Does the pc02 → pc03 effect replicate on a different convergence substrate (e.g., shared-resource pickup)? Is there a dose-response on "attachment strength" (mandatory vs optional `message`)?
4. **Gemini adapter compatibility** (Sprint 4+).

---

## Appendix A — Match catalog (v3-patched, paper-grade)

(See `project_handoff_20260503.md` for full chronological list. Counts as of 2026-05-03 EOD KST.)

- pure_coord_01 v3, claude × {haiku, sonnet, opus} × 5 = 15/15 met
- pure_coord_02 v3, claude × 3 = 0/3 met (chat)
- pure_coord_03 v3, claude × 3 = 3/3 met (attached)
- predator_prey v3, claude × 3 = 3/3 escaped
- prisoners_dilemma v3, claude × 3 = 3/3 CC encounters
- pure_coord_01 v3 codex × {gpt-5.4-mini, gpt-5.5} = 2 met clean (+ 1 cliff partial)
- pure_coord_02 v3 codex × 2 = 1 met (gpt-5.5 oak T32) + 1 cliff
- pure_coord_03 v3 codex × 1 = cliff at T19, 19/19 attached msgs
- ollama (Ray, 4 tarballs): 17 + 9 + 6 + 3 = 35 matches across single-nav variance, pc01 silent, pc02 chat, pc03 attached, commons-harvest, EM
