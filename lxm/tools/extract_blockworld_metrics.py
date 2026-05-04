"""Cross-substrate behavioral metrics extractor for Blockworld matches.

Walks `matches/`, identifies Blockworld matches (by `match_config.game.name`),
and emits one CSV row per match with:

  - identity:    match_id, scenario_id, mode, n_agents
  - models:      a_adapter, a_model, b_adapter, b_model, ...
  - tempo:       turn_count, outcome, summary
  - validity:    accepted, timeouts, refusals, rejections
  - per-agent:   say_count, attached_message_count, mean_msg_len,
                 moves_total, places, breaks, picks, crafts, drops,
                 final_inventory_size
  - substrate:   met / met_at_turn / final_distance        (pure_coord)
                 stag_captured_by / stag_capture_turn / hares_picked  (stag_hunt*)
                 trees_alive / trees_dead / total_apples_picked       (commons_harvest)
                 chase_outcome / chase_captured_at_turn               (predator_prey)
                 pd_encounters / pd_cc / pd_cd / pd_dc / pd_dd        (prisoners_dilemma)
                 selfish_picked / public_picked                       (externality_mushrooms)
                 navigate_reached / navigate_at_turn                  (single_navigate)

Usage:
    python -m lxm.tools.extract_blockworld_metrics \
        [--matches-dir matches] [--output blockworld_metrics.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MATCHES = PROJECT_ROOT / "matches"
DEFAULT_OUTPUT = PROJECT_ROOT / "blockworld_metrics.csv"

# Wide-format max — paper analysis is overwhelmingly 2-agent. We still
# capture ≤4 in case of multi-agent expansions; columns beyond present
# agents are blank.
MAX_AGENTS = 4
AGENT_SLOTS = ["a", "b", "c", "d"][:MAX_AGENTS]


def _safe_load(p: Path) -> dict | list | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _model_label(agent_cfg: dict) -> str:
    return f"{agent_cfg.get('adapter', '?')}:{agent_cfg.get('model', '?')}"


def _parse_say_event(text: str) -> tuple[str, str] | None:
    m = re.match(r"^(\w+) says: (.+)$", text)
    if not m:
        return None
    return m.group(1), m.group(2)


def _per_agent_zero(slots: list[str]) -> dict[str, dict[str, Any]]:
    return {s: {
        "say_count": 0,
        "attached_message_count": 0,
        "msg_len_total": 0,
        "moves_total": 0,
        "places": 0,
        "breaks": 0,
        "picks": 0,
        "crafts": 0,
        "drops": 0,
    } for s in slots}


def _substrate_metrics(state: dict, log: list, mode: str) -> dict[str, Any]:
    """Mode-specific metrics derived from final state.json or last log entry."""
    out = {}
    ctx = state.get("game", {}).get("context", {})
    cur = state.get("game", {}).get("current", {})

    if mode == "pure_coord":
        meet = cur.get("meet") or {}
        out["pc_met"] = bool(meet.get("met"))
        out["pc_met_at_turn"] = meet.get("at_turn")
        # Final manhattan distance (between first two agents).
        agents = cur.get("agents", {})
        ids = list(agents.keys())[:2]
        if len(ids) == 2:
            a, b = agents[ids[0]], agents[ids[1]]
            out["pc_final_manhattan"] = abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]) + abs(a["z"] - b["z"])

    elif mode in ("stag_hunt", "stag_hunt_repeated"):
        cap_log = ctx.get("stag_capture_log") or []
        out["sh_stag_captures"] = len(cap_log)
        if cap_log:
            first = cap_log[0]
            out["sh_first_stag_capturer"] = ",".join(first.get("captured_by", [])) if isinstance(first.get("captured_by"), list) else first.get("captured_by")
            out["sh_first_stag_turn"] = first.get("turn")
        hare_log = ctx.get("hare_pickup_log") or []
        out["sh_hares_picked_total"] = len(hare_log)

    elif mode == "commons_harvest":
        trees = cur.get("trees") or []
        out["ch_trees_alive"] = sum(1 for t in trees if not t.get("dead"))
        out["ch_trees_dead"] = sum(1 for t in trees if t.get("dead"))
        # Apple pickups via inventory in final agents.
        out["ch_apples_total_picked"] = sum(
            (ag.get("inventory") or {}).get("apple", 0)
            for ag in cur.get("agents", {}).values()
        )

    elif mode == "predator_prey":
        chase = cur.get("chase") or {}
        out["pp_captured"] = bool(chase.get("captured"))
        out["pp_captured_at_turn"] = chase.get("captured_at_turn")
        out["pp_captor"] = chase.get("captor")
        out["pp_victim"] = chase.get("victim")

    elif mode == "prisoners_dilemma":
        pd = cur.get("pd") or {}
        log_entries = pd.get("encounter_log") or []
        tally = {"CC": 0, "CD": 0, "DC": 0, "DD": 0}
        for e in log_entries:
            o = e.get("outcome")
            if o in tally:
                tally[o] += 1
        out["pd_encounters"] = len(log_entries)
        for k, v in tally.items():
            out[f"pd_{k}"] = v

    elif mode == "externality_mushrooms":
        # Tally pickup events from log (engine emits "a picked selfish_mushroom" etc).
        sel = pub = 0
        for entry in log:
            for e in (entry.get("post_move_state", {}) or {}).get("last_events", []) or []:
                s = str(e).lower()
                if "selfish_mushroom" in s and "picked" in s:
                    sel += 1
                elif "public_mushroom" in s and "picked" in s:
                    pub += 1
        out["em_selfish_picked"] = sel
        out["em_public_picked"] = pub

    elif mode == "single_navigate":
        nav = cur.get("navigate") or {}
        out["sn_reached"] = bool(nav.get("reached"))
        out["sn_at_turn"] = nav.get("at_turn")
        out["sn_target"] = nav.get("target_landmark_name")

    elif mode == "sandbox":
        out.update(_sandbox_metrics(state, log))

    return out


def _connected_components(cells: set, nb_offsets: list[tuple[int, int, int]]) -> list[set]:
    """Return list of connected components in `cells` under given neighbour offsets.

    Iterative BFS to avoid recursion-depth issues on large clusters.
    """
    components = []
    unvisited = set(cells)
    while unvisited:
        seed = unvisited.pop()
        comp = {seed}
        frontier = [seed]
        while frontier:
            (x, y, z) = frontier.pop()
            for (dxn, dyn, dzn) in nb_offsets:
                n = (x + dxn, y + dyn, z + dzn)
                if n in unvisited:
                    unvisited.remove(n)
                    comp.add(n)
                    frontier.append(n)
        components.append(comp)
    return components


def _shannon_entropy(counts: dict[Any, int]) -> float:
    """Bits of Shannon entropy. Returns 0 for ≤1 unique values or empty input."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    import math
    h = 0.0
    for n in counts.values():
        if n <= 0:
            continue
        p = n / total
        h -= p * math.log2(p)
    return round(h, 3)


def _sandbox_metrics(state: dict, log: list) -> dict[str, Any]:
    """Behavioral signature metrics for `mode: sandbox` matches.

    All keys prefixed `sb_`. Computed from the log (move-by-move) and the
    final state (placed cells, final inventory).

    Aggregates across ALL agents in the match. (Sandbox scenarios in this
    project are single-agent so far, but the math generalises.)
    """
    out = {}
    cur = state.get("game", {}).get("current", {})
    world = cur.get("world") or {}
    layers = world.get("layers")
    placed_grid = world.get("placed")
    dims = world.get("dimensions") or {}
    agents = cur.get("agents") or {}

    # ── spatial: visited cells, radius, z range, move dir entropy ───────
    visited: set[tuple[int, int, int]] = set()
    starts: dict[str, tuple[int, int, int]] = {}
    move_dirs: dict[str, int] = {}
    for entry in log:
        post = entry.get("post_move_state") or {}
        pos_agents = post.get("agents") or {}
        for aid, a in pos_agents.items():
            cell = (a.get("x"), a.get("y"), a.get("z"))
            if None in cell:
                continue
            visited.add(cell)
            starts.setdefault(aid, cell)
        if entry.get("result") == "accepted":
            move = (entry.get("envelope") or {}).get("move") or {}
            if move.get("verb") == "move":
                d = move.get("direction") or "?"
                move_dirs[d] = move_dirs.get(d, 0) + 1

    out["sb_unique_cells_visited"] = len(visited)
    out["sb_move_dir_entropy_bits"] = _shannon_entropy(move_dirs)
    if visited and starts:
        # Max manhattan radius any agent reached from its start cell.
        max_r = 0
        for aid, start in starts.items():
            for c in visited:
                r = abs(c[0] - start[0]) + abs(c[1] - start[1]) + abs(c[2] - start[2])
                if r > max_r:
                    max_r = r
        out["sb_max_radius_from_start"] = max_r
    if visited:
        zs = [c[2] for c in visited]
        out["sb_z_range_visited"] = (max(zs) - min(zs)) if zs else 0

    # ── construction: placed cells, types, connectivity ────────────────
    placed_cells: list[tuple[int, int, int, int]] = []  # (x,y,z,block_id)
    if layers and placed_grid and dims:
        dx, dy, dz = dims.get("x", 0), dims.get("y", 0), dims.get("z", 0)
        for z in range(dz):
            for y in range(dy):
                for x in range(dx):
                    try:
                        if placed_grid[z][y][x] == 1:
                            placed_cells.append((x, y, z, layers[z][y][x]))
                    except (IndexError, TypeError):
                        continue
    out["sb_blocks_placed_final"] = len(placed_cells)

    # Block-type entropy of placed cells.
    block_type_counts: dict[int, int] = {}
    for (_, _, _, bid) in placed_cells:
        block_type_counts[bid] = block_type_counts.get(bid, 0) + 1
    out["sb_placed_type_entropy_bits"] = _shannon_entropy(block_type_counts)
    out["sb_placed_unique_types"] = len(block_type_counts)

    # Connectivity: fraction of placed cells with ≥1 manhattan-3D neighbour
    # also in the placed set. High values → coherent structure; low → scattered.
    placed_set = {(x, y, z) for (x, y, z, _) in placed_cells}
    nb_offsets = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    if placed_set:
        connected = sum(
            1 for (x, y, z) in placed_set
            if any((x + dxn, y + dyn, z + dzn) in placed_set for (dxn, dyn, dzn) in nb_offsets)
        )
        out["sb_placed_connectivity"] = round(connected / len(placed_set), 3)
    else:
        out["sb_placed_connectivity"] = 0.0

    # ── cluster decomposition (E core: structure quality) ─────────────
    # Connected components via 6-connectivity. Each component is a
    # contiguous build; multiple disjoint components signal scattered work.
    components = _connected_components(placed_set, nb_offsets)
    out["sb_cluster_count"] = len(components)
    if components:
        # Largest cluster's size, vertical extent, dominant-block share,
        # and compactness (cells / bounding-box volume).
        largest = max(components, key=len)
        out["sb_cluster_max_size"] = len(largest)
        zs = [c[2] for c in largest]
        xs = [c[0] for c in largest]
        ys = [c[1] for c in largest]
        out["sb_cluster_max_vertical"] = (max(zs) - min(zs)) if zs else 0
        bbox_volume = (
            (max(xs) - min(xs) + 1)
            * (max(ys) - min(ys) + 1)
            * (max(zs) - min(zs) + 1)
        )
        out["sb_cluster_compactness"] = round(len(largest) / bbox_volume, 3) if bbox_volume else 0.0
        # Dominant block-type share within the largest cluster.
        cell_block = {(x, y, z): bid for (x, y, z, bid) in placed_cells}
        block_in_largest: dict[int, int] = {}
        for c in largest:
            bid = cell_block.get(c)
            if bid is not None:
                block_in_largest[bid] = block_in_largest.get(bid, 0) + 1
        if block_in_largest:
            dominant_count = max(block_in_largest.values())
            out["sb_cluster_dominant_block_share"] = round(dominant_count / len(largest), 3)
        else:
            out["sb_cluster_dominant_block_share"] = 0.0
    else:
        out["sb_cluster_max_size"] = 0
        out["sb_cluster_max_vertical"] = 0
        out["sb_cluster_compactness"] = 0.0
        out["sb_cluster_dominant_block_share"] = 0.0

    # ── tempo: active turns, idle streaks, early-late balance ──────────
    verbs_per_turn: list[str] = []
    for entry in log:
        if entry.get("result") != "accepted":
            verbs_per_turn.append("invalid")
            continue
        move = (entry.get("envelope") or {}).get("move") or {}
        verbs_per_turn.append(move.get("verb") or "?")

    active = [v for v in verbs_per_turn if v not in ("wait", "invalid")]
    out["sb_active_turns"] = len(active)
    out["sb_total_log_turns"] = len(verbs_per_turn)

    # Longest consecutive idle (wait or invalid).
    max_streak = streak = 0
    for v in verbs_per_turn:
        if v in ("wait", "invalid"):
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    out["sb_idle_streak_max"] = max_streak

    # Early-late activity balance: fraction of active turns in first half.
    if active and verbs_per_turn:
        midpoint = len(verbs_per_turn) // 2
        early_active = sum(
            1 for i, v in enumerate(verbs_per_turn[:midpoint])
            if v not in ("wait", "invalid")
        )
        out["sb_early_active_share"] = round(early_active / len(active), 3) if active else 0.0
    else:
        out["sb_early_active_share"] = 0.0

    # ── verb mix entropy ───────────────────────────────────────────────
    verb_counts: dict[str, int] = {}
    for v in verbs_per_turn:
        if v == "invalid":
            continue
        verb_counts[v] = verb_counts.get(v, 0) + 1
    out["sb_verb_entropy_bits"] = _shannon_entropy(verb_counts)
    out["sb_verb_unique"] = len(verb_counts)

    # ── final inventory diversity (across all agents) ──────────────────
    inv_types: set[str] = set()
    inv_total = 0
    for a in agents.values():
        for k, v in (a.get("inventory") or {}).items():
            inv_types.add(k)
            inv_total += int(v or 0)
    out["sb_final_inventory_unique_types"] = len(inv_types)
    out["sb_final_inventory_total"] = inv_total

    # ── intent capture (paper 2 V1 — Claim C') ─────────────────────────
    ctx = state.get("game", {}).get("context", {})
    intent_log = ctx.get("intent_log") or []
    out["sb_intent_count"] = len(intent_log)
    out["sb_intent_total_chars"] = sum(len(e.get("text") or "") for e in intent_log)
    if intent_log:
        out["sb_intent_t0_text"] = (intent_log[0].get("text") or "").replace("\n", " ")[:500]
        out["sb_intent_final_text"] = (intent_log[-1].get("text") or "").replace("\n", " ")[:500]
    else:
        out["sb_intent_t0_text"] = ""
        out["sb_intent_final_text"] = ""
    # Intent compliance: declared at expected turns? (paper 2 method observation)
    expected = ctx.get("intent_capture_turns") or []
    final_t = ctx.get("final_assessment_turn")
    if final_t is not None:
        expected = list(expected) + [final_t]
    declared_turns = {e.get("turn") for e in intent_log}
    out["sb_intent_expected_count"] = len(expected)
    out["sb_intent_compliance"] = (
        round(len(declared_turns & set(expected)) / len(expected), 3) if expected else 0.0
    )

    return out


def extract_one(match_dir: Path) -> dict[str, Any] | None:
    cfg = _safe_load(match_dir / "match_config.json")
    if not cfg:
        return None
    if cfg.get("game", {}).get("name") != "blockworld":
        return None
    state = _safe_load(match_dir / "state.json") or {}
    log = _safe_load(match_dir / "log.json") or []
    result = _safe_load(match_dir / "result.json") or {}

    ctx = state.get("game", {}).get("context", {})
    cur = state.get("game", {}).get("current", {})

    # Agent slots filled positionally.
    agents_cfg = cfg.get("agents", []) or []
    slots = AGENT_SLOTS[:len(agents_cfg)]
    per = _per_agent_zero(slots)
    aid_to_slot = {ac["agent_id"]: slots[i] for i, ac in enumerate(agents_cfg) if i < len(slots)}

    # Walk log for behavioral counts.
    accepted = timeouts = refusals = rejections = 0
    for entry in log:
        res = entry.get("result")
        if res == "accepted":
            accepted += 1
        elif res == "timeout":
            timeouts += 1
        elif res == "refusal":
            refusals += 1
        elif res == "rejected":
            rejections += 1
        # Move-level breakdown (only on accepted moves to avoid double counts).
        if res != "accepted":
            continue
        env = entry.get("envelope") or {}
        move = env.get("move") or {}
        verb = move.get("verb")
        aid = entry.get("agent_id")
        slot = aid_to_slot.get(aid)
        if not slot:
            continue
        rec = per[slot]
        rec["moves_total"] += 1
        if verb == "say":
            rec["say_count"] += 1
            rec["msg_len_total"] += len(str(move.get("message") or ""))
        elif verb in ("place", "break", "pick", "drop", "craft"):
            rec[f"{verb}s"] += 1
        # Attached message on action verb.
        if verb and verb != "say" and isinstance(move.get("message"), str):
            rec["attached_message_count"] += 1
            rec["msg_len_total"] += len(move["message"])

    # Final inventory sizes.
    for aid, slot in aid_to_slot.items():
        ag = cur.get("agents", {}).get(aid) or {}
        per[slot]["final_inventory_size"] = sum((ag.get("inventory") or {}).values())

    # Aggregate row.
    row = {
        "match_id": cfg.get("match_id") or match_dir.name,
        "scenario_id": ctx.get("scenario_id") or "",
        "mode": ctx.get("mode") or "",
        "n_agents": len(agents_cfg),
        "turn_count": cur.get("turn") or 0,
        "outcome": result.get("outcome") or ("running" if not result else ""),
        "summary": (result.get("summary") or "")[:160],
        "accepted": accepted,
        "timeouts": timeouts,
        "refusals": refusals,
        "rejections": rejections,
    }
    for i, ac in enumerate(agents_cfg):
        if i >= len(slots):
            break
        slot = slots[i]
        row[f"{slot}_agent_id"] = ac.get("agent_id")
        row[f"{slot}_adapter"] = ac.get("adapter")
        row[f"{slot}_model"] = ac.get("model")
        row[f"{slot}_label"] = _model_label(ac)
        rec = per[slot]
        for k, v in rec.items():
            if k == "msg_len_total":
                continue
            row[f"{slot}_{k}"] = v
        msg_count = rec["say_count"] + rec["attached_message_count"]
        row[f"{slot}_mean_msg_len"] = round(rec["msg_len_total"] / msg_count, 1) if msg_count else 0
    # Substrate-specific.
    row.update(_substrate_metrics(state, log, ctx.get("mode") or ""))
    return row


def collect_columns(rows: list[dict]) -> list[str]:
    base = [
        "match_id", "scenario_id", "mode", "n_agents", "turn_count",
        "outcome", "summary",
        "accepted", "timeouts", "refusals", "rejections",
    ]
    for slot in AGENT_SLOTS:
        for suffix in [
            "agent_id", "adapter", "model", "label",
            "say_count", "attached_message_count", "mean_msg_len",
            "moves_total", "places", "breaks", "picks", "crafts", "drops",
            "final_inventory_size",
        ]:
            base.append(f"{slot}_{suffix}")
    # Substrate columns — collect from rows dynamically (sorted, prefix groups).
    substrate_keys = set()
    for r in rows:
        for k in r:
            if k not in base and any(k.startswith(p) for p in ("pc_", "sh_", "ch_", "pp_", "pd_", "em_", "sn_", "sb_")):
                substrate_keys.add(k)
    base.extend(sorted(substrate_keys))
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches-dir", type=Path, default=DEFAULT_MATCHES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--filter-mode", type=str, default=None,
                        help="Only include matches whose mode equals this (e.g. pure_coord)")
    parser.add_argument("--filter-scenario", type=str, default=None,
                        help="Only include matches whose scenario_id matches this prefix")
    args = parser.parse_args()

    if not args.matches_dir.exists():
        print(f"matches dir not found: {args.matches_dir}", file=sys.stderr)
        return 1

    rows: list[dict] = []
    skipped = 0
    for match_dir in sorted(args.matches_dir.iterdir()):
        if not match_dir.is_dir():
            continue
        try:
            row = extract_one(match_dir)
        except Exception as ex:
            print(f"  warn: {match_dir.name} extraction failed: {ex}", file=sys.stderr)
            skipped += 1
            continue
        if not row:
            continue
        if args.filter_mode and row.get("mode") != args.filter_mode:
            continue
        if args.filter_scenario and not (row.get("scenario_id") or "").startswith(args.filter_scenario):
            continue
        rows.append(row)

    if not rows:
        print("no Blockworld matches matched.", file=sys.stderr)
        return 1

    columns = collect_columns(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {len(rows)} rows → {args.output}")
    if skipped:
        print(f"  ({skipped} matches skipped due to extraction errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
