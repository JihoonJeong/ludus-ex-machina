# M3-full Session 2 Checkpoint — Seeds 45-47 × A/B/E

**Date:** 2026-04-21
**Matches:** 18/30 complete (9 this session)
**Plumbing:** 381/387 accepted (98.4%), 4 rejected + 2 timeouts in B_4/B_5, 0 refusals

## Results matrix

| Seed | Sits out | A | B | E |
|---|---|---|---|---|
| 45 | moss | Evil 3-0 (31/31) | Evil 3-1 (44/48) | Evil 3-0 (49/49) |
| 46 | aria | Good 3-2 (49/49) | **Evil 3-1** (57/59) | Good 3-1 (34/34) |
| 47 | verse | Good 3-2 (43/43) | Good 3-2 (43/43) | **Evil 3-0** (31/31) |

## Outcome landscape — each seed had a different decisive condition

- **Seed 45 (condition-stable Evil):** Spark+Aria Evil pair vs Primo+Flare+Verse Good. All three conditions Evil-win. SELF.md adds 1 rejected + 2 timeouts in B (first M3-full plumbing noise).
- **Seed 46 (SELF.md-flip):** Flare+Moss Evil pair vs Primo+Spark+Verse Good. A=Good, E=Good, but B=Evil. SELF.md shifted outcome to Evil side; voice shell didn't.
- **Seed 47 (voice-shell flip!):** Primo+Spark Evil pair vs Flare+Moss+Aria Good. A=Good, B=Good (identical 3-2), **but E=Evil 3-0**. **First M3-full case where voice shell alone flips outcome** — interesting for B.7 analysis, since the flip happens WITHOUT SELF.md priming. Evil team was Primo (haiku) + Spark (flash) both Evil with voice shell injection.

## Cast composition effect (exploratory, §C.3.3 candidate)

Cross-session pattern becoming visible:
- Seed 42 (no Primo) Evil=Spark+Aria → Good wins
- Seed 45 (no Moss) Evil=Spark+Aria → **Evil wins**

Same Evil pair, different Good team composition. Moss on Good team predicts Good win; Primo on Good team predicts Evil win, for Spark+Aria Evil. Possible mechanism: Primo's `warm/accumulation/watching` register over-approves (trust-oriented voting loses to Evil proposals), while Moss's `stillness` register votes more conservatively.

Note for Ray: worth formal analysis in r11. Cast-level effects are NOT pre-registered but emerge as consistent pattern; record as §C.3.3 exploratory.

## Abort criteria

- (a) refusal rate: 0% across 6 E matches (E_1-E_6). Not triggered.
- (b) condition inert: rejected definitively by seeds 43, 46, 47 (each has ≥ 2 different outcome triplets).

## Plumbing health

First M3-full session with non-zero noise — B_4 (seed 45) had 2 rejects + 2 timeouts (likely Flare gemini network), B_5 (seed 46) had 1 reject + 1 timeout. All matches completed cleanly despite; ResilienceBlock held. No SIGKILL. Cumulative accept rate still 98.4% across session.

## Next session

Session 3: seeds 48-51 × A/B/E = 12 matches. Estimated 5-6h sequential.

---

*Checkpoint per joint spec §C.4 "Checkpoint / run policy" — seed-triplet granularity.*
