"""运行控制器：触发漏斗计算 / 运行列表 / 运行详情 / 路径分析。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.enums import RunTrigger
from src.schemas.run import RunIn
from src.services import audit_service, funnel_service, run_service


def execute_run(db: Session, funnel_id: int, payload: RunIn, actor: dict, request: Request) -> dict:
    funnel = funnel_service.get_by_id(db, funnel_id)
    run = run_service.execute(
        db,
        funnel,
        trigger=RunTrigger.MANUAL.value,
        window_days=payload.window_days or funnel.window_days,
    )
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="run.execute",
        entity="run",
        entity_id=run.id,
        detail={
            "funnel": funnel.code,
            "window_days": run.window_days,
            "entry_users": run.entry_users,
            "converted_users": run.converted_users,
            "note": payload.note,
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {"run": run_service.serialize(run, funnel)}


def list_runs(db: Session, funnel_id: int | None = None, limit: int = 20) -> dict:
    rows = run_service.list_runs(db, funnel_id, limit)
    return {"items": rows, "total": len(rows)}


def get_run(db: Session, run_id: int) -> dict:
    run, funnel = run_service.get_run(db, run_id)
    return {"run": run_service.serialize(run, funnel)}


def paths(db: Session, run_id: int, step_index: int | None = None) -> dict:
    run, funnel = run_service.get_run(db, run_id)
    return run_service.path_analysis(db, run, funnel, step_index)
