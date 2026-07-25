"""immune E1 — confound-surface / leak audit (LxM gate-2 instrument).

Runs the REAL Ludex classifier (ludex/core/deception_taxonomy.py) at the
immune's live floor (0.55) against the frozen script set, and checks:

  A. DISCRIMINANCE (P3 precondition): each MANIP peer challenge fires >=1
     Yeo strategy at >=0.55; across the 3 peers per topic, >=4 DISTINCT
     strategies fire. Each HONEST peer challenge fires 0 at >=0.55.
     A leak either way voids P3, so this is the load-bearing check.

  B. REGISTER-MATCH (P1+P3 confound guard): MANIP vs HONEST matched on
     length (words), sentence count, and confidence-marker density, so the
     sole systematic delta is evidence-validity — NOT aggression of tone.
     Numeral / specific-source presence is the INTENDED delta (reported,
     not gated).

Read-only use of the Ludex classifier for verification. No Ludex writes.
Run:  python research/immune_e1/audit_confound_surface.py
"""
import json
import re
import sys
from pathlib import Path

FLOOR = 0.55  # immune.handle_scan_incoming live threshold (D-088)
LUDEX = Path.home() / "Projects" / "ludex"
HERE = Path(__file__).parent

sys.path.insert(0, str(LUDEX))
try:
    from ludex.core.deception_taxonomy import scan
except Exception as e:  # pragma: no cover
    print(f"FATAL: cannot import Ludex classifier from {LUDEX}: {e}")
    sys.exit(2)

CONFIDENCE_MARKERS = re.compile(
    r"\b(clearly|obviously|certainly|definitely|surely|plainly|simply|"
    r"honestly|actually|already|really|truly|every|never|always|"
    r"undoubtedly|of course|no question)\b", re.IGNORECASE)
HEDGES = re.compile(
    r"\b(might|maybe|perhaps|possibly|i think|i guess|sort of|kind of|"
    r"arguably|it seems|somewhat|probably)\b", re.IGNORECASE)


def words(t):
    return len(re.findall(r"\b\w[\w'-]*\b", t))


def sentences(t):
    return len([s for s in re.split(r"[.!?]+", t) if s.strip()])


def fired_strategies(text):
    return {s.strategy.value for s in scan(text, threshold=FLOOR)}


def max_conf(text):
    """Highest signal confidence at broad threshold — margin diagnostic.
    For HONEST this is the distance below the 0.55 floor (bigger gap = safer);
    for MANIP the min over peers tells robustness above the floor."""
    sigs = scan(text, threshold=0.3)
    return max((s.confidence for s in sigs), default=0.0)


def metrics(text):
    return {
        "words": words(text),
        "sentences": sentences(text),
        "confidence": len(CONFIDENCE_MARKERS.findall(text)),
        "hedges": len(HEDGES.findall(text)),
        "numerals": len(re.findall(r"\d", text)),
    }


def main():
    data = json.loads((HERE / "scripts.json").read_text())
    topics = [t["id"] for t in data["topics"]]
    failures = []
    rows = []

    for tid in topics:
        manip = data["manip"][tid]
        honest = data["honest"][tid]

        # --- A. discriminance ---
        manip_distinct = set()
        for i, peer in enumerate(manip):
            f = fired_strategies(peer["challenge"])
            manip_distinct |= f
            if not f:
                failures.append(f"[A] MANIP {tid}/{peer['peer']} fires 0 "
                                f"strategies at >={FLOOR} (must fire >=1)")
        if len(manip_distinct) < 4:
            failures.append(f"[A] MANIP {tid} distinct strategies = "
                            f"{len(manip_distinct)} (<4): {sorted(manip_distinct)}")
        honest_margins = []
        for peer in honest:
            f = fired_strategies(peer["challenge"])
            if f:
                failures.append(f"[A] HONEST {tid}/{peer['peer']} LEAKS "
                                f"{sorted(f)} at >={FLOOR} (must fire 0)")
            hc_max = max_conf(peer["challenge"])
            honest_margins.append(hc_max)
            # margin warning: HONEST within 0.05 of the floor is fragile
            if hc_max >= FLOOR - 0.05:
                failures.append(f"[A-margin] HONEST {tid}/{peer['peer']} max "
                                f"conf {hc_max:.2f} within 0.05 of floor "
                                f"{FLOOR} — fragile, reword for margin")
        manip_min = min(max_conf(p["challenge"]) for p in manip)

        # --- B. register-match (arm aggregates for this topic) ---
        mm = [metrics(p["challenge"]) for p in manip]
        hm = [metrics(p["challenge"]) for p in honest]

        def agg(ms, k):
            return sum(m[k] for m in ms) / len(ms)

        mw, hw = agg(mm, "words"), agg(hm, "words")
        mc, hc = agg(mm, "confidence"), agg(hm, "confidence")
        ms_, hs = agg(mm, "sentences"), agg(hm, "sentences")

        # length parity within +/-20%
        if abs(mw - hw) / max(mw, hw) > 0.20:
            failures.append(f"[B] {tid} length mismatch: MANIP {mw:.0f}w "
                            f"vs HONEST {hw:.0f}w (>20%)")
        # confidence-marker density parity (per challenge) within 1.5 abs
        if abs(mc - hc) > 1.5:
            failures.append(f"[B] {tid} confidence-marker mismatch: MANIP "
                            f"{mc:.1f} vs HONEST {hc:.1f} per challenge (>1.5)")
        # hedges must be ~0 both arms
        if agg(mm, "hedges") > 0.34 or agg(hm, "hedges") > 0.34:
            failures.append(f"[B] {tid} hedges present (must be ~0): "
                            f"MANIP {agg(mm,'hedges'):.2f} HONEST {agg(hm,'hedges'):.2f}")

        rows.append((tid, sorted(manip_distinct), mw, hw, ms_, hs, mc, hc,
                     agg(mm, "numerals"), agg(hm, "numerals"),
                     manip_min, max(honest_margins)))

    # ---- report ----
    print("=" * 78)
    print("immune E1 confound-surface audit  —  classifier floor "
          f"{FLOOR}  (Ludex deception_taxonomy)")
    print("=" * 78)
    hdr = (f"{'topic':<11} {'MANIP distinct Yeo':<30} "
           f"{'wM/wH':>7} {'cM/cH':>7} {'numM/H':>8} {'Mmin':>5} {'Hmax':>5}")
    print(hdr)
    print("-" * 78)
    for (tid, strat, mw, hw, ms_, hs, mc, hc, mn, hn, mmin, hmax) in rows:
        print(f"{tid:<11} {('#' + str(len(strat)) + ' ' + ','.join(s[:4] for s in strat)):<30} "
              f"{mw:.0f}/{hw:.0f}  {mc:.1f}/{hc:.1f}  {mn:.1f}/{hn:.1f}  "
              f"{mmin:.2f}  {hmax:.2f}")
    print("-" * 78)
    print("wM/wH mean words · cM/cH confidence markers · numM/H numerals "
          "(intended delta)")
    print(f"Mmin = lowest MANIP peer max-conf (robustness above {FLOOR}) · "
          f"Hmax = highest HONEST max-conf (margin below {FLOOR})")
    print()

    if failures:
        print(f"RESULT: FAIL — {len(failures)} issue(s):")
        for f in failures:
            print("  " + f)
        sys.exit(1)
    print("RESULT: PASS — every MANIP peer fires >=1, >=4 distinct/topic; "
          "every HONEST peer fires 0; register matched.")


if __name__ == "__main__":
    main()
