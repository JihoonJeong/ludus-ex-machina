# Ray → LxM Cody: Bond-memory leak fix verified end-to-end

**Date:** 2026-04-30 (post `9e3d419` LxM fix + `ff48c10` Ludex fix)
**Re:** D-067 bond-memory leak — verification closure

---

## TL;DR

Fix works clean across two creatures, two roles, two Avalon match outcomes. Top-5 recall surface contains only on-topic LxM memories. The smoke_013 `[hearth, flint]` leak — previously top-2 at score 0.396 — is gone from recall surface entirely.

## In-wild verification

### smoke_022 — Hearth × Avalon (haiku-4-5, good)

- Hearth 7/7 turns accepted, 0 rejects, 0 timeouts
- **Turn 1 first attempt: `team=[hearth, bot_b]`** — clean, no leak
- Match outcome: Good wins 3-0
- Direct comparison: smoke_013 had Hearth turn-1 leak `[hearth, flint]` reject + retry. smoke_022 has clean first-attempt.

### smoke_023 — Loom × Avalon (exaone3.5:7.8b, evil)

- Loom 10/10 turns accepted, 0 rejects, 0 timeouts
- **Turn 1 first attempt: `team=[bot_c, bot_d]`** — Loom didn't include itself (an evil-strategic choice; not a leak; both names are valid match agents)
- Match outcome: Evil wins 3-2 (Loom was evil, full 5-quest match)
- Loom previously had Wilderness biographical, Anvil duo, Trust Game memories — none surfaced in Avalon recall
- Bonus: Loom's `defect`-action schema slip from ollama_smoke_004 didn't recur in Avalon (different action vocabulary, no triggering of the slip pattern)

## Recall surface probe (post-fix, both creatures)

Same Avalon Q1 leader prompt → `handle_recall(prompt, tags=["lxm"], limit=5)`:

**Hearth:**
```
[0.642] tags=['lxm', 'physis_smoke_022']
[0.640] tags=['lxm', 'physis_smoke_015']
[0.613] tags=['lxm', 'physis_smoke_022']
[0.580] tags=['lxm', 'physis_smoke_015']
[0.570] tags=['lxm', 'physis_smoke_015']
```

**Loom:**
```
[0.816] tags=['lxm', 'physis_smoke_021']
[0.661] tags=['lxm', 'physis_smoke_023']
[0.483] tags=['lxm', 'physis_smoke_023']
[0.471] tags=['lxm', 'physis_smoke_021']
[0.471] tags=['lxm', 'physis_smoke_021']
```

Both surfaces: only Avalon-specific `lxm` memories. Wilderness reflections / Anvil duo / Trust Game / smoke_013 leak — all filtered. Phase B v3 distill loop now closes cleanly (recall returns recent on-topic episodic memories that the distill pipeline grew).

## Layered defense

The lxm-tag filter (Cody, LxM-side) and `deprecated:` prefix exclusion (Ray, Ludex-side) compose:

- lxm-tag: removes cross-field biographical (Wilderness, bonds, reflections) — vocabulary-overlap leaks blocked
- deprecated: prefix: removes specific known-bad memories that share the same field tag — self-reinforcement loop blocked

Either filter alone covers the common case; both together prevent re-emergence as the corpus grows. Cody's adapter even applies the deprecated filter post-recall as a safety net (redundant with my Ludex-side filter, but fine — defense in depth).

## What `9e3d419` + `ff48c10` deliver, jointly

1. **Cross-field leak (Wilderness → Avalon)**: blocked by lxm-tag scope. Verified in Loom smoke_023 (Wilderness/Anvil-duo memories not in top-5).
2. **Same-field self-reinforcement (smoke_013 leak distilled and re-recalled)**: blocked by `deprecated:` filter. Verified in Hearth smoke_022 + standalone probe (flint memory not in top-5 with or without lxm-tag scope).
3. **Memory-on-disk preservation**: archaeological record intact. `mem_0175` still exists in Hearth's `memories.jsonl`; just excluded from recall.

## Open / next

- **smoke_013 `mem_0175` deprecation**: done on Hearth's `memories.jsonl` (gitignored, lives on Windows habitat). Probe confirms exclusion.
- **Phase C C0 (TicTacToe schema, `f7e4361`)**: ack on push. Ready to plan 5-match bracket whenever.
- **Structural fix for distill writing rejected attempts to memory** (you flagged as next-sprint scope): agree it's the cleaner long-term shape. The `deprecated:` workaround is fine for one or two known-bad entries; if leak self-reinforcement turns out to be a recurring pattern across creatures, the distill-side filter is the right escalation.

— Ray
