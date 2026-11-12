"""演示数据契约：行知教育增长组埋点 fixture 的全部常量。

设计原则：**全部确定性**，不用随机数。用户按「渠道 × 设备 × 路径原型」逐行分配，
因此两次 seed 的每个计数完全一致；主流程验收里的 6000 / 3180 / 742 / 1.8 天 /
31.4% / 58.2% / +12.6pp 都是由这里的计数**构造**出来的，不是写死的结果。
"""
from __future__ import annotations

from datetime import datetime

DEMO_PASSWORD = "Demo@2026"

DEMO_USERS = (
    ("admin@funnelpath.io", "林知远", "admin"),
    ("analyst@funnelpath.io", "苏澜", "analyst"),
    ("viewer@funnelpath.io", "周雨桐", "viewer"),
)

# 数据窗口起点（UTC+8 的 2026-09-01 08:00），所有埋点时间由此推导
ANCHOR = datetime(2026, 9, 1, 8, 0, 0)

TARGET_USERS = 6000
TARGET_EVENTS = 36000
DUPLICATE_EVENTS = 1080          # 3.0% 重复上报
DUPLICATE_STRIDE = 32            # 每 32 个唯一事件复制 1 条
OUT_OF_ORDER_STRIDE = 20         # 每 20 个事件里有 1 个被「提前入库」（5%）

FUNNELS = (
    {
        "code": "signup-trial-pay",
        "name": "注册 → 试听完成 → 付费",
        "description": "K12 素养课主转化链路。跨会话、跨天，是现在手写 SQL 最容易拼错的一段。",
        "line_no": "L1",
        "line_color": "line-a",
        "steps": [
            {"key": "register", "label": "注册", "event": "register"},
            {"key": "trial", "label": "试听完成", "event": "trial_complete"},
            {"key": "pay", "label": "付费", "event": "pay"},
        ],
        "noise_events": [
            "browse_course",
            "trial_start",
            "trial_short_stay",
            "trial_incomplete",
            "pricing_view",
            "consult_chat",
            "course_compare",
            "exit",
        ],
        "window_days": 7,
        "cross_session": True,
        "status": "published",
    },
    {
        "code": "browse-cart-order",
        "name": "浏览商品 → 加购 → 下单",
        "description": "教具商城的辅助链路：验证窗口 3 天时有多少人超窗丢单。",
        "line_no": "L2",
        "line_color": "line-b",
        "steps": [
            {"key": "browse_item", "label": "浏览商品", "event": "browse_item"},
            {"key": "add_cart", "label": "加购", "event": "add_cart"},
            {"key": "order", "label": "下单", "event": "order"},
        ],
        "noise_events": ["exit"],
        "window_days": 3,
        "cross_session": True,
        "status": "published",
    },
    {
        "code": "coupon-redeem",
        "name": "领券 → 核销",
        "description": "运营发券后的核销链路，单会话内完成即可，跨会话开关关闭。",
        "line_no": "L3",
        "line_color": "line-c",
        "steps": [
            {"key": "claim_coupon", "label": "领券", "event": "claim_coupon"},
            {"key": "redeem_coupon", "label": "核销", "event": "redeem_coupon"},
        ],
        "noise_events": ["exit"],
        "window_days": 5,
        "cross_session": False,
        "status": "published",
    },
)

# 路径原型（事件序列）。每个计数都在 SEGMENT_ROWS 里逐行给死。
ARCHETYPE_SHAPES = {
    "pay": ["register", "browse_course", "trial_start", "trial_complete", "pay", "exit"],
    "price": ["register", "browse_course", "trial_complete", "pricing_view", "exit"],
    "consult": ["register", "browse_course", "trial_complete", "consult_chat", "exit"],
    "consult_compare": [
        "register",
        "browse_course",
        "trial_complete",
        "consult_chat",
        "course_compare",
        "exit",
    ],
    "compare": ["register", "browse_course", "trial_complete", "course_compare", "exit"],
    "trial_short": ["register", "browse_course", "trial_short_stay", "exit"],
    "trial_incomplete": ["register", "browse_course", "trial_incomplete", "exit"],
    "browse": ["register", "browse_course", "exit"],
    "register_only": ["register", "exit"],
}

# 「试听未完成」不是一个动作，而是 4 条可区分的前置路径；卡点按末事件聚合，
# 路径榜按具体序列排名 —— 所以 58.2% 的卡点由多条路径共同贡献，单条最大的是
# 「试听页停留<30s」那条（31.4%，验收里的 Top1）。
INCOMPLETE_VARIANTS = (
    ("inc_plain", 700, ["register", "browse_course", "trial_incomplete", "exit"]),
    ("inc_trial_start", 480, ["register", "browse_course", "trial_start", "trial_incomplete", "exit"]),
    ("inc_consult", 300, ["register", "browse_course", "consult_chat", "trial_incomplete", "exit"]),
    (
        "inc_short_stay",
        161,
        ["register", "browse_course", "trial_start", "trial_short_stay", "trial_incomplete", "exit"],
    ),
)

# 会走到「试听完成」的用户原型（这 3180 人贡献 register→trial 的步间耗时样本）
TRIAL_REACHING = ("pay", "price", "consult", "consult_compare", "compare")
# 只到注册就流失的原型（这 2820 人贡献「试听完成」步的流失队列）
TRIAL_DROPPING = ("trial_short", "trial_incomplete", "browse", "register_only")

# 渠道 × 设备 × 路径原型的人数矩阵（行内 conv/drop 之和 = users）
SEGMENT_ROWS = (
    {
        "channel": "organic",
        "device": "ios",
        "conv": {"pay": 140, "price": 165, "consult": 95, "consult_compare": 50, "compare": 130},
        "drop": {"trial_short": 90, "trial_incomplete": 193, "browse": 27, "register_only": 10},
    },
    {
        "channel": "organic",
        "device": "android",
        "conv": {"pay": 150, "price": 175, "consult": 100, "consult_compare": 55, "compare": 140},
        "drop": {"trial_short": 109, "trial_incomplete": 228, "browse": 31, "register_only": 12},
    },
    {
        "channel": "feed",
        "device": "ios",
        "conv": {"pay": 95, "price": 120, "consult": 70, "consult_compare": 37, "compare": 102},
        "drop": {"trial_short": 207, "trial_incomplete": 355, "browse": 41, "register_only": 23},
    },
    {
        "channel": "feed",
        "device": "android",
        "conv": {"pay": 86, "price": 109, "consult": 63, "consult_compare": 34, "compare": 92},
        "drop": {"trial_short": 190, "trial_incomplete": 320, "browse": 35, "register_only": 21},
    },
    {
        "channel": "social",
        "device": "ios",
        "conv": {"pay": 118, "price": 139, "consult": 80, "consult_compare": 43, "compare": 110},
        "drop": {"trial_short": 100, "trial_incomplete": 180, "browse": 20, "register_only": 10},
    },
    {
        "channel": "social",
        "device": "android",
        "conv": {"pay": 84, "price": 99, "consult": 57, "consult_compare": 31, "compare": 79},
        "drop": {"trial_short": 80, "trial_incomplete": 145, "browse": 15, "register_only": 10},
    },
    {
        "channel": "referral",
        "device": "ios",
        "conv": {"pay": 48, "price": 57, "consult": 33, "consult_compare": 18, "compare": 44},
        "drop": {"trial_short": 60, "trial_incomplete": 120, "browse": 12, "register_only": 8},
    },
    {
        "channel": "referral",
        "device": "android",
        "conv": {"pay": 21, "price": 36, "consult": 22, "consult_compare": 12, "compare": 41},
        "drop": {"trial_short": 50, "trial_incomplete": 100, "browse": 12, "register_only": 6},
    },
)

# 步间耗时桶：3180 个「注册→试听完成」+ 742 个「试听完成→付费」
D1_SHORT_COUNT = 1450
D1_EXACT_COUNT = 300
D1_LONG_COUNT = 1430
D1_EXACT_HOURS = 43.2          # 1.8 天，正是验收里的步间 P50
D2_SHORT_COUNT = 510
D2_LONG_COUNT = 232

# 漏斗 B（浏览→加购→下单）：前 1820 个用户参与
B_ORDER_IN_WINDOW = 280
B_ORDER_EXPIRED = 20           # 第 4.5 天下单，窗口 3 天 → expired
B_CART_ABANDON = 500
B_BROWSE_ONLY = 400
B_USER_SPAN = (0, B_ORDER_IN_WINDOW + B_ORDER_EXPIRED + B_CART_ABANDON + B_BROWSE_ONLY)

# 漏斗 C（领券→核销）：索引 4200 起的 953 个用户参与
C_REDEEM = 603
C_CLAIM_ONLY = 350
C_USER_START = 4200
C_USER_SPAN = (C_USER_START, C_USER_START + C_REDEEM + C_CLAIM_ONLY)

# 自检期望值（verify_fixture.py 与 seed 都会校验）
EXPECTED = {
    "users": 6000,
    "unique_events": 34920,
    "duplicate_events": DUPLICATE_EVENTS,
    "events": 36000,
    "funnel_entry": 6000,
    "trial_users": 3180,
    "pay_users": 742,
    "trial_drop_cohort": 2820,
    "step_p50_days": 1.8,
    "top_path_share_pct": 31.4,
    "choke_share_pct": 58.2,
    "max_gap_pp": 12.6,
    "report_paths": 8,
}

# 种子报告：模板化结论（数值由算法回填，不在文案里写死）
SEED_REPORT_CONCLUSION = (
    "「试听完成」是本链路最大的单点流失：从注册到试听完成的 7 天窗口里，"
    "多数人卡在试听页本身（停留过短或中途退出），而不是价格。"
    "信息流渠道 × iOS 的流失率显著高于整体，建议先做试听页的前 30 秒引导与"
    "信息流素材的承诺对齐，再评估价格页改版。"
)
