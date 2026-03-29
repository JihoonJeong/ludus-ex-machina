"""LxM API Server — FastAPI + Upstash Redis."""

from __future__ import annotations

import logging
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(race_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "redis": "connected" if redis else "not configured",
        "version": "0.1.0",
    }
