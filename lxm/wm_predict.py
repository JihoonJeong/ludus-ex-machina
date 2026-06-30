"""Predict-before-act world-model eval (contract v1).

Game-agnostic core: per-game specs live in WM_SPECS — 'blockworld' (the Ludex RFP
harness, format-locked below) and 'mud' (the language world-model field). The
Blockworld functions below ARE the blockworld spec; MUD and future contract-v1
fields use the generic compare_facts + WMSpec at the bottom of this module.

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


def build_predict_prompt(semantic_state: dict, action: dict, instruction: str | None = None) -> str:
    """Assemble the predict-before-act prompt (Ludex pattern + our state).

    `instruction` selects the per-game framing; it defaults to the Blockworld
    instruction so existing Blockworld callers are unchanged.
    """
    return (
        (instruction if instruction is not None else PREDICT_INSTRUCTION)
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


# ── Generic, game-agnostic world-model layer ────────────────────────────────
# Everything above is the Blockworld spec (format-locked with Ludex). MUD — and
# any future field whose build_semantic_state emits contract_version 1 — plugs in
# here via a WMSpec: a per-game predict instruction, the scored top-level keys,
# and a comparator. extract_prediction() and summarize() are shared as-is.

MUD_PREDICT_INSTRUCTION = (
    "MUD WORLD MODEL — predict the agent-local next state.\n"
    "Given the CURRENT semantic state (JSON) and an ACTION, predict the EXACT "
    "next semantic state.\n"
    "Rules:\n"
    "- Preserve the state format exactly (same keys/shape).\n"
    "- Change ONLY what the action changes; keep everything else identical.\n"
    "- Invalid / blocked actions are NO-OPs → return the state unchanged "
    "(locked exit, empty hand, absent or hidden target, missing key, "
    "already-open container).\n"
    "- The verb is authoritative: go/look/examine/read/take/drop/open/close/"
    "unlock/use/talk/give/search/wait.\n"
    "- agent.inventory and room.objects hold the SAME object descriptors "
    "({id, name, takeable, ...}). 'take' moves an object's descriptor from "
    "room.objects into agent.inventory unchanged; 'drop' is the reverse.\n"
    "- 'open' sets a container open=true; 'unlock' clears locked only if you hold "
    "the key. 'use'/'search'/'give' may set flags, reveal hidden objects, or "
    "change object state per the world's own logic.\n"
    "- 'go' through a valid UNLOCKED exit replaces 'room' with the destination "
    "room's scope (room.id = the exit's 'to'); a blocked 'go' is a NO-OP.\n"
    "- look/examine/read/talk and waiting do NOT change the scored state.\n"
    "- 'events' and 'turn' are NOT scored — you may omit or approximate them.\n"
    "Think briefly, then output ONLY:\n"
    "<predicted_observation>{the next semantic_state JSON}</predicted_observation>"
)


def compare_facts(predicted: dict, actual: dict, scored_keys) -> dict:
    """Generic per-fact comparison over selected top-level keys (contract v1).

    Each scored key whose value is a dict is expanded one level into sub-facts
    (e.g. agent.location, room.exits, flags.<name>); other values compare as a
    single fact. Facts compare by value (deep equality), so equivalent
    serializations score equal. Returns format_ok / exact / factuality /
    mismatches — the game-agnostic analogue of compare_semantic (which stays
    Blockworld-bespoke for its set-valued cells).
    """
    if not isinstance(predicted, dict):
        return {"format_ok": False, "exact": False, "factuality": 0.0,
                "detail": "prediction is not a JSON object"}
    format_ok = all(k in predicted for k in scored_keys)
    checks: list[tuple[str, bool]] = []
    mismatches: dict = {}
    for k in scored_keys:
        pv, av = predicted.get(k), actual.get(k)
        if isinstance(av, dict) or isinstance(pv, dict):
            pd = pv if isinstance(pv, dict) else {}
            ad = av if isinstance(av, dict) else {}
            for sk in sorted(set(ad) | set(pd), key=str):
                ok = pd.get(sk) == ad.get(sk)
                checks.append((f"{k}.{sk}", ok))
                if not ok:
                    mismatches[f"{k}.{sk}"] = {"predicted": pd.get(sk), "actual": ad.get(sk)}
        else:
            ok = pv == av
            checks.append((k, ok))
            if not ok:
                mismatches[k] = {"predicted": pv, "actual": av}
    n_ok = sum(1 for _, ok in checks if ok)
    factuality = n_ok / len(checks) if checks else 0.0
    return {
        "format_ok": format_ok,
        "exact": format_ok and all(ok for _, ok in checks),
        "factuality": round(factuality, 3),
        "mismatches": mismatches,
    }


class WMSpec:
    """Per-game world-model eval spec: predict framing + scored projection +
    comparator. Lets the harness score any contract-v1 field uniformly."""

    def __init__(self, game, instruction, scored_keys, comparator):
        self.game = game
        self.instruction = instruction
        self.scored_keys = tuple(scored_keys)
        self._comparator = comparator

    def build_prompt(self, semantic_state: dict, action: dict) -> str:
        return build_predict_prompt(semantic_state, action, self.instruction)

    def scored(self, state: dict) -> dict:
        """The scored projection of a semantic state (drops turn/events/meta)."""
        return {k: (state or {}).get(k) for k in self.scored_keys}

    def is_no_op(self, before: dict, after: dict) -> bool:
        return self.scored(before) == self.scored(after)

    def compare(self, predicted: dict, actual: dict) -> dict:
        return self._comparator(predicted, actual, self.scored_keys)


# Blockworld keeps its bespoke comparator (set-valued cells, format-locked); the
# registry just adapts its 2-arg signature to the (pred, actual, keys) protocol.
WM_SPECS = {
    "blockworld": WMSpec("blockworld", PREDICT_INSTRUCTION, ("agent", "view"),
                         lambda p, a, _keys: compare_semantic(p, a)),
    "mud": WMSpec("mud", MUD_PREDICT_INSTRUCTION, ("agent", "room", "flags"),
                  compare_facts),
}


def get_wm_spec(game: str) -> "WMSpec":
    if game not in WM_SPECS:
        raise ValueError(f"no world-model spec for game {game!r} (have: {sorted(WM_SPECS)})")
    return WM_SPECS[game]
