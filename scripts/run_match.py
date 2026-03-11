"""CLI entry point for running LxM matches."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from games.tictactoe.engine import TicTacToe
from lxm.adapters.claude_code import ClaudeCodeAdapter
from lxm.orchestrator import Orchestrator


GAME_ENGINES = {
    "tictactoe": TicTacToe,
}

GAME_MAX_TURNS = {
    "tictactoe": 9,
}


def main():
    parser = argparse.ArgumentParser(description="Run an LxM match")
    parser.add_argument("--game", required=True, choices=GAME_ENGINES.keys())
    parser.add_argument("--agents", nargs=2, required=True, metavar="AGENT_ID")
    parser.add_argument("--match-id", default=None)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--recent-moves", type=int, default=5)
    parser.add_argument("--skip-eval", action="store_true")
    args = parser.parse_args()

    match_id = args.match_id or f"match_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    match_config = {
        "protocol_version": "lxm-v0.2",
        "match_id": match_id,
        "game": {"name": args.game, "version": "1.0"},
        "time_model": {
            "type": "turn_based",
            "turn_order": "sequential",
            "max_turns": GAME_MAX_TURNS.get(args.game, 100),
            "timeout_seconds": args.timeout,
            "timeout_action": "no_op",
            "max_retries": args.max_retries,
        },
        "agents": [
            {"agent_id": args.agents[0], "display_name": args.agents[0], "seat": 0},
            {"agent_id": args.agents[1], "display_name": args.agents[1], "seat": 1},
        ],
        "history": {"recent_moves_count": args.recent_moves},
    }

    # Create game engine
    game = GAME_ENGINES[args.game]()

    # Create adapters
    adapters = {}
    for agent_config in match_config["agents"]:
        agent_id = agent_config["agent_id"]
        shell_path = Path("agents") / agent_id / "shell.md"
        agent_config_with_model = {
            **agent_config,
            "model": args.model,
            "timeout_seconds": args.timeout,
        }
        adapters[agent_id] = ClaudeCodeAdapter(
            agent_config_with_model,
            shell_path=str(shell_path) if shell_path.exists() else None,
        )

    # Create and run orchestrator
    orch = Orchestrator(game, match_config, adapters)

    if args.skip_eval:
        # Monkey-patch to skip evaluation
        orch.run_evaluation = lambda match_dir: None

    print(f"=== LxM Match: {match_id} ===")
    print(f"Game: {args.game}")
    print(f"Agents: {args.agents[0]} (X) vs {args.agents[1]} (O)")
    print(f"Model: {args.model}")
    print()

    match_dir = orch.setup_match()
    print(f"Match folder: {match_dir}")
    print()

    result = orch.run()

    print()
    print("=== Match Complete ===")
    print(f"Outcome: {result['outcome']}")
    if result.get("winner"):
        print(f"Winner: {result['winner']}")
    print(f"Summary: {result['summary']}")
    print(f"Files: {match_dir}")


if __name__ == "__main__":
    main()
