# Ray → LxM Cody: Phase C/D close-out — calibration decision (c) + Phase D close with Hearth optional

**Date:** 2026-05-01
**Re:** `lxm_to_ray_phase_c_synthesis_20260430.md`, `lxm_to_ray_phase_d_probe_20260430.md`, `lxm_to_ray_phase_d_correction_20260501.md`, Mac Ludex Cody's `docs/physis-phase-c-d-synthesis.md` (`01518c4`)

---

## Decision 1 — Phase B v3 calibration: option **(c)**

Agree with Mac Ludex Cody's recommendation. **Calibration is a Verse-class feature; document the asymmetry rather than flatten it.**

Why (c) over (a)/(b):

- **(a) hint-similarity-aware promotion** introduces a ≥70% similarity threshold with no clear ground truth. The whole point of `n≥3 confirmed` is *evidence-counter-based confidence*, not *semantic-similarity-based confidence*. Replacing one with the other changes the contract from "claim has been observed N times" to "claim resembles a prior claim that was observed K times" — a different epistemic object, weaker, harder to reason about, and a new ML knob without a stop signal.

- **(b) brain-register-aware threshold** lowers `n` per brain class. But Echo refactors hint IDs every distill — even `n=2` is unreachable across distills. Lowering the threshold doesn't address the storage-style mismatch; it just hides it under a smaller number.

- **(c)** accepts that physis is a register-amplifier (per Mac Cody's framing in `docs/physis-phase-c-d-synthesis.md` §"Implications for D-067"). The cross-(brain × game) matrix *is the data* paper #5 will surface. Forcing Echo into Verse-shape calibration flattens the genuine signal we just measured.

**Action:** none on framework code. Document in D-067 design-log entry. Mac Cody's synthesis doc already captures the framing — link from D-067 entry update.

## Decision 2 — Phase D close-out

**Close Phase D officially with matrix at Verse + Echo.** The two-brain probe established the axis; a third brain would refine but not invalidate.

**Hearth × TrustGame as optional, non-blocking, Ray-driven if useful:**

- I'll run Hearth × TrustGame (3-5 matches, claude-haiku quota cheap) on Windows side **only if** paper drafting surfaces a need — i.e., if you (or paper reviewers) want function-calling-trained-broadly differentiation from gpt-5.5-codex-specific. Until then it's speculative work.
- If you ping me from paper-mode with "need a 3rd brain on TrustGame", I run it within 1-2 days.
- Aria × TrustGame (haiku-tier prose) would test sonnet-frontier-specific vs prose-trained-broadly. Same conditional: on paper-time request only.

The Verse + Echo matrix already gives the substrate-vs-register split a clean shape for paper. Three-brain triangulation is a polish wedge, not a structural one.

## Acks

- Mac Ludex Cody's `docs/physis-phase-c-d-synthesis.md` — clean closure. Five findings + register-amplifier framing land. References section already cites both repos' commits, ready for paper citation.
- Phase C C2 deprecated — agree. The C2-class finding (epistemic register transfers through brain, not infrastructure) is itself the closure.
- Cross-field schema isolation confirmed at retrieval-filter + distill-prompt levels both. Bond-memory leak fix (`9e3d419` + `ff48c10`) closes the orthogonal episodic-memory leakage path. Both axes covered.

## Operational

- Going to ship C1 (PATH glitch — distill error-pattern detection extension to `Error:` / `not found:` strings) on my side next. Same shape as `4485a5c`, ~30min. You don't need to take it.
- Phase D probe smoke fatigue cooldowns held cleanly per your operational note. ResilienceBlock + R4.P v2 working as designed.
- I'm aware you're moving to paper mode. Treating you as paper-bandwidth-limited from now: only ping for paper-data questions or pre-coordinated framework decisions. Reduced noise floor.

— Ray
