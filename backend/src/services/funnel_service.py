"""FunnelDef 服务：定义 CRUD / 发布 / 试算。"""
from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import FunnelStatus, label_of_channel
from src.constants import error_codes
from src.models.event import EventLog
from src.models.funnel import FunnelDef
from src.schemas.funnel import FunnelIn, FunnelPatch
from src.services import funnel_engine
from src.utils.errors import conflict, not_found


def serialize(funnel: FunnelDef) -> dict:
    return {
        "id": funnel.id,
        "code": funnel.code,
        "name": funnel.name,
        "description": funnel.description,
        "line_no": funnel.line_no,
        "line_color": funnel.line_color,
        "steps": funnel.steps,
        "noise_events": funnel.noise_events,
        "window_days": funnel.window_days,
        "cross_session": funnel.cross_session,
        "status": funnel.status,
        "version": funnel.version,
        "owner_email": funnel.owner_email,
        "step_count": len(funnel.steps),
        "updated_at": funnel.updated_at.isoformat() if funnel.updated_at else None,
    }


def list_funnels(db: Session, status: str | None = None) -> list[dict]:
    stmt = select(FunnelDef).order_by(FunnelDef.line_no, FunnelDef.id)
    if status:
        stmt = select(FunnelDef).where(FunnelDef.status == status).order_by(FunnelDef.line_no, FunnelDef.id)
    return [serialize(row) for row in db.scalars(stmt).all()]


def get_by_id(db: Session, funnel_id: int) -> FunnelDef:
    funnel = db.get(FunnelDef, funnel_id)
    if funnel is None:
        raise not_found({"funnel_id": funnel_id})
    return funnel


def get_by_code(db: Session, code: str) -> FunnelDef:
    funnel = db.scalar(select(FunnelDef).where(FunnelDef.code == code))
    if funnel is None:
        raise not_found({"code": code})
    return funnel


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


def create(db: Session, payload: FunnelIn, owner_email: str) -> FunnelDef:
    code = (payload.code or _slug(payload.name)).lower()
    if db.scalar(select(FunnelDef).where(FunnelDef.code == code)):
        raise conflict({"code": code})
    existing_lines = db.scalar(select(func.count()).select_from(FunnelDef)) or 0
    funnel = FunnelDef(
        code=code,
        name=payload.name,
        description=payload.description,
        line_no=payload.line_no or f"L{existing_lines + 1}",
        line_color=payload.line_color,
        steps=[step.model_dump() for step in payload.steps],
        noise_events=payload.noise_events,
        window_days=payload.window_days,
        cross_session=payload.cross_session,
        status=FunnelStatus.DRAFT.value,
        owner_email=owner_email,
    )
    db.add(funnel)
    db.flush()
    return funnel


def update(db: Session, funnel: FunnelDef, payload: FunnelPatch) -> FunnelDef:
    data = payload.model_dump(exclude_unset=True)
    steps = data.pop("steps", None)
    if steps is not None:
        funnel.steps = [step if isinstance(step, dict) else step for step in steps]
    for key, value in data.items():
        if value is not None:
            setattr(funnel, key, value)
    funnel.version = (funnel.version or 1) + 1
    db.flush()
    return funnel


def publish(db: Session, funnel: FunnelDef) -> FunnelDef:
    if funnel.status == FunnelStatus.ARCHIVED.value:
        raise conflict({"status": funnel.status})
    funnel.status = FunnelStatus.PUBLISHED.value
    funnel.version = (funnel.version or 1) + 1
    db.flush()
    return funnel


def trial(db: Session, steps: list[dict], window_days: int, noise_events: list[str]) -> dict:
    """试算：直接对全量事件跑一次状态机，不写库。"""
    vocabulary = {step["event"] for step in steps} | set(noise_events)
    rows = db.scalars(
        select(EventLog)
        .where(EventLog.event_name.in_(list(vocabulary)))
        .order_by(EventLog.user_key, EventLog.event_ts, EventLog.seq)
    ).all()
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        grouped[row.user_key].append(row)
    result = funnel_engine.run_funnel(grouped, steps, window_days, vocabulary)
    return {
        "steps": result["steps"],
        "duration": result["duration"],
        "discard": result["discard"],
        "entry_users": result["entry_users"],
        "converted_users": result["converted_users"],
        "window_days": window_days,
    }


def channels_summary(db: Session) -> list[dict]:
    rows = db.execute(
        select(EventLog.channel, func.count(func.distinct(EventLog.user_key))).group_by(EventLog.channel)
    ).all()
    return [{"channel": row[0], "label": label_of_channel(row[0]), "users": int(row[1])} for row in rows]
