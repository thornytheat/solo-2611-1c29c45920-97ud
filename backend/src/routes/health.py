from __future__ import annotations

from fastapi import APIRouter

from src.config.database import ping_db, ping_redis
from src.config.settings import settings
from src.schemas.common import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> dict:
    db_ok = ping_db()
    redis_ok = ping_redis()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "redis": redis_ok,
        "service": settings.app_name,
        "version": "1.0.0",
    }
