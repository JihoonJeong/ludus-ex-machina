"""Generate spectator commentary for a finished match (post-hoc, Phase 1).

Usage:
    python scripts/commentate_match.py <match_dir> \
        [--commentator claude:sonnet] [--commentator gemini:gemini-2.5-flash] \
        [--out <path>]

Each --commentator (adapter:model, repeatable) produces one bilingual track.
Default: a single claude:sonnet commentator. Writes <match_dir>/commentary.json
(spectator-only — never fed back to players).
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.commentary import commentate


def main():
    p = argparse.ArgumentParser(description="Generate spectator commentary for a match")
    p.add_argument("match_dir")
    p.add_argument("--commentator", action="append", default=None, metavar="ADAPTER:MODEL",
                   help="Commentator brain (repeatable). Default: claude:sonnet")
    p.add_argument("--out", default=None, help="Output path (default: <match_dir>/commentary.json)")
    args = p.parse_args()

    if not os.path.isdir(args.match_dir):
        p.error(f"match dir not found: {args.match_dir}")

    specs = args.commentator or ["claude:sonnet"]
    commentators = []
    for s in specs:
        adapter, _, model = s.partition(":")
        commentators.append((adapter, model or "sonnet"))

    result = commentate(args.match_dir, commentators)
    out = args.out or os.path.join(args.match_dir, "commentary.json")
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    n_beats = sum(len(t["beats"]) for t in result["commentators"])
    print(f"wrote {out}")
    print(f"  game: {result['game']} | {len(result['commentators'])} track(s) | {n_beats} beats total")
    # preview first beat of first track
    if result["commentators"] and result["commentators"][0]["beats"]:
        b = result["commentators"][0]["beats"][0]
        print(f"  sample [{b['label']}] EN: {b['en'][:120]}")
        print(f"  sample [{b['label']}] KO: {b['ko'][:120]}")


if __name__ == "__main__":
    main()
