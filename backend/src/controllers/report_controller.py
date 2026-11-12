"""归因报告控制器：生成 / 列表 / 详情 / 复核流转。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.models.funnel import FunnelDef
from src.schemas.report import ReportIn, ReportPatch
from src.services import audit_service, report_service, run_service


def create_report(db: Session, payload: ReportIn, actor: dict) -> dict:
    run, funnel = run_service.get_run(db, payload.run_id)
    report = report_service.create(db, run, funnel, payload, actor["email"])
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="report.create",
        entity="report",
        entity_id=report.id,
        detail={
            "funnel": funnel.code,
            "drop_step": report.drop_step_label,
            "cohort_users": report.cohort_users,
            "paths": len(report.top_paths or []),
        },
    )
    db.commit()
    return {"report": report_service.serialize(report, funnel)}


def list_reports(db: Session, funnel_id: int | None = None) -> dict:
    rows = report_service.list_reports(db, funnel_id)
    return {"items": rows, "total": len(rows)}


def get_report(db: Session, report_id: int) -> dict:
    report = report_service.get(db, report_id)
    funnel = db.get(FunnelDef, report.funnel_id)
    run, _ = run_service.get_run(db, report.run_id)
    return {
        "report": report_service.serialize(report, funnel),
        "run": run_service.serialize(run, funnel),
    }


def patch_report(db: Session, report_id: int, payload: ReportPatch, actor: dict, request: Request) -> dict:
    report = report_service.get(db, report_id)
    report = report_service.patch(db, report, payload, actor["role"], actor["email"])
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="report.update",
        entity="report",
        entity_id=report.id,
        detail={"status": report.status, "version": report.version},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    funnel = db.get(FunnelDef, report.funnel_id)
    return {"report": report_service.serialize(report, funnel)}
