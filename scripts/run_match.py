"""CLI entry point for running LxM matches."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from games.tictactoe.engine import TicTacToe
from games.chess.engine import ChessGame
from games.trustgame.engine import TrustGame
from games.codenames.engine import CodenamesGame
from games.poker.engine import PokerGame
from games.avalon.engine import AvalonGame
from lxm.adapters.claude_code import ClaudeCodeAdapter
from lxm.orchestrator import Orchestrator


GAME_ENGINES = {
    "tictactoe": TicTacToe,
    "chess": ChessGame,
    "trustgame": TrustGame,
    "codenames": CodenamesGame,
    "poker": PokerGame,
    "avalon": AvalonGame,
}

GAME_MAX_TURNS = {
    "tictactoe": 9,
    "chess": 200,
    "trustgame": 100,  # 2 moves per round × 50 max rounds
    "codenames": 50,
    "poker": 2000,
    "avalon": 200,
}


CODENAMES_ROLES = [
    {"team": "red", "role": "spymaster"},
    {"team": "red", "role": "guesser"},
    {"team": "blue", "role": "spymaster"},
    {"team": "blue", "role": "guesser"},
]


def main():
    parser = argparse.ArgumentParser(description="Run an LxM match")
    parser.add_argument("--game", required=True, choices=GAME_ENGINES.keys())
    parser.add_argument("--agents", nargs="+", required=True, metavar="AGENT_ID",
                        help="Agent IDs (2 for most games, 4 for codenames)")
    parser.add_argument("--match-id", default=None)
    parser.add_argument("--model", default="sonnet", help="Default model for all agents")
    parser.add_argument("--models", nargs="+", default=None, metavar="MODEL",
                        help="Per-agent models (overrides --model)")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--recent-moves", type=int, default=5)
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--invocation-mode", choices=["file", "inline"], default=None,
                        help="Invocation mode: inline (state in prompt, default) or file (read state.json).")
    parser.add_argument("--discovery-turns", type=int, default=1,
                        help="Number of initial turns per agent that use file mode (default: 1)")
    parser.add_argument("--no-shell", action="store_true",
                        help="Run agents without shell (no Hard/Soft Shell injection)")
    parser.add_argument("--shell-paths", nargs="+", default=None, metavar="PATH",
                        help="Per-agent shell paths (use 'none' to skip). Overrides --no-shell.")
    parser.add_argument("--good-shell", default=None, metavar="PATH",
                        help="Shell file for Good-role agents (Avalon). Injected based on assigned role.")
    parser.add_argument("--evil-shell", default=None, metavar="PATH",
                        help="Shell file for Evil-role agents (Avalon). Injected based on assigned role.")
    args = parser.parse_args()

    # Validate agent count
    n_agents = len(args.agents)
    if args.game == "poker":
        if n_agents < 2 or n_agents > 6:
            parser.error(f"Poker requires 2-6 agents, got {n_agents}")
    elif args.game == "codenames":
        if n_agents != 4:
            parser.error(f"Codenames requires 4 agents, got {n_agents}")
    elif args.game == "avalon":
        if n_agents < 5 or n_agents > 10:
            parser.error(f"Avalon requires 5-10 agents, got {n_agents}")
    else:
        if n_agents != 2:
            parser.error(f"Game '{args.game}' requires 2 agents, got {n_agents}")

    match_id = args.match_id or f"match_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    models = args.models or [args.model] * n_agents
    if len(models) != n_agents:
        parser.error(f"--models must have {n_agents} values, got {len(models)}")

    # Build agent configs
    agent_configs = []
    for i, agent_id in enumerate(args.agents):
        cfg = {"agent_id": agent_id, "display_name": agent_id, "seat": i}
        if args.game == "codenames":
            cfg.update(CODENAMES_ROLES[i])

        # Per-agent hard shell from --shell-paths (legacy) or default lookup
        if args.shell_paths:
            sp = args.shell_paths[i] if i < len(args.shell_paths) else "none"
            if sp != "none":
                cfg["hard_shell"] = sp
        elif not args.no_shell:
            default_path = Path("agents") / agent_id / "shell.md"
            if default_path.exists():
                cfg["hard_shell"] = str(default_path)

        agent_configs.append(cfg)

    match_config = {
        "protocol_version": "lxm-v0.2",
        "match_id": match_id,
        "game": {"name": args.game, "version": "1.0"},
        "time_model": {
            "type": "turn_based",
            "turn_order": "custom" if args.game in ("codenames", "poker", "avalon") else "sequential",
            "max_turns": GAME_MAX_TURNS.get(args.game, 100),
            "timeout_seconds": args.timeout,
            "timeout_action": "no_op",
            "max_retries": args.max_retries,
        },
        "agents": agent_configs,
        "history": {"recent_moves_count": 30 if args.game == "avalon" else (20 if args.game == "poker" else args.recent_moves)},
        "invocation": {
            "mode": args.invocation_mode or "inline",
            "discovery_turns": args.discovery_turns,
        },
    }

    # Add role-based shells (Avalon)
    role_shells = {}
    if args.good_shell:
        role_shells["good"] = args.good_shell
    if args.evil_shell:
        role_shells["evil"] = args.evil_shell
    if role_shells:
        match_config["role_shells"] = role_shells

    # Add teams block for codenames
    if args.game == "codenames":
        match_config["teams"] = {
            "red": {"spymaster": args.agents[0], "guesser": args.agents[1]},
            "blue": {"spymaster": args.agents[2], "guesser": args.agents[3]},
        }

    # Create game engine
    game = GAME_ENGINES[args.game]()

    # Create adapters
    adapters = {}
    for i, agent_config in enumerate(match_config["agents"]):
        agent_id = agent_config["agent_id"]
        agent_config_with_model = {
            **agent_config,
            "model": models[i],
            "timeout_seconds": args.timeout,
        }
        adapters[agent_id] = ClaudeCodeAdapter(agent_config_with_model)

    # Create and run orchestrator
    orch = Orchestrator(game, match_config, adapters)

    if args.skip_eval:
        # Monkey-patch to skip evaluation
        orch.run_evaluation = lambda match_dir: None

    print(f"=== LxM Match: {match_id} ===")
    print(f"Game: {args.game}")
    agent_strs = [f"{a} ({m})" for a, m in zip(args.agents, models)]
    print(f"Agents: {', '.join(agent_strs)}")
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
