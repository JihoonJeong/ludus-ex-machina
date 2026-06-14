"""API routes for LxM server."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .match_driver import MatchError, open_match, submit_move, turn_payload
from .match_store import load_match, match_exists
from .models import (
    AgentCreate, AgentResponse,
    MatchSubmit, MatchResponse,
    MatchCreateRequest, MoveRequest,
    LeaderboardEntry,
)

router = APIRouter(prefix="/api")

# Key prefix — shares Upstash DB with Dugout without collision
P = "lxm:"

# Will be set during app lifespan
def _get_redis():
    from .app import redis
    return redis


# ── Agents ──

@router.post("/agents", response_model=AgentResponse)
def create_agent(agent: AgentCreate, request: Request):
    """Register a new agent."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")

    key = f"{P}agents:{agent.agent_id}"
    if r.exists(key):
        raise HTTPException(409, f"Agent '{agent.agent_id}' already exists")

    # Extract user_id from auth token if present
    from .auth import _verify_token
    auth = request.headers.get("Authorization", "")
    user_id = "local"
    if auth.startswith("Bearer "):
        payload = _verify_token(auth[7:])
        if payload:
            user_id = payload.get("user_id", "local")

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

    # Add to leaderboard sorted sets with initial ELO
    for g in agent.games:
        r.zadd(f"{P}leaderboard:{g}", 1500, agent.agent_id)

    return AgentResponse(**data)


@router.get("/agents/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str):
    """Get agent details."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")

    data = r.get_json(f"{P}agents:{agent_id}")
    if not data:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    return AgentResponse(**data)


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str):
    """Delete an agent."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")

    key = f"{P}agents:{agent_id}"
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

    keys = r.keys(f"{P}agents:*")
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
        r.set_json(f"{P}matches:{match.match_id}", match_data)

        # Update agent stats + ELO
        for agent in match.agents:
            agent_key = f"{P}agents:{agent.agent_id}"
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
            r.zadd(f"{P}leaderboard:{game}", agent_data["elo"][game], agent.agent_id)

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

    data = r.get_json(f"{P}matches:{match_id}")
    if not data:
        raise HTTPException(404, f"Match '{match_id}' not found")
    return data


@router.get("/matches")
def list_matches(game: str | None = None, user: str | None = None, limit: int = 20):
    """List recent matches."""
    r = _get_redis()
    if not r:
        return []

    keys = r.keys(f"{P}matches:*")
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


# ── Live cross-machine matches (RFP Stage A: A1/A3) ──

_MATCH_ERROR_STATUS = {
    "not_found": 404,
    "not_active": 409,
    "not_remote_turn": 409,
    "wrong_turn": 409,
    "illegal_move": 400,
}


def _match_view(env: dict) -> dict:
    """Public lifecycle view of a hosted match (omits the orchestrator snapshot)."""
    return {
        "match_id": env["match_id"],
        "game": env["game"],
        "status": env["status"],
        "to_move": env["to_move"],
        "to_move_kind": env["to_move_kind"],
        "to_move_turn": env["to_move_turn"],
        "participants": env["participants"],
        "result": env["result"],
        "updated_at": env.get("updated_at"),
    }


@router.post("/matches")
def create_live_match(req: MatchCreateRequest):
    """Open a hosted cross-machine match (A1). Auto-plays leading local turns;
    returns halted at the first remote turn (or completed)."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")
    match_id = req.match_id or f"live_{uuid.uuid4().hex[:12]}"
    if match_exists(r, match_id):
        raise HTTPException(409, f"Match '{match_id}' already exists")
    participants = [p.model_dump() for p in req.participants]
    try:
        env = open_match(r, match_id=match_id, game_name=req.game,
                         participants=participants, config=req.config)
    except KeyError as e:  # unknown game or adapter name
        raise HTTPException(400, str(e))
    return _match_view(env)


@router.get("/matches/{match_id}/state")
def get_live_match_state(match_id: str):
    """Current lifecycle state of a hosted match."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")
    env = load_match(r, match_id)
    if env is None:
        raise HTTPException(404, f"Match '{match_id}' not found")
    return _match_view(env)


def _load_or_404(match_id: str) -> dict:
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")
    env = load_match(r, match_id)
    if env is None:
        raise HTTPException(404, f"Match '{match_id}' not found")
    return env


@router.get("/matches/{match_id}/config")
def get_live_match_config(match_id: str):
    """Hosted match config in the viewer's expected shape (A6)."""
    return _load_or_404(match_id)["config"]


@router.get("/matches/{match_id}/log")
def get_live_match_log(match_id: str):
    """Hosted match per-turn log in the viewer's expected shape (A6)."""
    return _load_or_404(match_id).get("orchestrator", {}).get("log", [])


@router.get("/matches/{match_id}/result")
def get_live_match_result(match_id: str):
    """Hosted match final result (null while in progress) (A6)."""
    return _load_or_404(match_id).get("result")


@router.get("/matches/{match_id}/turns/{turn}")
def get_live_turn(match_id: str, turn: int):
    """Turn payload for the remote participant to act on (A3 poll path)."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")
    env = load_match(r, match_id)
    if env is None:
        raise HTTPException(404, f"Match '{match_id}' not found")
    payload = turn_payload(env)
    if payload is None:
        raise HTTPException(409, "no remote turn is pending")
    if turn != payload["turn"]:
        raise HTTPException(409, f"current turn is {payload['turn']}, not {turn}")
    return payload


@router.post("/matches/{match_id}/turns/{turn}/move")
def submit_live_move(match_id: str, turn: int, body: MoveRequest):
    """Submit a remote participant's move; advances the shared match (A3)."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")
    try:
        env = submit_move(r, match_id, turn=turn, move=body.move,
                          dialogue=body.dialogue, thoughts=body.thoughts)
    except MatchError as e:
        raise HTTPException(_MATCH_ERROR_STATUS.get(e.code, 400),
                            {"code": e.code, "message": e.message})
    return _match_view(env)


# ── Live match events (RFP A2: SSE your_turn) ──

# Server-side poll of the Redis envelope, pushed to the client as SSE, so the
# client holds one connection instead of polling. The poll path (GET /state,
# /turns/{n}) stays the durable fallback (Q1). Redis-poll based, so it works
# across workers and the stateless request model; the sync Redis call is run
# off the event loop via asyncio.to_thread.
SSE_POLL_SECONDS = 1.0
SSE_MAX_SECONDS = 300


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


async def _event_stream(redis, match_id: str, as_agent: str):
    last_turn = None
    elapsed = 0.0
    while elapsed < SSE_MAX_SECONDS:
        env = await asyncio.to_thread(load_match, redis, match_id)
        if env is None:
            yield _sse({"type": "gone", "match_id": match_id})
            return
        if env["status"] == "complete":
            yield _sse({"type": "match_complete", "match_id": match_id,
                        "result": env.get("result")})
            return
        if env["to_move"] == as_agent and env["to_move_turn"] != last_turn:
            last_turn = env["to_move_turn"]
            yield _sse({"type": "your_turn", "match_id": match_id, "turn": last_turn,
                        "deadline": env["config"]["time_model"]["timeout_seconds"]})
        else:
            yield ": heartbeat\n\n"
        await asyncio.sleep(SSE_POLL_SECONDS)
        elapsed += SSE_POLL_SECONDS
    yield _sse({"type": "stream_timeout", "match_id": match_id})


@router.get("/matches/{match_id}/events")
async def match_events(match_id: str, as_agent: str = Query(..., alias="as")):
    """SSE stream of your_turn / match_complete for a participant (A2). Subscribe
    with ?as={agent_id}; the poll path (GET /turns/{n}) remains the fallback."""
    r = _get_redis()
    if not r:
        raise HTTPException(503, "No persistence configured")
    if not match_exists(r, match_id):
        raise HTTPException(404, f"Match '{match_id}' not found")
    return StreamingResponse(
        _event_stream(r, match_id, as_agent),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Leaderboard ──

@router.get("/leaderboard/{game}", response_model=list[LeaderboardEntry])
def get_leaderboard(game: str, limit: int = 50):
    """Get ELO leaderboard for a game."""
    r = _get_redis()
    if not r:
        return []

    entries = r.zrevrange(f"{P}leaderboard:{game}", 0, limit - 1, withscores=True)
    if not entries:
        return []

    result = []
    for rank, i in enumerate(range(0, len(entries), 2)):
        agent_id = entries[i]
        elo = float(entries[i + 1])
        agent_data = r.get_json(f"{P}agents:{agent_id}")
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
        agent_data = r.get_json(f"{P}agents:{agent.agent_id}")
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
