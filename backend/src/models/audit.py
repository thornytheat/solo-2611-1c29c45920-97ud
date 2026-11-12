"""审计日志：HTTP 层（中间件）+ 领域动作（controller/service）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seed_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    actor_email: Mapped[str] = mapped_column(String(160), nullable=False, default="anonymous")
    actor_role: Mapped[str] = mapped_column(String(24), nullable=False, default="anonymous")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity: Mapped[str] = mapped_column(String(48), nullable=False, default="api")
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    layer: Mapped[str] = mapped_column(String(16), nullable=False, default="domain")
    detail: Mapped[dict] = mapped_column(JSON, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
