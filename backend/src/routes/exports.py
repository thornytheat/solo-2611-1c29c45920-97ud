from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import export_controller
from src.middlewares.rbac import require_permission
from src.schemas.export import ExportIn

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("")
def export_report(
    payload: ExportIn,
    principal: dict = Depends(require_permission("export:read")),
    db: Session = Depends(get_db),
) -> dict:
    return export_controller.export_report(db, payload, principal)
