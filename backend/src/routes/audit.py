from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import audit_controller
from src.middlewares.rbac import require_permission

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    limit: int = Query(default=80, ge=1, le=200),
    entity: str | None = Query(default=None),
    principal: dict = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
) -> dict:
    return audit_controller.list_audit(db, limit, entity)
