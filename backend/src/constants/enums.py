"""共享枚举（后端侧）：与 frontend/src/constants/enums.ts 一一对应。

README「枚举出现位置」章节列出全部引用点。
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"          # 增长负责人：漏斗定义 / 窗口 / 发布 / 复核
    ANALYST = "analyst"      # 产品分析师：跑漏斗 / 看路径 / 写归因
    VIEWER = "viewer"        # 运营：只读结果


class Channel(str, Enum):
    ORGANIC = "organic"      # 自然搜索
    FEED = "feed"            # 信息流
    SOCIAL = "social"        # 私域社群
    REFERRAL = "referral"    # 转介绍


class Device(str, Enum):
    IOS = "ios"
    ANDROID = "android"


class FunnelStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunTrigger(str, Enum):
    SEED = "seed"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class DropReason(str, Enum):
    """漏斗状态机里被丢弃/中止的原因计数口径。"""

    EXPIRED = "expired"                  # 超窗：命中下一步但已超出窗口
    DUPLICATE = "duplicate"              # 同事件同秒重复上报，折叠
    NEVER_ENTERED = "never_entered"      # 漏斗内事件存在但从未命中首步
    CONVERTED = "converted"              # 走完全部步骤


class ReportStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    PUBLISHED = "published"


class ExportFormat(str, Enum):
    MARKDOWN = "md"
    CSV = "csv"


class CacheJobStatus(str, Enum):
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "增长负责人",
    Role.ANALYST.value: "产品分析师",
    Role.VIEWER.value: "运营（只读）",
}

CHANNEL_LABELS: dict[str, str] = {
    Channel.ORGANIC.value: "自然搜索",
    Channel.FEED.value: "信息流",
    Channel.SOCIAL.value: "私域社群",
    Channel.REFERRAL.value: "转介绍",
}

DEVICE_LABELS: dict[str, str] = {
    Device.IOS.value: "iOS",
    Device.ANDROID.value: "Android",
}

FUNNEL_STATUS_LABELS: dict[str, str] = {
    FunnelStatus.DRAFT.value: "草稿",
    FunnelStatus.PUBLISHED.value: "已发布",
    FunnelStatus.ARCHIVED.value: "已归档",
}

REPORT_STATUS_LABELS: dict[str, str] = {
    ReportStatus.DRAFT.value: "草稿",
    ReportStatus.REVIEWED.value: "已复核",
    ReportStatus.PUBLISHED.value: "已发布",
}

# 埋点事件 -> 中文站名（视觉上是地铁站名牌）
EVENT_LABELS: dict[str, str] = {
    "register": "注册",
    "browse_course": "浏览课程",
    "trial_start": "试听开始",
    "trial_short_stay": "试听页停留<30s",
    "trial_incomplete": "试听未完成",
    "trial_complete": "试听完成",
    "pricing_view": "价格页",
    "consult_chat": "顾问咨询",
    "course_compare": "课程对比",
    "pay": "付费",
    "exit": "退出",
    "browse_item": "浏览商品",
    "add_cart": "加购",
    "order": "下单",
    "claim_coupon": "领券",
    "redeem_coupon": "核销",
}

# 会话结束标记：路径压缩时只保留末尾一次（否则跨会话会切碎路径）
TERMINAL_EVENTS: frozenset[str] = frozenset({"exit"})

DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 30
DEFAULT_PATH_DEPTH = 6
TOP_PATHS_K = 8
SEGMENT_GAP_DECIMALS = 1


def label_of_event(event: str) -> str:
    return EVENT_LABELS.get(event, event)


def label_of_channel(channel: str) -> str:
    return CHANNEL_LABELS.get(channel, channel)


def label_of_device(device: str) -> str:
    return DEVICE_LABELS.get(device, device)
