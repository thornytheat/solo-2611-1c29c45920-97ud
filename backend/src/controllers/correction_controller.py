"""事件补录 / 校正运行控制器：单事务提交，失败回滚保留上一版。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.models.data_version import DataVersion
from src.schemas.correction import CorrectionIn
from src.services import (
    audit_service,
    correction_service,
    data_version_service,
    funnel_service,
    run_service,
)


def apply_correction(db: Session, funnel_id: int, payload: CorrectionIn, actor: dict, request: Request) -> dict:
    funnel = funnel_service.get_by_id(db, funnel_id)
    events = [item.model_dump() for item in payload.events]
    try:
        result = correction_service.apply_correction(
            db,
            funnel,
            events,
            note=payload.note,
            actor_email=actor["email"],
        )
    except Exception:
        # 显式回滚：确保切换失败时旧 run / 旧数据版本继续 current
        db.rollback()
        raise

    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="correction.apply",
        entity="funnel",
        entity_id=funnel.id,
        detail={
            "funnel": funnel.code,
            "batch": result["batch_code"],
            "baseline_run": result["baseline_run"].code,
            "correction_run": result["correction_run"].code,
            "data_version": result["data_version"].code,
            "ingested": result["counters"].get("ingested", 0),
            "rejected_duplicate": result["counters"].get("rejected_duplicate", 0),
            "late": result["counters"].get("late", 0),
            "affected_users": result["correction_meta"]["affected_user_count"],
            "demoted_reports": result["demoted_reports"],
            "note": payload.note,
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()

    correction_run = result["correction_run"]
    version = db.get(DataVersion, correction_run.data_version_id)
    return {
        "batch": correction_service.get_batch(db, result["batch_code"], funnel.id),
        "data_version": data_version_service.serialize(version),
        "baseline_run": run_service.serialize(result["baseline_run"], funnel),
        "correction_run": run_service.serialize(correction_run, funnel, version),
        "correction_meta": result["correction_meta"],
    }


def list_corrections(db: Session, funnel_id: int | None = None, limit: int = 20) -> dict:
    items = correction_service.list_corrections(db, funnel_id, limit)
    return {"items": items, "total": len(items)}


def get_correction(db: Session, batch_code: str) -> dict:
    return {"batch": correction_service.get_batch(db, batch_code)}


def list_versions(db: Session, funnel_id: int) -> dict:
    funnel = funnel_service.get_by_id(db, funnel_id)
    return {"items": data_version_service.list_versions(db, funnel.id)}
