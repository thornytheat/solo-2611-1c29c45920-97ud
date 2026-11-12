"""审计：领域动作统一落库，HTTP 层动作由中间件写入。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.audit import AuditLog


def record(
    db: Session,
    *,
    actor_email: str,
    actor_role: str,
    action: str,
    entity: str,
    entity_id: str | None = None,
    detail: dict | None = None,
    layer: str = "domain",
    ip: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            detail=detail or {},
            layer=layer,
            ip=ip,
        )
    )


def list_recent(db: Session, limit: int = 80, entity: str | None = None) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if entity:
        stmt = select(AuditLog).where(AuditLog.entity == entity).order_by(AuditLog.id.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    return [
        {
            "id": row.id,
            "actor_email": row.actor_email,
            "actor_role": row.actor_role,
            "action": row.action,
            "entity": row.entity,
            "entity_id": row.entity_id,
            "layer": row.layer,
            "detail": row.detail,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
