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
    for entry in log:
        post_state = entry.get("post_move_state") or {}
        post_ctx = entry.get("post_move_context") or {}
        envelope = entry.get("envelope") or {}
        move = envelope.get("move")

        line = {
            "kind": "turn",
            "turn": entry.get("turn"),
            "active_agent_id": entry.get("agent_id"),
            "phase": post_state.get("phase"),
            "ground_truth_state": _project(post_state, gt_keys) if gt_keys else dict(post_state),
            "context_state": _project(post_ctx, ctx_keys) if ctx_keys else dict(post_ctx),
            "action": move,
            "validation": entry.get("validation"),
            "result": entry.get("result"),
            "events": post_state.get("last_events") or [],
            "timestamp": entry.get("timestamp"),
        }
        yield line

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
