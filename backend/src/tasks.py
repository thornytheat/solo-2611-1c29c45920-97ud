"""Celery 任务：心跳、路径缓存刷新、流失漂移巡检。"""
from __future__ import annotations

import json
import os
import time

from src.config.celery_app import TASK_DRIFT_SCAN, TASK_HEARTBEAT, TASK_REFRESH_CACHE, celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")
HEARTBEAT_KEY = "funnelpath:worker:heartbeat"
DRIFT_KEY = "funnelpath:drift:latest"


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name=TASK_HEARTBEAT)
def heartbeat() -> str:
    _redis().set(HEARTBEAT_KEY, f"{time.time():.0f}")
    return "beat"


@celery_app.task(name=TASK_REFRESH_CACHE, bind=True, max_retries=1)
def refresh_path_cache(self, funnel_id: int) -> dict:
    """重算最新 run 的 Top 路径与卡点，写入 Redis 供前端轮询。"""
    from src.config.database import SessionLocal
    from src.models.funnel import FunnelDef
    from src.services import cache_service, path_engine, run_service
    from src.utils.timeutil import now_biz

    try:
        with SessionLocal() as db:
            funnel = db.get(FunnelDef, funnel_id)
            if funnel is None:
                cache_service.mark_failed(funnel_id, "funnel not found")
                return {"ok": False}
            run = run_service.latest_run(db, funnel_id)
            if run is None:
                cache_service.mark_failed(funnel_id, "no run yet")
                return {"ok": False}
            outcomes = run_service.outcomes_for_run(db, run)
            step_index = run_service.max_loss_step(run.step_counts or [{"users": 0}])
            cohort = path_engine.analyze_cohort(outcomes, run.step_counts, step_index)
            payload = {
                "refreshed_at": now_biz().strftime("%Y-%m-%d %H:%M:%S"),
                "top_path": (cohort["top_path"] or {}).get("path", ""),
                "cohort_users": cohort["cohort_users"],
                "source_run": run.code,
                "detail": {
                    "step_label": cohort["step_label"],
                    "top_paths": cohort["paths"][:3],
                    "choke_points": cohort["choke_points"][:3],
                },
            }
            cache_service.store_result(funnel_id, payload)
            logger.info("cache refreshed funnel=%s run=%s", funnel_id, run.code)
            return {"ok": True, **payload}
    except Exception as exc:  # noqa: BLE001
        cache_service.mark_failed(funnel_id, str(exc))
        logger.warning("cache refresh failed funnel=%s: %s", funnel_id, exc)
        return {"ok": False, "error": str(exc)}


@celery_app.task(name=TASK_DRIFT_SCAN)
def nightly_drift_scan() -> dict:
    """每 10 分钟巡检一次：各漏斗最新 run 的最大分群差，写 Redis + 审计。"""
    from sqlalchemy import select

    from src.config.database import SessionLocal
    from src.models.audit import AuditLog
    from src.models.funnel import FunnelDef
    from src.services import run_service

    summary: list[dict] = []
    try:
        with SessionLocal() as db:
            funnels = db.scalars(select(FunnelDef)).all()
            for funnel in funnels:
                run = run_service.latest_run(db, funnel.id)
                if run is None:
                    continue
                rows = [row for row in (run.segment_rows or []) if row.get("level") == "device"]
                ranked = sorted(rows, key=lambda row: -row.get("gap_pp", 0))
                top = ranked[0] if ranked else None
                summary.append(
                    {
                        "funnel": funnel.code,
                        "run": run.code,
                        "max_gap_pp": top["gap_pp"] if top else 0,
                        "segment": f"{top['channel_label']}·{top['device_label']}" if top else "",
                    }
                )
            db.add(
                AuditLog(
                    actor_email="system@funnelpath",
                    actor_role="system",
                    action="drift.scan",
                    entity="funnel",
                    entity_id=None,
                    detail={"funnels": summary},
                    layer="worker",
                )
            )
            db.commit()
        _redis().set(DRIFT_KEY, json.dumps({"scanned_at": int(time.time()), "funnels": summary}, ensure_ascii=False))
        return {"funnels": len(summary)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("drift scan failed: %s", exc)
        return {"funnels": 0, "error": str(exc)}


def worker_heartbeat_age() -> float | None:
    try:
        value = _redis().get(HEARTBEAT_KEY)
        if not value:
            return None
        return time.time() - float(value)
    except Exception:
        return None
