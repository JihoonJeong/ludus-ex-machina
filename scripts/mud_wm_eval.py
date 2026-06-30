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
    open(out_path, "w").close()  # truncate
    for i, action in enumerate(actions):
        before = game.build_semantic_state(args.agent, state)
        valid = game.validate_move(action, args.agent, state)
        prompt = spec.build_prompt(before, action)
        try:
            res = adapter.invoke(scratch, prompt)
            text = res.get("stdout", "") if isinstance(res, dict) else ""
        except Exception as e:
            text = ""
            print(f"  [turn {i+1}] adapter error: {e}")
        predicted = wm.extract_prediction(text)

        # apply the real action (in-place mutation of state["game"]["current"])
        if valid.get("valid"):
            game.apply_move(action, args.agent, state)
        after = game.build_semantic_state(args.agent, state)

        noop = spec.is_no_op(before, after)
        comparison = spec.compare(predicted, after) if predicted is not None else {
            "format_ok": False, "exact": False, "factuality": 0.0, "detail": "no prediction parsed"}
        record = {
            "turn": i + 1,
            "action": action,
            "valid": valid.get("valid"),
            "is_no_op": noop,
            "parsed": predicted is not None,
            "comparison": comparison,
            "predicted": predicted,
            "actual": spec.scored(after),
        }
        records.append(record)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        tag = "NO-OP" if noop else "act"
        verb = action.get("verb", "?")
        print(f"  [turn {i+1}] {verb:7} {tag:5} parsed={predicted is not None} "
              f"exact={comparison.get('exact')} factuality={comparison.get('factuality')}")

    summary = wm.summarize(records)
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nwrote {out_path} ({len(records)} records)")


if __name__ == "__main__":
    main()
