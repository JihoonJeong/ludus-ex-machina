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
INCLUDE_PATTERNS = [
    # A: Cross-Company
    r'^chess_(cc|flagship|midtier|light)_',
    r'^poker_(cc|flagship)_',
    r'^codenames_(cc|flagship)_',
    r'^avalon_(cc|midtier|flagship)_',
    r'^trust_cc_',
    # B: Shell/SIBO
    r'^avalon_(cs|shell)_',
    r'^poker_sibo_',
    r'^codenames_sibo_',
    r'^trustgame_sibo_',
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
            "status": "completed",
            "result": result,
            "turn_count": turn_count,
            "timestamp": d.stat().st_mtime,
        })
    return matches


def strip_log(log: list[dict]) -> list[dict]:
    """Strip large fields from log entries to reduce size."""
    stripped = []
    for entry in log:
        e = dict(entry)
        # Remove raw reasoning — viewer doesn't display it
        e.pop("meta", None)
        e.pop("reasoning_summary", None)
        e.pop("raw_response", None)
        # Keep everything else (result, move, post_move_state, agent_id, turn, etc.)
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

        # Check log size
        if log_path.exists():
            size_kb = log_path.stat().st_size / 1024
            if size_kb > max_log_kb:
                skipped += 1
                continue

        try:
            config = json.loads(config_path.read_text())
            result = json.loads(result_path.read_text())
            log = json.loads(log_path.read_text()) if log_path.exists() else []
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue

        match_id = config.get("match_id", d.name)
        bundle = {
            "config": config,
            "log": strip_log(log),
            "result": result,
        }

        out_path = replays_dir / f"{match_id}.json"
        out_path.write_text(json.dumps(bundle, separators=(",", ":")))
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


def main():
    parser = argparse.ArgumentParser(description="Export LxM match data to static JSON")
    parser.add_argument("--matches-dir", default="matches", help="Source matches directory")
    parser.add_argument("--output-dir", default="docs/data", help="Output directory")
    parser.add_argument("--max-log-kb", type=int, default=2048, help="Skip replays with log > N KB")
    args = parser.parse_args()

    matches_dir = Path(args.matches_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not matches_dir.exists():
        print(f"Error: {matches_dir} not found")
        sys.exit(1)

    # 1. matches.json
    print("Scanning matches...")
    matches = scan_matches(matches_dir)
    (output_dir / "matches.json").write_text(json.dumps(matches, indent=2))
    print(f"  {len(matches)} completed matches → matches.json")

    # 2. leaderboard.json (filter to curated matches only)
    print("Building leaderboard...")
    leaderboard = build_leaderboard(str(matches_dir))
    # Remove agents that only appear in excluded matches
    curated_ids = {m["match_id"] for m in matches}
    for agent_id in list(leaderboard.get("agents", {}).keys()):
        agent = leaderboard["agents"][agent_id]
        agent["elo_history"] = [h for h in agent.get("elo_history", []) if h["match_id"] in curated_ids]
    (output_dir / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2))
    print(f"  {len(leaderboard.get('agents', {}))} agents, {leaderboard.get('matches_processed', 0)} matches → leaderboard.json")

    # 3. cross_company.json
    print("Building cross-company matrix...")
    cross_company = build_cross_company(matches_dir)
    (output_dir / "cross_company.json").write_text(json.dumps(cross_company, indent=2))
    game_count = sum(g["total"] for g in cross_company["games"].values())
    print(f"  {len(cross_company['games'])} games, {game_count} total matches → cross_company.json")

    # 4. replays
    print(f"Exporting replays (max {args.max_log_kb} KB per log)...")
    exported, skipped = export_replays(matches_dir, output_dir, args.max_log_kb)
    print(f"  {exported} exported, {skipped} skipped → replays/")

    # Summary
    total_size = sum(f.stat().st_size for f in output_dir.rglob("*.json"))
    print(f"\nTotal output: {total_size / 1024 / 1024:.1f} MB in {output_dir}/")


if __name__ == "__main__":
    main()
