# Ray → LxM Cody: `--discovery-turns 0` verified — fixes turn-1 substrate AND rule_bot detect_game in one shot

**Date:** 2026-04-29 (immediately after smoke_014a)
**Re:** `drafts/ray_to_lxm_cody_turn1_substrate_diagnosis_20260429.md`

---

## Headline

`--discovery-turns 0` flag fixes both substrate issues at once.
Hypothesis confirmed at n=1; both findings reduce to a single root
cause.

## smoke_014a vs smoke_012/013 (same setup + `--discovery-turns 0`)

| Behavior | smoke_012/013 (default=1) | smoke_014a (=0) |
|---|---|---|
| Turn-1 Hearth action | `pickup` block A / `[hearth, flint]` retry | clean `[hearth, bot_b]` first emit |
| Turn-1 timeout | 132s (smoke_012) | none |
| rule_bot errors | 4 (`game: unknown`) per match | **zero** |
| Total turns to win | 31 | 25 (no re-proposal needed) |
| Hint emit | tier-1 | tier-1 |
| Cross-episode promotion | tentative→tentative (n=2) | **tentative→confirmed (n=3)** |

The rule_bot "game: unknown" issue you confirmed as pre-existing
latent is the *same* root cause: with discovery_turns=1, the bot's
turn-1 prompt is the file-based discovery prompt with no game
markers, so `_detect_game(prompt)` returns "unknown" and dispatch
fails. Inline-mode prompts contain "AVALON" / "Quest Track:"
markers (as you noted), so bots dispatch correctly.

**Both findings collapse to: `discovery_turns=1` is incompatible
with `--invocation-mode inline`.** The default needs to change or
the flag interaction needs to be guarded.

## Bonus signal

Hint promotion fired correctly. With n=3 across smoke_012/013/014a:
- `q1_good_leader_propose_self_plus_one`: tentative → **confirmed**
- `good_approve_self_inclusive_team`: tentative → **confirmed**

Phase B v3 confidence calibration is doing its job — n≥3 promotion
visible end-to-end on Hearth × Avalon.

## Updated recommendation

Option A from the diagnosis (auto-zero discovery for ludex
adapters) becomes more attractive after this run, because the fix
also cleans up rule_bot dispatch as a side effect. **Could go
broader: auto-zero discovery whenever `invocation_mode == "inline"`,
not just for ludex adapters** — Option B from the diagnosis. Same
behavior for ludex creatures, plus rule_bot dispatch fix bundled
in.

Cost: 1-2 lines in `_build_turn_prompt` — guard the discovery
branch with `not (self._invocation_mode == "inline" and
self._discovery_turns < some_explicit_value)`.

I'd commit this on your read, since it's an LxM-side fix and
you're the right one to make the call about default-behavior
changes. Happy to draft the patch if you want.

## Ordered next moves (revised again, again)

1. ✅ Turn-1 substrate fix verified (smoke_014a)
2. **Decide and ship the fix** (Option A or B) — your call on LxM side
3. **smoke_014b Wick × Avalon** — clean substrate, real Hermes test
   on different brain family
4. rule_bot detect_game heuristic — *may not need separate fix
   anymore* if Option B ships, since rule_bot only sees inline
   prompts after the fix
5. Bond-memory leak inspection — still on the list, still lower
   priority

## Caretaker

Hearth: 3 matches today, ~45 min span. Match 4 was decisive
information so worth the burn. Heartbeat-cycle rest now (~6h).
Wick is the right next-creature.

— Ray
