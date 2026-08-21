#!/usr/bin/env python3
"""Landing page: HTML fallback text must match the i18n source of truth.

Every `data-i18n="key"` element carries inline English text that renders only
until i18n.js applies (and permanently if it fails to load). That inline copy
and `i18n.js`'s English string are two copies of one claim, and nothing kept
them in sync: the platform card advertised "all 6 games ... GIF export" long
after the count reached 13 and the export button was removed.

Run before deploying docs/. Exits non-zero on drift so it fails loudly.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT))   # importable standalone, not only via export_static


def i18n_english(js: str) -> dict[str, str]:
    """First occurrence of each key = the English block (ko follows)."""
    out: dict[str, str] = {}
    for m in re.finditer(r'^\s*(\w+):\s*("(?:[^"\\]|\\.)*")\s*,?\s*$', js, re.M):
        key, quoted = m.group(1), m.group(2)
        if key in out:
            continue
        try:
            out[key] = json.loads(quoted)   # handles \uXXXX and \" exactly
        except json.JSONDecodeError:
            continue
    return out


def fallbacks(page: str) -> list[tuple[str, str]]:
    return re.findall(r'data-i18n="(\w+)"[^>]*>(.*?)</', page, re.S)


def norm(s: str) -> str:
    return " ".join(html.unescape(s).split())


# Copy-vs-copy is not enough: two copies can agree and both be wrong. The game
# count is asserted nine times across the page, the metadata, and both languages,
# and until now nothing crossed any of them against the registry — a claim with
# no crossing path at all, which is the condition drift lives longest under.
# Only the game count is machined here because _GAME_SPECS is a clean source of
# truth; "5 AI Runtimes" and "4 Companies" stay hand-verified, since encoding
# which adapters count as runtimes would just mint another unchecked copy.
_WORD_COUNT = {"Thirteen": 13, "Fourteen": 14, "Twelve": 12}


def claim_vs_reality() -> list[str]:
    from lxm.adapters.registry import _GAME_SPECS

    truth = len(_GAME_SPECS)
    problems: list[str] = []
    for name in ("index.html", "i18n.js"):
        text = (DOCS / name).read_text(encoding="utf-8")
        for claimed in re.findall(r"(\d+)\s*(?:games|개 게임)", text):
            if int(claimed) != truth:
                problems.append(f"{name}: claims {claimed} games, registry has {truth}")
        for word in re.findall(r"(\w+) games testing|(\w+) games\b", text):
            token = next((w for w in word if w in _WORD_COUNT), None)
            if token and _WORD_COUNT[token] != truth:
                problems.append(f"{name}: claims '{token}' games, registry has {truth}")
        for stat in re.findall(r'<span class="stat-number">(\d+)</span>\s*\n\s*'
                               r'<span class="stat-label" data-i18n="stat_games">', text):
            if int(stat) != truth:
                problems.append(f"{name}: stats bar says {stat} games, registry has {truth}")
    return problems


def main() -> int:
    en = i18n_english((DOCS / "i18n.js").read_text(encoding="utf-8"))
    pairs = fallbacks((DOCS / "index.html").read_text(encoding="utf-8"))
    drift = [(k, norm(t), norm(en[k])) for k, t in pairs
             if k in en and norm(t) != norm(en[k])]
    missing = sorted({k for k, _ in pairs} - set(en))

    print(f"data-i18n elements: {len(pairs)} · checked against i18n.js English")
    for key in missing:
        print(f"  [no i18n string] {key}")
    for key, got, want in drift:
        print(f"\n  DRIFT [{key}]\n    html: {got}\n    i18n: {want}")
    stale_claims = claim_vs_reality()
    for problem in stale_claims:
        print(f"\n  STALE CLAIM  {problem}")
    if drift or stale_claims:
        if drift:
            print(f"\n{len(drift)} drifted. Fix the HTML fallback to match i18n.js.")
        if stale_claims:
            print(f"{len(stale_claims)} claim(s) no longer match the registry.")
        return 1
    print("all fallbacks match · game count matches the registry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
