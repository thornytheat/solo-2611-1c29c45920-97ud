"""账号：三角色（admin / analyst / viewer）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base
from src.constants.enums import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False, default=Role.VIEWER.value)
    team: Mapped[str] = mapped_column(String(80), nullable=False, default="增长产品组")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def as_public(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "team": self.team,
        }
