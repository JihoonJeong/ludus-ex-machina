"""ELO rating system for LxM agents."""

import json
from pathlib import Path


DEFAULT_ELO = 1200
K_PROVISIONAL = 32  # First 30 games
K_ESTABLISHED = 16  # After 30 games
PROVISIONAL_THRESHOLD = 30

# Per-game weights for computing overall ELO (weighted average of game ELOs).
# Games not listed default to 1.0.
DEFAULT_GAME_WEIGHTS = {
    "chess": 1.0,
    "trustgame": 1.0,
    "tictactoe": 0.5,
}


def compute_elo_change(elo_a: float, elo_b: float, outcome_a: float, k: int = 32) -> tuple[float, float]:
    """Compute ELO changes for a single game.

    outcome_a: 1.0 = A wins, 0.0 = A loses, 0.5 = draw
    Returns (new_elo_a, new_elo_b).
    """
    expected_a = 1 / (1 + 10 ** ((elo_b - elo_a) / 400))
    expected_b = 1 - expected_a

    outcome_b = 1.0 - outcome_a

    new_a = elo_a + k * (outcome_a - expected_a)
    new_b = elo_b + k * (outcome_b - expected_b)

    return round(new_a), round(new_b)


def k_factor(games_played: int) -> int:
    return K_PROVISIONAL if games_played < PROVISIONAL_THRESHOLD else K_ESTABLISHED


def weighted_overall_elo(by_game: dict, game_weights: dict) -> int:
    """Compute overall ELO as weighted average of per-game ELOs.

    Only includes games the agent has actually played.
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for game_name, stats in by_game.items():
        if stats["games"] == 0:
            continue
        w = game_weights.get(game_name, 1.0)
        weighted_sum += stats["elo"] * w
        total_weight += w
    if total_weight == 0:
        return DEFAULT_ELO
    return round(weighted_sum / total_weight)


def build_leaderboard(matches_dir: str = "matches", game_weights: dict | None = None) -> dict:
    """Scan all completed matches and compute per-game ELO for all agents.

    Overall ELO is a weighted average of per-game ELOs.

    Returns:
        {
            "game_weights": { "chess": 1.0, ... },
            "games": ["chess", "trustgame", ...],
            "agents": {
                "agent_id": {
                    "display_name": str,
                    "elo": int,  # weighted overall
                    "games": int, "wins": int, "losses": int, "draws": int,
                    "by_game": { "chess": { "elo", "games", "wins", "losses", "draws" }, ... },
                    "elo_history": [ { "match_id", "elo_before", "elo_after", "game" } ],
                },
            },
            "matches_processed": int,
        }
    """
    if game_weights is None:
        game_weights = DEFAULT_GAME_WEIGHTS

    matches_path = Path(matches_dir)
    if not matches_path.exists():
        return {"game_weights": game_weights, "games": [], "agents": {}, "matches_processed": 0}

    # Collect completed matches sorted by modification time
    completed = []
    for d in sorted(matches_path.iterdir(), key=lambda p: p.stat().st_mtime):
        if not d.is_dir():
            continue
        config_path = d / "match_config.json"
        result_path = d / "result.json"
        if not config_path.exists() or not result_path.exists():
            continue
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        completed.append({"config": config, "result": result, "dir": d.name})

    # Initialize agents
    agents = {}
    all_games = set()

    def ensure_agent(agent_id, display_name=None):
        if agent_id not in agents:
            agents[agent_id] = {
                "display_name": display_name or agent_id,
                "elo": DEFAULT_ELO,
                "games": 0, "wins": 0, "losses": 0, "draws": 0,
                "by_game": {},
                "elo_history": [],
            }
        elif display_name and agents[agent_id]["display_name"] == agent_id:
            agents[agent_id]["display_name"] = display_name

    def ensure_game_stats(agent_id, game_name):
        by_game = agents[agent_id]["by_game"]
        if game_name not in by_game:
            by_game[game_name] = {
                "elo": DEFAULT_ELO, "games": 0,
                "wins": 0, "losses": 0, "draws": 0,
            }

    # Process matches chronologically
    for match in completed:
        config = match["config"]
        result = match["result"]
        match_id = config.get("match_id", match["dir"])
        game_name = config.get("game", {}).get("name", "unknown")
        all_games.add(game_name)

        agent_configs = config.get("agents", [])
        if len(agent_configs) != 2:
            continue  # ELO only for 2-player games

        a_id = agent_configs[0].get("agent_id")
        b_id = agent_configs[1].get("agent_id")
        if not a_id or not b_id:
            continue

        ensure_agent(a_id, agent_configs[0].get("display_name"))
        ensure_agent(b_id, agent_configs[1].get("display_name"))
        ensure_game_stats(a_id, game_name)
        ensure_game_stats(b_id, game_name)

        # Determine outcome
        winner = result.get("winner")

        if winner == a_id:
            outcome_a = 1.0
        elif winner == b_id:
            outcome_a = 0.0
        else:
            outcome_a = 0.5  # draw

        # Compute per-game ELO
        game_a = agents[a_id]["by_game"][game_name]
        game_b = agents[b_id]["by_game"][game_name]
        game_k = min(k_factor(game_a["games"]), k_factor(game_b["games"]))
        game_elo_before_a = game_a["elo"]
        game_elo_before_b = game_b["elo"]
        game_new_a, game_new_b = compute_elo_change(game_a["elo"], game_b["elo"], outcome_a, game_k)

        # Update per-game stats
        game_a["elo"] = game_new_a
        game_b["elo"] = game_new_b
        for gs, oa in [(game_a, outcome_a), (game_b, 1.0 - outcome_a)]:
            gs["games"] += 1
            if oa == 1.0:
                gs["wins"] += 1
            elif oa == 0.0:
                gs["losses"] += 1
            else:
                gs["draws"] += 1

        # Update overall tallies
        for aid, oa in [(a_id, outcome_a), (b_id, 1.0 - outcome_a)]:
            agents[aid]["games"] += 1
            if oa == 1.0:
                agents[aid]["wins"] += 1
            elif oa == 0.0:
                agents[aid]["losses"] += 1
            else:
                agents[aid]["draws"] += 1

        # ELO history (per-game ELO changes)
        agents[a_id]["elo_history"].append({
            "match_id": match_id, "elo_before": game_elo_before_a,
            "elo_after": game_new_a, "game": game_name,
        })
        agents[b_id]["elo_history"].append({
            "match_id": match_id, "elo_before": game_elo_before_b,
            "elo_after": game_new_b, "game": game_name,
        })

    # Compute weighted overall ELO from per-game ELOs
    for agent in agents.values():
        agent["elo"] = weighted_overall_elo(agent["by_game"], game_weights)

    return {
        "game_weights": game_weights,
        "games": sorted(all_games),
        "agents": agents,
        "matches_processed": len(completed),
    }


def save_leaderboard(matches_dir: str = "matches") -> Path:
    """Build and save leaderboard.json."""
    data = build_leaderboard(matches_dir)
    out = Path(matches_dir) / "leaderboard.json"
    out.write_text(json.dumps(data, indent=2))
    return out
