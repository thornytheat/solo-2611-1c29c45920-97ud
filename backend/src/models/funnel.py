"""FunnelDef：漏斗定义（步骤序列 / 窗口 / 跨会话 / 版本 / 去噪白名单）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base
from src.constants.enums import FunnelStatus


class FunnelDef(Base):
    __tablename__ = "funnel_defs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 地铁线路视觉：L1 / L2 / L3 + 线路色（oklch 变量名）
    line_no: Mapped[str] = mapped_column(String(8), nullable=False, default="L1")
    line_color: Mapped[str] = mapped_column(String(32), nullable=False, default="line-a")
    steps: Mapped[list] = mapped_column(JSON, nullable=False)
    noise_events: Mapped[list] = mapped_column(JSON, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    cross_session: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=FunnelStatus.DRAFT.value)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    owner_email: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    @property
    def vocabulary(self) -> set[str]:
        names = {step["event"] for step in self.steps}
        names.update(self.noise_events or [])
        return names
