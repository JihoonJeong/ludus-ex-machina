"""API routes for LxM server."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from .models import (
    AgentCreate, AgentResponse,
    MatchSubmit, MatchResponse,
    LeaderboardEntry,
)

router = APIRouter(prefix="/api")

# Will be set during app lifespan
def _get_redis():
    from .app import redis
    return redis


# ── Agents ──

@router.post("/agents", response_model=AgentResponse)
def create_agent(agent: AgentCreate):
    """Register a new agent."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")

    key = f"agents:{agent.agent_id}"
    if r.exists(key):
        raise HTTPException(409, f"Agent '{agent.agent_id}' already exists")

    # TODO: extract user_id from auth token
    user_id = "local"

    data = {
        "agent_id": agent.agent_id,
        "user_id": user_id,
        "display_name": agent.display_name,
        "adapter": agent.adapter,
        "model": agent.model,
        "hard_shell_name": agent.hard_shell_name,
        "hard_shell_hash": agent.hard_shell_hash,
        "games": agent.games,
        "elo": {g: 1500 for g in agent.games},
        "stats": {g: {"wins": 0, "losses": 0, "draws": 0} for g in agent.games},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r.set_json(key, data)
    return AgentResponse(**data)


@router.get("/agents/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str):
    """Get agent details."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")

    data = r.get_json(f"agents:{agent_id}")
    if not data:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    return AgentResponse(**data)


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str):
    """Delete an agent."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")

    key = f"agents:{agent_id}"
    if not r.exists(key):
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    r.delete(key)
    return {"deleted": agent_id}


@router.get("/agents", response_model=list[AgentResponse])
def list_agents(user_id: str | None = None):
    """List all agents, optionally filtered by user."""
    r = _get_redis()
    if not r:
        return []

    keys = r.keys("agents:*")
    agents = []
    for key in keys:
        data = r.get_json(key)
        if data:
            if user_id and data.get("user_id") != user_id:
                continue
            agents.append(AgentResponse(**data))
    return agents


# ── Match Results ──

@router.post("/matches/result", response_model=MatchResponse)
def submit_match_result(match: MatchSubmit):
    """Submit match result and update ELO."""
    r = _get_redis()

    # Calculate ELO changes
    elo_changes = _calculate_elo_changes(match, r)

    # Store match metadata
    match_data = {
        **match.model_dump(),
        "elo_changes": elo_changes,
    }

    if r:
        r.set_json(f"matches:{match.match_id}", match_data)

        # Update agent stats + ELO
        for agent in match.agents:
            agent_key = f"agents:{agent.agent_id}"
            agent_data = r.get_json(agent_key)
            if not agent_data:
                continue

            game = match.game
            score = match.result.scores.get(agent.agent_id, 0)

            # Update stats
            if game not in agent_data.get("stats", {}):
                agent_data["stats"][game] = {"wins": 0, "losses": 0, "draws": 0}
            if score >= 1.0:
                agent_data["stats"][game]["wins"] += 1
            elif score <= 0.0:
                agent_data["stats"][game]["losses"] += 1
            else:
                agent_data["stats"][game]["draws"] += 1

            # Update ELO
            if game not in agent_data.get("elo", {}):
                agent_data["elo"][game] = 1500
            agent_data["elo"][game] += elo_changes.get(agent.agent_id, 0)

            r.set_json(agent_key, agent_data)

            # Update leaderboard sorted set
            r.zadd(f"leaderboard:{game}", agent_data["elo"][game], agent.agent_id)

    return MatchResponse(
        match_id=match.match_id,
        game=match.game,
        timestamp=match.timestamp,
        duration_seconds=match.duration_seconds,
        agents=match.agents,
        result=match.result,
        elo_changes=elo_changes,
    )


@router.get("/matches/{match_id}")
def get_match(match_id: str):
    """Get match metadata."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")

    data = r.get_json(f"matches:{match_id}")
    if not data:
        raise HTTPException(404, f"Match '{match_id}' not found")
    return data


@router.get("/matches")
def list_matches(game: str | None = None, user: str | None = None, limit: int = 20):
    """List recent matches."""
    r = _get_redis()
    if not r:
        return []

    keys = r.keys("matches:*")
    matches = []
    for key in sorted(keys, reverse=True)[:limit * 3]:  # Over-fetch for filtering
        data = r.get_json(key)
        if not data:
            continue
        if game and data.get("game") != game:
            continue
        if user:
            agent_users = [a.get("user_id") for a in data.get("agents", [])]
            if user not in agent_users:
                continue
        matches.append(data)
        if len(matches) >= limit:
            break
    return matches


# ── Leaderboard ──

@router.get("/leaderboard/{game}", response_model=list[LeaderboardEntry])
def get_leaderboard(game: str, limit: int = 50):
    """Get ELO leaderboard for a game."""
    r = _get_redis()
    if not r:
        return []

    entries = r.zrevrange(f"leaderboard:{game}", 0, limit - 1, withscores=True)
    if not entries:
        return []

    result = []
    for rank, i in enumerate(range(0, len(entries), 2)):
        agent_id = entries[i]
        elo = float(entries[i + 1])
        agent_data = r.get_json(f"agents:{agent_id}")
        if not agent_data:
            continue
        stats = agent_data.get("stats", {}).get(game, {})
        result.append(LeaderboardEntry(
            rank=rank + 1,
            agent_id=agent_id,
            user_id=agent_data.get("user_id", ""),
            display_name=agent_data.get("display_name", agent_id),
            elo=elo,
            wins=stats.get("wins", 0),
            losses=stats.get("losses", 0),
            draws=stats.get("draws", 0),
        ))
    return result


# ── ELO Calculation ──

def _calculate_elo_changes(match: MatchSubmit, r) -> dict[str, float]:
    """Calculate ELO changes for all agents in a match."""
    K = 32  # Standard K-factor
    changes = {}

    if not r:
        return changes

    # Get current ELOs
    elos = {}
    for agent in match.agents:
        agent_data = r.get_json(f"agents:{agent.agent_id}")
        if agent_data:
            elos[agent.agent_id] = agent_data.get("elo", {}).get(match.game, 1500)
        else:
            elos[agent.agent_id] = 1500

    # For each pair of agents, calculate ELO change
    agents = match.agents
    for i, a in enumerate(agents):
        total_change = 0
        for j, b in enumerate(agents):
            if i == j:
                continue
            ra = elos[a.agent_id]
            rb = elos[b.agent_id]
            ea = 1 / (1 + 10 ** ((rb - ra) / 400))

            sa = match.result.scores.get(a.agent_id, 0)
            sb = match.result.scores.get(b.agent_id, 0)
            if sa > sb:
                actual = 1.0
            elif sa < sb:
                actual = 0.0
            else:
                actual = 0.5

            total_change += K * (actual - ea)

        # Average change across all opponents
        n_opponents = len(agents) - 1
        changes[a.agent_id] = round(total_change / n_opponents, 1) if n_opponents else 0

    return changes
