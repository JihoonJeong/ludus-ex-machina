"""Upstash Redis REST client — adapted from Dugout pattern."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def is_redis_available() -> bool:
    return bool(os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN"))


class UpstashRedis:
    """Upstash Redis REST API wrapper. Serverless, no driver needed."""

    def __init__(self):
        url = os.getenv("UPSTASH_REDIS_REST_URL", "")
        token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
        if not url or not token:
            raise RuntimeError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN must be set")
        self._url = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = httpx.Client(timeout=10)

    def _cmd(self, *args: str) -> Any:
        resp = self._client.post(self._url, headers=self._headers, json=list(args))
        resp.raise_for_status()
        data = resp.json()
        return data.get("result")

    def get(self, key: str) -> str | None:
        return self._cmd("GET", key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        if ex:
            self._cmd("SET", key, value, "EX", str(ex))
        else:
            self._cmd("SET", key, value)

    def delete(self, key: str) -> None:
        self._cmd("DEL", key)

    def keys(self, pattern: str) -> list[str]:
        result = self._cmd("KEYS", pattern)
        return result if result else []

    def exists(self, key: str) -> bool:
        return bool(self._cmd("EXISTS", key))

    def incr(self, key: str) -> int:
        return self._cmd("INCR", key)

    # Sorted sets (for leaderboards)
    def zadd(self, key: str, score: float, member: str) -> None:
        self._cmd("ZADD", key, str(score), member)

    def zrevrange(self, key: str, start: int, stop: int, withscores: bool = False) -> list:
        if withscores:
            return self._cmd("ZREVRANGE", key, str(start), str(stop), "WITHSCORES")
        return self._cmd("ZREVRANGE", key, str(start), str(stop))

    def zscore(self, key: str, member: str) -> float | None:
        result = self._cmd("ZSCORE", key, member)
        return float(result) if result is not None else None

    # JSON helpers
    def get_json(self, key: str) -> Any:
        raw = self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key: str, value: Any, ex: int | None = None) -> None:
        self.set(key, json.dumps(value), ex=ex)
