"""DataVersion：一次数据快照版本，绑定当时的漏斗配置与事件指纹。

校正运行的可追溯性核心：
- 每次 run 都冻结一份 config_snapshot（步骤 / 窗口 / 跨会话 / 白名单 / 引擎版本）；
- fingerprint 是该版本事件集合的指纹，任一次补录都会产生新版本；
- parent_version_id 串起版本链，baseline_run_id / correction_run_id 绑定两侧运行；
- 校正事务成功才把新版本置为 active；失败回滚，上一版继续 active（“切换失败保留上一版”）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base
from src.constants.enums import DataVersionStatus


class DataVersion(Base):
    __tablename__ = "data_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    funnel_id: Mapped[int] = mapped_column(Integer, ForeignKey("funnel_defs.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=DataVersionStatus.BUILDING.value)
    parent_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("data_versions.id"), nullable=True
    )
    baseline_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("funnel_runs.id"), nullable=True
    )
    correction_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("funnel_runs.id"), nullable=True
    )
    # 冻结当时的漏斗配置：steps / window_days / cross_session / noise_events / engine_version
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingested_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    late_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # {"max_event_ts": iso, "max_seq": int}：迟到判定的水位线
    watermark: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
