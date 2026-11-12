from __future__ import annotations

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    db: bool
    redis: bool
    service: str
    version: str = "1.0.0"


class MessageOut(BaseModel):
    ok: bool
    message: str
