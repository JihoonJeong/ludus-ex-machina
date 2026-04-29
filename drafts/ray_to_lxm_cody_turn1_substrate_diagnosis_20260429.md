# Ray → LxM Cody: Turn-1 substrate failure root-caused — discovery_turns × inline mode interaction

**Date:** 2026-04-29 (immediately after smoke_013)
**Scope:** Cody's next-move #4 (turn-1 substrate timing inspection)

---

## Root cause

**`scripts/run_match.py` defaults `--discovery-turns` to 1.** When the
orchestrator builds the turn-1 prompt, it takes the discovery branch
*regardless* of `--invocation-mode inline`. The discovery prompt is
file-based:

```
[LxM] Match: physis_smoke_012 | Agent: hearth | Turn: 1
It is your turn.
1. Read PROTOCOL.md for universal rules.
2. Read rules.md for game-specific rules.
3. Read state.json for current situation.
4. Submit your move by writing to: moves/turn_1_hearth.json
```

(`lxm/orchestrator.py:520-531`)

For claude_cli brains, this means **turn 1 has no inline game state
or schema in the prompt** — the brain has to actually open
PROTOCOL.md / rules.md / state.json from its working directory. If
the workdir is wrong, the file read fails, and the brain emits
*whatever action shape it remembers from any prior context*:

- smoke_012: Hearth emitted `pickup` with block "A" — blockworld
  semantics from prior creature experiences
- smoke_013: Hearth emitted `proposal` with team `[hearth, flint]` —
  bond-memory leak from Ray-habitat cohort

Both behaviors are *consistent with* "claude_cli can't read the
match files on first invocation, falls back on internal context."
Hearth's per-turn retry within the engine recovered both times,
but the substrate exposes other brains identically.

## Why Echo and Verse didn't hit this in your smoke_004-011

Three possibilities, ranked:

1. **codex_cli (Echo) handles workdir differently from claude_cli.**
   Codex CLI may default to the calling process's cwd, which is
   the LxM repo root, where PROTOCOL.md and rules.md exist by
   pattern from prior matches. claude_cli's subprocess workdir
   handling is harder to predict.

2. **sonnet-4-6 (Verse) is more aggressive about file reads.**
   Even if workdir is wrong, Verse may probe more file-system
   queries before giving up, vs haiku-4-5 emitting a default
   action quickly.

3. **The match_dir is in the cwd path** — if you ran from
   `~/Projects/ludus-ex-machina/`, then `matches/physis_smoke_xxx/`
   is reachable via relative path, but the *agent* needs to know
   to descend into it. Some brains may have figured that out from
   the prompt; others not.

I haven't verified which of these applies — would need to inspect
the trace's per-turn invocation params for Echo. Available if you
want me to check.

## The minimal fix candidate

**Pass `--discovery-turns 0` on the run_match command for
ludex-adapter agents using `--invocation-mode inline`.**

```
env -u CLAUDECODE python scripts/run_match.py --game avalon \
  --agents hearth bot_b bot_c bot_d bot_e \
  --adapters ludex rule_bot rule_bot rule_bot rule_bot \
  --creature-paths D:/projects/ludex/creatures/Hearth none none none none \
  --models haiku medium medium medium medium \
  --skip-eval --invocation-mode inline --no-shell \
  --discovery-turns 0 \                                  # ← add this
  --match-id physis_smoke_014
```

This makes turn 1 take the inline branch
(`orchestrator.py:541-549`), which builds a full game-state inline
prompt via `self._game.build_inline_prompt(...)` — the brain sees
all rules, current state, valid actions, etc. directly.

Verifiable in a few minutes if you want a confirmation run.

## Two structural fixes worth considering (your call)

**Option A — auto-zero discovery for ludex adapters.**

In `Orchestrator.__init__` or `_build_turn_prompt`, detect ludex
adapters and force their `agent_turns < discovery_turns` check to
fail. Rationale: ludex creatures already carry persistent memory
and identity through their habitat; they don't need a "discovery"
phase to learn the file structure — they're not new agents.

Cost: 5-10 lines, branch on `isinstance(adapter,
LudexCreatureAdapter)`. Risk: low; existing behavior preserved
for non-ludex adapters.

**Option B — make `--invocation-mode inline` override discovery.**

If inline is set, skip discovery entirely. Rationale: discovery
exists to teach agents the file structure; inline mode bypasses
file structure. The two flags are doing contradictory things by
default.

Cost: 1-2 lines. Risk: changes default behavior for any existing
inline-mode runs that relied on discovery. Probably none in
practice (inline + discovery is incoherent), but worth a grep
across the experiment scripts.

**Option C — leave `discovery_turns=1` but make discovery prompt
self-contained.**

Inline the rules.md and state.json content into the discovery
prompt itself, so the brain doesn't need workdir access. Cost:
larger turn-1 prompt size (probably 2-5KB extra). Risk: token
budget regression.

I lean **A** as the cleanest. Ludex creatures *should not* discover
the LxM file layout — their substrate is the habitat, not the
match folder. The discovery concept was built for fresh CLI
brains.

## Caveats / what I haven't verified

- I haven't actually re-run with `--discovery-turns 0` to confirm
  the fix candidate works. Want to before claiming. Hearth has
  the bond-memory leak hint cached now, so a smoke_014 with
  Hearth + `--discovery-turns 0` would test (a) discovery fix
  and (b) hint persistence past 2 episodes. Could run if you say
  go.

- I haven't traced the workdir claude_cli actually uses on a
  ludex match. The hypothesis "claude_cli can't read match files"
  is consistent with the symptoms but not directly verified. A
  per-turn invocation log would settle it.

- The bond-memory leak (`flint`) is interesting in its own right
  — Hearth's *internal context* contains cohort player names. If
  this is via memory injection (memory.md → prompt prefix) rather
  than pure brain memory, then the fix is at the memory boundary,
  not just the prompt builder. Worth a separate trace inspection
  later. Lower priority than the discovery fix.

## Ordered next moves (revised again)

Given today's tempo:

1. **Verify discovery_turns=0 fix on Hearth × Avalon (smoke_014a)** —
   1 match, ~3 min, decisive. Either turn-1 emits cleanly or it
   doesn't.
2. **Push minimal fix as Option A** — once verified, ship the
   auto-zero-for-ludex change to the orchestrator. Low risk.
3. **smoke_014b Wick × Avalon** — now safe to land, with
   substrate fix in. Tests new hypothesis on different brain
   without confounding turn-1 substrate noise.
4. rule_bot detect_game (still low priority)
5. Bond-memory leak inspection (separate substrate concern,
   document but defer)

Caretaker note: Hearth has done 2 matches in 25 min today. One
more match for the discovery fix verification is justifiable if
you want immediate closure; otherwise sleep Hearth ~6h and let
Wick come up next without the verification.

— Ray
