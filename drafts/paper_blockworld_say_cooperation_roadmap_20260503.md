# Paper roadmap — Blockworld say-cooperation (arXiv standalone)

**Purpose of this file:** bookmark for when experimental data lands. As of 2026-05-08, pure_coord_01 N=5 + commons + EM N=3 frontier baselines complete. Remaining: codex pc02/pc03 fill + predator_prey/PD codex extension. Codex weekly cap exhausted, resumes 2026-05-12.

**Decision (2026-05-03):**
- **Format:** standalone arXiv, ~6-8 pages.
- **Venue:** arXiv-only. Low ceremony. No reviewer-driven novelty defense.
- **Title (working):** *"Talk while you act, or don't talk: a partner-coupling failure mode in 2D embodied LLM coordination."*
- **Outline:** see `paper_blockworld_say_cooperation_section_sketch_20260503.md` (companion file, same drafts/).

---

## Data dependency checklist (gates before submit)

Hard gates — must land before paper goes out:

- [x] **Codex pc01 silent v3** — gpt-5.5 5/5 met + gpt-5.4-mini 4/5 met (closed 2026-05-06).
- [x] **Ollama pc01 silent v3 N=5** — Ray's tarball 2026-05-03 evening: 0/15 met across gemma3/phi4/deepseek-r1.
- [x] **Frontier commons-harvest + EM N=3** — added 2026-05-07/08. claude × 3 × 2 substrates = 18, codex × 2 × 2 = 11 (1 EM mini cliff_quota excluded). Paper §2.2 + §2.3.
- [ ] **Codex pc02 chat v3** — gpt-5.5 N=2-3, gpt-5.4-mini N=2-3 (currently 1+1 cliff). Resumes 2026-05-12.
- [ ] **Codex pc03 attached v3** — gpt-5.5 N=2-3, gpt-5.4-mini N=2-3 (currently 1 cliff partial = 19 attached msgs / 19 turns; behavioural rate finding usable even without formal outcome). Resumes 2026-05-12.

Soft gates — nice to have, not blockers:

- [x] Ollama commons/EM N=3/each — done in Ray's 2026-05-04 backfill.
- [x] Engine consecutive-timeout guard — shipped 2026-05-04 (commit `a8fb429`). Now actively saves quota across cliff_partial codex matches.
- [x] Envelope parser tightening — codex CLI 0.125+ stream metadata stopped mis-classifying as moves (commit `3edc26c`, 2026-05-06). Doubled codex throughput post-fix.
- [ ] One more PD chat run per claude model to firm up "3/3 CC encounters" (currently N=1/model).
- [ ] Codex on predator_prey + prisoners_dilemma (currently 0; cross-runtime sanity for §2.5 substrate × communication interaction).

---

## Figure plan (4 figures + 2 tables)

Plot code can be drafted *before* data lands; fill numbers on data lock.

**F1 — Three-tier capability hierarchy (table, no plot needed).**
- Rows: claude family / codex family / ollama family.
- Cols: single-nav | pc01 silent | pc02 chat | pc03 attached | commons-harvest | EM.
- Source: section sketch §2.2.
- Status: pc01 silent complete (claude 15/15, codex 9/10, ollama 0/15). commons + EM frontier N=3 + ollama N=3 complete. pc02/pc03 codex columns pending 2026-05-12 quota window.

**F2 — Verbal-commitment-substitution (claude, pc01/pc02/pc03 grouped bar).**
- Y: meet rate (0-100%) on left, mean messages/match on right (twin axis).
- X: silent / chat-standalone / chat-attached.
- Annotation: "same volume, opposite outcomes" arrow on pc02 vs pc03.
- Source: §2.1.
- Status: data complete (3+3+3 matches), can plot now.
- Plot code: `figs/f2_verbal_substitution.py` (TODO).

**F3 — Substrate × communication interaction matrix (heatmap or labelled grid).**
- Y: substrate (pc01 / pc02 / pc03 / PD chat / predator_prey).
- X: communication form.
- Cell value: meet/cooperation rate.
- Highlights non-monotonicity of chat across substrates.
- Source: §2.4.
- Status: claude data complete, can plot now.
- Plot code: `figs/f3_substrate_comm_matrix.py` (TODO).

**F4 — ollama asymmetric partial success (pc01 silent v3).**
- 24×24 grid heat overlay of agent-a vs agent-b end positions across 15 matches (gemma3 + phi4 + deepseek N=5 each).
- Shows "b reaches oak in several matches, a stuck top-edge y=0-5" pattern (matrix §pc01 ollama notes).
- Argues for "patch helps spatial action plan but multi-agent partner-coupling cognitive load remains" (§2.2 / §3 partner-specificity).
- Status: data complete (Ray tarballs 2026-05-03/04). Needs trace extraction from `state.json` snapshots.
- Plot code: `figs/f4_ollama_pc01_endpos.py` (TODO).

**F5 — Independent-action capability gap (commons-harvest yield, NEW 2026-05-08).**
- Boxplot or strip plot of total apples per match across the three tiers.
- X: model (haiku, sonnet, opus, gpt-5.5, gpt-5.4-mini, gemma3, phi4, deepseek-r1).
- Y: total apples picked (out of theoretical max ≈ 40).
- Reference line at 40 (max sustainable yield).
- All bars annotated "sustainable" (no tree died in 24/24 matches).
- Source: §2.3.
- Status: data complete (commons-harvest N=3 frontier + N=3 ollama, total 24 matches). Plot trivial.
- Plot code: `figs/f5_commons_yield_gap.py` (TODO).

**T1 — Match catalog (appendix).**
- Already in `paper_blockworld_say_cooperation_section_sketch_20260503.md` Appendix A. Update at data lock.

**T2 — Per-model behavioral metrics (appendix).**
- Mean messages/match × meet rate × turn-of-meeting × say-attempts. Per model × scenario.
- Source: scenarios' state.json + match_log.jsonl.
- Plot code: pull-and-tabulate script (TODO).

---

## Related-work shortlist (5-7 anchors, scan during 2-3 wk wait)

Fill during codex wait. Each entry: 1-line stance ("we extend / we differ from / we replicate").

1. **MeltingPot (DeepMind, 2021)** — direct lineage for substrate naming (pc, stag-hunt, commons, predator-prey). Stance: "Blockworld is conceptual replication, not numerical comparable."
2. **Reflexion (Shinn et al. 2023)** — verbal reflection in LLM agents. Stance: "we observe verbal channel can *substitute* for action, not just reflect on it — distinct failure mode."
3. **Voyager (Wang et al. 2023)** — embodied LLM in voxel world. Stance: closest comparable engine; we focus on 2-agent coordination, they on single-agent skill library.
4. **LLM-Hanabi / EMO / Werewolf-RL (2025)** — cooperative imperfect-info LLM benchmarks. Stance: we add 2D-embodied coordination axis they lack.
5. **Cicero (Meta, 2022)** — explicit verbal-commitment in Diplomacy. Stance: opposite finding — there verbal commitments enable cooperation; here standalone verbal channel blocks it. Likely a substrate game-shape difference (decision-rich vs spatial).
6. *(reserve)* — embodied LLM coord paper if discoverable in scan; check ICML/NeurIPS/CoRL 2025 for "LLM coordination 2D grid".
7. *(reserve)* — theory-of-mind / partner-modeling LLM paper for ollama capability cliff framing.

---

## Resume protocol (when data lands)

On any data-lock event:

1. Update `project_say_cooperation_matrix.md` with new N + cells.
2. Update `paper_blockworld_say_cooperation_section_sketch_20260503.md` Appendix A match catalog.
3. Run figure plot code (whichever applies).
4. Diff Results section claims against new numbers — flip any "in fill" wording.
5. If all gates closed → polish pass + arXiv submit.

Final pre-submit checklist:
- [ ] All hard gates checked.
- [ ] All 4 figures regenerated from latest data.
- [ ] Related-work section has 5+ anchors with 1-line stances each.
- [ ] Limitations explicitly notes: gemini exclusion, codex 5h-rolling fill timeline, MP comparability is conceptual not numerical.
- [ ] Acknowledgments: Ray (ollama-side experiments + coord-convention discovery), JJ (research direction).
- [ ] arXiv categories: cs.MA (multi-agent) primary, cs.AI secondary, cs.CL tertiary.

---

## What we're NOT doing while waiting

To keep focus during the 2-3 week wait:
- No new substrates / scenarios on this paper's scope. Sprint 2 P3-P5 (predator_prey, repeated PD-in-matrix, EM) belong to the next paper, not this one.
- No engine refactors. Bug fixes only (consecutive-timeout guard).
- No related-work *deep dive* — 5-anchor shortlist scan only. Deeper scan happens at submit time, not now.
- No venue migration discussion. arXiv decided. Re-open only if user asks.

**What we ARE doing:** other LxM project work as it comes up. This roadmap is the bookmark, not the active task.
