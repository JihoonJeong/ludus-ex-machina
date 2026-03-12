"""Run a series of LxM matches with color alternation."""

import argparse
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Run an LxM tournament (multiple matches)")
    parser.add_argument("--game", required=True)
    parser.add_argument("--agents", nargs=2, required=True, metavar="AGENT_ID")
    parser.add_argument("--rounds", type=int, default=10, help="Total games to play")
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--start-round", type=int, default=1, help="Starting round number (to resume)")
    parser.add_argument("--tag", default=None, help="Tournament tag for match IDs")
    args = parser.parse_args()

    tag = args.tag or f"{args.game}_{args.model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    agent_a, agent_b = args.agents

    print(f"=== LxM Tournament: {tag} ===")
    print(f"Game: {args.game} | Model: {args.model}")
    print(f"Agents: {agent_a} vs {agent_b}")
    print(f"Rounds: {args.start_round}-{args.rounds} (alternating colors)")
    print()

    results = []

    for i in range(args.start_round, args.rounds + 1):
        # Alternate colors: odd rounds = a is White, even rounds = b is White
        if i % 2 == 1:
            white, black = agent_a, agent_b
        else:
            white, black = agent_b, agent_a

        match_id = f"{tag}_r{i:02d}"
        print(f"--- Round {i}/{args.rounds}: {white} (W) vs {black} (B) ---")

        cmd = [
            sys.executable, "scripts/run_match.py",
            "--game", args.game,
            "--agents", white, black,
            "--model", args.model,
            "--timeout", str(args.timeout),
            "--max-retries", str(args.max_retries),
            "--match-id", match_id,
            "--skip-eval",
        ]

        proc = subprocess.run(cmd, capture_output=False, text=True)

        # Read result
        result_path = Path("matches") / match_id / "result.json"
        if result_path.exists():
            result = json.loads(result_path.read_text())
            results.append({
                "round": i,
                "match_id": match_id,
                "white": white,
                "black": black,
                "outcome": result.get("outcome"),
                "winner": result.get("winner"),
                "summary": result.get("summary"),
            })
            print(f"  → {result.get('summary', '?')}")
        else:
            print(f"  → No result file found")
            results.append({
                "round": i,
                "match_id": match_id,
                "white": white,
                "black": black,
                "outcome": "error",
                "winner": None,
                "summary": "No result file",
            })

        print()

    # Summary
    print("=" * 60)
    print(f"TOURNAMENT COMPLETE: {tag}")
    print("=" * 60)

    wins = {agent_a: 0, agent_b: 0}
    draws = 0
    for r in results:
        if r["winner"] == agent_a:
            wins[agent_a] += 1
        elif r["winner"] == agent_b:
            wins[agent_b] += 1
        else:
            draws += 1

    total = len(results)
    print(f"  {agent_a}: {wins[agent_a]} wins ({wins[agent_a]/total:.0%})")
    print(f"  {agent_b}: {wins[agent_b]} wins ({wins[agent_b]/total:.0%})")
    print(f"  Draws: {draws} ({draws/total:.0%})")
    print()

    # Save tournament summary
    summary_path = Path("matches") / f"{tag}_summary.json"
    summary = {
        "tag": tag,
        "game": args.game,
        "model": args.model,
        "agents": [agent_a, agent_b],
        "rounds": results,
        "totals": {
            "games": total,
            agent_a: {"wins": wins[agent_a], "win_rate": round(wins[agent_a] / total, 3)},
            agent_b: {"wins": wins[agent_b], "win_rate": round(wins[agent_b] / total, 3)},
            "draws": draws,
            "draw_rate": round(draws / total, 3),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary saved: {summary_path}")

    # Per-game stats
    print()
    print("Per-game retry rates:")
    for r in results:
        match_dir = Path("matches") / r["match_id"]
        log_path = match_dir / "log.json"
        if log_path.exists():
            log = json.loads(log_path.read_text())
            accepted = len([e for e in log if e["result"] == "accepted"])
            rejected = len([e for e in log if e["result"] == "rejected"])
            total_entries = len(log)
            retry_rate = rejected / total_entries if total_entries > 0 else 0
            outcome = r["outcome"] or "?"
            print(f"  R{r['round']:>2}: {accepted:>3} moves, {retry_rate:.0%} retry, {outcome}")


if __name__ == "__main__":
    main()
