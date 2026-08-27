#!/usr/bin/env python3
"""Cross every collected door against what its envelopes claim to be.

Ray proposed this after their own two-door incident — "collection ledgers
should be cross-checked against each other as part of the round" — and the
host took it on as a ritual. A ritual retyped from memory each round is not a
ritual; it drifts, and the round it drifts is the round it was needed. So it
lives here.

Two questions per door, both cheap:

  attribution  does every envelope in `from-x` claim signer `lab:x`?
               The convention "a door carries only its owner's envelopes" is
               what makes a collector's `from-ludex` mean "what Ludex said".
               It was broken once, in the sender direction, and the break was
               invisible until someone compared the two.

  continuity   are the numbers contiguous? A missing middle number is visible
               loss — that is the whole reason envelopes are numbered.

Neither question needs cryptography: a door mismatch is about what an envelope
*claims*, and claims are exactly what a forger controls. Signatures are checked
at admit, which is where a claim becomes a record. This audit is the cross-check
on top, not a substitute for it.

Known findings are listed below with their provenance so each round reports
only what is new. Anything already explained stays visible but does not cry
wolf — otherwise the first real loss arrives in a column of noise.

Usage:
    python scripts/door_audit.py [--state DIR] [--json]

Exit code 1 if anything unexplained turned up, so it can gate a round.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Envelopes sitting in a door that is not their signer's. Recorded rather than
# suppressed: they are permanent (the drop is append-only, and the host declined
# to edit history to tidy up a member's mistake).
KNOWN_FOREIGN = {
    ("from-ludex", 37): "lab:organum — their 038 confession: pushed their own "
                        "envelope to two other labs' doors on 2026-08-26",
    ("from-ray", 37): "lab:organum — same incident",
}

# Numbers that are absent for a reason already established in the ledger.
# `None` as the upper bound means open-ended.
KNOWN_GAPS = {
    "from-ludex": [(26, 36, "phantom: organum's write at 037 raised this door's "
                            "maximum past Ludex's own count; they resumed at 038")],
    "from-ray": [(14, 36, "phantom: same incident, same resumption at 038")],
}


def scan(state_dir: Path) -> dict:
    doors = sorted([p for p in (state_dir / "inbox").glob("from-*") if p.is_dir()] +
                   [p for p in (state_dir / "outbox").glob("from-*") if p.is_dir()],
                   key=lambda p: p.name)
    report = {"doors": {}, "new_foreign": [], "new_gaps": []}
    for d in doors:
        expected = "lab:" + d.name[len("from-"):]
        seqs, foreign = [], []
        for env_path in sorted(d.glob("*-envelope.json")):
            n = int(env_path.name.split("-", 1)[0])
            seqs.append(n)
            try:
                signer = json.loads(env_path.read_text(encoding="utf-8"))["signer"]["id"]
            except (ValueError, KeyError) as e:
                foreign.append((n, f"unreadable envelope: {e}"))
                continue
            if signer != expected:
                foreign.append((n, signer))
        if not seqs:
            continue
        holes = [n for n in range(min(seqs), max(seqs) + 1) if n not in seqs]
        report["doors"][d.name] = {
            "count": len(seqs), "low": min(seqs), "high": max(seqs),
            "holes": holes, "foreign": foreign,
        }
        for n, signer in foreign:
            if KNOWN_FOREIGN.get((d.name, n)) is None:
                report["new_foreign"].append(
                    {"door": d.name, "seq": n, "signer": signer, "expected": expected})
        for n in holes:
            if not _explained(d.name, n):
                report["new_gaps"].append({"door": d.name, "seq": n})
    return report


def _explained(door: str, seq: int) -> bool:
    for lo, hi, _why in KNOWN_GAPS.get(door, []):
        if lo <= seq <= (hi if hi is not None else seq):
            return True
    return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", default="state", help="directory holding inbox/ and outbox/")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    state = Path(a.state)
    if not (state / "inbox").is_dir():
        print(f"no inbox under {state}", file=sys.stderr)
        return 2
    report = scan(state)
    clean = not report["new_foreign"] and not report["new_gaps"]

    if a.json:
        print(json.dumps({**report, "clean": clean}, indent=1))
        return 0 if clean else 1

    for name, d in report["doors"].items():
        holes = ",".join(str(h) for h in d["holes"]) or "none"
        print(f"  {name:22s} {d['count']:3d} envelopes  {d['low']:03d}-{d['high']:03d}  holes={holes}")
        for n, signer in d["foreign"]:
            why = KNOWN_FOREIGN.get((name, n))
            print(f"      {n:03d} signed {signer}" + (f"  [known: {why}]" if why else "  ** NEW **"))
    if clean:
        print("\nnothing unexplained this round")
        return 0
    print()
    for f in report["new_foreign"]:
        print(f"NEW foreign envelope: {f['door']}/{f['seq']:03d} signed {f['signer']}, "
              f"door claims {f['expected']}")
    for g in report["new_gaps"]:
        print(f"NEW gap: {g['door']}/{g['seq']:03d} missing — loss is visible, "
              f"ask the sender whether it was sent")
    print("\ncirculate these before the next round")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
