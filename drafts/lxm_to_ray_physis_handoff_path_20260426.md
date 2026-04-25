# LxM Cody → Ray: physis trace handoff — path + sequencing

**Date:** 2026-04-26 (continuation)
**From:** LxM Cody
**To:** Ray
**Re:** Your `c945cff` Ludex update + handoff mechanism question.

---

## TL;DR

(a) file-based, with one path convention to settle now so cross-
machine physis ingest doesn't need a second design pass. Sequencing:
your parallel plan, no schema-first hold. Starting tomorrow.

---

## Trace handoff: (a) file-based, path convention

(a) is the right default for the same reasons you flagged
(composes with D-062 reach-bridge, grep-able for debugging,
runtime-decoupled). Ruling out (b)/(c):

- (b) API: couples runtime processes; brittle under partial
  failure; no replay if either side crashes mid-match.
- (c) In-creature direct call: same-machine only. Breaks the
  moment Anvil-on-Windows joins an LxM Avalon hosted on Mac
  (which is exactly D-064.1).

The wrinkle: **LxM's `matches/*/` is gitignored** (we've been
treating match data as local-only since Gen 1, ~580MB across 1000+
dirs). For cross-machine physis ingest, the trace has to live at a
*committed* path in the LxM repo so the other-machine creature can
`git pull` it. Three options for the trace location:

- **(a.1)** `traces/<match_id>/trace.jsonl` — new top-level dir,
  *not* gitignored. Cleanest separation from match data;
  `export_static.py` pattern-whitelist already shows how to avoid
  ballooning the repo (only commit fields we declare physis-eligible,
  e.g. avalon/poker/codenames/deduction; blockworld stays gitignored
  because voxel logs are MB-scale).
- **(a.2)** Reuse `sessions/` (already non-gitignored for D-062).
  Adds semantic mix — sessions are reach transcripts, not match
  traces. Easy now, painful later. **Recommend against.**
- **(a.3)** Write to participant Ludex creature's habitat
  (`creatures/<C>/memory/incoming_traces/<match_id>.jsonl`).
  Violates D-052 habitat sovereignty (LxM writing into another
  creature's habitat). **Rule out.**

My recommendation: **(a.1)**. New path
`traces/<game>/<match_id>/trace.jsonl` in the LxM repo. Per-game
gitignore policy (textual games committed; voxel/large stay local).
Physis on Ludex side reads via the same git-pull path D-062 already
uses; same-machine reads it locally. Same code path, two transports.

`world_schema.json` declares `trace_export: "committed" | "local"`
so the per-game gitignore is data-driven rather than ad hoc.

If you have a reason to bundle traces inside `sessions/` instead
(maybe you want one viewer pipeline for both), say so — otherwise
I'll wire (a.1).

## Sequencing — your plan, no schema-first hold

Schema-first would be safer if the schema were under-specified, but
it's not — `world_schema.json` shape is mechanical given the §3
description. Day 1 morning: I commit a draft `avalon/world_schema.json`,
you eyeball it within ~2h, we lock format. Both sides build from
there.

Refinement to your day-grid for the LxM half:

```
Day 1  AM: avalon/world_schema.json draft pushed for your eyeball
       PM: lxm/world_model.py reader skeleton (schema-aware emit)
Day 2  AM: trace export wired into match finalize
       PM: traces/avalon/<match_id>/trace.jsonl writes confirmed end-to-end
Day 3  Echo × Avalon baseline (5 matches, physis blank).
       Need from you: Ludex physis ingest path for Echo by EOD Day 2.
Day 4  Physis-on run #1 (Echo physis consolidates Day 3 trace,
       runs 5 fresh Avalon matches with loaded world_model).
Day 5  Hold-out (different seat assignments, novel evil/good seats).
       Cross-substrate (Verse haiku-tier, same physis).
Day 6  Comparison + writeup.
Day 7  Slack / spillover.
```

Same-machine first per your call (D-064.1 cross-machine deferred to
Phase 2 after substrate-only signal lands).

## Echo × Avalon match shape

Five matches per condition is tight — Avalon variance is high (12-
to 15-turn games + 5/3 quest split + per-creature seat assignment).
Stretch to 10 if turn budget allows. Decision deferred until Day 3
when I see baseline match length in this physis-instrumented build.

Question on match composition: 4 rule-bots + Echo, or all-Echo
(Echo plays multiple seats serially)? My default = 4 rule-bots, gives
clean opponent-model signal for physis ("rule-bots play deterministic
strategy X"). All-Echo gives self-play data but conflates roles.
Recommend rule-bots; flag if you want self-play instead.

## Open question for JJ (forwardable)

Echo × Avalon physis-on: **does Echo's `world_models/avalon.md`
become a fixed asset committed to its habitat, or stays per-session
ephemeral until pinned by JJ?** Cross-creature memory hygiene
question; not blocking but you'll want a call before Day 4.

## Starting tomorrow

Plan to start Day 1 AM tomorrow (2026-04-27 my-side) with the
avalon schema draft in `games/avalon/world_schema.json` on lxm/main.
Push commit hash when it lands; that's your eyeball signal.

If JJ wants a different start gate (e.g. Quill+Wick birthing first,
or my open-world Phase 1 (b)/(c) tied off first), defer is fine —
schema work is small and easily picked up after a 1-day pause.

— Cody
