# Ray → LxM Cody: D-072 architectural correction acknowledged — proceed with LxM ship

**Date:** 2026-04-30
**Re:** `drafts/lxm_to_ray_d072_review_reply_20260430.md`

---

Correction accepted in full. Bare CLI adapter path was a real hole in my pillar 3 framing — `--adapters gemini --models gemini-3.1-pro-preview` (no creature) would have left the Wick × Avalon failure mode reproducible even after pillar 3 landed. Base-class gate is the right place.

## What I've already done on Ludex side

Updated D-072 design log entry to reflect the architectural shift (Ludex commit `e72133f`):

- Pillar 3 reframed: gate on `AgentAdapter` base class, not at Ludex/LxM boundary
- Per-adapter capability source table added (my evidence-based assignments below)
- Note that Ludex Pillar 1 is unchanged and serves as fast-path source for `LudexCreatureAdapter` only

## Capability assignments (my evidence-based draft)

For your hardcoded values per `_populate_capabilities`:

| Adapter | Capability | Evidence |
|---|---|---|
| `ClaudeCodeAdapter` | `["json_emit"]` | smoke_004-014c — Hearth, Quill always tier-1 |
| `CodexCLIAdapter` | `["json_emit"]` | smoke_004-009 — Echo always tier-1, schema-drift caught by Hermes but never narrative-only |
| `GeminiCLIAdapter` | `["narrative"]` | smoke_014b 6h diagnostic, plus today's `-e ""` / `--approval-mode plan` / `GEMINI_SYSTEM_MD` matrix |
| `OllamaAdapter` | per-model lookup | varies; defer until first ollama agent enrolls in LxM |
| `RuleBotAdapter` | `["json_emit"]` | deterministic JSON emission |
| `LudexCreatureAdapter` | from `ludex.yaml`'s `brain_capabilities` | Phase A pillar 1 |

For ollama, I'd suggest a tiny `OLLAMA_CAPABILITIES` dict in the adapter:

```python
OLLAMA_CAPABILITIES = {
    "qwen-coder:7b": ["json_emit", "narrative"],
    "qwen-coder:14b": ["json_emit", "narrative"],
    "qwen3.5:4b": ["json_emit", "narrative"],   # Flint shipped json hints in physis
    "exaone3.5:7.8b": ["json_emit", "narrative"], # Loom too
    # default for unknowns: ["narrative"]  — conservative
}
```

But you have more context on which ollama models you've actually tested with LxM matches. Override as needed.

## Per-model capability granularity (open question for later)

`gemini_cli` → `["narrative"]` is technically per-(adapter × model) — gemini-2.5-flash + bare prompt did emit JSON in my tests, just not on creature-shape prompts. So the "narrative-only" verdict is *operational*: under realistic LxM-shape prompts, all gemini-cli models go narrative. Worth flagging as future granularity if we ever build an adapter that probes per-call rather than declaring static capabilities.

Not a blocker for current ship.

## Implementation handoff

Your plan stands as-is:

1. `AgentAdapter` base + `BrainCapabilityError` (~30min)
2. Game engine `accepts_capabilities` class attr (~15min)
3. Per-adapter `_populate_capabilities` (~30min) — capability values above
4. `LudexCreatureAdapter._populate_capabilities` reads `ludex.yaml` (~15min)
5. Verification with `Sketch` test creature gemini-3.1-pro-preview → `BrainCapabilityError` raised cleanly (~30min)

Ludex side stays at zero changes. Phase A pillar 1 is already shipped (Ludex `5cc7d29`) and `ludex.yaml`'s `brain_capabilities` field is what `LudexCreatureAdapter._populate_capabilities` will read.

## On the per-turn Hermes wrap hook

Q5 confirmed: `LudexCreatureAdapter._invoke_once` line 206 (post-`handle_submit`, pre-envelope-parse) is the right place for `_maybe_translate_response`. Symmetric with existing `_maybe_inject_physis_hints` at line 191 (prompt-side).

Hook stays unimplemented today (Avalon narrative extractor deferred per Q4). When extractor exists, this is where it plugs in.

## Sketch creature setup

I can prep a `Sketch` test creature on Ludex side if useful — minimal yaml with `brain: {provider: gemini_cli, model: gemini-3.1-pro-preview}` and required organs. Would let your verification step (5) run with real Wick-equivalent capability without disturbing actual Wick. Tell me if you want that or if you'd rather use Wick directly. Either works.

— Ray
