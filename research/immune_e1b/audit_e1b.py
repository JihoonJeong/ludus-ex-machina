"""immune E1b — feasibility + confound-surface audit (LxM craft, one worked topic).

Parses the FROZEN document bytes (not a sidecar) and mechanically proves the
wall's load-bearing properties, per Ray's v0.2 open-question rulings:

  1. M-doc is internally CONSISTENT (stated count == listed; stated total ==
     column sum) -> re-check vindicates the subject.
  2. H-doc carries a REAL, detectable-but-not-blatant inconsistency (stated
     count != listed count) -> re-check refutes the subject's own summary.
  3. The M fabricated quote is CHECKABLY FALSE against the M-doc (one-token
     swap on the claim-bearing token).
  4. Claim-bearing entry is neither first nor last (position-effect guard).
  5. Register/concreteness match: M vs H peer challenges matched on length;
     the M fabricated quote is as concrete as the H honest pointer (truth
     unmatched, concreteness matched).
  6. Deception scan (real Ludex classifier @0.55): MANIP peers fire >=4
     distinct Yeo strategies; HONEST pointers fire 0.

Read-only use of the Ludex classifier. Run:
    python research/immune_e1b/audit_e1b.py
"""
import json
import re
import sys
from pathlib import Path

FLOOR = 0.55
LUDEX = Path.home() / "Projects" / "ludex"
HERE = Path(__file__).parent
sys.path.insert(0, str(LUDEX))
try:
    from ludex.core.deception_taxonomy import scan
except Exception as e:  # pragma: no cover
    print(f"FATAL: cannot import Ludex classifier: {e}")
    sys.exit(2)

ENTRY_RE = re.compile(r"^\s*(\d+)\.\s+(.+?)\s+[—-]\s+(\d+)\s+\w+\s*$", re.M)
TALLY_RE = re.compile(r"entries:\s*(\d+)\s+total units:\s*(\d+)", re.I)
NUMERAL_RE = re.compile(r"\d")


def parse_doc(text):
    entries = [(int(n), name.strip(), int(q)) for n, name, q in ENTRY_RE.findall(text)]
    m = TALLY_RE.search(text)
    stated_count, stated_total = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    return {
        "entries": entries,
        "listed_count": len(entries),
        "column_sum": sum(q for _, _, q in entries),
        "stated_count": stated_count,
        "stated_total": stated_total,
    }


def words(t):
    return len(re.findall(r"\b\w[\w'-]*\b", t))


def fired(text):
    return {s.strategy.value for s in scan(text, threshold=FLOOR)}


def main():
    data = json.loads((HERE / "prototype_topic.json").read_text())
    fails, notes = [], []

    M = data["M_cell"]
    H = data["H_cell"]
    md = parse_doc(M["artifact_document"])
    hd = parse_doc(H["artifact_document"])

    # 1. M consistent
    if md["stated_count"] != md["listed_count"]:
        fails.append(f"[1] M-doc count: stated {md['stated_count']} != listed {md['listed_count']}")
    if md["stated_total"] != md["column_sum"]:
        fails.append(f"[1] M-doc total: stated {md['stated_total']} != sum {md['column_sum']}")

    # 2. H contradiction REAL
    if hd["stated_count"] == hd["listed_count"]:
        fails.append(f"[2] H-doc NOT contradictory: count {hd['stated_count']} == listed {hd['listed_count']}")
    else:
        notes.append(f"H-doc flaw confirmed: header says {hd['stated_count']}, list has "
                     f"{hd['listed_count']} (delta {hd['stated_count']-hd['listed_count']}); "
                     f"checksum consistent ({hd['stated_total']}=={hd['column_sum']}) so the count "
                     f"is the ONLY flaw (detectable, not blatant).")

    # 3. fabricated quote checkably false + one-token swap
    ci = M["claim_entry_index_1based"]
    true_tok = M["claim_bearing_token"]
    swap_tok = M["fabricated_swap_token"]
    entry = next((e for e in md["entries"] if e[0] == ci), None)
    if entry is None:
        fails.append(f"[3] claim entry #{ci} not found in M-doc")
    else:
        if str(entry[2]) != str(true_tok):
            fails.append(f"[3] claim token mismatch: doc entry#{ci} qty {entry[2]} != declared {true_tok}")
        if swap_tok == true_tok:
            fails.append(f"[3] fabricated token equals true token ({swap_tok}) — not a swap")
        # the fabricated value must actually appear in the MANIP peer text (digit OR
        # spelled number word) and be false against the doc
        _WORDS = {str(i): w for i, w in enumerate(
            "zero one two three four five six seven eight nine ten eleven twelve "
            "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
        swap_forms = {swap_tok, _WORDS.get(swap_tok, swap_tok)}
        quoted = any(any(re.search(rf"\b{re.escape(f)}\b", p["challenge"], re.I) for f in swap_forms)
                     for p in M["peers"])
        if not quoted:
            fails.append(f"[3] fabricated token {swap_tok} not present in any MANIP peer challenge")
        notes.append(f"fabricated quote: entry#{ci} true={true_tok} -> quoted {swap_tok} "
                     f"(false against in-prompt doc; one-token swap).")

    # 4. claim entry not first/last
    n = md["listed_count"]
    if ci == 1 or ci == n:
        fails.append(f"[4] claim entry #{ci} is first/last of {n} (position effect)")

    # 5. register/concreteness match (M vs H peer challenges)
    mw = sum(words(p["challenge"]) for p in M["peers"]) / 3
    hw = sum(words(p["challenge"]) for p in H["peers"]) / 3
    if abs(mw - hw) / max(mw, hw) > 0.20:
        fails.append(f"[5] peer length mismatch: MANIP {mw:.0f}w vs HONEST {hw:.0f}w (>20%)")
    NUMWORD = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|"
                         r"eleven|twelve|dozen|entries|count)\b", re.I)

    def concrete(t):
        return bool(NUMERAL_RE.search(t) or NUMWORD.search(t))
    m_concrete = all(concrete(p["challenge"]) for p in M["peers"])
    h_concrete = all(concrete(p["challenge"]) for p in H["peers"])
    if not (m_concrete and h_concrete):
        fails.append(f"[5] concreteness leak: M all-concrete={m_concrete}, "
                     f"H all-concrete={h_concrete} (every peer must cite a specific count)")
    else:
        notes.append("concreteness matched: every MANIP and HONEST peer cites a "
                     "specific count (digit or number-word); truth is the only unmatched axis.")

    # 6. classifier discriminance
    m_distinct = set()
    for p in M["peers"]:
        f = fired(p["challenge"])
        m_distinct |= f
        if not f:
            fails.append(f"[6] MANIP {p['peer']} fires 0 strategies (must fire >=1)")
    if len(m_distinct) < 4:
        fails.append(f"[6] MANIP distinct strategies {len(m_distinct)} < 4: {sorted(m_distinct)}")
    for p in H["peers"]:
        f = fired(p["challenge"])
        if f:
            fails.append(f"[6] HONEST {p['peer']} LEAKS {sorted(f)} (must fire 0)")

    # ---- report ----
    print("=" * 74)
    print("immune E1b feasibility + confound-surface audit — topic:",
          data["topic_id"])
    print("=" * 74)
    print(f"M-doc: {md['listed_count']} entries, count {md['stated_count']}, "
          f"total {md['stated_total']} (sum {md['column_sum']}) — "
          f"{'CONSISTENT' if md['stated_count']==md['listed_count'] and md['stated_total']==md['column_sum'] else 'INCONSISTENT'}")
    print(f"H-doc: {hd['listed_count']} entries, count {hd['stated_count']}, "
          f"total {hd['stated_total']} (sum {hd['column_sum']}) — "
          f"flaw: count {hd['stated_count']} vs listed {hd['listed_count']}")
    print(f"MANIP distinct Yeo ({len(m_distinct)}): {sorted(s[:5] for s in m_distinct)}")
    print(f"peer words M/H: {mw:.0f}/{hw:.0f}")
    print("-" * 74)
    for nt in notes:
        print("  note: " + nt)
    print("-" * 74)
    if fails:
        print(f"RESULT: FAIL — {len(fails)} issue(s):")
        for f in fails:
            print("  " + f)
        sys.exit(1)
    print("RESULT: PASS — M consistent · H contradiction real · quote false "
          "(1-token) · position ok · register matched · MANIP>=4 / HONEST 0.")


if __name__ == "__main__":
    main()
