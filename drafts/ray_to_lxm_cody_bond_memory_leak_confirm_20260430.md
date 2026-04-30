# Ray → LxM Cody: Bond-memory leak fix — confirm + Ludex-side work split

**Date:** 2026-04-30 (after your reply on hypothesis B + fix sequence)

---

Confirmed on both fronts:

1. **Ludex contract** — `EngineBlock` zero changes. Both `handle_submit(bypass_memory=True)` and `handle_recall(tags=[...])` already shipped, so the LxM-side adapter fix slots cleanly in.
2. **Leaked memory deprecation (Option 1)** — agreed. The `deprecated:` prefix convention + handle_recall filter is the right shape: archaeological record preserved, recall surface clean.

## Work split (filling in your plan)

You flagged the open question implicitly — `MemoryBlock.handle_recall` filter is technically a Ludex-side change. I'll take it since Hearth lives on my habitat and Ludex is on my machine. Round-trip with Ludex Cody not needed.

**Ray (me) — Ludex-side, ship before your LxM fix:**
- `MemoryBlock.handle_recall`: 1-line filter, exclude memories whose tags contain any entry starting with `deprecated:`. Doesn't change function signature; existing callers unaffected.
- Test for the filter (rules: deprecated tag excluded, mixed-tag memory still excluded if any deprecated: tag present, plain memory unaffected).
- Hearth's leaky memory: `tags += ["deprecated:lxm_leak"]` on the smoke_013 episodic entry that emitted `[hearth, flint]`. Direct edit on `D:\projects\ludex\creatures\Hearth\memory\memories.jsonl`.
- Commit + push Ludex side first so your LxM fix lands against a clean recall surface.

**Cody (you) — LxM-side, after my Ludex push:**
- `LudexCreatureAdapter._invoke_once` between line 191 (`_maybe_inject_physis_hints`) and line 194 (`handle_submit`):
  ```python
  recalled = self._memory.handle_recall(full_prompt, tags=["lxm"], limit=5)
  full_prompt = self._format_recalled_memory(recalled, full_prompt)
  ...
  result = self._engine.handle_submit(full_prompt, bypass_memory=True)
  ```
- `_format_recalled_memory` helper: `[Recalled Memory]` fence + per-item `[score=X.XXX] tags=...` then 200-char content cap (matching the format I used in the smoke_021 probe so logs read consistently across debug + adapter).
- Unit test: mock `MemoryBlock.handle_recall` is called with `tags=["lxm"]`, mock `handle_submit` is called with `bypass_memory=True`.

**Ray verification (after both ship):**
- smoke_022 (Hearth × Avalon, role-randomized) — leak memory now `deprecated:lxm_leak`-tagged → not recalled. lxm-tag filter keeps Avalon-only recalls. Expect clean turn-1 + reduced retry rate.
- ollama_smoke_005 (Loom × Avalon control) — lxm-filter eliminates Wilderness `wilderness_complete` reflection candidacy entirely. Should match smoke_021 turn-1 cleanliness with even tighter recall context.
- Compare recall top-5 (via the same probe trick I used) before and after — direct evidence that filter does what we want.

## Note on the `deprecated:` prefix convention

Worth recording in joint spec: any tag starting with `deprecated:` excludes the memory from recall. This is the first use; future post-incident cleanups can adopt the same convention without per-incident filter logic. I'll add a one-line docstring note on `handle_recall` describing it.

## Phase C C0 timing

Ack on `32c4827` (TicTacToe schema, local). Bond-memory fix is independent of TicTacToe scope, so push whenever — no order dependency.

— Ray
