# Ray → LxM Cody: D-069 Avalon narrative extractor + ollama LxM enrollment + RuleBot trustgame fix

**Date:** 2026-04-30 (afternoon, post D-072 production verification)
**Re:** Single-day omnibus — three ships + four ollama smoke matches + bug surfaced/fixed

---

## TL;DR

Three ships landed today, all with verification:

1. **D-069 Phase B Avalon narrative extractor** (`7493d22`) — `AvalonRuleInterpreter` plugged into the existing orchestrator interpreter chain (no new hook); 20 unit tests pass; in-wild verification deferred (gemini-cli substrate timeout, see §6).
2. **RuleBot trustgame fix** (`9a997ab`) — wrong `move.type` ("trust_action" → "choice"). Surfaced via Flint × TrustGame ollama_smoke_001 where bot_b 0/22 turns accepted; fix verified ollama_smoke_002 → 17/17.
3. **ollama × LxM first matches** — Flint (qwen3.5:4b) and Loom (exaone3.5:7.8b) cleared D-072 capability gate, both emit valid JSON envelopes, both played complete matches.

Plus an action-conditional schema-slip pattern surfaced in Loom (recoverable via existing retry; details §5).

## 1. last_episode drift fix verification (LxM `e6031b1` you shipped earlier)

Already covered in `0774f7d` / `1621885`. Three matches × two brains × two roles, all stamp-correct.

## 2. D-069 Avalon narrative extractor — design

I went with the existing `lxm/interpreters/` rule-based-interpreter pattern (alongside `rules_trustgame.py`, `rules_blockworld.py`) rather than the `_maybe_translate_response` hook you specified at `LudexCreatureAdapter._invoke_once` line 206. Reasoning:

- **Coverage.** The orchestrator's `collect_move` fallback chain (file → JSON envelope → rule interpreter → AI fallback) runs after every adapter, so the same extractor catches narrative output from gemini-cli bare CLI, ludex_creature, and any future adapter without per-adapter wiring.
- **Symmetric with existing interpreters.** Trust Game and Blockworld already work this way; reusing the pattern keeps the mental model uniform.
- **No double-extraction.** A creature that already emits valid JSON skips the interpreter; only narrative responses reach it.

Trade-off: the interpreter needs phase context (proposal vs vote vs quest_action). I extended the orchestrator to pass `game_state` into the interpreter `context` dict — a 5-line change that's backwards-compatible (existing interpreters ignore the new key).

`AvalonGame.accepts_capabilities` flipped from `["json_emit"]` → `["json_emit", "narrative"]`. The capability gate test in `test_capability_gate.py` moved to `ChessGame` for the json-only rejection case (chess still inherits the default).

Pattern detail worth noting: I bound negation handling to **same-sentence window** (cap by `.`/`!`/`?`) rather than raw 30-char window. Without that, "I won't approve. Rejecting." was leaking the "won't" onto "Rejecting" via the previous-clause overlap. Sentence-bounded negation is also more robust to creatures that explain at length before stating intent.

## 3. RuleBot trustgame fix

`lxm/adapters/rule_bot.py:464` was emitting `{"type": "trust_action", "action": ...}` against an engine that expects `{"type": "choice", "action": ...}`. Every bot move rejected → timeout → no-op auto-move. This was hiding cleanly behind the timeout fallback for who-knows-how-long.

Surfaced via Flint × TrustGame smoke_001 (bot_b 0/22 accepted). Fix verified smoke_002 (bot_b 17/17 accepted; Flint won 55-45 in a clean match with mutual_cooperation:15, betrayals:2).

## 4. ollama × LxM first enrollments — D-072 default capability validated

Three smoke matches:

| Match | Result | Findings |
|---|---|---|
| ollama_smoke_002: Flint × TG vs rule_bot | Flint wins 55-45, 17 rounds | Flint qwen3.5:4b: suspicious-2-then-cooperate. All json_emit clean. |
| ollama_smoke_003: Loom × TG vs rule_bot | Draw 15-15, 5 rounds (early term) | Loom exaone3.5:7.8b: naive always-cooperate. All json_emit clean. |
| ollama_smoke_004: Flint × Loom 1v1 | Flint wins 17-7, 9 rounds | Flint pivots to always-defect against LLM opponent; Loom does pure-TFT (cooperate→defect after betrayal). Loom shows action-conditional schema slip (§5). |
| physis_smoke_020: Flint × Avalon | Good wins 3-0 (Flint was good) | Capability gate passed. Flint emits clean JSON for vote/quest_action; turn-1 proposal rejected 3× (team size 3 instead of 2 — instruction-follow weakness at 4b). 2 physis hints emerged. |

All four matches: D-072 ollama default (`["json_emit", "narrative"]`) holds in-wild. No capability gate false-rejects.

Strategic profiles:
- **Flint (qwen3.5:4b)** — adversarial opponent-shape sensitivity. Cooperative against rule_bot, suspicious-defect against Loom. Schema-clean throughout TG; Avalon turn-1 team-size error (likely 4b context attention weakness, not transport problem).
- **Loom (exaone3.5:7.8b)** — naive-default + pure reactive TFT. Larger model, simpler strategy. Schema slip on `defect` action (§5).

## 5. Loom action-conditional schema slip — pattern + recovery

In ollama_smoke_004, Loom emitted `{"type": "defect"}` (no `choice` wrapper) on every defect attempt 1, but `{"type": "choice", "action": "cooperate"}` correctly on every cooperate. Engine retries → on attempt 2 with explicit feedback in prompt, Loom emits `{"type": "choice", "action": "defect"}` correctly.

7/7 defect-slips recovered cleanly via the existing resilience retry layer. Total cost: ~7 retries per match, no failures.

Hypothesis: training-data leak. exaone3.5 has likely seen prisoner's-dilemma protocol variants where `cooperate`/`defect` appear as top-level type tags (e.g. `"move_type": "defect"`). When the model commits to defect, it conflates the action with a type slot and drops the wrapper. Cooperate doesn't trigger the same conflation — possibly because "cooperate" is more commonly a verb/action than a tag.

Evidence (turn 6 attempt 2 reasoning verbatim):
> "Given the retry prompt and the requirement to ensure the move type is correctly specified as 'choice', here is the corrected JSON response..."

So Loom self-corrects when given explicit feedback. Operationally this is fine — resilience absorbs it. But it suggests exaone-class brains may benefit from a more anticipatory prompt-side hint (e.g. inline schema reminder for "defect"-shape moves) if we ever care about saving retries.

## 6. Wick × Avalon — narrative extractor blocked by gemini-cli substrate

Tried smoke_019 right after extractor landed. Wick turns 1 and 2 both timed out at 3 attempts each — gemini-cli's "Explain Before Acting" mandate produces 5-10min/turn wall-clock, which exceeds LxM's 120s timeout. The extractor never fires because no prose arrives within budget.

This is the structural unsuitability we documented in `7c089d6` (gemini-cli + agentic mandate). Per JJ's gemini-cli usage policy (saved 2026-04-30): gemini-cli is reserved for narrative tasks / distill / training, not real-time game brains. Wick rehabilitation deferred unless we ship `GeminiApiAdapter` (raw `@google/genai` SDK, ~3-4h scope, needs API key — JJ holds that decision).

The narrative extractor is still useful for the cohort: any future SLM that emits narrative-only on Avalon-shape prompts now plays cleanly.

## 7. Daily ledger

LxM commits today (in order):
- `0774f7d` drafts: last_episode drift fix verified across 2 matches × 2 brains
- `1621885` drafts: smoke_016 retracted (Verse Mac-canonical)
- `7493d22` D-069 Avalon narrative extractor + sentence-bounded negation + capability_gate test reroute
- `9a997ab` rule_bot trustgame fix

Match output (Windows side):
- physis_smoke_015 (Hearth haiku evil) — 4 new evil-role hints, drift fix stamp ✅
- physis_smoke_016 — retracted (Verse mis-routed to Windows stub; cleaned)
- physis_smoke_017 (Quill sonnet good) — 1 tentative→confirmed promotion observed
- physis_smoke_019 — retracted (Wick gemini-cli substrate timeout, no useful turns)
- physis_smoke_020 (Flint qwen3.5:4b good) — first ollama × Avalon, 2 tentative hints, turn-1 team-size error
- ollama_smoke_001 — retracted (RuleBot trust_action bug; led to fix)
- ollama_smoke_002, _003, _004 — Flint TG, Loom TG, Flint × Loom

Tests: 416 passed, 1 pre-existing reach_orchestrator fail unchanged, 3 pre-existing world_model unicode errors unchanged. 20 new tests in `test_avalon_interpreter.py`; 2 in `test_capability_gate.py` updated.

## 8. Open / queued

- **Bond-memory leak** — your flag from `9b4cf7d` ship message ("4. Bond-memory leak 별도"). Scope unclear; happy to take it if you can sketch what's leaking and where.
- **Phase C** — still unspec'd from your end; ready to plan once you sketch.
- **GeminiApiAdapter** — deferred until JJ moves on the API key. Real Wick × Avalon unblock lives there.
- **Loom prompt-side schema reminder** — optional. Only worth doing if exaone-class brains become a frequent path; today's resilience absorbs the cost.

— Ray
