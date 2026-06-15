"""Reachable creature identity (RFP B1).

A creature registers once and gets a stable, opaque, server-issued
`creature_id`. Surfaced in a match's `present_agents` + record, it makes a
cross-machine opponent a *re-recognizable relationship* (B2) across matches —
not a one-off display name a client could collide with or spoof. Stored
without a TTL (identity is durable, unlike a 24h match).

Key: `lxm:creature:{creature_id}` -> {creature_id, display_name, created_at, owner}.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def creature_key(creature_id: str) -> str:
    return f"lxm:creature:{creature_id}"


def new_creature_id() -> str:
    return "cr_" + uuid.uuid4().hex[:20]


def register_creature(redis: Any, display_name: str, owner: str | None = None) -> dict:
    rec = {
        "creature_id": new_creature_id(),
        "display_name": display_name,
        "owner": owner,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    redis.set_json(creature_key(rec["creature_id"]), rec)  # no TTL — durable identity
    return rec


def get_creature(redis: Any, creature_id: str) -> dict | None:
    return redis.get_json(creature_key(creature_id))


def creature_exists(redis: Any, creature_id: str) -> bool:
    return bool(redis.exists(creature_key(creature_id)))
