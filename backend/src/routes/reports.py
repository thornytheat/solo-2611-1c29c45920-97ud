from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import report_controller
from src.middlewares.rbac import require_permission
from src.schemas.report import ReportIn, ReportPatch

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def list_reports(
    funnel_id: int | None = Query(default=None),
    principal: dict = Depends(require_permission("report:read")),
    db: Session = Depends(get_db),
) -> dict:
    return report_controller.list_reports(db, funnel_id)


@router.post("")
def create_report(
    payload: ReportIn,
    principal: dict = Depends(require_permission("report:write")),
    db: Session = Depends(get_db),
) -> dict:
    return report_controller.create_report(db, payload, principal)


@router.get("/{report_id}")
def get_report(
    report_id: int,
    principal: dict = Depends(require_permission("report:read")),
    db: Session = Depends(get_db),
) -> dict:
    return report_controller.get_report(db, report_id)


@router.patch("/{report_id}")
def patch_report(
    report_id: int,
    payload: ReportPatch,
    request: Request,
    principal: dict = Depends(require_permission("report:write")),
    db: Session = Depends(get_db),
) -> dict:
    return report_controller.patch_report(db, report_id, payload, principal, request)
