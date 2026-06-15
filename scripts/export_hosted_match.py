#!/usr/bin/env python3
"""Export a hosted match's replay for permanent web viewing (the `published`
durable store).

Pulls config/log/result from the live LxM API and writes the viewer's replay
bundle to a durable store. The viewer falls back to it once the live match
expires from Redis, so an exported match stays viewable forever.

Backends (--backend):
  gcs    public GCS bucket (default) — the long-term store; CORS-friendly,
         size-agnostic (heavy blockworld replays too), ~pennies/GB, no git bloat.
         Needs a service-account key (.secrets/gcs-sa.json or --sa /
         GOOGLE_APPLICATION_CREDENTIALS).
  pages  docs/data/replays/{id}.json — GitHub Pages, zero provisioning, fine for
         light games (git-versioned; commit + push to publish).

Usage:
    python scripts/export_hosted_match.py live_xxxx                 # -> GCS
    python scripts/export_hosted_match.py live_xxxx --backend pages
    python scripts/export_hosted_match.py live_xxxx --bucket lxm-replays
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_API = "https://lxm-api.onrender.com"
DEFAULT_BUCKET = "lxm-replays"
DEFAULT_SA = ".secrets/gcs-sa.json"
VIEWER = "https://jihoonjeong.github.io/ludus-ex-machina/viewer/#/match/"


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=90) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


def pull_bundle(api: str, match_id: str) -> dict:
    base = api.rstrip("/")
    status, state = _get(f"{base}/api/matches/{match_id}/state")
    if status != 200 or state is None:
        sys.exit(f"match '{match_id}' not found ({status})")
    if state.get("status") != "complete":
        print(f"warning: match is '{state.get('status')}', not complete", file=sys.stderr)
    if state.get("kind") != "published":
        print(f"note: match kind is '{state.get('kind')}' — exporting anyway", file=sys.stderr)
    bundle = {}
    for part in ("config", "log", "result"):
        s, j = _get(f"{base}/api/matches/{match_id}/{part}")
        if s != 200:
            sys.exit(f"GET /{part} failed ({s})")
        bundle[part] = j
    return bundle


def write_pages(bundle: dict, match_id: str, out_dir: str) -> str:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{match_id}.json"
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size} B)")
    print(f"publish: git add {path} && git commit && git push")
    return str(path)


def write_gcs(bundle: dict, match_id: str, bucket: str, sa_path: str | None) -> str:
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
    except ImportError:
        sys.exit("GCS backend needs: pip install -r requirements-gcs.txt")
    if sa_path and os.path.isfile(sa_path):
        creds = service_account.Credentials.from_service_account_file(sa_path)
        client = storage.Client(credentials=creds)
    else:
        client = storage.Client()  # falls back to GOOGLE_APPLICATION_CREDENTIALS / ADC
    blob = client.bucket(bucket).blob(f"replays/{match_id}.json")
    blob.cache_control = "public, max-age=3600"
    blob.upload_from_string(json.dumps(bundle, indent=2), content_type="application/json")
    url = f"https://storage.googleapis.com/{bucket}/replays/{match_id}.json"
    print(f"uploaded {url} ({blob.size} B)")
    return url


def main():
    ap = argparse.ArgumentParser(description="Export a hosted match replay (durable store).")
    ap.add_argument("match_id")
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--backend", default="gcs", choices=["gcs", "pages"])
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--sa", default=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_SA))
    ap.add_argument("--out", default="docs/data/replays")
    args = ap.parse_args()

    bundle = pull_bundle(args.api, args.match_id)
    if args.backend == "gcs":
        if not (args.sa and os.path.isfile(args.sa)):
            sys.exit(f"GCS backend needs a service-account key (looked at '{args.sa}'). "
                     f"Set --sa / GOOGLE_APPLICATION_CREDENTIALS, or use --backend pages.")
        write_gcs(bundle, args.match_id, args.bucket, args.sa)
    else:
        write_pages(bundle, args.match_id, args.out)
    print(f"viewer: {VIEWER}{args.match_id}")


if __name__ == "__main__":
    main()
