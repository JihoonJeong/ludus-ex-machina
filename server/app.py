"""LxM API Server — FastAPI + Upstash Redis."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .redis_client import UpstashRedis, is_redis_available
from .routes import router
from .auth import router as auth_router
from .race import router as race_router

logger = logging.getLogger(__name__)

# Global Redis instance (None if not configured)
redis: UpstashRedis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis
    if is_redis_available():
        try:
            redis = UpstashRedis()
            logger.info("Connected to Upstash Redis")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Running without persistence.")
            redis = None
    else:
        logger.info("No Redis configured. Running in local mode (no persistence).")
    yield


app = FastAPI(
    title="LxM",
    description="Ludus Ex Machina — Where Machines Come to Play",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: pin to known frontends. allow_origins=["*"] with allow_credentials=True
# is an auth-from-any-origin hole (RFP B3), so list explicit origins. Override
# via LXM_CORS_ORIGINS (comma-separated) to add the Ludex app origin on deploy.
_DEFAULT_ORIGINS = [
    "https://jihoonjeong.github.io",
    "http://localhost:8080",
    "http://localhost:8000",
    "http://127.0.0.1:8080",
]
_origins_env = os.getenv("LXM_CORS_ORIGINS", "").strip()
ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()] or _DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(race_router)


@app.get("/health")
def health():
    """Liveness, plus which commit is actually answering.

    `version` is hand-written and moves when someone remembers to move it, so
    it cannot settle "is the fix deployed?". That question came up for real:
    a consumer lab probed this service in production and reasoned about which
    semantics were live, and neither side could check it from outside — the
    answer lived only in whoever had pressed Deploy. Render injects
    RENDER_GIT_COMMIT into every service, so the deployed pin can just say so.

    Absent locally, where the answer is "whatever is checked out" — reported as
    null rather than a guess.
    """
    return {
        "status": "ok",
        "redis": "connected" if redis else "not configured",
        "version": "0.1.0",
        "commit": os.getenv("RENDER_GIT_COMMIT") or None,
    }
