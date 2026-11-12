"""SessionPath：压缩后的会话路径（每个用户在每个 run 内一条）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class SessionPath(Base):
    __tablename__ = "session_paths"
    __table_args__ = (
        UniqueConstraint("funnel_id", "run_id", "user_key", name="uq_session_path_user_run"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    funnel_id: Mapped[int] = mapped_column(Integer, ForeignKey("funnel_defs.id"), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("funnel_runs.id"), nullable=False)
    user_key: Mapped[str] = mapped_column(String(24), nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    device: Mapped[str] = mapped_column(String(16), nullable=False)
    path_key: Mapped[str] = mapped_column(String(480), nullable=False)
    path_json: Mapped[list] = mapped_column(JSON, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    drop_step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    terminal_event: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    is_converted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
