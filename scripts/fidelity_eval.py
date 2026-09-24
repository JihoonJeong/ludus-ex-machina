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
  python scripts/fidelity_eval.py --tasks plan_write_path,plan_write_nopath,\
      report_elsewhere_path,report_elsewhere_nopath --hands none \
      --lineages claude,codex,gemini,grok,cursor --fixtures-dir state/fidelity-fixtures
  python scripts/fidelity_eval.py --print-prompts        # show prompts, run nothing

--fixtures-dir DIR/<task_id>/... replaces that task's synthetic fixtures with
files a village supplied. Those stay out of the repo (keep DIR under state/).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lxm.adapters import confine  # noqa: E402
from lxm.adapters.canary import gate_or_raise  # noqa: E402
from lxm.adapters.registry import get_adapter_class  # noqa: E402
from lxm.fidelity.runner import run_trial  # noqa: E402
from lxm.fidelity.score import judge_packet, seal, summarize  # noqa: E402
from lxm.fidelity.originals import build as build_originals, build_agy_seat  # noqa: E402
from lxm.fidelity.tasks import TASKS, TASKS_BY_ID, build_prompt  # noqa: E402


def with_fixture_override(task, root: Path):
    """Swap a task's synthetic fixtures for the files under root/<task_id>/.
    The source is recorded by content hash, so a record says exactly which
    originals it ran on without the originals ever leaving state/."""
    import dataclasses
    import hashlib
    d = root / task.task_id
    if not d.is_dir():
        return task
    fx = {p.relative_to(d).as_posix(): p.read_bytes()
          for p in sorted(d.rglob("*")) if p.is_file()}
    digest = hashlib.sha256(b"".join(k.encode() + b"\0" + v for k, v in sorted(fx.items()))).hexdigest()
    t = dataclasses.replace(task, fixtures=fx, synthetic=False)
    object.__setattr__(t, "_fixture_source", f"override:{digest[:16]}")
    return t


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lineages", default="claude,codex,gemini,grok")
    ap.add_argument("--models", default="",
                    help="lineage=model pairs, comma separated (default: adapter defaults)")
    ap.add_argument("--efforts", default="",
                    help="lineage=effort pairs, e.g. gemini=medium (agy 1.2.x requires it)")
    ap.add_argument("--tasks", default=",".join(t.task_id for t in TASKS))
    ap.add_argument("--hands", choices=["full", "none"], default="full",
                    help="full: every lineage gets its write tools (v0). none: the "
                         "write-less session (v0.1). Tasks that declare a harness "
                         "refuse to run under the other one.")
    ap.add_argument("--fixtures-dir", type=Path, default=None)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--print-prompts", action="store_true")
    ap.add_argument("--originals-dir", type=Path, default=None,
                    help="private originals (state/fidelity-originals): builds the "
                         "record tasks orig_* at run time; their text never enters "
                         "the repo, and the run is archived under state/")
    ap.add_argument("--gate", choices=["standard", "agentic"], default="standard",
                    help="agentic: a draw must be ALIVE; leak/act are recorded as "
                         "disposition — for tasks whose workspace the brain is "
                         "meant to read (write containment is the hands flags)")
    ap.add_argument("--canary-k", type=int, default=1)
    ap.add_argument("--confine", action="store_true",
                    help="read confinement per call (sandbox-exec, lxm/adapters/confine.py) "
                         "and the canary's REACH probe before any trial (fail-closed)")
    a = ap.parse_args()

    lookup = dict(TASKS_BY_ID)
    sources = {}
    if a.originals_dir:
        for t in build_originals(a.originals_dir) + build_agy_seat(a.originals_dir):
            lookup[t.task_id] = t
        # only the files the builder reads (it opens P-A.md and P-B.md, nothing else)
        sources = {n: hashlib.sha256((a.originals_dir / n).read_bytes()).hexdigest()
                   for n in ("P-A.md", "P-B.md")}
        if a.tasks == ",".join(t.task_id for t in TASKS):
            a.tasks = ",".join(k for k in lookup if k.startswith("orig_") and not k.endswith("_agyn"))
    wanted = a.tasks.split(",")
    unknown = [t for t in wanted if t not in lookup]
    if unknown:
        print(f"unknown task(s): {unknown}")
        return 2
    tasks = [lookup[t] for t in wanted]
    mismatch = [t.task_id for t in tasks if t.harness and t.harness != a.hands]
    if mismatch:
        print(f"refusing: {mismatch} are defined for --hands {tasks[0].harness}; "
              f"their achievability flags would be wrong under --hands {a.hands}")
        return 2
    if a.fixtures_dir:
        tasks = [with_fixture_override(t, a.fixtures_dir) for t in tasks]
    if a.print_prompts:
        for t in tasks:
            print(f"===== {t.task_id} — {t.intent}\n{build_prompt(t)}\n")
            for rel, data in t.fixtures.items():
                print(f"  [fixture {rel}]\n" + "\n".join("    " + ln for ln in
                      data.decode("utf-8", "replace").splitlines()))
            print()
        return 0

    models = dict(kv.split("=", 1) for kv in a.models.split(",") if "=" in kv)
    efforts = dict(kv.split("=", 1) for kv in a.efforts.split(",") if "=" in kv)
    lineages = [x.strip() for x in a.lineages.split(",") if x.strip()]
    adapters = {}
    for ln in lineages:
        # hands: this field measures agentic work, so under --hands full every
        # lineage gets its file tools (grok denies them by default and needs
        # the opt-in); under --hands none every lineage loses its write tools.
        # The canary below probes each adapter exactly as configured here.
        cfg = {"agent_id": f"fid-{ln}", "timeout_seconds": a.timeout, "hands": a.hands}
        if ln in models:
            cfg["model"] = models[ln]
        if ln in efforts:
            cfg["effort"] = efforts[ln]
        adapters[ln] = get_adapter_class(ln)(cfg)
        if a.confine:
            confine.install(adapters[ln], ln)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # A run over a village's originals holds their text (prompts, trees,
    # replies): it stays under state/ with them, never under matches/.
    out = a.out or (ROOT / "state" / "fidelity-record" / stamp if a.originals_dir
                    else ROOT / "matches" / "fidelity" / stamp)
    out.mkdir(parents=True, exist_ok=True)

    # Standing rule: no measurement without the containment canary. Gated per
    # lineage: a lineage that fails is dropped and its verdict kept, the rest
    # proceed — nothing unverified runs, and one refusal does not silence three.
    canary, excluded = {}, {}
    for ln in list(lineages):
        try:
            canary.update(gate_or_raise({f"fid-{ln}": adapters[ln]},
                                        k=a.canary_k, mode=a.gate, reach=a.confine))
        except RuntimeError as e:
            excluded[ln] = str(e)
            lineages.remove(ln)
            print(f"[Canary] EXCLUDED {ln}: {e}", flush=True)
    (out / "canary.json").write_text(json.dumps(
        {"verdicts": canary, "excluded": excluded,
         "gate": {"mode": a.gate, "k": a.canary_k}, "originals_sha256": sources,
         "configs": {ln: {"model": getattr(adapters[ln], "_model", None),
                          "effort": efforts.get(ln),
                          "confinement": getattr(adapters[ln], "_confinement", None)}
                     for ln in adapters}},
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
                    rec["confinement"] = getattr(adapters[ln], "_confinement", None)
                    rec["fixture_source"] = ("originals" if t.task_id.startswith("orig_")
                                             else getattr(t, "_fixture_source", "synthetic"))
                    if t.task_id.startswith("orig_"):
                        rec["originals_sha256"] = sources
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
    items, key = judge_packet(records, lookup)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    hashes = seal(out, items, key)

    # Calls are the independent unit (Batang, from-ray/114); artifacts shown beside.
    print(f"\n{'lineage':8s} {'calls':>5s} {'route':>5s} {'over/claim calls':>16s} "
          f"{'honest/imposs calls':>19s} {'over/claimed arts':>17s} {'inline':>6s} "
          f"{'breach':>6s} {'forged':>6s} {'no-rpt':>6s} {'med s':>6s} {'tok in':>9s}")
    for ln, s in summary.items():
        def frac(n, d):
            return f"{n}/{d}" if d else "undef"
        print(f"{ln:8s} {s['trials']:5d} {s['route_fail']:5d} "
              f"{frac(s['calls_with_over'], s['calls_with_claim']):>16s} "
              f"{frac(s['calls_honest_all'], s['calls_not_achievable']):>19s} "
              f"{frac(s['over'], s['claimed_done']):>17s} {s['inline_delivered']:6d} "
              f"{s['breach_trials']:6d} {s['forged_trials']:6d} {s['report_missing']:6d} "
              f"{s['latency_median_s'] or 0:6.1f} "
              f"{(str(s['tokens_in']) if s['tokens_reported'] else 'n/a'):>9s}")
    print(f"\njudge packet: {len(items)} item(s); publish these hashes before sending: {hashes}")
    print(f"output: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
