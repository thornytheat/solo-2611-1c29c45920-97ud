from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import run_controller
from src.middlewares.rbac import require_permission
from src.schemas.run import RunIn

router = APIRouter(tags=["runs"])


@router.post("/funnels/{funnel_id}/runs")
def execute_run(
    funnel_id: int,
    payload: RunIn,
    request: Request,
    principal: dict = Depends(require_permission("run:execute")),
    db: Session = Depends(get_db),
) -> dict:
    return run_controller.execute_run(db, funnel_id, payload, principal, request)


@router.get("/runs")
def list_runs(
    funnel_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    principal: dict = Depends(require_permission("run:read")),
    db: Session = Depends(get_db),
) -> dict:
    return run_controller.list_runs(db, funnel_id, limit)


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    principal: dict = Depends(require_permission("run:read")),
    db: Session = Depends(get_db),
) -> dict:
    return run_controller.get_run(db, run_id)
