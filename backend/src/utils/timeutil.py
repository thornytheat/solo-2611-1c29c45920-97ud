"""时间工具：固定业务时区（UTC+8），不做系统时区推断。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.config.settings import settings

BIZ_TZ = timezone(timedelta(minutes=settings.app_timezone_offset_minutes))


def now_biz() -> datetime:
    return datetime.now(BIZ_TZ)


def to_biz(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=BIZ_TZ)
    return value.astimezone(BIZ_TZ)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return to_biz(value).isoformat()


def day_index(value: datetime, anchor: datetime) -> int:
    return (to_biz(value).date() - to_biz(anchor).date()).days


def humanize_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{int(seconds)} 秒"
    if seconds < 3600:
        return f"{seconds / 60:.1f} 分钟"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} 小时"
    return f"{seconds / 86400:.2f} 天"
