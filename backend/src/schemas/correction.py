from __future__ import annotations

from pydantic import BaseModel, Field

from src.constants.enums import Channel, Device


class CorrectionEventIn(BaseModel):
    user_key: str = Field(min_length=1, max_length=24)
    event_name: str = Field(min_length=1, max_length=48)
    # ISO 8601；服务层统一转 naive 业务时区
    event_ts: str = Field(min_length=4, max_length=40)
    seq: int = Field(default=0, ge=0)
    session_id: str = Field(default="", max_length=48)
    channel: Channel = Channel.ORGANIC
    device: Device = Device.IOS
    source: str = Field(default="backfill", max_length=24)


class CorrectionIn(BaseModel):
    note: str = Field(default="事件补录校正", max_length=200)
    events: list[CorrectionEventIn] = Field(min_length=1, max_length=500)
