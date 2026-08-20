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

DOCS = Path(__file__).resolve().parent.parent / "docs"


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
    if drift:
        print(f"\n{len(drift)} drifted. Fix the HTML fallback to match i18n.js.")
        return 1
    print("all fallbacks match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
