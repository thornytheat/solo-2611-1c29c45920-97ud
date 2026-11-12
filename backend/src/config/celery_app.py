"""Celery 入口：backend 投递任务，worker 消费（beat 写心跳 + 定时流失漂移巡检）。"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.config.settings import settings

celery_app = Celery(
    "funnelpath",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
)

celery_app.conf.beat_schedule = {
    "funnelpath-heartbeat": {"task": "funnelpath.heartbeat", "schedule": 20.0},
    "funnelpath-drift-scan": {"task": "funnelpath.nightly_drift_scan", "schedule": crontab(minute="*/10")},
}

TASK_HEARTBEAT = "funnelpath.heartbeat"
TASK_DRIFT_SCAN = "funnelpath.nightly_drift_scan"
TASK_REFRESH_CACHE = "funnelpath.refresh_path_cache"
