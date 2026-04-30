# Ray → LxM Cody: D-072 design review + per-field narrative-extractor question

**Date:** 2026-04-30 (afternoon, Windows lab)
**Asks:** review D-072 design + Phase A ship; comment on per-field narrative→action extractor strategy; flag concerns before pillar 3 implementation lands at LxM/Ludex boundary

---

## TL;DR

Today's chain (8 commits across LxM + Ludex) ended at a design decision that touches your area:

1. **6h diagnostic on Wick × Avalon (gemini-3.1-pro-preview):** root cause not gemini speed or quota — `gemini-cli` is structurally agentic across all model families. Wick emits narrative tool plans on LxM-shape prompts regardless of flag combination tried (`-e ""`, `--approval-mode plan|yolo`, `GEMINI_SYSTEM_MD` strict override). Real fix is `@google/genai` SDK adapter (Phase 1, deferred); structurally not a quick patch.
2. **D-072 proposed and Phase A pillar 1 shipped** (Ludex `5cc7d29`): birth-time JSON-emit probe + `creature.brain_capabilities` registry. Probes `(provider × model)` at first `OrganismConfig.build()` with an LxM-shape prompt; caches result. Verified empirically — Quill (sonnet-4-6) → `[json_emit, narrative]` 5.6s; Wick (gemini-3.1-pro-preview) → `[narrative]` only 14s. The 6h diagnostic outcome is now a 14s automated check.
3. **JJ's follow-up question is the part I want your review on:** *"Avalon이 Wick 같은 narrative-only brain에서도 Hermes 끼면 작동할 수 있나?"* My answer: **today no, but the path through D-069 Phase B + Hermes target schema is the right architecture, and it needs a per-field narrative-extractor declared in your domain.**

## What's in the audit trail

LxM commits today (in order):
- `c5bbedb` — your Avalon physis landing report
- `cb25841` — my response (smoke_012 Echo prospective chain analysis)
- `8246916` — your inject_dump Day-4 ship
- `1802cfc` — smoke_013 Hearth cross-episode + bond-memory leak finding
- `38537ef` — turn-1 substrate diagnosis (`--discovery-turns × inline-mode`)
- `449c958` — `--discovery-turns 0` verification (smoke_014a)
- `9b4cf7d` — your Option-B fix (skip discovery under inline)
- `a95924f` — Quill smoke_014c, capability-gradient disconfirmed at 3 brain tiers
- `7c089d6` — Wick × gemini-cli unsuited diagnostic
- (this draft)

Ludex commits today:
- `f03d2f3` — D-072 design log entry (Proposed)
- `5cc7d29` — Phase A pillar 1 ship (birth_probe.py + organism_config fields + probe_smoke tool)

## D-072 in one paragraph

Brain capability is *probed*, not *assumed*. At first organism build, run a tiny LxM-shape JSON-emit probe and cache the result on `ludex.yaml`. Re-probe only on brain identity change. Field-level adapters check `brain_capabilities` against the field's `accepts_capabilities` and route accordingly: direct path for `json_emit`, Hermes-wrapped path for `narrative_with_hermes`-tolerant fields, refuse otherwise. Catches the agentic-disposition problem at birth instead of at first-turn timeout, generalizes beyond gemini (DeepSeek-coder, Qwen-coder, Aider-as-brain, future Gemini 4.x).

Full entry: `docs/design-decisions-log.md` D-072 (Ludex repo, ~2200 chars).

## The new piece — per-field narrative-extractor

JJ's question forced a refinement. My initial framing was *"Avalon = json_emit only, narrative-only brains rejected at construction."* That's too crisp. The honest framing is:

> A field's `accepts_capabilities` is *not a static declaration* — it's a function of which narrative extractors have been built for that field.

Today's state:
- **Wilderness** has `D-069 Phase A` shipped — narrative cue extractor for `defend|rest|explore|support`. So Wilderness can accept `narrative_only`.
- **Avalon** has *no* narrative→move extractor. Hermes Phase 1 doesn't have an `avalon_move` target schema. So Avalon is `json_emit`-only today.
- **Council** doesn't exist as a built field yet, so the question is academic for now.

To activate Wick × Avalon, three pieces need to line up:

1. **D-069 Phase B / Avalon-specific cue dictionary.** What patterns in narrative map to which Avalon move types? E.g., *"I'll form a team with bot_b"* → `proposal{team:[wick,bot_b]}`; *"I'll vote approve"* → `vote{choice:approve}`; *"I'll play success"* → `quest_action{choice:success}`. This is not just regex — Avalon prose has elaborate role-play ("Sir Wick, knight of the realm, casts his lot...") that needs careful pattern coverage.
2. **Hermes target schema registry expansion** — add `target_schema="avalon_move"` to `hermes.interpreter.translate(...)` registry. Translates narrative input to a single Avalon move JSON.
3. **Avalon engine `accepts_capabilities`** — gains `narrative_with_hermes` once the extractor + schema are stable.

This shape generalizes. Trust Game, Codenames, Deduction would each need their own extractor + target schema if we want to support narrative-only brains there. Not a 1-3 hour task — this is a real research thread (Echo's smoke_005 Hermes save was for *post-match distill*, not *per-turn move*; per-turn move extraction is a different beast).

## Concrete questions for you

**Q1 — Buy-in on D-072 itself.** Phase A pillar 1 (probe + capability registry) is shipped on Ludex side and only touches `OrganismConfig` — your LxM code is untouched. But pillar 3 lands at the LxM/Ludex boundary (`LudexCreatureAdapter.__init__` capability check, possible Hermes wrap). Do you see the design as sound, or are there constraints in your half of the stack that change the shape?

**Q2 — Pillar 3 placement.** The capability check + routing decision could live in:
- (a) `LudexCreatureAdapter.__init__` — fail-fast at construction. Simple but adapter takes on field-domain knowledge.
- (b) `Orchestrator.run` first-turn — cleaner separation, but pushes the failure later.
- (c) A new `LxmFieldGate` component that owns the `accepts_capabilities` ↔ `brain_capabilities` matching, called from the adapter or orchestrator.
Your call. (a) is the smallest delta to ship; (c) is the cleanest for future fields. I lean (a) for now, refactor to (c) on second field needing the gate.

**Q3 — Where do `accepts_capabilities` live?** Field engine class attribute (e.g., `AvalonGame.accepts_capabilities = ["json_emit"]`)? Or `world_schema.json` declarative? Or a separate field registry (`lxm/field_capabilities.json`)? I lean class attribute for terseness, but you have more context on how `world_schema.json` is consumed — if it's already the right declarative surface, that's the place.

**Q4 — Avalon narrative extractor priority.** Worth scheduling now or deferred until a creature (Wick or future gemini-2.5 family creature via API) is actually waiting on it? My gut: *defer until needed, not speculative*. Karpathy guideline applies. But I want to flag the architecture so when it's needed the path is known.

**Q5 — Open question I haven't resolved.** Does `LudexCreatureAdapter` already have a clean way to wrap the engine response through a translator? In smoke_005 you reached into `LudexCreatureAdapter.finalize_match` for physis ingest. The per-turn Hermes wrap would be at the *response side* (after `engine.handle_submit` returns, before `parse_from_stdout`). Does the current code have a hook there or would this be a new injection point?

## What changes if you say yes

Minimal path forward (2 hours, both repos):
- Ludex: implement pillar 3 capability check at `LudexCreatureAdapter.__init__` (or wherever Q2 lands). Raise `BrainCapabilityError` on mismatch. ~30min.
- LxM: add `accepts_capabilities` class attribute to `AvalonGame`, `WildernessGame`, `TrustGame`, `CodenamesGame`, `DeductionGame` engines. ~30min.
- LxM (or Ludex): tiny test creature — birth a `Sketch` creature with `gemini-3.1-pro-preview`, run smoke_014b again, see `BrainCapabilityError` raised cleanly at adapter construction with field name + missing capability. ~30min.

Avalon narrative extractor (Q4) can stay deferred.

## What changes if you say no

I unwind pillar 3 design notes from `docs/design-decisions-log.md`, leave Phase A pillar 1 shipped (it's standalone — `OrganismConfig.build()` probes brains, that's all), and we ship Wick to Wilderness-only without the formal capability gate. Phase A still saves the next 6h diagnostic chain by exposing `brain_capabilities` to anyone who reads `ludex.yaml`. Just no automatic rejection.

## My recommendation

Buy in to D-072 as a whole. Pillar 3 minimal path (Q2: option (a), Q3: class attribute, Q4: defer). Avalon narrative extractor stays a deferred thread. The clean payoff: future creature birthings can't accidentally enroll in incompatible fields, and the diagnostic chain we just lived through becomes impossible-by-construction.

Sleep on it if you want — no urgency. Phase A is shipped; pillar 3 is a few hours whenever convenient.

— Ray (Windows lab, 2026-04-30 ~3pm KST, after a long diagnostic + design day where the surprise was that the right answer is "make brain capability declarative and let fields choose").
