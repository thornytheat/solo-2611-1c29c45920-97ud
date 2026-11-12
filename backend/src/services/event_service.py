"""EventLog 查询：筛选 + 分页 + 事件字典统计。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import CHANNEL_LABELS, DEVICE_LABELS, label_of_event
from src.models.event import EventLog
from src.utils.timeutil import iso


def serialize(row: EventLog) -> dict:
    return {
        "id": row.id,
        "user_key": row.user_key,
        "event_name": row.event_name,
        "event_label": label_of_event(row.event_name),
        "event_ts": iso(row.event_ts),
        "seq": row.seq,
        "session_id": row.session_id,
        "channel": row.channel,
        "channel_label": CHANNEL_LABELS.get(row.channel, row.channel),
        "device": row.device,
        "device_label": DEVICE_LABELS.get(row.device, row.device),
    }


def list_events(
    db: Session,
    *,
    funnel_vocabulary: set[str] | None = None,
    user_key: str | None = None,
    event_name: str | None = None,
    channel: str | None = None,
    device: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[dict], int]:
    conditions = []
    if funnel_vocabulary:
        conditions.append(EventLog.event_name.in_(list(funnel_vocabulary)))
    if user_key:
        conditions.append(EventLog.user_key == user_key.strip())
    if event_name:
        conditions.append(EventLog.event_name == event_name)
    if channel:
        conditions.append(EventLog.channel == channel)
    if device:
        conditions.append(EventLog.device == device)

    stmt = select(EventLog)
    count_stmt = select(func.count()).select_from(EventLog)
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = int(db.scalar(count_stmt) or 0)
    rows = db.scalars(stmt.order_by(EventLog.event_ts.desc(), EventLog.seq.desc()).offset(offset).limit(limit)).all()
    return [serialize(row) for row in rows], total


def vocabulary_stats(db: Session, vocabulary: set[str]) -> list[dict]:
    if not vocabulary:
        return []
    rows = db.execute(
        select(EventLog.event_name, func.count())
        .where(EventLog.event_name.in_(list(vocabulary)))
        .group_by(EventLog.event_name)
        .order_by(func.count().desc())
    ).all()
    return [
        {"event": row[0], "label": label_of_event(row[0]), "count": int(row[1])}
        for row in rows
    ]
