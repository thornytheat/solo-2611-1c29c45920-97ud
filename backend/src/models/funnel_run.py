"""FunnelRun：一次漏斗计算（步骤人数 / 耗时 / 丢弃原因 / 分群矩阵）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, func
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
    # ---- 版本绑定：每个 run 都冻结当时的配置与数据版本 ----
    data_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("data_versions.id"), nullable=True, index=True
    )
    # 校正运行指向它所校正的基线运行；普通运行为 None
    baseline_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("funnel_runs.id"), nullable=True, index=True
    )
    # 冻结的漏斗配置快照（steps/window/cross_session/noise/funnel_version）
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    data_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # 是否仍是该漏斗的当前结论；同一漏斗至多一个 current（校正切换原子翻转）
    is_current: Mapped[bool] = mapped_column(
        # 服务层保证唯一；MySQL 用 TINYINT(1)，SQLite 用 INTEGER
        Boolean, nullable=False, default=True, index=True
    )
    # 校正差异（仅 trigger=correction 有值）：见 correction_service.build_correction
    correction_meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
