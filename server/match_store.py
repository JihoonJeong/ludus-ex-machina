"""Redis-backed store for live cross-machine matches (RFP Stage A).

A hosted match lives at `lxm:match:{id}` as one JSON envelope so participants
on different machines share one game state and a match survives a mid-match
server restart (RFP A1). The local in-process path (`scripts/run_match.py`)
does not use this — it keeps state in the match folder on disk.

Envelope shape (assembled by the match driver, A4):
    {
      "match_id": str,
      "game": str,                    # game name, to reconstruct the engine
      "config": dict,                 # the full match_config
      "participants": [               # who is playing and how they're reached
        {"id": str, "kind": "local"|"remote", "display": str, ...},
      ],
      "status": "waiting"|"in_progress"|"complete",
      "to_move": str | None,          # agent_id whose turn it is
      "to_move_kind": "local"|"remote"|None,
      "orchestrator": dict,           # Orchestrator.to_snapshot() — mutable state + log
      "result": dict | None,          # final result once complete
      "created_at": str, "updated_at": str,
    }
"""

from __future__ import annotations

from typing import Any

# A live match idle longer than this is considered abandoned.
MATCH_TTL_SECONDS = 60 * 60 * 24


def match_key(match_id: str) -> str:
    return f"lxm:match:{match_id}"


def save_match(redis: Any, match_id: str, envelope: dict,
               ttl: int = MATCH_TTL_SECONDS) -> None:
    """Persist (or overwrite) the match envelope with a sliding TTL."""
    redis.set_json(match_key(match_id), envelope, ex=ttl)


def load_match(redis: Any, match_id: str) -> dict | None:
    """Return the match envelope, or None if it does not exist / expired."""
    return redis.get_json(match_key(match_id))


def match_exists(redis: Any, match_id: str) -> bool:
    return bool(redis.exists(match_key(match_id)))


def delete_match(redis: Any, match_id: str) -> None:
    redis.delete(match_key(match_id))
