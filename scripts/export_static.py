"""Export match data to static JSON for GitHub Pages deployment.

Usage:
    python scripts/export_static.py [--matches-dir matches/] [--output-dir docs/data/] [--max-log-kb 2048]

Outputs:
    data/matches.json           — match metadata index
    data/leaderboard.json       — ELO leaderboard
    data/cross_company.json     — cross-company matrix
    data/replays/{match_id}.json — bundled config + log + result per match
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.elo import build_leaderboard


import re

# Whitelist: only include matches matching these patterns
# A: Cross-Company headlines
# B: Shell/SIBO stories
# C: Blockworld shelter + sandbox + seed sweeps (2026-04-23/24)
INCLUDE_PATTERNS = [
    # A: Cross-Company
    r'^chess_(cc|flagship|midtier|light)_',
    r'^poker_(cc|flagship)_',
    r'^codenames_(cc|flagship)_',
    r'^avalon_(cc|midtier|flagship)_',
    r'^trust_cc_',
    r'^diplomacy_',
    # B: Shell/SIBO
    r'^avalon_(cs|shell)_',
    r'^poker_sibo_',
    r'^codenames_sibo_',
    r'^trustgame_sibo_',
    # C: Blockworld
    r'^bw_',
    # MUD (language world model field)
    r'^mud_',
    # Legacy-integration fields (conquest board)
    r'^tk_',
    r'^agora12_',
]
INCLUDE_RE = re.compile('|'.join(INCLUDE_PATTERNS))


def should_include(match_id: str) -> bool:
    """Return True if match should be included in export."""
    return bool(INCLUDE_RE.search(match_id))


def scan_matches(matches_dir: Path) -> list[dict]:
    """Scan matches directory, return metadata list (completed + curated only)."""
    matches = []
    for d in sorted(matches_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        if not should_include(d.name):
            continue
        config_path = d / "match_config.json"
        result_path = d / "result.json"
        if not config_path.exists() or not result_path.exists():
            continue
        try:
            config = json.loads(config_path.read_text())
            result = json.loads(result_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if result.get("outcome") == "cliff_timeout":
            continue  # infra abort (CLI timeout burst), not a real attempt

        log_path = d / "log.json"
        turn_count = 0
        if log_path.exists():
            try:
                log = json.loads(log_path.read_text())
                turn_count = len([
                    e for e in log
                    if e.get("result") == "accepted"
                    or (e.get("result") == "timeout" and e.get("post_move_state"))
                ])
            except (json.JSONDecodeError, OSError):
                pass

        matches.append({
            "match_id": config.get("match_id", d.name),
            "game": config.get("game", {}).get("name", "unknown"),
            "agents": [a.get("display_name", a.get("agent_id")) for a in config.get("agents", [])],
            "agent_ids": [a.get("agent_id") for a in config.get("agents", [])],
            "adapters": [a.get("adapter", "unknown") for a in config.get("agents", [])],
            "models": [a.get("model", "unknown") for a in config.get("agents", [])],
            "creature_paths": [a.get("creature_path") for a in config.get("agents", [])],
            "status": "completed",
            "result": result,
            "turn_count": turn_count,
            "timestamp": d.stat().st_mtime,
        })
    return matches


def strip_log(log: list[dict]) -> list[dict]:
    """Strip large fields from log entries to reduce size.

    Blockworld-aware: the first log entry keeps its full voxel grid; every
    subsequent entry stores only the cells that changed (`layer_diffs`).
    The renderer folds diffs into its running state so turn-by-turn
    playback works in static mode without shipping ~400 KB/turn.
    """
    stripped = []
    prev_layers: list | None = None
    for entry in log:
        e = dict(entry)
        # Remove raw reasoning — viewer doesn't display it
        e.pop("meta", None)
        e.pop("reasoning_summary", None)
        e.pop("raw_response", None)
        pms = e.get("post_move_state")
        if isinstance(pms, dict):
            world = pms.get("world")
            if isinstance(world, dict) and "layers" in world:
                layers = world["layers"]
                world = dict(world)
                if prev_layers is None:
                    # Keep the baseline full grid.
                    pass
                else:
                    # Diff against previous; strip layers, attach diff.
                    diffs = []
                    for z, (prev_layer, cur_layer) in enumerate(zip(prev_layers, layers)):
                        for y, (prev_row, cur_row) in enumerate(zip(prev_layer, cur_layer)):
                            for x, (pv, cv) in enumerate(zip(prev_row, cur_row)):
                                if pv != cv:
                                    diffs.append([x, y, z, cv])
                    world.pop("layers", None)
                    world["layer_diffs"] = diffs
                prev_layers = layers
                pms = dict(pms)
                pms["world"] = world
                e["post_move_state"] = pms
        stripped.append(e)
    return stripped


def export_replays(matches_dir: Path, output_dir: Path, max_log_kb: int) -> tuple[int, int]:
    """Export replay bundles. Returns (exported, skipped) counts."""
    replays_dir = output_dir / "replays"
    replays_dir.mkdir(parents=True, exist_ok=True)

    exported = 0
    skipped = 0

    for d in sorted(matches_dir.iterdir()):
        if not d.is_dir():
            continue
        if not should_include(d.name):
            continue
        config_path = d / "match_config.json"
        result_path = d / "result.json"
        log_path = d / "log.json"
        if not config_path.exists() or not result_path.exists():
            continue

        try:
            config = json.loads(config_path.read_text())
            result = json.loads(result_path.read_text())
            log = json.loads(log_path.read_text()) if log_path.exists() else []
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue

        stripped = strip_log(log)
        match_id = config.get("match_id", d.name)
        bundle = {
            "config": config,
            "log": stripped,
            "result": result,
        }
        # optional spectator commentary track(s)
        commentary_path = d / "commentary.json"
        if commentary_path.exists():
            try:
                bundle["commentary"] = json.loads(commentary_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        # Size check on the stripped bundle, not the raw log file.
        bundle_text = json.dumps(bundle, separators=(",", ":"))
        if len(bundle_text) / 1024 > max_log_kb:
            skipped += 1
            continue

        out_path = replays_dir / f"{match_id}.json"
        out_path.write_text(bundle_text, encoding="utf-8")
        exported += 1

    return exported, skipped


def build_cross_company(matches_dir: Path) -> dict:
    """Build cross-company matrix from match data."""
    # Collect matchup results grouped by game
    games = {}

    for d in sorted(matches_dir.iterdir()):
        if not d.is_dir():
            continue
        if not should_include(d.name):
            continue
        config_path = d / "match_config.json"
        result_path = d / "result.json"
        if not config_path.exists() or not result_path.exists():
            continue

        try:
            config = json.loads(config_path.read_text())
            result = json.loads(result_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if result.get("outcome") == "cliff_timeout":
            continue  # infra abort (CLI timeout burst), not a real attempt

        game_name = config.get("game", {}).get("name", "unknown")
        agents = config.get("agents", [])
        winner = result.get("winner")

        if game_name not in games:
            games[game_name] = {"matchups": {}, "total": 0}

        games[game_name]["total"] += 1

        # Extract adapter info for cross-company identification
        adapters = []
        for a in agents:
            adapter = a.get("adapter", "unknown")
            model = a.get("model", "unknown")
            agent_id = a.get("agent_id", "")
            adapters.append({
                "agent_id": agent_id,
                "adapter": adapter,
                "model": model,
                "display_name": a.get("display_name", agent_id),
            })

        # For 2-player games, track head-to-head
        if len(agents) == 2:
            a_adapter = adapters[0]["adapter"]
            b_adapter = adapters[1]["adapter"]

            # Only track cross-company matchups
            if a_adapter == b_adapter:
                continue

            key = tuple(sorted([a_adapter, b_adapter]))
            if key not in games[game_name]["matchups"]:
                games[game_name]["matchups"][key] = {
                    "a": key[0], "b": key[1],
                    "a_wins": 0, "b_wins": 0, "draws": 0,
                    "matches": [],
                }

            matchup = games[game_name]["matchups"][key]
            if winner:
                winner_agent = next((a for a in agents if a.get("agent_id") == winner), None)
                if winner_agent:
                    winner_adapter = winner_agent.get("adapter", "")
                    if winner_adapter == key[0]:
                        matchup["a_wins"] += 1
                    elif winner_adapter == key[1]:
                        matchup["b_wins"] += 1
                    else:
                        matchup["draws"] += 1
                else:
                    matchup["draws"] += 1
            else:
                matchup["draws"] += 1

            matchup["matches"].append({
                "match_id": config.get("match_id", d.name),
                "winner": winner,
            })

    # Convert matchup dicts to lists
    output = {"games": {}}
    for game_name, data in games.items():
        output["games"][game_name] = {
            "total": data["total"],
            "matchups": list(data["matchups"].values()),
        }

    return output


# ── Reach session scanning (D-062 Phase 2b) ──────────────────────────────

# Whitelist for reach sessions. session_id format:
# `reach_<YYYY-MM-DD>_<peer-a>_<peer-b>_<nnn>` per the Ludex schema.
SESSION_INCLUDE_RE = re.compile(r'^reach_\d{4}-\d{2}-\d{2}_')


def _parse_frontmatter_md(text: str) -> tuple[dict, str]:
    """Split a markdown file with YAML frontmatter into (meta, body).
    Returns ({}, text) if no frontmatter is found."""
    import yaml as _yaml
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5:]
    try:
        meta = _yaml.safe_load(fm_text) or {}
    except _yaml.YAMLError:
        meta = {}
    return meta, body


def _load_yaml(path: Path) -> dict:
    import yaml as _yaml
    try:
        return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (_yaml.YAMLError, OSError):
        return {}


def bundle_session(session_dir: Path) -> dict | None:
    """Assemble a reach session into a single JSON bundle.

    Layout expected (per reach_session_schema.md):
        sessions/<session_id>/
          meta.yaml
          turn.yaml
          prompts/NNN.md
          responses/NNN_<creature>_<machine>.md
          close_<creature>_<machine>.md
    """
    meta_path = session_dir / "meta.yaml"
    turn_path = session_dir / "turn.yaml"
    if not meta_path.exists():
        return None

    meta = _load_yaml(meta_path)
    turn_state = _load_yaml(turn_path) if turn_path.exists() else {}

    # Prompts: prompts/NNN.md
    prompts: dict[int, dict] = {}
    prompts_dir = session_dir / "prompts"
    if prompts_dir.is_dir():
        for f in sorted(prompts_dir.iterdir()):
            if f.suffix != ".md":
                continue
            stem = f.stem  # "001"
            try:
                turn_no = int(stem)
            except ValueError:
                continue
            fm, body = _parse_frontmatter_md(f.read_text(encoding="utf-8"))
            prompts[turn_no] = {"frontmatter": fm, "body": body, "filename": f.name}

    # Responses: responses/NNN_<creature>_<machine>.md — may be multiple per turn
    # in multi-peer scenarios (Phase 4+). Grouped by turn_no.
    responses: dict[int, list[dict]] = {}
    responses_dir = session_dir / "responses"
    if responses_dir.is_dir():
        for f in sorted(responses_dir.iterdir()):
            if f.suffix != ".md":
                continue
            stem_parts = f.stem.split("_", 1)
            try:
                turn_no = int(stem_parts[0])
            except (ValueError, IndexError):
                continue
            fm, body = _parse_frontmatter_md(f.read_text(encoding="utf-8"))
            responses.setdefault(turn_no, []).append(
                {"frontmatter": fm, "body": body, "filename": f.name}
            )

    # Close markers: close_*.md at the session root
    closes: list[dict] = []
    for f in sorted(session_dir.glob("close_*.md")):
        fm, body = _parse_frontmatter_md(f.read_text(encoding="utf-8"))
        closes.append({"frontmatter": fm, "body": body, "filename": f.name})

    # Assemble turn timeline
    all_turns = sorted(set(prompts.keys()) | set(responses.keys()))
    turns = []
    for t in all_turns:
        turns.append({
            "turn": t,
            "prompt": prompts.get(t),
            "responses": responses.get(t, []),
        })

    return {
        "session_id": meta.get("session_id", session_dir.name),
        "meta": meta,
        "turn_state": turn_state,
        "turns": turns,
        "closes": closes,
    }


def scan_sessions(sessions_dir: Path) -> list[dict]:
    """Scan sessions/ directory, return a lobby-density index.

    This is the *short* list written to `sessions.json` and consumed by
    the viewer's Reach tab. It deliberately omits fields that are only
    needed when viewing a single session in detail (notably
    `machine_id`, `pairing_id`, per-participant role metadata, and the
    full frontmatter of each turn). For those, load the per-session
    bundle at `docs/data/sessions/<session_id>.json` produced by
    `export_session_bundles()` — the bundle carries everything the
    schema §2 defines without elision.
    """
    sessions = []
    if not sessions_dir.is_dir():
        return sessions
    for d in sorted(sessions_dir.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        if not SESSION_INCLUDE_RE.search(d.name):
            continue
        meta_path = d / "meta.yaml"
        if not meta_path.exists():
            continue
        meta = _load_yaml(meta_path)
        # Count turns from responses/ (robust to incomplete prompts/)
        turn_count = 0
        responses_dir = d / "responses"
        if responses_dir.is_dir():
            turn_count = sum(1 for f in responses_dir.iterdir() if f.suffix == ".md")
        sessions.append({
            "session_id": meta.get("session_id", d.name),
            "field": meta.get("field"),
            "participants": [
                {
                    "creature": p.get("creature"),
                    "machine_alias": p.get("machine_alias"),
                }
                for p in meta.get("participants", [])
            ],
            "status": meta.get("status", "unknown"),
            "close_reason": meta.get("close_reason", ""),
            "created_at": meta.get("created_at"),
            "turn_count": turn_count,
            "max_turns": meta.get("max_turns"),
        })
    return sessions


def export_session_bundles(sessions_dir: Path, output_dir: Path) -> int:
    """Export per-session bundles to docs/data/sessions/<session_id>.json."""
    if not sessions_dir.is_dir():
        return 0
    out = output_dir / "sessions"
    out.mkdir(parents=True, exist_ok=True)
    exported = 0
    for d in sorted(sessions_dir.iterdir()):
        if not d.is_dir():
            continue
        if not SESSION_INCLUDE_RE.search(d.name):
            continue
        bundle = bundle_session(d)
        if bundle is None:
            continue
        (out / f"{bundle['session_id']}.json").write_text(
            json.dumps(bundle, separators=(",", ":"), ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        exported += 1
    return exported


def main():
    parser = argparse.ArgumentParser(description="Export LxM match data to static JSON")
    parser.add_argument("--matches-dir", default="matches", help="Source matches directory")
    parser.add_argument("--sessions-dir", default="sessions", help="Source reach sessions directory")
    parser.add_argument("--output-dir", default="docs/data", help="Output directory")
    parser.add_argument("--max-log-kb", type=int, default=2048, help="Skip replays with log > N KB")
    args = parser.parse_args()

    matches_dir = Path(args.matches_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not matches_dir.exists():
        print(f"Error: {matches_dir} not found")
        sys.exit(1)

    # 1. matches.json — STABLE across re-exports: a match keeps the timestamp it
    # was first exported with (st_mtime drifts when a dir is touched, which used
    # to reshuffle the whole file into a noisy diff), and ties break on match_id.
    print("Scanning matches...")
    matches = scan_matches(matches_dir)
    prev_path = output_dir / "matches.json"
    if prev_path.exists():
        try:
            prev = {m["match_id"]: m.get("timestamp")
                    for m in json.loads(prev_path.read_text(encoding="utf-8"))}
        except (ValueError, OSError):
            prev = {}
        for m in matches:
            if prev.get(m["match_id"]):
                m["timestamp"] = prev[m["match_id"]]
    matches.sort(key=lambda m: (-(m.get("timestamp") or 0), m["match_id"]))
    (output_dir / "matches.json").write_text(
        json.dumps(matches, indent=2), encoding="utf-8"
    )
    print(f"  {len(matches)} completed matches → matches.json")

    # 2. leaderboard.json (filter to curated matches only)
    print("Building leaderboard...")
    leaderboard = build_leaderboard(str(matches_dir))
    # Remove agents that only appear in excluded matches
    curated_ids = {m["match_id"] for m in matches}
    for agent_id in list(leaderboard.get("agents", {}).keys()):
        agent = leaderboard["agents"][agent_id]
        agent["elo_history"] = [h for h in agent.get("elo_history", []) if h["match_id"] in curated_ids]
    (output_dir / "leaderboard.json").write_text(
        json.dumps(leaderboard, indent=2), encoding="utf-8"
    )
    print(f"  {len(leaderboard.get('agents', {}))} agents, {leaderboard.get('matches_processed', 0)} matches → leaderboard.json")

    # 3. cross_company.json
    print("Building cross-company matrix...")
    cross_company = build_cross_company(matches_dir)
    (output_dir / "cross_company.json").write_text(
        json.dumps(cross_company, indent=2), encoding="utf-8"
    )
    game_count = sum(g["total"] for g in cross_company["games"].values())
    print(f"  {len(cross_company['games'])} games, {game_count} total matches → cross_company.json")

    # 4. replays
    print(f"Exporting replays (max {args.max_log_kb} KB per log)...")
    exported, skipped = export_replays(matches_dir, output_dir, args.max_log_kb)
    print(f"  {exported} exported, {skipped} skipped → replays/")

    # 5. reach sessions (D-062 Phase 2b)
    sessions_dir = Path(args.sessions_dir)
    print("Scanning reach sessions...")
    sessions = scan_sessions(sessions_dir)
    (output_dir / "sessions.json").write_text(
        json.dumps(sessions, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"  {len(sessions)} sessions → sessions.json")
    if sessions:
        bundles = export_session_bundles(sessions_dir, output_dir)
        print(f"  {bundles} session bundles → sessions/")

    # Summary
    total_size = sum(f.stat().st_size for f in output_dir.rglob("*.json"))
    print(f"\nTotal output: {total_size / 1024 / 1024:.1f} MB in {output_dir}/")

    # Landing claims: the HTML fallback under each data-i18n and i18n.js are two
    # copies of one claim. The platform card advertised "6 games ... GIF export"
    # long after the count reached 13 and the export button was removed, because
    # nothing checked. Run it where the deploy runs, so drift can't ship quietly.
    print("\nChecking landing i18n fallbacks...")
    from check_landing_i18n import main as check_landing
    if check_landing() != 0:
        print("^ landing text drifted — fix before deploying docs/")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
