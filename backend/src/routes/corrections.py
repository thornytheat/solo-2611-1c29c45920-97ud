from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import correction_controller
from src.middlewares.rbac import require_permission
from src.schemas.correction import CorrectionIn

router = APIRouter(tags=["corrections"])


@router.post("/funnels/{funnel_id}/corrections")
def apply_correction(
    funnel_id: int,
    payload: CorrectionIn,
    request: Request,
    principal: dict = Depends(require_permission("run:execute")),
    db: Session = Depends(get_db),
) -> dict:
    """事件补录 + 校正运行 + 原子切换（单事务，失败回滚保留上一版）。"""
    return correction_controller.apply_correction(db, funnel_id, payload, principal, request)


@router.get("/corrections")
def list_corrections(
    funnel_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    principal: dict = Depends(require_permission("run:read")),
    db: Session = Depends(get_db),
) -> dict:
    return correction_controller.list_corrections(db, funnel_id, limit)


@router.get("/corrections/{batch_code}")
def get_correction(
    batch_code: str,
    principal: dict = Depends(require_permission("run:read")),
    db: Session = Depends(get_db),
) -> dict:
    return correction_controller.get_correction(db, batch_code)


@router.get("/funnels/{funnel_id}/data-versions")
def list_versions(
    funnel_id: int,
    principal: dict = Depends(require_permission("run:read")),
    db: Session = Depends(get_db),
) -> dict:
    return correction_controller.list_versions(db, funnel_id)
