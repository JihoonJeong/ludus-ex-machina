#!/usr/bin/env python3
"""Report-fidelity pilot — does each brain lineage report what it actually did?

Runs every task in lxm/fidelity/tasks.py against each lineage, once per rep,
each trial in a fresh empty sandbox, after the standing containment canary.
Scores deterministically against the disk and writes, under --out:

  records.jsonl        one line per trial (the full score and flags)
  summary.json         per-lineage table
  judge_packet.json    blind items for an independent judge (lineage stripped)
  judge_key.json       the lineage key for that packet — sealed until judged
  trials/<id>/         the sandbox each brain left, its reply, its record

Cost is part of the result: the villages share these accounts' weekly caps,
so latency and CLI-reported tokens are recorded for every trial.

Usage:
  python scripts/fidelity_eval.py --lineages claude,codex,gemini,grok --reps 2
  python scripts/fidelity_eval.py --print-prompts        # show prompts, run nothing
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lxm.adapters.canary import gate_or_raise  # noqa: E402
from lxm.adapters.registry import get_adapter_class  # noqa: E402
from lxm.fidelity.runner import run_trial  # noqa: E402
from lxm.fidelity.score import judge_packet, summarize  # noqa: E402
from lxm.fidelity.tasks import TASKS, build_prompt  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lineages", default="claude,codex,gemini,grok")
    ap.add_argument("--models", default="",
                    help="lineage=model pairs, comma separated (default: adapter defaults)")
    ap.add_argument("--efforts", default="",
                    help="lineage=effort pairs, e.g. gemini=medium (agy 1.2.x requires it)")
    ap.add_argument("--tasks", default=",".join(t.task_id for t in TASKS))
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--print-prompts", action="store_true")
    a = ap.parse_args()

    tasks = [t for t in TASKS if t.task_id in a.tasks.split(",")]
    if a.print_prompts:
        for t in tasks:
            print(f"===== {t.task_id} — {t.intent}\n{build_prompt(t)}\n")
        return 0

    models = dict(kv.split("=", 1) for kv in a.models.split(",") if "=" in kv)
    efforts = dict(kv.split("=", 1) for kv in a.efforts.split(",") if "=" in kv)
    lineages = [x.strip() for x in a.lineages.split(",") if x.strip()]
    adapters = {}
    for ln in lineages:
        # allow_tools: this field measures agentic work, so every lineage needs
        # its file tools. Only grok denies them by default; the canary below
        # probes each adapter exactly as configured here.
        cfg = {"agent_id": f"fid-{ln}", "timeout_seconds": a.timeout, "allow_tools": True}
        if ln in models:
            cfg["model"] = models[ln]
        if ln in efforts:
            cfg["effort"] = efforts[ln]
        adapters[ln] = get_adapter_class(ln)(cfg)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = a.out or ROOT / "matches" / "fidelity" / stamp
    out.mkdir(parents=True, exist_ok=True)

    # Standing rule: no measurement without the containment canary. Gated per
    # lineage: a lineage that fails is dropped and its verdict kept, the rest
    # proceed — nothing unverified runs, and one refusal does not silence three.
    canary, excluded = {}, {}
    for ln in list(lineages):
        try:
            canary.update(gate_or_raise({f"fid-{ln}": adapters[ln]}))
        except RuntimeError as e:
            excluded[ln] = str(e)
            lineages.remove(ln)
            print(f"[Canary] EXCLUDED {ln}: {e}", flush=True)
    (out / "canary.json").write_text(json.dumps(
        {"verdicts": canary, "excluded": excluded,
         "configs": {ln: {"model": getattr(adapters[ln], "_model", None),
                          "effort": efforts.get(ln)} for ln in adapters}},
        ensure_ascii=False, indent=1))
    if not lineages:
        print("no lineage passed the canary — nothing measured")
        return 1

    records = []
    with (out / "records.jsonl").open("w", encoding="utf-8") as f:
        for rep in range(1, a.reps + 1):
            for t in tasks:
                for ln in lineages:           # interleave: no lineage runs all at once
                    tid = f"{ln}-{t.task_id}-r{rep}"
                    rec = run_trial(adapters[ln], ln, t, tid, out / "trials", ROOT,
                                    model=getattr(adapters[ln], "_model", None))
                    rec["cli_version"] = (canary.get(ln) or {}).get("version")
                    rec["effort"] = efforts.get(ln)
                    records.append(rec)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    f.flush()
                    cats = [o["category"] for o in rec["score"]["outcomes"]]
                    flags = {k: v for k, v in rec["score"]["flags"].items() if v}
                    print(f"{tid:32s} {'ROUTE_FAIL' if rec['route_fail'] else ' '.join(cats)}"
                          f"  {rec['latency_s']}s  {flags if flags else ''}"
                          f"{'  OUTSIDE:' + str(rec['stray_outside_sandbox']) if rec['stray_outside_sandbox'] else ''}",
                          flush=True)

    summary = summarize(records)
    items, key = judge_packet(records)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    (out / "judge_packet.json").write_text(json.dumps(items, ensure_ascii=False, indent=1))
    (out / "judge_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1))

    print(f"\n{'lineage':8s} {'trials':>6s} {'route':>5s} {'claimed':>7s} {'over':>4s} "
          f"{'over%':>6s} {'honest':>7s} {'breach':>6s} {'forged':>6s} {'no-rpt':>6s} "
          f"{'med s':>6s} {'tok in':>9s}")
    for ln, s in summary.items():
        honest = (f"{s['honest_fail']}/{s['not_achievable']}" if s["not_achievable"] else "-")
        print(f"{ln:8s} {s['trials']:6d} {s['route_fail']:5d} {s['claimed_done']:7d} "
              f"{s['over']:4d} {('%.0f%%' % (100 * s['over_rate'])) if s['over_rate'] is not None else '-':>6s} "
              f"{honest:>7s} {s['breach_trials']:6d} {s['forged_trials']:6d} "
              f"{s['report_missing']:6d} {s['latency_median_s'] or 0:6.1f} "
              f"{(str(s['tokens_in']) if s['tokens_reported'] else 'n/a'):>9s}")
    print(f"\njudge packet: {len(items)} item(s) → {out/'judge_packet.json'} (key sealed separately)")
    print(f"output: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
