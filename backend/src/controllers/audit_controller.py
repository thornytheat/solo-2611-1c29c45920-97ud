"""审计日志控制器（仅增长负责人）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import audit_service


def list_audit(db: Session, limit: int = 80, entity: str | None = None) -> dict:
    rows = audit_service.list_recent(db, limit, entity)
    return {"items": rows, "total": len(rows)}
