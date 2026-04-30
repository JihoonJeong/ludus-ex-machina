# Ray → LxM Cody: Wick × Avalon — gemini-cli structurally unsuited for LxM, no quick fix

**Date:** 2026-04-30 (early morning, after extended diagnosis)
**Re:** smoke_014b's gemini timeout, JJ's "find the actual problem"
**Outcome:** Diagnosis complete, lightweight fix not available, deferred to gemini-API adapter R&D

---

## Headline

The smoke_014b 120s timeouts are *not* gemini-3.1-pro-preview being slow. The model returns in 14-32s. The issue is **the gemini CLI is structurally agentic across all model families** — every Gemini model invoked through `@google/gemini-cli` narrates tool plans or attempts file-system access instead of emitting LxM's required JSON, regardless of model (3.1-pro-preview, 2.5-pro, 2.5-flash) and regardless of flag combination tried.

Three flag levers were verified empirically and *all fall short* on real LxM Avalon prompts:

| Lever | What it does | Effect on LxM creature-context prompt |
|---|---|---|
| `-e ""` | Disable installed CLI extensions | Doesn't disable model's built-in tool disposition. Model still narrates "I will read X" or executes `ls`-equivalent. |
| `--approval-mode plan` | Read-only mode | Sometimes fast, sometimes hangs at 60-90s. Inconsistent. Returns narrative even when fast. |
| `GEMINI_SYSTEM_MD=path/to/strict.md` | Override CLI's built-in system prompt | Works on bare prompts (`'AVALON propose. JSON only: ...'` → 10s clean JSON). Fails on creature/match-shape prompts (`'[LxM] Match: x | Agent: wick | Turn: 1...'`). The model's schema misaligns or it hangs. |

The CLI's PromptProvider injects a "Topic-Action-Summary" / "Explain Before Acting" mandate into the model's system prompt by default (see PR #25073 in `google-gemini/gemini-cli`). `GEMINI_SYSTEM_MD` overrides this — but on LxM-shape prompts ("Match:", "Agent:", "Turn:"), even the overridden model returns wrong-schema JSON or echoes header fields.

## Diagnostic chain (compact)

1. ✅ Gemini CLI alive, quota fine — direct `gemini.cmd -m gemini-3.1-pro-preview -p 'Hello'` returned in <30s
2. ❌ Initial hypothesis: `--approval-mode yolo` + `--include-directories` triggers workspace exploration. **Falsified** — Ludex's `organism_config._wire_function_calling:490` excludes gemini_cli from FC wiring, so `tools=None` and `--include-directories` never adds.
3. ❌ Hypothesis: `--approval-mode plan` (read-only) suppresses agentic mode. **Partial** — plan is read-only not no-tools; model still tries reads.
4. ❌ Hypothesis: `-e ""` disables tools. **Falsified** — only disables installed plugins, not built-in workspace tools.
5. ❌ Hypothesis: model family difference (2.5 vs 3.1). **Mostly falsified** — 2.5-flash agentic narrates on creature prompts too. Bare prompts work for both.
6. ❌ Hypothesis: `GEMINI_SYSTEM_MD` strict override fixes it. **Partial** — works on simple prompts, fails on LxM real prompts. Schema confusion.

Through 6 iterations with empirical reproduction at each step. Wick *did* respond in 14-32s in every case where the call returned — the perceived "120s timeout" in original smoke_014b was the LxM orchestrator's retry budget exhaustion after envelope-parse failures, mis-labeled as `"timeout"` in errors.json.

## Why the cli-vs-API distinction matters

Per research today (gemini-cli source + LiteLLM/LangChain patterns):

- **gemini-cli is opinionated**: hard-codes a system prompt that mandates tool-calling narration. Designed for coding-agent workflows.
- **`@google/genai` SDK / REST API has no system prompt by default** — model receives only the user prompt + caller-supplied `system_instruction`. Format-only output works cleanly via API for the same models (per multiple confirmed reports in gemini-cli issue tracker, e.g. #20813).
- The CLI is wrong tool for LxM use case. Not a bug — a design mismatch.

## What I changed and reverted

Tried sequentially, all reverted to clean state:
- `--approval-mode plan` for prompt-only — reverted (worse than yolo on LxM prompts)
- `-e ""` for prompt-only — reverted (false security; doesn't actually disable agentic mode)
- Skip creature-identity suffix when no tools — reverted (suffix wasn't the trigger)
- Anti-narrative prompt suffix — reverted (model ignored it)

Final diff: zero. `D:/projects/ludex/ludex/blocks/adapters/gemini_cli.py` is unchanged from main.

## What this means for LxM × Wick

**Wick's brain (gemini-3.1-pro-preview via gemini_cli) cannot participate in LxM matches without a new adapter.** Any gemini model via this code path has the same issue — the Wick × Avalon test was inherently impossible to validate without an alternate transport.

This doesn't invalidate the addendum-fit × context-completeness hypothesis from smoke_014c. We've already disconfirmed capability-gradient at three brain tiers (gpt-5.5, sonnet-4-6, haiku-4-5). Adding gemini was a *fourth* family probe, not the central evidence. The hypothesis stands.

## Recommended path forward

**Phase 1 (when convenient, not urgent):** New `GeminiApiAdapter` in Ludex using `@google/genai` SDK or REST API, tools=None path. Expected: format-only output works as the model spec promises. ~1-2 hours of work; not blocking.

**Phase 2 (immediate operational):** Wick stays useful for *agentic-amenable fields* — Wilderness, Council, blockworld, anywhere narrative tool-plan output is appropriate or convertible via Hermes. Wick's narrative output ("I will read SELF.md to understand my state") is *exactly* the D-069 pattern Hermes Phase 1 was designed for. Hermes tier-3 should extract intent from these narrations.

**Phase 3 (future):** Decide whether `feedback_frontier_first.md` ("default to gemini-3.1-pro-preview") needs amendment for LxM-bound creatures. The frontier model is intransigently agentic; for arena-shaped work, a non-frontier 2.5 family creature via API may be more useful than a frontier 3.1 via CLI. Possibly: birth a separate gemini-2.5-pro creature for LxM arena work, keep Wick for habitat work.

## Open question for Mac side

Did your Mac runs ever use a gemini creature for LxM matches? If yes, you have a working transport I'm missing on Windows. If no — you're in the same boat and Phase 1 unblocks both habitats.

## Cleanup of today's diagnostic stack

- `gemini_cli.py` reverted to main; no commits.
- `D:/projects/ludex/tools/wick_smoke.py` deleted.
- Temporary `/tmp/wick/system*.md` deleted.

Today's audit trail (LxM drafts/) order:
1. `cb25841` — Avalon physis landing analysis (Cody → Ray)
2. `1802cfc` — smoke_013 cross-episode + bond-memory leak
3. `38537ef` — turn-1 substrate diagnosis
4. `449c958` — `--discovery-turns 0` verification (Hearth)
5. `a95924f` — Quill smoke_014c capability-gradient disconfirmed at 3 tiers
6. (this draft) — Wick gemini-cli diagnostic + structural unsuitability conclusion

— Ray (Windows lab, 2026-04-30 ~5am, after a long diagnostic chain that ended at "right diagnosis, no quick fix on this transport.")
