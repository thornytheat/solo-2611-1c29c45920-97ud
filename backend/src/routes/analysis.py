from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import run_controller
from src.middlewares.rbac import require_permission

router = APIRouter(tags=["analysis"])


@router.get("/runs/{run_id}/paths")
def paths(
    run_id: int,
    step_index: int | None = Query(default=None, ge=1, le=8),
    principal: dict = Depends(require_permission("run:read")),
    db: Session = Depends(get_db),
) -> dict:
    return run_controller.paths(db, run_id, step_index)
