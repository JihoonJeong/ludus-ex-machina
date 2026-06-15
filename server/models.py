"""Pydantic request/response models for LxM API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# ── Agent Models ──

class AgentCreate(BaseModel):
    agent_id: str = Field(..., examples=["jj-opus-tag"])
    display_name: str = Field(..., examples=["JJ's TAG Opus"])
    adapter: str = Field(..., examples=["claude"])
    model: str = Field(..., examples=["opus"])
    hard_shell_name: Optional[str] = Field(None, examples=["tight_aggressive"])
    hard_shell_hash: Optional[str] = Field(None, description="SHA256 of shell content")
    games: list[str] = Field(default_factory=list, examples=[["poker", "avalon"]])


class AgentResponse(BaseModel):
    agent_id: str
    user_id: str
    display_name: str
    adapter: str
    model: str
    hard_shell_name: Optional[str] = None
    hard_shell_hash: Optional[str] = None
    games: list[str] = []
    elo: dict[str, float] = {}
    stats: dict[str, dict] = {}
    created_at: str = ""


# ── Match Models ──

class MatchAgent(BaseModel):
    agent_id: str
    user_id: str
    adapter: str
    model: str
    role: Optional[str] = None


class MatchResult(BaseModel):
    outcome: str
    winner: Optional[str] = None
    scores: dict[str, float] = {}
    summary: str = ""


class MatchSubmit(BaseModel):
    match_id: str
    game: str
    timestamp: str
    duration_seconds: int = 0
    agents: list[MatchAgent]
    result: MatchResult
    shell_hashes: dict[str, Optional[str]] = {}
    invocation_mode: str = "inline"


class MatchResponse(BaseModel):
    match_id: str
    game: str
    timestamp: str
    duration_seconds: int = 0
    agents: list[MatchAgent]
    result: MatchResult
    elo_changes: dict[str, float] = {}


# ── Live cross-machine match (RFP Stage A) ──

class ParticipantSpec(BaseModel):
    id: str = Field(..., examples=["aria"])
    kind: str = Field("local", description='"local" or "remote"')
    display: Optional[str] = None
    adapter: Optional[str] = Field(None, examples=["rule_bot"])
    model: Optional[str] = None
    # B1: stable server-issued identity (from POST /api/creatures). Surfaced in
    # present_agents so an opponent is re-recognizable across matches.
    creature_id: Optional[str] = None


class CreatureCreate(BaseModel):
    display_name: str = Field(..., examples=["Aria"])


class MatchCreateRequest(BaseModel):
    game: str = Field(..., examples=["tictactoe"])
    participants: list[ParticipantSpec]
    match_id: Optional[str] = None
    config: dict = Field(default_factory=dict)
    # "practice" = ephemeral (24h Redis); "published" = durable + viewable.
    # General persistence metadata — applies to any participant.
    kind: str = Field("practice", description='"practice" or "published"')


class MoveRequest(BaseModel):
    move: dict
    dialogue: Optional[str] = None
    thoughts: Optional[str] = None


# ── Leaderboard ──

class LeaderboardEntry(BaseModel):
    rank: int
    agent_id: str
    user_id: str
    display_name: str
    elo: float
    wins: int = 0
    losses: int = 0
    draws: int = 0


# ── Auth ──

class TokenResponse(BaseModel):
    token: str
    user_id: str
    display_name: str
