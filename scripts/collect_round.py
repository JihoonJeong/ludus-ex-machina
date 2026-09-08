#!/usr/bin/env python3
"""Collect one round from the hosted drop — every tree, every door, then audit.

The round used to be typed by hand: six hub-ops doors, then whichever board
trees the operator happened to remember. Twice in one week the memory was
short. On 09-05 the round pulled hub-ops only, so the W36 host slot on the
plaza went unseen and our column stayed empty; the same morning a channel
opened while our consent for the previous one was still leaving the outbox.
door_audit already says why this has to be a script: a ritual retyped from
memory is not a ritual — it drifts, and the round it drifts is the round it
was needed.

What it does, in order:

  1. GET /v0/channels — the facility's own list of trees and doors. This is
     the plan; nothing is remembered. The call also warms the instance, so
     the pulls that follow run --no-warmup.
  2. Pull every door of every tree into the layout the rounds already use:
     hub-ops at state/inbox/<door> (the flat shape from the first weeks),
     every other tree at state/<tree>/inbox/<door>, which is the shape
     door_audit --state expects. A door never pulled before gets --since 000;
     the default cursor is max(local), and an empty directory has no max.
     Our own hub-ops door is skipped (its copy is state/outbox), but our own
     board doors are pulled — reading a post back is the proof the mirror
     took it.
  3. door_audit.scan on each tree; print only what it has not explained.
  4. One headline per arrival, so the operator reads titles, not listings.

Usage: python scripts/collect_round.py [--dry-run] [--timeout 600]
Exit 1 if any pull failed or any audit found something unexplained.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:  # `python -m pytest` from the repo root sees scripts/ as a namespace package
    from scripts import door_audit
except ImportError:  # `python scripts/collect_round.py` puts scripts/ itself first
    import door_audit  # type: ignore[no-redef]

HUB_OPS = "hub-ops"
DEFAULT_BASE = "https://lxm-drop.onrender.com"


@dataclass(frozen=True)
class Pull:
    tree: str
    door: str
    dest: Path
    since: str | None

    @property
    def label(self) -> str:
        return f"{self.tree}/{self.door}"


def tree_root(state_root: Path, tree: str) -> Path:
    """Where a tree's inbox/ and outbox/ live."""
    return state_root if tree == HUB_OPS else state_root / tree


def plan_pulls(channels: dict[str, list[str]], state_root: Path,
               self_door: str) -> list[Pull]:
    plan = []
    for tree in sorted(channels):
        for door in sorted(channels[tree]):
            if tree == HUB_OPS and door == self_door:
                continue
            dest = tree_root(state_root, tree) / "inbox" / door
            seen = any(dest.glob("*-envelope.json"))
            plan.append(Pull(tree, door, dest, None if seen else "000"))
    return plan


def fetch_channels(hub: Path, base: str, token_file: Path,
                   timeout: int) -> dict[str, list[str]]:
    out = subprocess.run(
        [str(hub), "channels", "--url", f"{base}/v0/channels",
         "--token-file", str(token_file), "--timeout", str(timeout)],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)["channels"]


def run_pull(hub: Path, base: str, token_file: Path, timeout: int,
             pull: Pull) -> tuple[list[str], str | None]:
    """Returns (pulled numbers, error). A pull that did not answer in JSON is
    a failure with its stderr, never an empty success."""
    cmd = [str(hub), "pull", "--url", f"{base}/v0/{pull.tree}/{pull.door}",
           "--dest", str(pull.dest), "--token-file", str(token_file),
           "--no-warmup", "--timeout", str(timeout)]
    if pull.since:
        cmd += ["--since", pull.since]
    pull.dest.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    try:
        return json.loads(last).get("pulled", []), None
    except ValueError:
        return [], (r.stderr.strip() or last or f"exit {r.returncode}")


def headline(body: Path) -> str:
    """A markdown title, or for a board event its kind, post id and first line."""
    if body.suffix == ".json":
        try:
            ev = json.loads(body.read_text(encoding="utf-8"))
        except ValueError:
            return "(unreadable json)"
        bits = [str(ev.get("kind", "?"))]
        if ev.get("post_id"):
            bits.append(str(ev["post_id"]))
        if ev.get("reply_to"):
            bits.append(f"re={ev['reply_to']}")
        text = str(ev.get("text") or ev.get("name") or "").strip().splitlines()
        if text:
            bits.append(text[0][:100])
        return " ".join(bits)
    for line in body.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            return line.strip()[:120]
    return "(empty body)"


def body_of(dest: Path, n: str) -> Path | None:
    hits = sorted(dest.glob(f"{n}-body.*"))
    return hits[0] if hits else None


def audit_trees(channels: dict[str, list[str]], state_root: Path) -> dict[str, dict]:
    return {tree: door_audit.scan(tree_root(state_root, tree))
            for tree in sorted(channels)
            if (tree_root(state_root, tree) / "inbox").is_dir()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--hub", type=Path, default=Path(".venv/bin/organum-hub"))
    ap.add_argument("--token-file", type=Path, default=Path("state/drop-token.txt"))
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--self", dest="self_lab", default="lxm",
                    help="our lab short name; from-<self> in hub-ops is skipped")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true", help="print the plan, pull nothing")
    a = ap.parse_args()

    channels = fetch_channels(a.hub, a.base, a.token_file, a.timeout)
    plan = plan_pulls(channels, a.state, f"from-{a.self_lab}")
    print(f"channels: {len(channels)} trees, {len(plan)} doors to pull")
    for p in plan:
        print(f"  {p.label:32s} {'(new door, --since 000)' if p.since else ''}")
    if a.dry_run:
        return 0

    failures, arrivals = 0, []
    print("\npull:")
    for p in plan:
        pulled, err = run_pull(a.hub, a.base, a.token_file, a.timeout, p)
        if err:
            failures += 1
            print(f"  {p.label:32s} FAILED: {err[:160]}")
            continue
        print(f"  {p.label:32s} {' '.join(pulled) if pulled else '-'}")
        arrivals += [(p, n) for n in pulled]

    unexplained = 0
    print("\naudit:")
    for tree, r in audit_trees(channels, a.state).items():
        n_new = len(r["new_foreign"]) + len(r["new_gaps"])
        unexplained += n_new
        status = "clean" if n_new == 0 else f"{n_new} UNEXPLAINED"
        print(f"  {tree:16s} {len(r['doors'])} doors  {status}")
        for f in r["new_foreign"]:
            print(f"    foreign: {f['door']}/{f['seq']:03d} signed {f['signer']} (expected {f['expected']})")
        for g in r["new_gaps"]:
            print(f"    gap:     {g['door']}/{g['seq']:03d} missing")

    print(f"\narrivals: {len(arrivals)}")
    for p, n in arrivals:
        b = body_of(p.dest, n)
        print(f"  {p.label}/{n}  {headline(b) if b else '(no body file)'}")

    if failures or unexplained:
        print(f"\n{failures} pull failure(s), {unexplained} unexplained audit finding(s)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
