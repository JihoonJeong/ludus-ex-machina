"""ELO rating system for LxM agents."""

import json
from pathlib import Path


DEFAULT_ELO = 1200
K_PROVISIONAL = 32  # First 30 games
K_ESTABLISHED = 16  # After 30 games
PROVISIONAL_THRESHOLD = 30


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


def build_leaderboard(matches_dir: str = "matches") -> dict:
    """Scan all completed matches and compute ELO for all agents.

    Returns:
        {
            "agents": {
                "agent_id": {
                    "display_name": str,
                    "elo": int,
                    "games": int, "wins": int, "losses": int, "draws": int,
                    "by_game": { "chess": { ... }, ... },
                    "elo_history": [ { "match_id", "elo_before", "elo_after", "game" } ],
                },
            },
            "matches_processed": int,
        }
    """
    matches_path = Path(matches_dir)
    if not matches_path.exists():
        return {"agents": {}, "matches_processed": 0}

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
            config = json.loads(config_path.read_text())
            result = json.loads(result_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        completed.append({"config": config, "result": result, "dir": d.name})

    # Initialize agents
    agents = {}

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
        outcome = result.get("outcome", "")

        if winner == a_id:
            outcome_a = 1.0
        elif winner == b_id:
            outcome_a = 0.0
        else:
            outcome_a = 0.5  # draw

        # Compute ELO change (using overall ELO)
        k = min(k_factor(agents[a_id]["games"]), k_factor(agents[b_id]["games"]))
        elo_before_a = agents[a_id]["elo"]
        elo_before_b = agents[b_id]["elo"]
        new_a, new_b = compute_elo_change(elo_before_a, elo_before_b, outcome_a, k)

        # Also compute per-game ELO
        game_a = agents[a_id]["by_game"][game_name]
        game_b = agents[b_id]["by_game"][game_name]
        game_k = min(k_factor(game_a["games"]), k_factor(game_b["games"]))
        game_new_a, game_new_b = compute_elo_change(game_a["elo"], game_b["elo"], outcome_a, game_k)

        # Update overall stats
        agents[a_id]["elo"] = new_a
        agents[b_id]["elo"] = new_b

        for aid, oa in [(a_id, outcome_a), (b_id, 1.0 - outcome_a)]:
            agents[aid]["games"] += 1
            if oa == 1.0:
                agents[aid]["wins"] += 1
            elif oa == 0.0:
                agents[aid]["losses"] += 1
            else:
                agents[aid]["draws"] += 1

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

        # ELO history
        agents[a_id]["elo_history"].append({
            "match_id": match_id, "elo_before": elo_before_a,
            "elo_after": new_a, "game": game_name,
        })
        agents[b_id]["elo_history"].append({
            "match_id": match_id, "elo_before": elo_before_b,
            "elo_after": new_b, "game": game_name,
        })

    return {"agents": agents, "matches_processed": len(completed)}


def save_leaderboard(matches_dir: str = "matches") -> Path:
    """Build and save leaderboard.json."""
    data = build_leaderboard(matches_dir)
    out = Path(matches_dir) / "leaderboard.json"
    out.write_text(json.dumps(data, indent=2))
    return out
