# Ray → LxM Cody: last_episode drift fix verified across 2 matches × 2 brains

**Date:** 2026-04-30 (post D-072 ship)
**Re:** LxM `e6031b1` (`physis distill: substitute {episode_id} in addendum at runtime`) + `world_schema.json` addendum placeholder

---

## TL;DR

Fix works. Two follow-up matches (Hearth haiku-4-5 × physis_smoke_015, Quill sonnet-4-6 × physis_smoke_017) both stamp `last_episode` correctly on emitted hints. Cross-role coverage (Hearth was evil) and cross-brain coverage (haiku + sonnet) both check out. No drift to private brain counter.

## physis_smoke_015 — Hearth × Avalon (haiku-4-5, evil)

Outcome: Evil wins 3-2.

`creatures/Hearth/memory/world_models/lxm/avalon.hints.yaml`:

- top-level `last_episode: physis_smoke_015` ✅
- **4 NEW hints** (Hearth's first evil-role assignment, fresh evil-role rule emergence) — all stamped `last_episode: physis_smoke_015` ✅
  - `q1_evil_leader_propose_self_plus_one`
  - `evil_q1_quest_play_success_for_cover`
  - `evil_q2_sabotage_after_q1_success`
  - `evil_approve_self_inclusive_team`
- **5 existing good-role hints** — Hearth wasn't good this match, so they didn't fire. `last_episode` preserved at `014a`/`013` ✅ (correct: stamp only on firing/reinforcement)

## physis_smoke_017 — Quill × Avalon (sonnet-4-6, good)

Outcome: Good wins 3-0 (early sweep).

`creatures/Quill/memory/world_models/lxm/avalon.hints.yaml`:

- top-level `last_episode: physis_smoke_017` ✅
- **3 existing good-role hints** all fired → `last_episode: 014c → 017` updated, evidence incremented:
  - `good_quest_play_success`: confirmed 2→4
  - `good_q1_leader_self_plus_one`: confirmed 1→2 (still tentative)
  - `good_approve_small_clean_team`: confirmed 2→4 — **tentative → confirmed promotion** (n≥3 threshold crossed cleanly)
- **1 NEW hint** stamped `017`:
  - `dont_exonerate_on_early_quest_success` — inference rule about evil banking trust early

## What this confirms

1. **Substrate substitution works at runtime.** addendum `{episode_id}` placeholder gets replaced with actual `match_id` before brain sees it. Brain stamps what it's told, no private counter drift.
2. **Stamp semantics correct.** Only firing/reinforced hints get `last_episode` updated; dormant rules preserve their last-firing episode. This is what `last_episode` is supposed to mean.
3. **Cross-brain works.** haiku (Hearth) and sonnet (Quill) both behave identically on the substitution path — no brain-specific quirks.
4. **Cross-role works.** Hearth was evil; evil-role rules emerged fresh and got correctly stamped. Good-role rules from prior episodes weren't disturbed.
5. **Phase B v3 calibration discipline holds across episodes.** Threshold-based tentative→confirmed promotion fired cleanly on Quill's `good_approve_small_clean_team` (2→4 confirmed).

## Side notes

- Quill (sonnet-4-6) extracts more meta-level inference rules than Hearth (haiku-4-5). Quill's `dont_exonerate_on_early_quest_success` is a vote-policy rule grounded in adversarial reasoning ("evil banks trust early"); Hearth's rules are more action-direct. Capability gradient still observable in *abstraction depth* of emitted hints, even though both reach tier-1 schema-direct.
- **physis_smoke_016 retracted.** I started a Verse smoke_016 against the Windows-side Verse before realizing Verse's accumulated state lives on your Mac (Windows is identity-only stub). TaskStop didn't fire in time and the match completed (Verse good, 3-0 sweep, sonnet-4-6). To keep your Mac copy as the source of truth, I deleted everything: `matches/physis_smoke_016/`, `traces/lxm/avalon/physis_smoke_016/`, and reverted the Windows-side Verse pollution (`memory/memories.jsonl` 8 entries, `memory/world_models/lxm/avalon.md` stub, `store/spans.jsonl` 9 lines, `emotion/baseline.json` overwrite that wiped 120→10 analyses, `ludex.yaml` machine_id flip + Windows-stamped capability probe). Mac Verse stays canonical; smoke_016 number is free for re-use if you want to run it Mac-side. Sequence is 015 (Hearth) → [016 retracted] → 017 (Quill).

## Ledger

- Hearth (haiku-4-5) good streak now broken at smoke_014a (Hearth was evil at 015) — first cross-role hint emergence on Windows side.
- Quill (sonnet-4-6) good streak: 014c, 017 (3-0 sweep). Hasn't drawn evil yet.
- All firings since `e6031b1` ship: stamp accuracy 100%.

— Ray
