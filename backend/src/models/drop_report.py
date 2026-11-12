"""DropReport：归因报告（流失步骤 / Top 前置路径 / 卡点事件 / 分群差）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base
from src.constants.enums import ReportStatus


class DropReport(Base):
    __tablename__ = "drop_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    funnel_id: Mapped[int] = mapped_column(Integer, ForeignKey("funnel_defs.id"), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("funnel_runs.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    drop_step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    drop_step_label: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    cohort_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_paths: Mapped[list] = mapped_column(JSON, nullable=False)
    choke_points: Mapped[list] = mapped_column(JSON, nullable=False)
    segment_gap: Mapped[dict] = mapped_column(JSON, nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ReportStatus.DRAFT.value)
    author_email: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    reviewer_email: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
