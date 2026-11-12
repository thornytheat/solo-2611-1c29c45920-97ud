from __future__ import annotations

from pydantic import BaseModel, Field

from src.constants.enums import ReportStatus


class ReportIn(BaseModel):
    run_id: int
    drop_step_index: int | None = Field(default=None, ge=1, le=8)
    title: str = Field(min_length=2, max_length=160)
    conclusion: str = Field(default="", max_length=2000)


class ReportPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    conclusion: str | None = Field(default=None, max_length=2000)
    status: ReportStatus | None = None
