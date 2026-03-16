"""Run a series of LxM matches with color alternation and optional parallelism."""

import argparse
import subprocess
import sys
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def run_single_match(round_num, tag, game, white, black, model, timeout, max_retries,
                     no_shell=False, models=None, shell_paths=None):
    """Run a single match. Returns result dict. Designed for parallel execution."""
    match_id = f"{tag}_r{round_num:02d}"
    cmd = [
        sys.executable, "scripts/run_match.py",
        "--game", game,
        "--agents", white, black,
        "--timeout", str(timeout),
        "--max-retries", str(max_retries),
        "--match-id", match_id,
        "--skip-eval",
    ]
    if models:
        cmd.extend(["--models", models[0], models[1]])
    else:
        cmd.extend(["--model", model])
    if shell_paths:
        cmd.extend(["--shell-paths", shell_paths[0], shell_paths[1]])
    elif no_shell:
        cmd.append("--no-shell")

    subprocess.run(cmd, capture_output=True, text=True)

    result_path = Path("matches") / match_id / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text())
        return {
            "round": round_num,
            "match_id": match_id,
            "white": white,
            "black": black,
            "outcome": result.get("outcome"),
            "winner": result.get("winner"),
            "summary": result.get("summary"),
        }
    else:
        return {
            "round": round_num,
            "match_id": match_id,
            "white": white,
            "black": black,
            "outcome": "error",
            "winner": None,
            "summary": "No result file",
        }


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
    parser.add_argument("--parallel", type=int, default=1, help="Max concurrent games per batch")
    parser.add_argument("--no-shell", action="store_true", help="Run agents without shell injection")
    parser.add_argument("--models", nargs=2, default=None, metavar="MODEL",
                        help="Per-agent models (overrides --model)")
    parser.add_argument("--shell-paths", nargs=2, default=None, metavar="PATH",
                        help="Per-agent shell paths ('none' to skip)")
    args = parser.parse_args()

    tag = args.tag or f"{args.game}_{args.model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    agent_a, agent_b = args.agents
    parallel = max(1, args.parallel)

    # Build round list with color alternation
    rounds = []
    for i in range(args.start_round, args.rounds + 1):
        if i % 2 == 1:
            white, black = agent_a, agent_b
        else:
            white, black = agent_b, agent_a
        rounds.append((i, white, black))

    print(f"=== LxM Tournament: {tag} ===")
    print(f"Game: {args.game} | Model: {args.model}")
    print(f"Agents: {agent_a} vs {agent_b}")
    print(f"Rounds: {args.start_round}-{args.rounds} | Parallel: {parallel}")
    print()

    results = []

    # Split into batches
    for batch_start in range(0, len(rounds), parallel):
        batch = rounds[batch_start:batch_start + parallel]
        batch_label = ", ".join(f"R{r[0]:02d}" for r in batch)
        print(f"=== Batch: {batch_label} ===")
        for rnd, w, b in batch:
            print(f"  R{rnd:02d}: {w} (W) vs {b} (B)")
        print()

        if parallel == 1:
            # Sequential — show output live
            rnd, w, b = batch[0]
            match_id = f"{tag}_r{rnd:02d}"
            cmd = [
                sys.executable, "scripts/run_match.py",
                "--game", args.game,
                "--agents", w, b,
                "--timeout", str(args.timeout),
                "--max-retries", str(args.max_retries),
                "--match-id", match_id,
                "--skip-eval",
            ]
            if args.models:
                cmd.extend(["--models", args.models[0], args.models[1]])
            else:
                cmd.extend(["--model", args.model])
            if args.shell_paths:
                cmd.extend(["--shell-paths", args.shell_paths[0], args.shell_paths[1]])
            elif args.no_shell:
                cmd.append("--no-shell")
            subprocess.run(cmd, capture_output=False, text=True)
            result_path = Path("matches") / match_id / "result.json"
            if result_path.exists():
                result = json.loads(result_path.read_text())
                r = {
                    "round": rnd, "match_id": match_id, "white": w, "black": b,
                    "outcome": result.get("outcome"), "winner": result.get("winner"),
                    "summary": result.get("summary"),
                }
            else:
                r = {
                    "round": rnd, "match_id": match_id, "white": w, "black": b,
                    "outcome": "error", "winner": None, "summary": "No result file",
                }
            results.append(r)
            print(f"  → {r['summary']}")
            print()
        else:
            # Parallel batch
            with ProcessPoolExecutor(max_workers=parallel) as executor:
                futures = {}
                for rnd, w, b in batch:
                    f = executor.submit(
                        run_single_match, rnd, tag, args.game,
                        w, b, args.model, args.timeout, args.max_retries,
                        no_shell=args.no_shell, models=args.models,
                        shell_paths=args.shell_paths,
                    )
                    futures[f] = rnd

                for f in as_completed(futures):
                    r = f.result()
                    results.append(r)
                    print(f"  R{r['round']:02d} done → {r['summary']}")

            print()

    # Sort results by round number
    results.sort(key=lambda r: r["round"])

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
