"""路径缓存刷新：backend 投递 Celery 任务，worker 计算后写 Redis，前端轮询状态。"""
from __future__ import annotations

import json

from src.config.settings import settings
from src.constants.enums import CacheJobStatus

KEY_PREFIX = "funnelpath:pathcache"
STATUS_TTL = 3600


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)


def dispatch(funnel_id: int) -> dict:
    from src.config.celery_app import TASK_REFRESH_CACHE, celery_app

    client = _redis()
    client.hset(
        f"{KEY_PREFIX}:{funnel_id}",
        mapping={"status": CacheJobStatus.QUEUED.value, "funnel_id": funnel_id},
    )
    client.expire(f"{KEY_PREFIX}:{funnel_id}", STATUS_TTL)
    task = celery_app.send_task(TASK_REFRESH_CACHE, args=[funnel_id])
    return {"funnel_id": funnel_id, "task_id": task.id, "status": CacheJobStatus.QUEUED.value}


def status(funnel_id: int) -> dict:
    try:
        data = _redis().hgetall(f"{KEY_PREFIX}:{funnel_id}") or {}
    except Exception:
        data = {}
    return {
        "funnel_id": funnel_id,
        "status": data.get("status", CacheJobStatus.IDLE.value),
        "refreshed_at": data.get("refreshed_at"),
        "top_path": data.get("top_path"),
        "cohort_users": int(data["cohort_users"]) if data.get("cohort_users") else None,
        "source_run": data.get("source_run"),
    }


def store_result(funnel_id: int, payload: dict) -> None:
    client = _redis()
    mapping = {
        "status": CacheJobStatus.READY.value,
        "funnel_id": funnel_id,
        "refreshed_at": payload["refreshed_at"],
        "top_path": payload["top_path"],
        "cohort_users": payload["cohort_users"],
        "source_run": payload["source_run"],
        "detail": json.dumps(payload.get("detail", {}), ensure_ascii=False),
    }
    client.hset(f"{KEY_PREFIX}:{funnel_id}", mapping=mapping)
    client.expire(f"{KEY_PREFIX}:{funnel_id}", STATUS_TTL)


def mark_failed(funnel_id: int, message: str) -> None:
    try:
        client = _redis()
        client.hset(f"{KEY_PREFIX}:{funnel_id}", mapping={"status": CacheJobStatus.FAILED.value, "error": message})
        client.expire(f"{KEY_PREFIX}:{funnel_id}", STATUS_TTL)
    except Exception:
        pass
