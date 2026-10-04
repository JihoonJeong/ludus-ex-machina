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
  3. Ask again for every number the local copy lacks. The pull's cursor is
     the local maximum, so a number that reaches the drop *after* a higher
     one has been collected is never asked for. That is not hypothetical:
     hub-ops/from-ludex 026 and 027 were written after a stray 037 had
     raised the door's maximum, and sat on the drop unread for 39 days
     (found 2026-10-04 only by listing the whole door). So each run of
     missing numbers gets one GET from just below it, and whatever the door
     holds inside the run is written the way the client writes it. A hole
     the audit has already explained is asked too — 026 and 027 were inside
     an explained range.
  4. door_audit.scan on each tree; print only what it has not explained.
  5. One headline per arrival, so the operator reads titles, not listings.

Usage: python scripts/collect_round.py [--dry-run] [--timeout 600] [--max-probes 30]
Exit 1 if any pull or probe failed or any audit found something unexplained.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
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
N_RE = re.compile(r"^[0-9]{3,6}\Z")                 # the drop's own shapes (organum hub_drop)
BODY_NAME_RE = re.compile(r"^body\.[a-z0-9]{1,8}\Z")


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


def hole_ranges(dest: Path) -> list[tuple[int, int]]:
    """Runs of numbers the local copy of a door lacks, from 001 to its maximum."""
    have = {int(f.name.split("-", 1)[0]) for f in dest.glob("*-envelope.json")
            if N_RE.match(f.name.split("-", 1)[0])}
    runs: list[tuple[int, int]] = []
    for n in range(1, max(have, default=0) + 1):
        if n in have:
            continue
        if runs and runs[-1][1] == n - 1:
            runs[-1] = (runs[-1][0], n)
        else:
            runs.append((n, n))
    return runs


def probe_hole(fetch, dest: Path, lo: int, hi: int) -> list[str]:
    """Ask a door what it holds in lo..hi and write what the local copy lacks.

    `fetch(since)` returns one page of the door. One request settles a hole the
    door does not have either: the page starts above `hi` and nothing is
    written. Files are written as the client's pull writes them (sig with a
    trailing newline, then the body, the envelope last as the mark of a
    complete quad), and a quad whose envelope is already here is not touched.
    """
    filled, since = [], lo - 1
    while True:
        page = fetch(f"{since:03d}")
        quads = page.get("quads") or []
        for q in quads:
            n = str(q.get("n"))
            if not N_RE.match(n) or int(n) <= since:
                raise ValueError(f"door answered n={n!r} after since={since:03d}")
            if int(n) > hi:
                return filled
            since = int(n)
            env_p = dest / f"{n}-envelope.json"
            if env_p.exists():
                continue
            body_name = q.get("body_name")
            if body_name is not None and not BODY_NAME_RE.match(str(body_name)):
                raise ValueError(f"door answered body_name={body_name!r} for {n}")
            env_b = base64.b64decode(q["envelope_b64"])
            body_b = base64.b64decode(q["body_b64"]) if body_name else None
            (dest / f"{n}-sig.txt").write_bytes((q["sig"] + "\n").encode("utf-8"))
            if body_name:
                (dest / f"{n}-{body_name}").write_bytes(body_b)
            env_p.write_bytes(env_b)
            filled.append(n)
        if not quads or not page.get("more"):
            return filled


def _span(lo: int, hi: int) -> str:
    return f"{lo:03d}" if lo == hi else f"{lo:03d}-{hi:03d}"


def door_fetcher(base: str, token_file: Path, timeout: int, pull: Pull):
    from organum import hub_drop
    token = hub_drop.load_tokens(token_file)[0]
    url = f"{base}/v0/{pull.tree}/{pull.door}"
    return lambda since: hub_drop.fetch_page(url, token, since, timeout=timeout)


def headline(body: Path) -> str:
    """A markdown title, or for a board event its kind, post id and first line;
    for a creature letter (letters/ tree) its author, recipient and voice."""
    if body.suffix == ".json":
        try:
            ev = json.loads(body.read_text(encoding="utf-8"))
        except ValueError:
            return "(unreadable json)"
        bits = [str(ev.get("kind", "?"))]
        if ev.get("kind") == "creature.letter":        # who wrote to whom, and whether it carries a voice
            au, to = ev.get("author") or {}, ev.get("to") or {}
            bits.append(f"{au.get('lab', '?')}/{au.get('id', '?')} -> {to.get('lab_id', '?')}/{to.get('to_id', '?')}")
            bits.append("voice" if ev.get("voice") else "no-voice")
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
    ap.add_argument("--max-probes", type=int, default=30,
                    help="hole ranges asked per round (the drop allows 60 requests a minute)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, pull nothing")
    a = ap.parse_args()

    channels = fetch_channels(a.hub, a.base, a.token_file, a.timeout)
    plan = plan_pulls(channels, a.state, f"from-{a.self_lab}")
    print(f"channels: {len(channels)} trees, {len(plan)} doors to pull")
    for p in plan:
        print(f"  {p.label:32s} {'(new door, --since 000)' if p.since else ''}")
    if a.dry_run:
        return 0

    failures, arrivals, answered = 0, [], []
    print("\npull:")
    for p in plan:
        pulled, err = run_pull(a.hub, a.base, a.token_file, a.timeout, p)
        if err:
            failures += 1
            print(f"  {p.label:32s} FAILED: {err[:160]}")
            continue
        print(f"  {p.label:32s} {' '.join(pulled) if pulled else '-'}")
        arrivals += [(p, n, False) for n in pulled]
        answered.append(p)

    holes = [(p, lo, hi) for p in answered for lo, hi in hole_ranges(p.dest)]
    print(f"\nprobe: {len(holes)} hole range(s) below a door's maximum")
    for p, lo, hi in holes[:a.max_probes]:
        span = _span(lo, hi)
        try:
            filled = probe_hole(door_fetcher(a.base, a.token_file, a.timeout, p), p.dest, lo, hi)
        except Exception as e:  # a probe that died is not a hole confirmed empty
            failures += 1
            print(f"  {p.label:32s} {span:9s} FAILED: {type(e).__name__}: {str(e)[:140]}")
            continue
        print(f"  {p.label:32s} {span:9s} {'LATE ' + ' '.join(filled) if filled else '-'}")
        arrivals += [(p, n, True) for n in filled]
    for p, lo, hi in holes[a.max_probes:]:
        print(f"  {p.label:32s} {_span(lo, hi):9s} not asked this round (--max-probes {a.max_probes})")

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
    for p, n, late in arrivals:
        b = body_of(p.dest, n)
        print(f"  {p.label}/{n}{' (late, below the maximum)' if late else ''}  "
              f"{headline(b) if b else '(no body file)'}")

    if failures or unexplained:
        print(f"\n{failures} pull or probe failure(s), {unexplained} unexplained audit finding(s)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
