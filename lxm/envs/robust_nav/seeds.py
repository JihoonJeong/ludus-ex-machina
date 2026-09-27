"""Seed splits for robust_nav.

    dev    public — contract checks and the smoke
    tune   public — controller tuning
    final  sealed — only the sha256 of the manifest file is public
           (seeds_v0.json); the file itself is revealed once Yeoul freezes the
           controller designs (commit-reveal). Take its first N seeds, N fixed
           after the dev smoke.

None of the public seeds 1-20 of LxM 095 are used here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

MANIFEST_V0 = Path(__file__).with_name("seeds_v0.json")


def load(split: str, manifest=MANIFEST_V0) -> list[int]:
    m = json.loads(Path(manifest).read_text())
    s = m["splits"][split]
    if "seeds" not in s:
        raise LookupError(f"split {split!r} is sealed (sha256 {s['sha256'][:12]}…); reveal the manifest first")
    return list(s["seeds"])


def verify_final(path, manifest=MANIFEST_V0) -> list[int]:
    """Check a revealed final manifest against the sealed hash; return its seeds."""
    m = json.loads(Path(manifest).read_text())
    raw = Path(path).read_bytes()
    want = m["splits"]["final"]["sha256"]
    got = hashlib.sha256(raw).hexdigest()
    if got != want:
        raise ValueError(f"final manifest sha256 {got} does not match the sealed {want}")
    return list(json.loads(raw)["seeds"])
