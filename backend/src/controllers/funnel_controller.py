"""漏斗定义控制器：列表 / 详情 / 新建 / 编辑 / 发布 / 试算 / 缓存刷新。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants import error_codes
from src.constants.enums import RunTrigger
from src.schemas.funnel import FunnelIn, FunnelPatch, TrialIn
from src.services import audit_service, cache_service, funnel_service, run_service
from src.utils.errors import conflict


def list_funnels(db: Session, status: str | None = None) -> dict:
    rows = funnel_service.list_funnels(db, status)
    return {"items": rows, "total": len(rows)}


def get_funnel(db: Session, funnel_id: int) -> dict:
    funnel = funnel_service.get_by_id(db, funnel_id)
    latest = run_service.latest_run(db, funnel.id)
    return {
        "funnel": funnel_service.serialize(funnel),
        "latest_run": run_service.serialize(latest, funnel) if latest else None,
        "channels": funnel_service.channels_summary(db),
    }


def create_funnel(db: Session, payload: FunnelIn, actor: dict) -> dict:
    funnel = funnel_service.create(db, payload, actor["email"])
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="funnel.create",
        entity="funnel",
        entity_id=funnel.id,
        detail={"code": funnel.code, "steps": [step["event"] for step in funnel.steps]},
    )
    db.commit()
    return {"funnel": funnel_service.serialize(funnel)}


def update_funnel(db: Session, funnel_id: int, payload: FunnelPatch, actor: dict) -> dict:
    funnel = funnel_service.get_by_id(db, funnel_id)
    funnel = funnel_service.update(db, funnel, payload)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="funnel.update",
        entity="funnel",
        entity_id=funnel.id,
        detail={"version": funnel.version},
    )
    db.commit()
    return {"funnel": funnel_service.serialize(funnel)}


def publish_funnel(db: Session, funnel_id: int, actor: dict) -> dict:
    funnel = funnel_service.get_by_id(db, funnel_id)
    funnel = funnel_service.publish(db, funnel)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="funnel.publish",
        entity="funnel",
        entity_id=funnel.id,
        detail={"version": funnel.version},
    )
    db.commit()
    return {"funnel": funnel_service.serialize(funnel)}


def trial(db: Session, payload: TrialIn) -> dict:
    steps = [step.model_dump() for step in payload.steps]
    return funnel_service.trial(db, steps, payload.window_days, payload.noise_events)


def refresh_cache(db: Session, funnel_id: int, actor: dict) -> dict:
    funnel = funnel_service.get_by_id(db, funnel_id)
    latest = run_service.latest_run(db, funnel.id)
    if latest is None:
        raise conflict({"reason": "该漏斗还没有运行记录，先跑一次漏斗再刷新缓存"})
    result = cache_service.dispatch(funnel.id)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="cache.refresh",
        entity="funnel",
        entity_id=funnel.id,
        detail={"task_id": result["task_id"]},
    )
    db.commit()
    return result


def cache_status(db: Session, funnel_id: int) -> dict:
    funnel_service.get_by_id(db, funnel_id)
    return cache_service.status(funnel_id)
