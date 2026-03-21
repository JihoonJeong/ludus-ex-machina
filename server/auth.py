"""GitHub OAuth authentication for LxM."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse

from .redis_client import UpstashRedis

router = APIRouter(prefix="/api/auth")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET", "lxm-dev-secret-change-me")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")


def _get_redis() -> Optional[UpstashRedis]:
    from .app import redis
    return redis


# ── Simple JWT (no external dependency) ──

def _create_token(user_id: str, display_name: str) -> str:
    """Create a simple signed token. Not a full JWT — just HMAC-signed JSON."""
    payload = json.dumps({
        "user_id": user_id,
        "display_name": display_name,
        "exp": int(time.time()) + 86400 * 30,  # 30 days
    })
    sig = hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def _verify_token(token: str) -> dict | None:
    """Verify token and return payload, or None if invalid."""
    try:
        payload_str, sig = token.rsplit("|", 1)
        expected = hmac.new(JWT_SECRET.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(payload_str)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract user from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token = auth[7:]
    user = _verify_token(token)
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    return user


# ── OAuth Flow ──

@router.get("/login")
def login():
    """Redirect to GitHub OAuth authorization page."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(500, "GITHUB_CLIENT_ID not configured")
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&scope=read:user"
    )
    return RedirectResponse(url)


@router.get("/callback")
async def callback(code: str):
    """Handle GitHub OAuth callback. Exchange code for token, create/update user."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(500, "GitHub OAuth not configured")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(400, f"GitHub OAuth error: {data.get('error_description', 'unknown')}")

        # Get user profile
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        github_user = user_resp.json()

    user_id = github_user.get("login", "")
    display_name = github_user.get("name") or user_id
    avatar_url = github_user.get("avatar_url", "")

    # Store/update user in Redis
    r = _get_redis()
    if r:
        user_data = r.get_json(f"lxm:users:{user_id}") or {}
        user_data.update({
            "github_id": user_id,
            "display_name": display_name,
            "avatar_url": avatar_url,
        })
        if "created_at" not in user_data:
            from datetime import datetime, timezone
            user_data["created_at"] = datetime.now(timezone.utc).isoformat()
            user_data["agent_ids"] = []
        r.set_json(f"lxm:users:{user_id}", user_data)

    # Create token and redirect to frontend
    token = _create_token(user_id, display_name)
    return RedirectResponse(f"{FRONTEND_URL}/#/auth?token={token}&user={user_id}&name={display_name}")


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Get current user profile."""
    r = _get_redis()
    if r:
        user_data = r.get_json(f"lxm:users:{user['user_id']}")
        if user_data:
            return user_data
    return {"user_id": user["user_id"], "display_name": user["display_name"]}
