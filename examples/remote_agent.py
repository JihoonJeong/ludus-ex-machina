#!/usr/bin/env python3
"""Generic remote agent for the LxM cross-machine match plane.

LxM is an agent-agnostic play-field: ANY API/CLI agentic AI — or a human, or a
rule — can connect over plain HTTP and play. Ludex creatures are one client, not
a requirement. This reference shows the whole contract end to end:

    create/join  ->  poll /state (or SSE /events)  ->  GET /turns/{n}
    (a self-contained `prompt`)  ->  decide (any policy)  ->  POST .../move

Zero third-party deps (stdlib urllib) so it's copyable as a standalone client.
Full HTTP contract: docs/cross-machine-api.md

Policies (pluggable; --policy):
    first-empty   built-in tic-tac-toe (zero deps; quick self-contained demo)
    cli           shell out to a CLI LLM with the turn prompt (--cmd "claude -p")
    human         print the prompt, you type the move JSON

Examples:
    # self-contained demo: one process drives both sides to completion
    python examples/remote_agent.py --solo --game tictactoe

    # play one side of an existing match with a CLI LLM
    python examples/remote_agent.py --match live_xxx --me aria --policy cli --cmd "claude -p"

    # against a local server
    python examples/remote_agent.py --solo --api http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULT_API = "https://lxm-api.onrender.com"
VIEWER = "https://jihoonjeong.github.io/ludus-ex-machina/viewer/#/match/"


# ── HTTP (stdlib only) ──

def _req(method, url, body=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, None


class LxMClient:
    """Thin wrapper over the cross-machine match HTTP contract."""

    def __init__(self, api=DEFAULT_API):
        self.api = api.rstrip("/")

    def create(self, game, participants, kind="practice", match_id=None, config=None):
        body = {"game": game, "participants": participants, "kind": kind,
                "config": config or {}}
        if match_id:
            body["match_id"] = match_id
        status, j = _req("POST", f"{self.api}/api/matches", body)
        if status != 200:
            raise RuntimeError(f"create failed {status}: {j}")
        return j

    def state(self, match_id):
        status, j = _req("GET", f"{self.api}/api/matches/{match_id}/state")
        return j if status == 200 else None

    def turn(self, match_id, n):
        status, j = _req("GET", f"{self.api}/api/matches/{match_id}/turns/{n}")
        return j if status == 200 else None

    def move(self, match_id, n, move, dialogue=None):
        body = {"move": move}
        if dialogue:
            body["dialogue"] = dialogue
        return _req("POST", f"{self.api}/api/matches/{match_id}/turns/{n}/move", body)


# ── Move extraction + policies (payload -> move dict) ──

def _extract_move(text):
    """Pull a move dict from free text: the first balanced {...} that is (or
    contains, as `move`) a move. Mirrors how the server parses agent output."""
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(text[start:i + 1])
                except Exception:
                    obj = None
                if isinstance(obj, dict):
                    if isinstance(obj.get("move"), dict):
                        return obj["move"]
                    if obj.get("type"):
                        return obj
                start = None
    return None


def first_empty_policy(payload):
    """tic-tac-toe: first empty cell. Zero deps — for the self-contained demo."""
    board = (payload.get("state") or {}).get("board")
    if not board:
        return None
    for r, row in enumerate(board):
        for c, cell in enumerate(row):
            if cell is None:
                return {"type": "place", "position": [r, c]}
    return None


def cli_policy(cmd):
    """Shell out to a CLI LLM with the turn prompt; extract the move from output.
    Works for any game — the `prompt` field is self-contained (rules + state +
    move format)."""
    def policy(payload):
        prompt = (payload.get("prompt") or payload.get("state_readable")
                  or json.dumps(payload.get("state")))
        proc = subprocess.run(cmd, shell=True, input=prompt,
                              capture_output=True, text=True, timeout=240)
        move = _extract_move(proc.stdout)
        if move is None:
            print(f"  [cli] no parseable move in:\n{proc.stdout[:300]}", file=sys.stderr)
        return move
    return policy


def human_policy(payload):
    print("\n" + "=" * 64)
    print(payload.get("prompt") or json.dumps(payload.get("state"), indent=2))
    print("=" * 64)
    try:
        return json.loads(input('move JSON (e.g. {"type":"place","position":[1,1]}): '))
    except Exception:
        return None


# ── Play ──

def play_side(client, match_id, me, policy, poll=1.0, max_idle=600, verbose=True):
    """Play `me`'s turns until the match completes. Polls /state; on a remote
    turn for `me`, fetches the prompt, decides via `policy`, submits the move."""
    idle = 0
    while idle < max_idle:
        st = client.state(match_id)
        if st is None:
            print("match gone", file=sys.stderr)
            return None
        if st["status"] == "complete":
            return st
        if st["to_move"] == me and st["to_move_kind"] == "remote":
            n = st["to_move_turn"]
            move = policy(client.turn(match_id, n))
            if move is None:
                print(f"  [{me}] policy produced no move on turn {n}", file=sys.stderr)
                return None
            code, res = client.move(match_id, n, move, dialogue=f"{me}: {json.dumps(move)}")
            if code != 200:
                print(f"  [{me}] move rejected {code}: {res}", file=sys.stderr)
                return None
            if verbose:
                print(f"  [turn {n}] {me} -> {move}")
            idle = 0
        else:
            time.sleep(poll)
            idle += 1
    return client.state(match_id)


def solo_demo(client, game, me, vs, kind, policy):
    """Create a 2-remote match and drive BOTH sides with `policy` to completion —
    a self-contained proof that a generic (non-ludex) client plays the plane."""
    env = client.create(game, [{"id": me, "kind": "remote"},
                               {"id": vs, "kind": "remote"}], kind=kind)
    mid = env["match_id"]
    print(f"created {mid} (kind={env.get('kind', 'practice')}) — one generic client driving both sides")
    while True:
        st = client.state(mid)
        if st["status"] == "complete":
            break
        who, n = st["to_move"], st["to_move_turn"]
        move = policy(client.turn(mid, n))
        if move is None:
            print("policy gave no move; stopping", file=sys.stderr)
            break
        code, res = client.move(mid, n, move, dialogue=f"{who}: {json.dumps(move)}")
        if code != 200:
            print(f"move rejected {code}: {res}", file=sys.stderr)
            break
        print(f"  [turn {n}] {who} -> {move}")
    final = client.state(mid)
    print(f"\nfinal: {final['status']} — {(final.get('result') or {}).get('summary')}")
    print(f"viewer: {VIEWER}{mid}")
    return final


def _make_policy(args):
    if args.policy == "first-empty":
        return first_empty_policy
    if args.policy == "cli":
        if not args.cmd:
            sys.exit("--policy cli needs --cmd, e.g. --cmd 'claude -p'")
        return cli_policy(args.cmd)
    return human_policy


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--policy", default="first-empty",
                    choices=["first-empty", "cli", "human"])
    ap.add_argument("--cmd", help="CLI command for --policy cli (e.g. 'claude -p')")
    ap.add_argument("--kind", default="practice", choices=["practice", "published"])
    ap.add_argument("--solo", action="store_true", help="create a match, drive both sides")
    ap.add_argument("--game", default="tictactoe")
    ap.add_argument("--me", default="aria")
    ap.add_argument("--vs", default="kestrel")
    ap.add_argument("--match", help="join an existing match id and play --me's side")
    args = ap.parse_args()

    client = LxMClient(args.api)
    policy = _make_policy(args)

    if args.solo:
        solo_demo(client, args.game, args.me, args.vs, args.kind, policy)
    elif args.match:
        final = play_side(client, args.match, args.me, policy)
        print(f"done: {final['status'] if final else 'stopped'}")
    else:
        env = client.create(args.game, [{"id": args.me, "kind": "remote"},
                                        {"id": args.vs, "kind": "remote"}], kind=args.kind)
        print(f"created {env['match_id']} — playing {args.me}'s side "
              f"(run another client for {args.vs})")
        play_side(client, env["match_id"], args.me, policy)


if __name__ == "__main__":
    main()
