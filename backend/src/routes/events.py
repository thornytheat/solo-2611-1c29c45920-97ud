from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import event_controller
from src.middlewares.rbac import require_permission

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def list_events(
    funnel_id: int | None = Query(default=None),
    user_key: str | None = Query(default=None),
    event_name: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    device: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: dict = Depends(require_permission("event:read")),
    db: Session = Depends(get_db),
) -> dict:
    return event_controller.list_events(
        db,
        funnel_id=funnel_id,
        user_key=user_key,
        event_name=event_name,
        channel=channel,
        device=device,
        limit=limit,
        offset=offset,
    )
