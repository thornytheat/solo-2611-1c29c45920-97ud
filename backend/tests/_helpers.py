"""测试共用：轻量事件行（与 EventLog 同名字段）+ 真实 seed 的漏斗口径。

算法引擎只依赖事件行的 6 个属性（user_key / event_name / event_ts / seq /
channel / device），不依赖 SQLAlchemy Session，因此单测用本模块的 frozen
dataclass 构造输入即可，不连数据库、不 mock 算法。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# 与 scripts/demo_config.py 的 ANCHOR 一致（UTC+8 的 2026-09-01 08:00，
# 这里用 naive datetime 与 EventLog.event_ts 的存储方式保持一致）。
ANCHOR = datetime(2026, 9, 1, 8, 0, 0)


@dataclass(frozen=True)
class Event:
    """EventLog 的测试替身：字段名与 ORM 模型一致，但只是普通数据。"""

    user_key: str
    event_name: str
    event_ts: datetime
    seq: int = 0
    channel: str = "organic"
    device: str = "ios"


def ev(
    user_key: str,
    event_name: str,
    offset_hours: float,
    seq: int = 0,
    channel: str = "organic",
    device: str = "ios",
) -> Event:
    """按「相对 ANCHOR 的小时偏移」构造一条事件。"""
    return Event(
        user_key=user_key,
        event_name=event_name,
        event_ts=ANCHOR + timedelta(hours=offset_hours),
        seq=seq,
        channel=channel,
        device=device,
    )


# 与 demo_config.FUNNELS[0]（signup-trial-pay）完全一致的步骤与白名单。
STEPS3 = [
    {"key": "register", "label": "注册", "event": "register"},
    {"key": "trial", "label": "试听完成", "event": "trial_complete"},
    {"key": "pay", "label": "付费", "event": "pay"},
]
STEPS2 = STEPS3[:2]
VOCAB_A = {
    "register",
    "trial_complete",
    "pay",
    "browse_course",
    "trial_start",
    "trial_short_stay",
    "trial_incomplete",
    "pricing_view",
    "consult_chat",
    "course_compare",
    "exit",
}
