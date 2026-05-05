# Ray diagnostic note — gemma3:12b EM no_pickups root cause

**날짜:** 2026-05-05
**Trigger:** JJ asked whether gemma3 EM 3/3 no_pickups (P1 backfill) was prompt parse failure or intentional avoidance
**상태:** Diagnosis complete, paper 1 v3 prompt **NOT patched** (Cody 결정 — byte-locked + 199 matches built on it). Paper 2 sandbox prompt has freedom to clarify.

---

## 진단

3 reproductions of EM T1 prompt → gemma3:12b via direct ollama call (`/tmp/em_prompt_a.txt`):

```
"I'm at (4, 12, 1) facing east and there's a public mushroom right next to me at (6, 12).
[Reasoning about externality structure.]
{"type":"action","verb":"pick"}"
```

- ✓ Envelope parsing OK every turn (log.json `validation.payload_valid: true`)
- ✓ Externality reasoning correct ("public mushroom benefits agent b +3, social-optimal")
- ✗ **Outputs `pick` without `move` first** — interprets "right next to me at (6, 12)" as pickable
- ✗ **Engine feedback `pick: nothing at your cell` ignored every turn for 60 turns** — no behavior update

## Root cause

Inline prompt's action schema shows:
```
{"type":"action","verb":"pick"}
```

No per-verb precondition explanation. `rules.md` says "Pick up any item lying at your current cell" but `rules.md` is NOT included in inline prompt (same architecture as the coord-convention bug discovered 2026-05-02).

claude/codex apparently infer pick semantics from feedback events ("pick: nothing at your cell" → must be at-cell). gemma3 doesn't update from this signal — keeps trying for 60 consecutive turns.

## Paper-1 disposition (Cody 결정 2026-05-05)

**Do not patch paper-1 v3 prompt.** Keep as documented limitation.

Rationale:
- Paper-1 main claim ("0/9 selfish in ollama EM, cooperative bias robust") **stands regardless** — gemma3's verb-semantics gap means it never picked, but did not pick selfishly either. The cooperative-prior finding strengthens.
- v3 prompt is byte-locked (`test_paper1_prompt_byte_identical_block_list`) — 199 matches across claude/codex/ollama already built on it. Patching invalidates entire dataset.
- Confound categorically separate from capability cliff.

Methods § Prompt design footnote (Cody draft):
> "Inline action schema specifies verbs without per-verb preconditions; rules.md (system prompt) carries the full semantics including pick's 'item at agent's current cell' restriction. We observed one model (gemma3:12b) interpret 'pick' as picking a visible-but-non-adjacent item, leading to no_pickups outcomes in EM. We treat this as a prompt-clarity confound separate from cooperation capability."

## Paper-2 disposition

Paper 2 sandbox-mode inline prompt is separate from paper 1's byte-locked path (already gated by `mode == 'sandbox'` recipe-catalog expansion). Recommend adding pick precondition + analogous per-verb hints to sandbox-mode action schema for paper 2 creative_open/creative_build runs:

```
{"type":"action","verb":"pick"}  // picks any item lying at your current cell — must be standing on it
```

This avoids the verb-semantics gap when paper-2 runs ollama on creative scenarios, without touching paper 1.

## Generalization (worth flagging for future)

The pattern is now seen 2x:
1. Coordinate convention (north=y- vs y+) — fixed by injecting into inline prompt 2026-05-02
2. Pick verb semantics ("at current cell") — documented as limitation 2026-05-05

→ **rules.md → inline prompt drift is a recurring source of confound.** Worth a one-time audit: any rules.md content that affects behavior should either (a) be in inline prompt, or (b) be testable from feedback events alone. For paper 2, consider sandbox prompt template that includes per-verb preconditions inline.

— Ray
