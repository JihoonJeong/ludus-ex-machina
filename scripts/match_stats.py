"""Analyze match statistics from log.json — baseline data for Soft Shell experiments."""

import argparse
import json
import sys
from pathlib import Path


def analyze_match(match_dir: Path) -> dict:
    config = json.loads((match_dir / "match_config.json").read_text())
    log = json.loads((match_dir / "log.json").read_text())
    result_path = match_dir / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else None

    agents = {a["agent_id"]: a for a in config.get("agents", [])}
    game_name = config.get("game", {}).get("name", "unknown")

    # Per-agent stats
    agent_stats = {}
    for aid in agents:
        entries = [e for e in log if e["agent_id"] == aid]
        accepted = [e for e in entries if e["result"] == "accepted"]
        rejected = [e for e in entries if e["result"] == "rejected"]
        timeouts = [e for e in entries if e["result"] == "timeout"]
        total_attempts = len(entries)
        retry_rate = len(rejected) / total_attempts if total_attempts > 0 else 0

        agent_stats[aid] = {
            "accepted": len(accepted),
            "rejected": len(rejected),
            "timeouts": len(timeouts),
            "total_attempts": total_attempts,
            "retry_rate": round(retry_rate, 3),
        }

    # Overall
    accepted_all = [e for e in log if e["result"] == "accepted"]
    rejected_all = [e for e in log if e["result"] == "rejected"]

    stats = {
        "match_id": config.get("match_id"),
        "game": game_name,
        "total_accepted": len(accepted_all),
        "total_rejected": len(rejected_all),
        "overall_retry_rate": round(len(rejected_all) / len(log), 3) if log else 0,
        "agents": agent_stats,
        "result": result,
    }
    return stats


def print_stats(stats: dict):
    print(f"Match: {stats['match_id']}  |  Game: {stats['game']}")
    print(f"Moves: {stats['total_accepted']} accepted, {stats['total_rejected']} rejected")
    print(f"Overall retry rate: {stats['overall_retry_rate']:.1%}")
    print()

    for aid, s in stats["agents"].items():
        print(f"  {aid}:")
        print(f"    Accepted: {s['accepted']}  Rejected: {s['rejected']}  Timeouts: {s['timeouts']}")
        print(f"    Retry rate: {s['retry_rate']:.1%}")

    if stats["result"]:
        print()
        r = stats["result"]
        print(f"Result: {r.get('outcome', '?')}")
        if r.get("winner"):
            print(f"Winner: {r['winner']}")
        print(f"Summary: {r.get('summary', '?')}")
        if r.get("scores"):
            for aid, score in r["scores"].items():
                print(f"  {aid}: {score}")


def main():
    parser = argparse.ArgumentParser(description="Analyze LxM match statistics")
    parser.add_argument("match", help="Match ID or path to match folder")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    match_dir = Path(args.match)
    if not match_dir.exists():
        match_dir = Path("matches") / args.match
    if not match_dir.exists():
        print(f"Match not found: {args.match}")
        sys.exit(1)

    stats = analyze_match(match_dir)

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print_stats(stats)


if __name__ == "__main__":
    main()
