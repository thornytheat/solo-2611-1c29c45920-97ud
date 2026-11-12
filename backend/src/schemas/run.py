from __future__ import annotations

from pydantic import BaseModel, Field

from src.constants.enums import DEFAULT_WINDOW_DAYS, MAX_WINDOW_DAYS


class RunIn(BaseModel):
    window_days: int = Field(default=DEFAULT_WINDOW_DAYS, ge=1, le=MAX_WINDOW_DAYS)
    note: str = Field(default="", max_length=200)
