from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.constants.enums import DEFAULT_WINDOW_DAYS, MAX_WINDOW_DAYS


class StepIn(BaseModel):
    key: str = Field(min_length=1, max_length=24)
    label: str = Field(min_length=1, max_length=40)
    event: str = Field(min_length=1, max_length=48)


class FunnelIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=400)
    line_no: str = Field(default="L1", max_length=8)
    line_color: str = Field(default="line-a", max_length=32)
    steps: list[StepIn] = Field(min_length=2, max_length=8)
    noise_events: list[str] = Field(default_factory=list)
    window_days: int = Field(default=DEFAULT_WINDOW_DAYS, ge=1, le=MAX_WINDOW_DAYS)
    cross_session: bool = True
    code: str | None = Field(default=None, max_length=64)

    @field_validator("steps")
    @classmethod
    def _distinct_events(cls, value: list[StepIn]) -> list[StepIn]:
        events = [step.event for step in value]
        if len(set(events)) != len(events):
            raise ValueError("步骤事件不能重复")
        return value


class FunnelPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    line_no: str | None = Field(default=None, max_length=8)
    line_color: str | None = Field(default=None, max_length=32)
    steps: list[StepIn] | None = Field(default=None, min_length=2, max_length=8)
    noise_events: list[str] | None = None
    window_days: int | None = Field(default=None, ge=1, le=MAX_WINDOW_DAYS)
    cross_session: bool | None = None


class TrialIn(BaseModel):
    """试算：不落库，直接跑一次状态机看每步人数。"""

    steps: list[StepIn] = Field(min_length=2, max_length=8)
    window_days: int = Field(default=DEFAULT_WINDOW_DAYS, ge=1, le=MAX_WINDOW_DAYS)
    noise_events: list[str] = Field(default_factory=list)
