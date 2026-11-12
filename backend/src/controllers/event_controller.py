"""埋点事件控制器：筛选分页 + 事件字典统计。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import event_service, funnel_service


def list_events(
    db: Session,
    *,
    funnel_id: int | None = None,
    user_key: str | None = None,
    event_name: str | None = None,
    channel: str | None = None,
    device: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict:
    vocabulary = None
    if funnel_id:
        vocabulary = funnel_service.get_by_id(db, funnel_id).vocabulary
    items, total = event_service.list_events(
        db,
        funnel_vocabulary=vocabulary,
        user_key=user_key,
        event_name=event_name,
        channel=channel,
        device=device,
        limit=limit,
        offset=offset,
    )
    stats = event_service.vocabulary_stats(db, vocabulary) if vocabulary else []
    return {"items": items, "total": total, "limit": limit, "offset": offset, "stats": stats}
