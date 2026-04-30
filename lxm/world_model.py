"""Field-indexed world models — trace export reader (D-067 physis substrate).

Reads a completed LxM match's log + result and emits a `(state, action,
reward)` trace per the field's `world_schema.json`. The trace is the
contract by which Ludex creatures' physis organ ingests LxM match
outcomes for in-context RL.

Architecture context: `drafts/lxm_to_ray_field_indexed_world_models_
reply_20260426.md` (LxM-side) +
`drafts/ray_to_lxm_field_indexed_world_models_response_20260426.md`
(Ludex-side response). Per-game schema lives at
`games/<game>/world_schema.json`.

Skeleton scope (Day 1 PM):
  - Schema load + ground-truth state emit
  - Action + events emit
  - Terminal reward (from result.json) on last line
  - File-based handoff at `traces/<game>/<match_id>/trace.jsonl`

Deferred (Day 2+):
  - Agent-views via dynamic import of the schema-declared filter fn
  - Self-eval channel ingestion (when matches start logging it)
  - Intermediate reward derivation (per-quest deltas computed inline)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_TRACE_ROOT = PROJECT_ROOT / "traces"


# ── schema loading ─────────────────────────────────────────────────────────


def load_schema(game: str, *, project_root: Path | None = None) -> dict:
    """Load `games/<game>/world_schema.json`. Raise FileNotFoundError if
    the game has no schema yet — caller should treat that as
    "physis-not-yet-supported"."""
    root = project_root or PROJECT_ROOT
    path = root / "games" / game / "world_schema.json"
    if not path.exists():
        raise FileNotFoundError(
            f"no world_schema.json for game {game!r} at {path}. "
            f"Add a schema before running physis on this field."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def schema_for_match(match_id: str, *, project_root: Path | None = None) -> tuple[str, dict]:
    """Look at the match's config to derive the game name, then load
    that game's schema. Returns (game_name, schema)."""
    root = project_root or PROJECT_ROOT
    config_path = root / "matches" / match_id / "match_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"no match_config.json at {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    game = (config.get("game") or {}).get("name")
    if not game:
        raise ValueError(f"match {match_id!r} config has no game.name")
    return game, load_schema(game, project_root=root)


# ── trace emit ─────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _project(d: dict, keys: Iterable[str]) -> dict:
    """Return a new dict with only the listed keys (preserving missing)."""
    return {k: d.get(k) for k in keys}


def _agent_summary(config: dict) -> list[dict]:
    """Pull a public-shape summary of each participant from match_config.
    Roles / models / display names go in; secrets stay out."""
    agents = config.get("agents") or []
    out = []
    for a in agents:
        out.append({
            "agent_id": a.get("agent_id"),
            "display_name": a.get("display_name", a.get("agent_id")),
            "adapter": a.get("adapter"),
            "model": a.get("model"),
            "seat": a.get("seat"),
        })
    return out


# ── per-game extractors (D-067 Phase B v3) ─────────────────────────────────
#
# Each LxM game with a world_schema.json gets a signature extractor + a
# reward_per_turn deriver. Dispatched by schema["field"] in
# emit_trace_lines. Adding a new game = add two functions + a dispatch
# entry; no changes to the emit core.

def _band_rejection_streak(n: int) -> str:
    if n <= 0:
        return "none"
    if n <= 2:
        return "low"
    return "high"


def _avalon_signature(
    post_state: dict,
    post_context: dict,
    active_agent_id: str,
) -> dict:
    """State-signature for hint-precondition retrieval (Q1 of
    drafts/lxm_to_ray_d067_v3_avalon_replan_20260428.md). Active
    agent's perspective only.
    """
    players = post_state.get("players") or {}
    me = players.get(active_agent_id) or {}
    my_role = me.get("role")
    evil_players = post_state.get("evil_players") or []
    quest_sizes = post_state.get("quest_sizes") or []
    quest_round = post_state.get("quest_number") or 1
    team_size = quest_sizes[quest_round - 1] if 1 <= quest_round <= len(quest_sizes) else None

    # Evil sees the full evil roster; good knows nothing of it. Carry the
    # creature's actual epistemic position rather than the ground truth.
    if my_role == "evil":
        evil_revealed_count = len(evil_players)
    else:
        evil_revealed_count = None

    return {
        "phase": post_state.get("phase"),
        "my_role": my_role,
        "quest_round": quest_round,
        "rejection_streak_band": _band_rejection_streak(post_state.get("consecutive_rejections") or 0),
        "good_wins": post_context.get("good_wins") or 0,
        "evil_wins": post_context.get("evil_wins") or 0,
        "team_size": team_size,
        "is_leader": post_state.get("leader") == active_agent_id,
        "evil_revealed_count": evil_revealed_count,
    }


def _avalon_reward_per_turn(
    prev_post_state: dict,
    post_state: dict,
    prev_post_context: dict,
    post_context: dict,
    active_agent_id: str,
    is_final_turn: bool,
    final_scores: dict | None,
) -> float:
    """Per-turn scalar reward for the active agent. Sparse but
    informative:
      ±1.0 on final turn from result.scores
      ±0.5 on a quest just resolved (good_wins or evil_wins increased)
      -0.1 on a freshly-incremented rejection streak

    See §Q2 of `drafts/lxm_to_ray_d067_v3_avalon_replan_20260428.md`.
    """
    players = post_state.get("players") or {}
    me_role = (players.get(active_agent_id) or {}).get("role")
    if me_role not in ("good", "evil"):
        return 0.0
    my_faction = me_role  # one-of {good, evil}

    reward = 0.0

    # Quest just resolved → ±0.5 for the relevant faction.
    prev_good = (prev_post_context or {}).get("good_wins") or 0
    prev_evil = (prev_post_context or {}).get("evil_wins") or 0
    cur_good = post_context.get("good_wins") or 0
    cur_evil = post_context.get("evil_wins") or 0
    good_delta = cur_good - prev_good
    evil_delta = cur_evil - prev_evil
    if good_delta > 0:
        reward += 0.5 if my_faction == "good" else -0.5
    if evil_delta > 0:
        reward += 0.5 if my_faction == "evil" else -0.5

    # Rejection streak just incremented → -0.1 to whoever was the
    # active agent on the rejected proposal (and to everyone reading
    # this signal — it's a coordination cost shared by the field, but
    # we attribute to the active agent for trace simplicity).
    prev_streak = (prev_post_state or {}).get("consecutive_rejections") or 0
    cur_streak = post_state.get("consecutive_rejections") or 0
    if cur_streak > prev_streak:
        reward += -0.1

    # Terminal — ±1.0 from final scores when this is the last turn.
    if is_final_turn and final_scores:
        s = final_scores.get(active_agent_id)
        if isinstance(s, (int, float)):
            # final_scores are 1.0 winner / 0.0 loser already.
            reward += (1.0 if s >= 1.0 else -1.0)

    return reward


def _band_corners(board: list) -> str:
    if not board or len(board) != 3:
        return "none"
    corners = [board[0][0], board[0][2], board[2][0], board[2][2]]
    n = sum(1 for c in corners if c is not None)
    if n == 0:
        return "none"
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    return "three_or_four"


def _longest_line_for(board: list, mark: str) -> str:
    """Categorize longest line of `mark` into none/single/double.
    none = no line, single = exactly 2-in-a-row + open, double = 3-in-a-row.
    Used for opponent_threat / my_threat in TicTacToe state_signature.
    """
    if not board or not mark:
        return "none"
    lines = []
    for r in range(3):
        lines.append([board[r][0], board[r][1], board[r][2]])
    for c in range(3):
        lines.append([board[0][c], board[1][c], board[2][c]])
    lines.append([board[0][0], board[1][1], board[2][2]])
    lines.append([board[0][2], board[1][1], board[2][0]])

    longest = 0
    for line in lines:
        cnt_mark = sum(1 for v in line if v == mark)
        cnt_other = sum(1 for v in line if v is not None and v != mark)
        if cnt_other == 0 and cnt_mark > longest:
            longest = cnt_mark

    if longest >= 3:
        return "double"
    if longest == 2:
        return "single"
    return "none"


def _tictactoe_signature(
    post_state: dict,
    post_context: dict,
    active_agent_id: str,
) -> dict:
    """State-signature for TicTacToe Phase C negative-control bracket.
    Solved game; signature exposes the small categorical features hints
    could reasonably condition on (move number, center status, corner
    occupancy band, threat presence per side).
    """
    board = post_state.get("board") or [[None]*3, [None]*3, [None]*3]
    marks = post_state.get("marks") or {}
    my_mark = marks.get(active_agent_id)
    opp_mark = next((m for aid, m in marks.items() if aid != active_agent_id), None)
    move_count = post_context.get("move_count") or 0

    return {
        "my_mark": my_mark,
        "move_number": move_count + 1,
        "center_open": board[1][1] is None,
        "corners_taken_band": _band_corners(board),
        "opponent_threat": _longest_line_for(board, opp_mark) if opp_mark else "none",
        "my_threat": _longest_line_for(board, my_mark) if my_mark else "none",
    }


def _tictactoe_reward_per_turn(
    prev_post_state: dict,
    post_state: dict,
    prev_post_context: dict,
    post_context: dict,
    active_agent_id: str,
    is_final_turn: bool,
    final_scores: dict | None,
) -> float:
    """Terminal-only reward — Phase C negative-control hypothesis is
    that the absence of intermediate signal is part of why physis
    is expected to produce null/trivial output on this field.
    """
    if is_final_turn and final_scores:
        s = final_scores.get(active_agent_id)
        if isinstance(s, (int, float)):
            if s >= 1.0:
                return 1.0
            if s <= 0.0:
                return -1.0
            return 0.0  # draw
    return 0.0


def _band_round(r: int) -> str:
    if r <= 3:
        return "early"
    if r <= 7:
        return "mid"
    return "late"


def _band_count(n: int) -> str:
    if n <= 0:
        return "none"
    if n <= 2:
        return "low"
    return "high"


def _trustgame_signature(
    post_state: dict,
    post_context: dict,
    active_agent_id: str,
) -> dict:
    """State-signature for TrustGame Phase C C1 cross-field transfer
    probe. Categoricals chosen to map onto Avalon's rhetorical-hint
    space (trust-build, betrayal patterns) so cross-field hint
    structures can be compared.
    """
    history = post_context.get("history") or []
    scores = post_state.get("scores") or {}
    round_no = post_state.get("round") or 1

    # Identify opponent
    others = [aid for aid in scores.keys() if aid != active_agent_id]
    opp_id = others[0] if others else None

    # Opponent's last action
    opponent_last = "none"
    if history:
        last = history[-1]
        if opp_id and last.get(opp_id) in ("cooperate", "defect"):
            opponent_last = last[opp_id]

    # Streaks and tallies from history
    mutual_coop_streak = 0
    for r in reversed(history):
        if (r.get(active_agent_id) == "cooperate" and
                opp_id and r.get(opp_id) == "cooperate"):
            mutual_coop_streak += 1
        else:
            break

    betrayals_against_me = 0
    betrayals_by_me = 0
    for r in history:
        my = r.get(active_agent_id)
        op = r.get(opp_id) if opp_id else None
        if my == "cooperate" and op == "defect":
            betrayals_against_me += 1
        elif my == "defect" and op == "cooperate":
            betrayals_by_me += 1

    my_score = scores.get(active_agent_id, 0)
    opp_score = scores.get(opp_id, 0) if opp_id else 0
    if my_score > opp_score:
        score_position = "ahead"
    elif my_score < opp_score:
        score_position = "behind"
    else:
        score_position = "even"

    return {
        "round_band": _band_round(round_no),
        "opponent_last": opponent_last,
        "mutual_cooperate_streak_band": _band_count(mutual_coop_streak),
        "betrayals_against_me_band": _band_count(betrayals_against_me),
        "betrayals_by_me_band": _band_count(betrayals_by_me),
        "score_position": score_position,
    }


def _trustgame_reward_per_turn(
    prev_post_state: dict,
    post_state: dict,
    prev_post_context: dict,
    post_context: dict,
    active_agent_id: str,
    is_final_turn: bool,
    final_scores: dict | None,
) -> float:
    """Per-round dense payoff signal — score delta since last turn,
    normalized by the max single-round payoff (5) so values fall in
    [-1, 1]. Terminal final reward layered on top via final_scores.
    """
    prev_scores = (prev_post_state or {}).get("scores") or {}
    cur_scores = post_state.get("scores") or {}
    delta = (cur_scores.get(active_agent_id, 0) -
             prev_scores.get(active_agent_id, 0))
    reward = delta / 5.0  # max single-round payoff

    if is_final_turn and final_scores:
        s = final_scores.get(active_agent_id)
        if isinstance(s, (int, float)):
            # Add small terminal bonus/penalty in addition to round payoff.
            reward += (0.5 if s >= 1.0 else -0.5)

    return reward


_SIGNATURE_EXTRACTORS = {
    "lxm/avalon": _avalon_signature,
    "lxm/tictactoe": _tictactoe_signature,
    "lxm/trustgame": _trustgame_signature,
}

_REWARD_DERIVERS = {
    "lxm/avalon": _avalon_reward_per_turn,
    "lxm/tictactoe": _tictactoe_reward_per_turn,
    "lxm/trustgame": _trustgame_reward_per_turn,
}


def signature_extractor_for(field: str):
    return _SIGNATURE_EXTRACTORS.get(field)


def reward_deriver_for(field: str):
    return _REWARD_DERIVERS.get(field)


# ── physis ingest mapping (Day 3 PM, Mac Ludex Cody coordination) ──────────


# Accepted kwargs of `ludex.blocks.physis.PhysisBlock.handle_step` per
# the Phase B v3 ship. Keep this list in lockstep with the upstream
# signature; extra kwargs raise TypeError because the function uses
# `*,` for keyword-only enforcement.
_HANDLE_STEP_KWARGS = (
    "field",
    "turn",
    "ground_truth_state",
    "action",
    "reward",
    "phase",
    "active_agent_id",
    "agent_views",
    "reward_per_agent",
    "self_eval",
    "events",
)


def trace_line_to_handle_step_kwargs(line: dict, field: str) -> dict | None:
    """Map a trace.jsonl `kind=turn` line to PhysisBlock.handle_step
    kwargs. Returns None for non-turn lines (meta_first / meta_last /
    invalid). The mapping is small and explicit so any upstream
    handle_step signature change forces a visible failure here rather
    than silently dropping data.

    LxM-side trace.jsonl carries strictly more data than physis needs
    (state_signature, reward_per_turn, validation, result, timestamp,
    context_state, kind). This helper drops the extras and renames
    `reward_per_turn` to `reward` to match the Ludex contract.
    """
    if not isinstance(line, dict):
        return None
    if line.get("kind") != "turn":
        return None
    return {
        "field": field,
        "turn": int(line.get("turn") or 0),
        "ground_truth_state": dict(line.get("ground_truth_state") or {}),
        "action": dict(line.get("action") or {}),
        "reward": float(line.get("reward_per_turn") or 0.0),
        "phase": str(line.get("phase") or ""),
        "active_agent_id": str(line.get("active_agent_id") or ""),
        "events": list(line.get("events") or []),
        # agent_views, reward_per_agent, self_eval stay default —
        # LxM doesn't emit per-agent filtered views yet (Day 1 PM
        # deferred). Adding them later is purely additive on the
        # extractor + emit_trace_lines side.
    }


def emit_trace_lines(
    *,
    match_id: str,
    config: dict,
    log: list[dict],
    result: dict,
    schema: dict,
) -> Iterable[dict]:
    """Generate the jsonl lines for a single match. Caller is
    responsible for writing them. Returning a generator keeps memory
    flat for very long matches (rare, but Avalon can run 80+ turns
    under repeated rejections)."""
    game = schema.get("field", "lxm/?")
    gt_keys = schema.get("state_space", {}).get("ground_truth_keys", [])
    ctx_keys = schema.get("state_space", {}).get("context_keys", [])
    sig_fn = signature_extractor_for(game)
    reward_fn = reward_deriver_for(game)

    final_scores = result.get("scores") or {}
    last_idx = len(log) - 1

    # First line: meta header.
    yield {
        "kind": "meta_first",
        "match_id": match_id,
        "field": game,
        "schema_version": schema.get("schema_version", "?"),
        "agents": _agent_summary(config),
        "seed": config.get("seed") or (config.get("game") or {}).get("seed"),
        "started_at": (log[0].get("timestamp") if log else None),
        "exported_at": _utcnow_iso(),
    }

    # Per-turn lines.
    prev_post_state: dict = {}
    prev_post_ctx: dict = {}
    for i, entry in enumerate(log):
        post_state = entry.get("post_move_state") or {}
        post_ctx = entry.get("post_move_context") or {}
        envelope = entry.get("envelope") or {}
        move = envelope.get("move")
        active_agent_id = entry.get("agent_id")

        signature = None
        if sig_fn is not None and active_agent_id:
            signature = sig_fn(post_state, post_ctx, active_agent_id)

        reward = 0.0
        if reward_fn is not None and active_agent_id:
            reward = reward_fn(
                prev_post_state, post_state,
                prev_post_ctx, post_ctx,
                active_agent_id,
                i == last_idx,
                final_scores,
            )

        line = {
            "kind": "turn",
            "turn": entry.get("turn"),
            "active_agent_id": active_agent_id,
            "phase": post_state.get("phase"),
            "ground_truth_state": _project(post_state, gt_keys) if gt_keys else dict(post_state),
            "context_state": _project(post_ctx, ctx_keys) if ctx_keys else dict(post_ctx),
            "state_signature": signature,
            "reward_per_turn": reward,
            "action": move,
            "validation": entry.get("validation"),
            "result": entry.get("result"),
            "events": post_state.get("last_events") or [],
            "timestamp": entry.get("timestamp"),
        }
        yield line

        prev_post_state = post_state
        prev_post_ctx = post_ctx

    # Last line: meta closer with terminal reward.
    yield {
        "kind": "meta_last",
        "match_id": match_id,
        "outcome": result.get("outcome"),
        "winner": result.get("winner"),
        "scores": result.get("scores"),
        "summary": result.get("summary"),
        "ended_at": (log[-1].get("timestamp") if log else None),
    }


def export_match_trace(
    match_id: str,
    *,
    project_root: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    """End-to-end: read matches/<match_id>/{config,log,result}.json,
    look up the game's schema, emit a trace.jsonl in the path declared
    by the schema (`trace_path`). Returns the written path."""
    root = project_root or PROJECT_ROOT
    match_dir = root / "matches" / match_id
    config = json.loads((match_dir / "match_config.json").read_text(encoding="utf-8"))
    log = json.loads((match_dir / "log.json").read_text(encoding="utf-8"))
    result = json.loads((match_dir / "result.json").read_text(encoding="utf-8"))
    game, schema = schema_for_match(match_id, project_root=root)

    if output_dir is None:
        # Honor the schema's trace_path template if present, else default.
        template = schema.get("trace_path", f"traces/lxm/{game}/<match_id>/trace.jsonl")
        rel = template.replace("<match_id>", match_id)
        out_path = root / rel
    else:
        out_path = Path(output_dir) / "trace.jsonl"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for line in emit_trace_lines(
            match_id=match_id, config=config, log=log, result=result, schema=schema,
        ):
            f.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")
    return out_path


# ── CLI ────────────────────────────────────────────────────────────────────


def _main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Export an LxM match as a physis trace.jsonl")
    parser.add_argument("match_id", help="match folder under matches/")
    parser.add_argument("--output-dir", default=None,
                        help="override output directory (default: schema-declared trace_path)")
    parser.add_argument("--project-root", default=None,
                        help="LxM repo root (default: this module's parent.parent)")
    args = parser.parse_args(argv)

    root = Path(args.project_root) if args.project_root else None
    out = Path(args.output_dir) if args.output_dir else None
    path = export_match_trace(args.match_id, project_root=root, output_dir=out)
    print(f"trace -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
