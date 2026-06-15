#!/usr/bin/env python3
"""Export a hosted match's replay for permanent web viewing (the `published`
durable store).

Pulls config/log/result from the live LxM API and writes the viewer's replay
bundle to docs/data/replays/{id}.json — served permanently by GitHub Pages with
no Redis / 24h-TTL dependency. Run it on the matches worth keeping (published is
curated). The viewer falls back to this static replay once the live match
expires from Redis, so an exported match stays viewable forever.

Storage backend: `pages` (docs/data/replays → GitHub Pages) is the immediate,
provisioning-free store — fine for light games. The long-term store for heavy
games (blockworld replays are multi-MB) is a public GCS bucket (CORS-friendly,
~pennies/GB, no git bloat); add a `gcs` writer here + point datasource.js at the
bucket when it's provisioned. The pull side is backend-agnostic.

Usage:
    python scripts/export_hosted_match.py live_xxxx
    python scripts/export_hosted_match.py live_xxxx --api http://localhost:8000
    python scripts/export_hosted_match.py live_xxxx --out docs/data/replays
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_API = "https://lxm-api.onrender.com"
VIEWER = "https://jihoonjeong.github.io/ludus-ex-machina/viewer/#/match/"


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=90) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


def export_match(api: str, match_id: str, out_dir: str) -> Path:
    base = api.rstrip("/")
    status, state = _get(f"{base}/api/matches/{match_id}/state")
    if status != 200 or state is None:
        sys.exit(f"match '{match_id}' not found ({status})")
    if state.get("status") != "complete":
        print(f"warning: match is '{state.get('status')}', not complete", file=sys.stderr)
    if state.get("kind") != "published":
        print(f"note: match kind is '{state.get('kind')}' — exporting to Pages anyway",
              file=sys.stderr)

    bundle = {}
    for part in ("config", "log", "result"):
        s, j = _get(f"{base}/api/matches/{match_id}/{part}")
        if s != 200:
            sys.exit(f"GET /{part} failed ({s})")
        bundle[part] = j

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{match_id}.json"
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size} B)")
    print(f"viewer: {VIEWER}{match_id}")
    print(f"publish: git add {path} && git commit && git push  (GitHub Pages serves it)")
    return path


def main():
    ap = argparse.ArgumentParser(description="Export a hosted match replay to docs/data/replays.")
    ap.add_argument("match_id")
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--out", default="docs/data/replays")
    args = ap.parse_args()
    export_match(args.api, args.match_id, args.out)


if __name__ == "__main__":
    main()
