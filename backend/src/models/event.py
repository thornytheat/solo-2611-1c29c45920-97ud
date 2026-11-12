"""EventLog：埋点事件流（含乱序 seq 与重复上报，由算法折叠）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class EventLog(Base):
    __tablename__ = "event_logs"
    __table_args__ = (
        Index("ix_event_logs_user_ts", "user_key", "event_ts"),
        Index("ix_event_logs_event", "event_name"),
        Index("ix_event_logs_channel", "channel", "device"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seed_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    user_key: Mapped[str] = mapped_column(String(24), nullable=False)
    event_name: Mapped[str] = mapped_column(String(48), nullable=False)
    event_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    session_id: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    channel: Mapped[str] = mapped_column(String(24), nullable=False, default="organic")
    device: Mapped[str] = mapped_column(String(16), nullable=False, default="ios")
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="fixture")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
