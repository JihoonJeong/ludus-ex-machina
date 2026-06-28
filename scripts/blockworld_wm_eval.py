"""Blockworld predict-before-act world-model eval harness (Ludex RFP).

A brain is shown an agent-local semantic state + an action and predicts the next
state; we apply the real action and score the prediction (agent + view; events
excluded). Works with ANY adapter (claude/gemini/codex/ollama/ludex) — like the
Qwen-AgentWorld PoC, off-the-shelf brains can predict voxel transitions.

Usage:
    python scripts/blockworld_wm_eval.py \
        [--scenario sandbox_01] [--adapter claude] [--model sonnet] \
        [--agent a] [--out predictions.jsonl] [--actions actions.json]

Writes a predictions.jsonl (one record per action) + prints a competence
summary. No-op cases (move-into-solid / empty-hand place / break-air) are
weighted separately — the headline world-model test.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from games.blockworld.engine import BlockworldGame
from lxm.adapters.registry import get_adapter_class
from lxm import wm_predict as wm

# Default instructive action script for sandbox_01 (agent 'a' starts at
# (16,16,1) on a flat grass field). 3 effective actions + 3 no-ops so the eval
# exercises move/break/place AND no-op fidelity in one short run.
DEFAULT_ACTIONS = [
    {"type": "action", "verb": "move", "direction": "north"},   # (16,16,1)->(16,15,1)
    {"type": "action", "verb": "break", "direction": "down"},   # grass@(16,15,0)->air, +1 dirt
    {"type": "action", "verb": "place", "direction": "south"},  # NOTE: block filled below
    {"type": "action", "verb": "place", "direction": "south"},  # no-op: empty hand
    {"type": "action", "verb": "move", "direction": "south"},   # no-op: into placed block
    {"type": "action", "verb": "break", "direction": "north"},  # no-op: break air
]
for _a in DEFAULT_ACTIONS:
    if _a["verb"] == "place":
        _a["block"] = "dirt"


def main():
    p = argparse.ArgumentParser(description="Blockworld predict-before-act world-model eval")
    p.add_argument("--scenario", default="sandbox_01")
    p.add_argument("--adapter", default="claude")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--agent", default="a")
    p.add_argument("--creature-path", default=None,
                   help="path to a Ludex creature dir (required for the ludex creature adapter)")
    p.add_argument("--actions", default=None, help="JSON file: list of action dicts (default: built-in sandbox_01 script)")
    p.add_argument("--out", default=None, help="output predictions.jsonl (default: predictions_<scenario>.jsonl)")
    args = p.parse_args()

    actions = json.loads(Path(args.actions).read_text()) if args.actions else DEFAULT_ACTIONS
    out_path = args.out or f"predictions_{args.scenario}.jsonl"

    game = BlockworldGame(scenario_id=args.scenario)
    state = {"game": game.initial_state([{"agent_id": args.agent}]),
             "lxm": {"match_id": f"wm_eval_{args.scenario}"}}

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
    scratch = tempfile.mkdtemp(prefix="wm_eval_")

    records = []
    open(out_path, "w").close()  # truncate
    for i, action in enumerate(actions):
        before = game.build_semantic_state(args.agent, state)
        valid = game.validate_move(action, args.agent, state)
        prompt = wm.build_predict_prompt(before, action)
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

        noop = wm.is_no_op(before, after)
        comparison = wm.compare_semantic(predicted, after) if predicted is not None else {
            "format_ok": False, "exact": False, "factuality": 0.0, "detail": "no prediction parsed"}
        record = {
            "turn": i + 1,
            "action": action,
            "valid": valid.get("valid"),
            "is_no_op": noop,
            "parsed": predicted is not None,
            "comparison": comparison,
            "predicted": predicted,
            "actual": {"agent": after["agent"], "view": after["view"]},
        }
        records.append(record)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        tag = "NO-OP" if noop else "act"
        print(f"  [turn {i+1}] {action['verb']:6} {tag:5} parsed={predicted is not None} "
              f"exact={comparison.get('exact')} factuality={comparison.get('factuality')}")

    summary = wm.summarize(records)
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nwrote {out_path} ({len(records)} records)")


if __name__ == "__main__":
    main()
