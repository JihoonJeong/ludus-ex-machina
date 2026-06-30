"""MUD predict-before-act world-model eval harness (language world model).

Mirrors scripts/blockworld_wm_eval.py for the MUD text-adventure field: a brain
is shown an agent-local room-scope semantic state + an action and predicts the
next state; we apply the real action and score the prediction (agent + room +
flags; turn/events excluded). The deterministic, fog-of-war language world makes
this a clean test of whether an LLM tracks symbolic/relational state from prose.

Usage:
    python scripts/mud_wm_eval.py \
        [--scenario astronomer_tower] [--adapter claude] [--model sonnet] \
        [--agent a] [--out predictions.jsonl] [--actions actions.json]

The built-in action script stays in the start room (study): 2 effective changes +
4 no-ops, all fully predictable from the opening observation — so the score is a
fair world-model signal and no-op fidelity (no hallucinated effects) is the
headline test. Works with ANY adapter (claude/gemini/codex/ollama/ludex).
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from games.mud.engine import MudGame
from lxm.adapters.registry import get_adapter_class
from lxm import wm_predict as wm

# astronomer_tower start = 'study'. Each next-state is fully predictable from the
# opening observation: 2 effective (take/drop the star-chart) + 4 no-ops
# (examine, read, a locked 'go', taking a hidden object) — exercises within-room
# dynamics AND no-op fidelity, mirroring the blockworld script's 3+3 shape.
DEFAULT_ACTIONS = [
    {"type": "action", "verb": "take", "target": "star-chart"},   # effective: room -> inv
    {"type": "action", "verb": "examine", "target": "orrery"},    # no-op: text only
    {"type": "action", "verb": "read", "target": "star-chart"},   # no-op: text only
    {"type": "action", "verb": "go", "direction": "east"},        # no-op: observatory locked
    {"type": "action", "verb": "take", "target": "brass key"},    # no-op: hidden (not in view)
    {"type": "action", "verb": "drop", "target": "star-chart"},   # effective: inv -> room
]


def main():
    p = argparse.ArgumentParser(description="MUD predict-before-act world-model eval")
    p.add_argument("--scenario", default="astronomer_tower")
    p.add_argument("--adapter", default="claude")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--agent", default="a")
    p.add_argument("--creature-path", default=None,
                   help="path to a Ludex creature dir (required for the ludex creature adapter)")
    p.add_argument("--actions", default=None,
                   help="JSON file: list of action dicts (default: built-in study-room script)")
    p.add_argument("--out", default=None,
                   help="output predictions.jsonl (default: predictions_mud_<scenario>.jsonl)")
    args = p.parse_args()

    actions = json.loads(Path(args.actions).read_text()) if args.actions else DEFAULT_ACTIONS
    out_path = args.out or f"predictions_mud_{args.scenario}.jsonl"

    spec = wm.get_wm_spec("mud")
    game = MudGame(scenario_id=args.scenario)
    state = {"game": game.initial_state([{"agent_id": args.agent}]),
             "lxm": {"match_id": f"wm_eval_mud_{args.scenario}"}}

    adapter_config = {"agent_id": "wm_predictor", "model": args.model}
    if args.creature_path:
        adapter_config["creature_path"] = args.creature_path
        # eval is ephemeral — don't write the creature's episodic memory (D-090 spirit);
        # world-model learning happens via Ludex's physis-ingest of predictions.jsonl.
        adapter_config["record_memory"] = False
    adapter = get_adapter_class(args.adapter)(adapter_config)
    ctx = getattr(adapter, "set_context", None)
    if callable(ctx):
        try:
            ctx("wm_predictor")
        except Exception:
            pass
    scratch = tempfile.mkdtemp(prefix="wm_eval_mud_")

    records = []
    seen_rooms: set = set()
    open(out_path, "w").close()  # truncate
    for i, action in enumerate(actions):
        before = game.build_semantic_state(args.agent, state)
        seen_rooms.add((before.get("room") or {}).get("id"))
        valid = game.validate_move(action, args.agent, state)
        prompt = spec.build_prompt(before, action)
        # 1-shot retry on unparseable output (Ludex Cody round 3): a cheap,
        # contract-free robustness lever. retry_rate (in the summary) is the
        # agreed DATA SIGNAL for when full-state echo truncation warrants
        # introducing --output-mode delta — decide by signal, not by guess.
        attempts, predicted, text = 0, None, ""
        while attempts < 2 and predicted is None:
            attempts += 1
            try:
                res = adapter.invoke(scratch, prompt)
                text = res.get("stdout", "") if isinstance(res, dict) else ""
            except Exception as e:
                text = ""
                print(f"  [turn {i+1}] adapter error (attempt {attempts}): {e}")
            predicted = wm.extract_prediction(text)
        retried = attempts > 1

        # apply the real action (in-place mutation of state["game"]["current"])
        if valid.get("valid"):
            game.apply_move(action, args.agent, state)
        after = game.build_semantic_state(args.agent, state)

        # Fog-of-war scoring mask (Ludex Cody point 3): a `go` into a room not
        # yet observed reveals contents the agent could not have known — score
        # only the knowable `agent` projection (location), not the new room.
        after_room = (after.get("room") or {}).get("id")
        first_visit_go = (action.get("verb") == "go" and after_room is not None
                          and after_room not in seen_rooms)
        turn_keys = ("agent",) if first_visit_go else spec.scored_keys

        noop = spec.is_no_op(before, after)
        comparison = spec.compare(predicted, after, keys=turn_keys) if predicted is not None else {
            "format_ok": False, "exact": False, "factuality": 0.0, "detail": "no prediction parsed"}

        # No-op reason tag (point 1) + over/under-prediction split (point 2).
        noop_reason = wm.classify_mud_noop(action, before) if noop else None
        confabulated = bool(noop and predicted is not None and not comparison.get("exact"))
        missed = bool((not noop) and predicted is not None
                      and spec.compare(predicted, before, keys=turn_keys).get("exact"))

        record = {
            "turn": i + 1,
            "action": action,
            "valid": valid.get("valid"),
            "is_no_op": noop,
            "noop_reason": noop_reason,
            "fog_masked": first_visit_go,
            "scored_keys": list(turn_keys),
            "parsed": predicted is not None,
            "attempts": attempts,
            "retried": retried,
            "confabulated": confabulated,
            "missed": missed,
            "comparison": comparison,
            "predicted": predicted,
            "actual": spec.scored(after),
        }
        records.append(record)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        tag = f"NO-OP:{noop_reason}" if noop else "act"
        flags = (("F" if first_visit_go else "") + ("C" if confabulated else "")
                 + ("M" if missed else "") + ("R" if retried else ""))
        print(f"  [turn {i+1}] {action.get('verb','?'):7} {tag:20} parsed={predicted is not None} "
              f"exact={comparison.get('exact')} fact={comparison.get('factuality')} {flags}")

    summary = wm.summarize(records)
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nwrote {out_path} ({len(records)} records)")


if __name__ == "__main__":
    main()
