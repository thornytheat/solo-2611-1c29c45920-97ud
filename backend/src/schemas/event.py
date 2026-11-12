from __future__ import annotations

from pydantic import BaseModel


class EventRowOut(BaseModel):
    id: int
    user_key: str
    event_name: str
    event_label: str
    event_ts: str
    seq: int
    session_id: str
    channel: str
    channel_label: str
    device: str
