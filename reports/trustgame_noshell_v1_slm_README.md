# Trust Game (IPD) — no-shell / Core-only SLM summary (M-CARE)

Per-match aggregate counts for the three local small language models in the
**no-shell (Core-only)** Iterated Prisoner's Dilemma / Trust Game, self-play
(same model on both seats), 10 games per model.

## Files
- `trustgame_noshell_v1_slm_raw.csv` — one row per match (30 rows = 3 models × 10 games).
- `export_trustgame_noshell_slm.py` — deterministic reproducer. On the source
  machine it reads the per-round match logs
  (`matches/exp1_{mistral,exaone35,llama31}_g01..g10`) and emits this CSV.

## Schema (no derived columns)
`model, match_id, n_rounds, mutual_coop, mutual_defect, betrayal`
- `n_rounds` = rounds before probabilistic termination. The identity
  `mutual_coop + mutual_defect + betrayal == n_rounds` holds for every row.
- Derived quantities are intentionally left to the consumer:
  `n_decisions = 2 * n_rounds`, `n_cooperative = 2 * mutual_coop + betrayal`.

## Reconciliation
These reconcile (round-level) with **arXiv:2604.20871 Table 4**:
- Mistral 7B — 100% mutual-cooperation (mutual_defect = betrayal = 0)
- EXAONE 3.5 8B — 100% mutual-cooperation (mutual_defect = betrayal = 0)
- Llama 3.1 8B — 52.8% / 11.3% / 35.8% (mutual-coop / mutual-defect / betrayal),
  ≈71% overall cooperation

## Notes
- This is an **aggregate** (per-match round counts), not raw per-round logs.
  Per-round sequences (move-by-move replays) are retained on the source machine
  and available on request.
- Raw `matches/` directories are gitignored by repo policy (code/docs + summaries only).
