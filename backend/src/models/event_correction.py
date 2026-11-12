"""EventCorrection：事件补录批次的逐行登记（含迟到 / 重复判定与拒绝原因）。

同一批次用 batch_code 归并；每一行在进入校正事务时先做身份判定：
- fingerprint = sha256(user|event|event_ts(秒)|seq) 作为补录行的自然身份，UNIQUE 防重放；
- 与 event_logs 已存在的「同用户同事件同秒」记录冲突 => 重复，拒绝入库（不能让同一事件多算）；
- event_ts 早于基线水位 => 迟到（迟到但不重复仍会入库，由状态机按事件时间纠正顺序）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base
from src.constants.enums import CorrectionKind, CorrectionRowStatus


class EventCorrection(Base):
    __tablename__ = "event_corrections"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_event_correction_fingerprint"),
        Index("ix_event_correction_batch", "batch_code"),
        Index("ix_event_correction_funnel", "funnel_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_code: Mapped[str] = mapped_column(String(64), nullable=False)
    funnel_id: Mapped[int] = mapped_column(Integer, ForeignKey("funnel_defs.id"), nullable=False)
    data_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("data_versions.id"), nullable=True
    )
    user_key: Mapped[str] = mapped_column(String(24), nullable=False)
    event_name: Mapped[str] = mapped_column(String(48), nullable=False)
    event_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    session_id: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    channel: Mapped[str] = mapped_column(String(24), nullable=False, default="organic")
    device: Mapped[str] = mapped_column(String(16), nullable=False, default="ios")
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="backfill")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=CorrectionRowStatus.STAGED.value)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default=CorrectionKind.NORMAL.value)
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of_event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("event_logs.id"), nullable=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 判定时的上下文快照（水位线 / 冲突行 id），便于结果页展示前后差异
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
