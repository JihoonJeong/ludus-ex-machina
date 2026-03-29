"""Race Mode API — BYOK AI proxy for Deduction game.

Endpoints:
- POST /api/race/solve — Proxy AI API call with user's key (BYOK)
- POST /api/race/result — Submit race result (human + AI comparison)
- GET  /api/race/leaderboard — Race leaderboard

The server acts as a CORS proxy only. API keys are passed per-request,
never stored. The server adds no markup — raw API response is forwarded.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/race")

# ── Models ──

class SolveRequest(BaseModel):
    """BYOK API call request."""
    provider: str  # "anthropic" | "google" | "openai"
    api_key: str
    model: str  # e.g. "claude-sonnet-4-6", "gemini-2.0-flash", "gpt-4o"
    scenario_id: str
    prompt: str  # The full deduction prompt with case + evidence


class SolveResponse(BaseModel):
    answer: dict  # {"culprit": "B", "motive": "...", "method": "..."}
    raw_response: str
    model: str
    duration_ms: int


class RaceResult(BaseModel):
    scenario_id: str
    human_answer: dict
    human_score: float
    human_time_seconds: int
    human_files_read: int
    ai_answer: dict
    ai_score: float
    ai_model: str
    ai_provider: str
    winner: str  # "human" | "ai" | "tie"


# ── API Proxy ──

API_ENDPOINTS = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "google": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    "openai": "https://api.openai.com/v1/chat/completions",
}


@router.post("/solve", response_model=SolveResponse)
async def solve_mystery(req: SolveRequest):
    """Proxy AI API call. BYOK — key passed per-request, never stored."""

    start = time.time()

    try:
        if req.provider == "anthropic":
            result = await _call_anthropic(req)
        elif req.provider == "google":
            result = await _call_google(req)
        elif req.provider == "openai":
            result = await _call_openai(req)
        else:
            raise HTTPException(400, f"Unknown provider: {req.provider}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"API error: {e.response.text[:500]}")
    except Exception as e:
        raise HTTPException(502, f"API call failed: {str(e)[:500]}")

    duration_ms = int((time.time() - start) * 1000)

    # Parse answer from response
    answer = _extract_answer(result)

    return SolveResponse(
        answer=answer,
        raw_response=result[:2000],
        model=req.model,
        duration_ms=duration_ms,
    )


@router.post("/result")
async def submit_race_result(result: RaceResult):
    """Record race result and persist to Redis for leaderboard."""
    ts = datetime.now(timezone.utc)
    ts_str = ts.isoformat()

    from .app import redis as r
    if r:
        # Store full result
        result_key = f"lxm:race:result:{result.scenario_id}:{ts.strftime('%Y%m%d%H%M%S%f')}"
        r.set_json(result_key, {
            **result.model_dump(),
            "timestamp": ts_str,
        })

        # Update leaderboard sorted set (score-based, higher is better)
        lb_key = f"lxm:race:leaderboard:{result.scenario_id}"
        # Member = "human:{timestamp}" to keep entries unique
        if result.human_score > 0:
            member = f"human:{ts.strftime('%Y%m%d%H%M%S%f')}"
            r.zadd(lb_key, result.human_score, json.dumps({
                "type": "human",
                "score": result.human_score,
                "time_seconds": result.human_time_seconds,
                "files_read": result.human_files_read,
                "timestamp": ts_str,
            }))
        if result.ai_score > 0:
            member = f"ai:{result.ai_model}:{ts.strftime('%Y%m%d%H%M%S%f')}"
            r.zadd(lb_key, result.ai_score, json.dumps({
                "type": "ai",
                "model": result.ai_model,
                "provider": result.ai_provider,
                "score": result.ai_score,
                "timestamp": ts_str,
            }))

    return {
        "recorded": True,
        "persisted": r is not None,
        "scenario_id": result.scenario_id,
        "winner": result.winner,
        "human_score": result.human_score,
        "ai_score": result.ai_score,
        "timestamp": ts_str,
    }


@router.get("/leaderboard")
async def get_race_leaderboard(scenario_id: str | None = None, limit: int = 20):
    """Get race leaderboard. Optionally filter by scenario_id."""
    from .app import redis as r
    if not r:
        raise HTTPException(503, "Leaderboard unavailable (no Redis)")

    if scenario_id:
        keys = [f"lxm:race:leaderboard:{scenario_id}"]
    else:
        keys = r.keys("lxm:race:leaderboard:*")

    leaderboard = {}
    for key in keys:
        sid = key.split(":")[-1]
        raw = r.zrevrange(key, 0, limit - 1, withscores=True)
        if not raw:
            leaderboard[sid] = []
            continue
        entries = []
        # zrevrange with scores returns [member, score, member, score, ...]
        for i in range(0, len(raw), 2):
            try:
                entry = json.loads(raw[i])
            except (json.JSONDecodeError, TypeError):
                entry = {"raw": raw[i]}
            entry["leaderboard_score"] = float(raw[i + 1])
            entries.append(entry)
        leaderboard[sid] = entries

    return {"leaderboard": leaderboard}


# ── Provider-specific calls ──

async def _call_anthropic(req: SolveRequest) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            API_ENDPOINTS["anthropic"],
            headers={
                "x-api-key": req.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": req.model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": req.prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        # Extract text from Anthropic response
        content = data.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        return json.dumps(data)


async def _call_google(req: SolveRequest) -> str:
    url = API_ENDPOINTS["google"].format(model=req.model)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            url,
            params={"key": req.api_key},
            headers={"content-type": "application/json"},
            json={
                "contents": [{"parts": [{"text": req.prompt}]}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return json.dumps(data)


async def _call_openai(req: SolveRequest) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            API_ENDPOINTS["openai"],
            headers={
                "Authorization": f"Bearer {req.api_key}",
                "content-type": "application/json",
            },
            json={
                "model": req.model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": req.prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return json.dumps(data)


# ── Answer extraction ──

def _extract_answer(text: str) -> dict:
    """Extract culprit/motive/method from AI response text."""
    answer = {"culprit": "", "motive": "", "method": ""}

    # Try JSON parse first
    try:
        # Look for JSON object in text
        import re
        json_match = re.search(r'\{[^{}]*"culprit"[^{}]*\}', text)
        if json_match:
            parsed = json.loads(json_match.group())
            if "culprit" in parsed:
                return {
                    "culprit": str(parsed.get("culprit", "")),
                    "motive": str(parsed.get("motive", "")),
                    "method": str(parsed.get("method", "")),
                }
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: look for labeled fields
    import re
    for field in ["culprit", "motive", "method"]:
        match = re.search(rf'{field}[:\s]+["\']?([^"\'\n,]+)', text, re.IGNORECASE)
        if match:
            answer[field] = match.group(1).strip()

    return answer
