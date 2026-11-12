"""FunnelRun：一次漏斗计算（步骤人数 / 耗时 / 丢弃原因 / 分群矩阵）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base
from src.constants.enums import RunStatus, RunTrigger


class FunnelRun(Base):
    __tablename__ = "funnel_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    funnel_id: Mapped[int] = mapped_column(Integer, ForeignKey("funnel_defs.id"), nullable=False)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default=RunTrigger.MANUAL.value)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RunStatus.QUEUED.value)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    step_counts: Mapped[list] = mapped_column(JSON, nullable=False)
    duration_stats: Mapped[dict] = mapped_column(JSON, nullable=False)
    discard: Mapped[dict] = mapped_column(JSON, nullable=False)
    segment_rows: Mapped[list] = mapped_column(JSON, nullable=False)
    entry_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    converted_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engine_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0.0")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
