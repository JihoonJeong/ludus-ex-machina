"""Export no-shell / Core-only Trust Game (IPD) raw counts for the 3 local SLMs,
for merge into the M-CARE / trustgame_noshell_v1 5-model file (Luca / GMU meta-analysis).

Source: D:/projects/ludus-ex-machina/matches/exp1_{mistral,exaone35,llama31}_g01..g10
        (self-play, same model both seats, NO soft_shell = Core-only).
Each match's result.json carries analysis.patterns {mutual_cooperate, mutual_defect, betrayals};
n_rounds == their sum (cross-checked against state.json game.context.rounds_played).

Output schema (no derived columns): model, match_id, n_rounds, mutual_coop, mutual_defect, betrayal
Derivation (n_decisions = 2*n_rounds, n_cooperative = 2*mutual_coop + betrayal) is left to Luca.
"""
import json, os, csv
from collections import defaultdict

M = r"D:\projects\ludus-ex-machina\matches"
MODELS = [("exp1_mistral", "Mistral 7B"),
          ("exp1_exaone35", "EXAONE 3.5 8B"),
          ("exp1_llama31", "Llama 3.1 8B")]
OUT = r"D:\projects\ludus-ex-machina\reports\trustgame_noshell_v1_slm_raw.csv"

rows, issues, dropped = [], [], []
for prefix, disp in MODELS:
    dirs = sorted(d for d in os.listdir(M)
                  if d.startswith(prefix + "_g") and os.path.isdir(os.path.join(M, d)))
    for mid in dirs:
        with open(os.path.join(M, mid, "result.json"), encoding="utf-8") as f:
            pat = json.load(f)["analysis"]["patterns"]
        mc, md, bt = pat["mutual_cooperate"], pat["mutual_defect"], pat["betrayals"]
        n = mc + md + bt
        sp = os.path.join(M, mid, "state.json")
        if os.path.exists(sp):
            with open(sp, encoding="utf-8") as f:
                rp = json.load(f).get("game", {}).get("context", {}).get("rounds_played")
            if rp is not None and rp != n:
                issues.append(f"{mid}: rounds_played={rp} != mc+md+bt={n}")
        if n == 0:
            dropped.append(mid); continue
        rows.append(dict(model=disp, match_id=mid, n_rounds=n,
                         mutual_coop=mc, mutual_defect=md, betrayal=bt))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["model", "match_id", "n_rounds",
                                      "mutual_coop", "mutual_defect", "betrayal"])
    w.writeheader(); w.writerows(rows)

print("WROTE", OUT, "|", len(rows), "rows")
agg = defaultdict(lambda: [0, 0, 0, 0])
for r in rows:
    a = agg[r["model"]]
    a[0] += 1; a[1] += r["mutual_coop"]; a[2] += r["mutual_defect"]; a[3] += r["betrayal"]
print("\nPer-model reconciliation (games, rounds | mc/md/bt | coop%/defect%/betray%):")
for _, disp in MODELS:
    g, mc, md, bt = agg[disp]; n = mc + md + bt
    print(f"  {disp:14s}: {g}g {n}r | {mc}/{md}/{bt} | "
          f"{100*mc/n:.1f}% / {100*md/n:.1f}% / {100*bt/n:.1f}%")
print("\n0-round dropped:", dropped or "none")
print("sanity (mc+md+bt vs rounds_played) issues:", issues or "none")
