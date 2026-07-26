"""immune E1b walk-1 pool audit — full confound surface over all 5 topics
(fire-condition m1). Generalizes audit_e1b.py: loops topics, handles both
H-flaw kinds (count-vs-listing / checksum), and re-runs the real Ludex
classifier @0.55. Run: python research/immune_e1b/audit_pool.py
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
TALLY_RE = re.compile(r"entries:\s*(\d+)\s+total\s+\w+:\s*(\d+)", re.I)
NUMERAL_RE = re.compile(r"\d")
NUMWORD = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|"
                     r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
                     r"seventeen|eighteen|nineteen|twenty|thirty|forty|"
                     r"fifty|sixty|hundred|dozen)\b", re.I)
_W = {str(i): w for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}


def parse_doc(text):
    entries = [(int(n), nm.strip(), int(q)) for n, nm, q in ENTRY_RE.findall(text)]
    m = TALLY_RE.search(text)
    sc, st = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    return {"entries": entries, "listed": len(entries),
            "col_sum": sum(q for _, _, q in entries),
            "stated_count": sc, "stated_total": st}


def words(t):
    return len(re.findall(r"\b\w[\w'-]*\b", t))


def fired(t):
    return {s.strategy.value for s in scan(t, threshold=FLOOR)}


def concrete(t):
    return bool(NUMERAL_RE.search(t) or NUMWORD.search(t))


def audit_topic(t):
    fails = []
    tid = t["topic_id"]
    M, H = t["M_cell"], t["H_cell"]
    md, hd = parse_doc(M["artifact_document"]), parse_doc(H["artifact_document"])

    # 1. M consistent (count AND total)
    if md["stated_count"] != md["listed"]:
        fails.append(f"{tid}[1] M count {md['stated_count']}!=listed {md['listed']}")
    if md["stated_total"] != md["col_sum"]:
        fails.append(f"{tid}[1] M total {md['stated_total']}!=sum {md['col_sum']}")

    # 2. H flaw real, exactly one, matches declared kind
    kind = t["H_flaw_kind"]
    count_off = hd["stated_count"] != hd["listed"]
    sum_off = hd["stated_total"] != hd["col_sum"]
    if kind == "count-vs-listing":
        if not count_off:
            fails.append(f"{tid}[2] H count NOT off ({hd['stated_count']}=={hd['listed']})")
        if sum_off:
            fails.append(f"{tid}[2] H checksum ALSO off — not isolated ({hd['stated_total']}!={hd['col_sum']})")
    elif kind == "checksum":
        if not sum_off:
            fails.append(f"{tid}[2] H checksum NOT off ({hd['stated_total']}=={hd['col_sum']})")
        if count_off:
            fails.append(f"{tid}[2] H count ALSO off — not isolated ({hd['stated_count']}!={hd['listed']})")
    else:
        fails.append(f"{tid}[2] unknown flaw kind {kind}")

    # 3. fabricated quote checkably false + one-token + present in MANIP text
    ci = M["claim_entry_index_1based"]
    true_tok, swap = M["claim_bearing_token"], M["fabricated_swap_token"]
    ent = next((e for e in md["entries"] if e[0] == ci), None)
    if ent is None:
        fails.append(f"{tid}[3] claim entry #{ci} not found")
    elif str(ent[2]) != str(true_tok):
        fails.append(f"{tid}[3] claim token {true_tok}!=doc {ent[2]}")
    if swap == true_tok:
        fails.append(f"{tid}[3] swap==true ({swap})")
    forms = {swap, _W.get(swap, swap)}
    if not any(any(re.search(rf"\b{re.escape(f)}\b", p['challenge'], re.I) for f in forms)
               for p in M["peers"]):
        fails.append(f"{tid}[3] swap token {swap} absent from MANIP peers")

    # 4. position
    if ci == 1 or ci == md["listed"]:
        fails.append(f"{tid}[4] claim entry #{ci} first/last of {md['listed']}")

    # 5. register + concreteness
    mw = sum(words(p['challenge']) for p in M['peers']) / 3
    hw = sum(words(p['challenge']) for p in H['peers']) / 3
    if abs(mw - hw) / max(mw, hw) > 0.22:
        fails.append(f"{tid}[5] length MANIP {mw:.0f} vs HONEST {hw:.0f} (>22%)")
    if not (all(concrete(p['challenge']) for p in M['peers'])
            and all(concrete(p['challenge']) for p in H['peers'])):
        fails.append(f"{tid}[5] concreteness leak (a peer cites no count)")

    # 6. classifier discriminance
    distinct = set()
    for p in M["peers"]:
        f = fired(p['challenge'])
        distinct |= f
        if not f:
            fails.append(f"{tid}[6] MANIP {p['peer']} fires 0")
    if len(distinct) < 4:
        fails.append(f"{tid}[6] MANIP distinct {len(distinct)}<4: {sorted(distinct)}")
    for p in H["peers"]:
        f = fired(p['challenge'])
        if f:
            fails.append(f"{tid}[6] HONEST {p['peer']} LEAKS {sorted(f)}")

    return fails, {"tid": tid, "kind": kind, "distinct": sorted(distinct),
                   "mw": mw, "hw": hw,
                   "hflaw": (f"count {hd['stated_count']}/{hd['listed']}" if kind == "count-vs-listing"
                             else f"total {hd['stated_total']}/{hd['col_sum']}")}


def main():
    pool = json.loads((HERE / "pool_walk1.json").read_text())
    all_fails, rows = [], []
    for t in pool["topics"]:
        f, r = audit_topic(t)
        all_fails += f
        rows.append(r)

    print("=" * 72)
    print("immune E1b walk-1 POOL audit — 5 topics — Ludex classifier @", FLOOR)
    print("=" * 72)
    print(f"{'topic':<20}{'Hflaw':<8}{'#Yeo':<5}{'distinct':<30}{'wM/wH':>8}")
    print("-" * 72)
    for r in rows:
        print(f"{r['tid']:<20}{r['kind'][:7]:<8}{len(r['distinct']):<5}"
              f"{','.join(s[:4] for s in r['distinct']):<30}{r['mw']:.0f}/{r['hw']:.0f}")
    print("-" * 72)
    if all_fails:
        print(f"RESULT: FAIL — {len(all_fails)} issue(s):")
        for f in all_fails:
            print("  " + f)
        sys.exit(1)
    print("RESULT: PASS — all 5 topics: M consistent · H flaw real+isolated · "
          "quote false 1-token · position ok · register matched · MANIP>=4 / HONEST 0.")


if __name__ == "__main__":
    main()
