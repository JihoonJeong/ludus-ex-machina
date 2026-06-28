"""Blockworld predict-before-act world-model eval (Ludex RFP, contract v1).

Distinct from `lxm/world_model.py` (that one exports (state, action, reward)
traces for the physis RL organ). THIS module scores a brain's NEXT-STATE
PREDICTION: given an agent-local semantic state
(`BlockworldGame.build_semantic_state`) + an action, the brain predicts the next
semantic state; we apply the real action and compare on `agent` + `view`.

Eval-only / spectator: predictions are NEVER fed back into a player's move — this
scores world-model competence, it does not influence play.

Format-lock decisions reflected here (cody_to_lxm_blockworld_format_lock_20260628):
- agent-local, absolute coords (§4)
- terrain = natural unplaced floor census; cells = feature + placed (§1, §5)
- events excluded from scoring (§2)
- envelope: brain emits <predicted_observation>{JSON}</predicted_observation>;
  we read the JSON as the predicted next semantic state (§3)
- no-op fidelity is weighted in the summary (Ludex's headline test)
"""

from __future__ import annotations

import json
import re

# Ludex-specified prompt pattern (§3). Only the *input* is our semantic state.
PREDICT_INSTRUCTION = (
    "BLOCKWORLD WORLD MODEL — predict the agent-local next state.\n"
    "Given the CURRENT semantic state (JSON) and an ACTION, predict the EXACT "
    "next semantic state.\n"
    "Rules:\n"
    "- Preserve the state format exactly (same keys/shape).\n"
    "- Change ONLY what the action changes; keep everything else identical.\n"
    "- Invalid / blocked actions are NO-OPs → return the state unchanged "
    "(e.g. move into a solid block, place with an empty hand, pick with a full "
    "inventory).\n"
    "- The verb is authoritative: move/break/place/pick/drop/craft/look/say/"
    "wait/interact.\n"
    "- view.terrain = {block: count} census of NATURAL unplaced floor only; "
    "agent-placed and feature blocks live in view.cells. Placing a block does "
    "NOT change the terrain census.\n"
    "Think briefly, then output ONLY:\n"
    "<predicted_observation>{the next semantic_state JSON}</predicted_observation>"
)


def build_predict_prompt(semantic_state: dict, action: dict) -> str:
    """Assemble the predict-before-act prompt (Ludex pattern + our state)."""
    return (
        PREDICT_INSTRUCTION
        + "\n\nCURRENT STATE:\n" + json.dumps(semantic_state, ensure_ascii=False)
        + "\n\nACTION:\n" + json.dumps(action, ensure_ascii=False)
    )


_TAG = re.compile(r"<predicted_observation>\s*(\{.*\})\s*</predicted_observation>", re.S)


def extract_prediction(text: str) -> dict | None:
    """Parse the brain's <predicted_observation>{JSON}</predicted_observation>.

    Falls back to the outermost {...} blob if the tag is missing. Returns None
    if no parseable JSON object is found.
    """
    if not text:
        return None
    m = _TAG.search(text)
    raw = m.group(1) if m else None
    if raw is None:
        a, b = text.find("{"), text.rfind("}")
        if a == -1 or b == -1 or b < a:
            return None
        raw = text[a:b + 1]
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _cells_set(view: dict) -> set:
    return {
        (c.get("x"), c.get("y"), c.get("z"), c.get("block"), bool(c.get("placed")))
        for c in (view or {}).get("cells", []) if isinstance(c, dict)
    }


def _scored(state: dict) -> dict:
    """The scored projection: agent + view (drops events / turn / meta)."""
    return {"agent": state.get("agent"), "view": state.get("view")}


def is_no_op(before: dict, after: dict) -> bool:
    """Did the action leave the scored state (agent + view) unchanged?"""
    return _scored(before) == _scored(after)


def compare_semantic(predicted: dict, actual: dict) -> dict:
    """Semantic comparison on agent + view (events excluded). Factuality-focused.

    Compares facts, not strings — equivalent serializations score equal. Returns
    per-fact correctness, an overall factuality fraction, and an `exact` flag.
    """
    if not isinstance(predicted, dict):
        return {"format_ok": False, "exact": False, "factuality": 0.0,
                "detail": "prediction is not a JSON object"}

    pa, aa = predicted.get("agent") or {}, actual.get("agent") or {}
    pv, av = predicted.get("view") or {}, actual.get("view") or {}
    format_ok = bool(predicted.get("agent") and predicted.get("view"))

    checks: list[tuple[str, bool]] = []
    agent_mismatches: dict = {}
    for f in ("x", "y", "z", "facing", "inventory", "above", "below"):
        ok = pa.get(f) == aa.get(f)
        checks.append((f"agent.{f}", ok))
        if not ok:
            agent_mismatches[f] = {"predicted": pa.get(f), "actual": aa.get(f)}

    terrain_ok = (pv.get("terrain") or {}) == (av.get("terrain") or {})
    checks.append(("view.terrain", terrain_ok))

    pcells, acells = _cells_set(pv), _cells_set(av)
    cells_ok = pcells == acells
    checks.append(("view.cells", cells_ok))

    n_ok = sum(1 for _, ok in checks if ok)
    factuality = n_ok / len(checks) if checks else 0.0
    return {
        "format_ok": format_ok,
        "exact": format_ok and all(ok for _, ok in checks),
        "factuality": round(factuality, 3),
        "agent_mismatches": agent_mismatches,
        "terrain_ok": terrain_ok,
        "cells_ok": cells_ok,
        "cells_missing": [list(c) for c in sorted(acells - pcells)],  # in actual, not predicted
        "cells_extra": [list(c) for c in sorted(pcells - acells)],    # predicted, not actual
    }


def summarize(records: list[dict]) -> dict:
    """Aggregate prediction records into a world-model competence report.

    No-op cases are reported separately AND weighted (Ludex's headline: a model
    that hallucinates an effect on a no-op is the main failure mode).
    """
    n = len(records)
    if not n:
        return {"n": 0}
    exact = [r for r in records if r.get("comparison", {}).get("exact")]
    noop = [r for r in records if r.get("is_no_op")]
    noop_exact = [r for r in noop if r.get("comparison", {}).get("exact")]
    active = [r for r in records if not r.get("is_no_op")]
    active_exact = [r for r in active if r.get("comparison", {}).get("exact")]
    fact = [r.get("comparison", {}).get("factuality", 0.0) for r in records]
    return {
        "n": n,
        "exact": len(exact),
        "exact_rate": round(len(exact) / n, 3),
        "mean_factuality": round(sum(fact) / n, 3),
        "active": {"n": len(active),
                   "exact": len(active_exact),
                   "rate": round(len(active_exact) / len(active), 3) if active else None},
        "no_op": {"n": len(noop),
                  "exact": len(noop_exact),
                  "rate": round(len(noop_exact) / len(noop), 3) if noop else None},
    }
