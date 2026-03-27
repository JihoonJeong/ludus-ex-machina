"""Resume an existing LxM match from where it left off."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lxm.adapters.claude_code import ClaudeCodeAdapter
from lxm.adapters.gemini_cli import GeminiCLIAdapter
from lxm.adapters.ollama import OllamaAdapter
from lxm.adapters.codex_cli import CodexCLIAdapter
from lxm.orchestrator import Orchestrator
from games.chess.engine import ChessGame
from games.tictactoe.engine import TicTacToe
from games.trustgame.engine import TrustGame
from games.codenames.engine import CodenamesGame
from games.poker.engine import PokerGame
from games.avalon.engine import AvalonGame

ADAPTER_CLASSES = {
    "claude": ClaudeCodeAdapter,
    "gemini": GeminiCLIAdapter,
    "ollama": OllamaAdapter,
    "codex": CodexCLIAdapter,
}

GAME_ENGINES = {
    "tictactoe": TicTacToe,
    "chess": ChessGame,
    "trustgame": TrustGame,
    "codenames": CodenamesGame,
    "poker": PokerGame,
    "avalon": AvalonGame,
}


def main():
    parser = argparse.ArgumentParser(description="Resume an existing LxM match")
    parser.add_argument("match_id", help="Match ID (directory name or full path)")
    parser.add_argument("--timeout", type=int, default=None,
                        help="Override timeout (default: use timeout from match_config.json)")
    parser.add_argument("--adapter", default=None,
                        help="Override adapter type (claude/gemini/ollama/codex)")
    parser.add_argument("--model", default=None,
                        help="Override model for all agents")
    args = parser.parse_args()

    # Resolve match directory
    match_dir = Path(args.match_id)
    if not match_dir.is_absolute():
        match_dir = Path("matches") / match_dir
    match_dir = match_dir.resolve()

    if not match_dir.exists():
        print(f"Error: Match directory not found: {match_dir}")
        sys.exit(1)

    config_file = match_dir / "match_config.json"
    if not config_file.exists():
        print(f"Error: match_config.json not found in {match_dir}")
        sys.exit(1)

    # Load existing match config
    match_config = json.loads(config_file.read_text(encoding="utf-8"))
    
    # Use provided timeout or default to config's timeout
    timeout = args.timeout if args.timeout is not None else match_config["time_model"].get("timeout_seconds", 120)
    
    print(f"=== Resuming Match: {match_config['match_id']} ===")
    print(f"Match directory: {match_dir}")
    print(f"Game: {match_config['game']['name']}")
    print(f"Timeout: {timeout} seconds")
    print()

    # Get game engine
    game_name = match_config["game"]["name"]
    if game_name not in GAME_ENGINES:
        print(f"Error: Unknown game: {game_name}")
        sys.exit(1)
    game = GAME_ENGINES[game_name]()

    # Create adapters with correct timeout
    adapters = {}
    for agent_config in match_config["agents"]:
        agent_id = agent_config["agent_id"]
        # Merge with override options
        adapter_config = {
            **agent_config,
            "timeout_seconds": timeout,
        }
        if args.model:
            adapter_config["model"] = args.model
        elif "model" not in adapter_config:
            adapter_config["model"] = "sonnet"  # Default model

        # Determine adapter type
        adapter_type = args.adapter or "claude"  # Default to claude
        if adapter_type not in ADAPTER_CLASSES:
            print(f"Error: Unknown adapter: {adapter_type}")
            sys.exit(1)

        AdapterClass = ADAPTER_CLASSES[adapter_type]
        adapters[agent_id] = AdapterClass(adapter_config)
        print(f"  {agent_id}: {adapter_type} adapter with {timeout}s timeout")

    print()

    # Create and run orchestrator
    orch = Orchestrator(game, match_config, adapters)
    
    # setup_match will detect existing state and resume
    match_dir_str = orch.setup_match(base_dir=str(match_dir.parent))
    
    print(f"Resuming from turn {orch._state.turn}...")
    print()

    result = orch.run()

    print()
    print("=== Match Complete ===")
    print(f"Outcome: {result['outcome']}")
    if result.get("winner"):
        print(f"Winner: {result['winner']}")
    print(f"Summary: {result['summary']}")


if __name__ == "__main__":
    main()
