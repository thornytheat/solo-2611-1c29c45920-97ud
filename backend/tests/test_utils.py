"""解析 / 归一 / 统计工具单测：分位数、四舍五入、百分比、时间、路径压缩、前缀树、分群。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.services.segment_service import build_segments
from src.utils.pathutil import build_prefix_tree, compress_events, flatten_tree, path_label
from src.utils.stats import median, pct, percentile, round_half_up, seconds_to_days
from src.utils.timeutil import BIZ_TZ, humanize_duration, iso, to_biz

# build_segments 需要每步的 users（分群矩阵与整体流失率都从它算）
STEPS_LABELS = [
    {"label": "注册", "event": "register", "users": 100},
    {"label": "试听完成", "event": "trial_complete", "users": 60},
    {"label": "付费", "event": "pay", "users": 30},
]


# --------------------------------------------------------------- 统计工具 (6)


def test_percentile_empty_single_and_linear_interpolation():
    assert percentile([], 50) is None
    assert percentile([7], 90) == pytest.approx(7.0)
    values = [1, 2, 3, 4]
    assert percentile(values, 25) == pytest.approx(1.75)
    assert percentile(values, 50) == pytest.approx(2.5)
    assert percentile(values, 90) == pytest.approx(3.7)
    assert median(values) == pytest.approx(2.5)


def test_round_half_up_avoids_banker_rounding():
    assert round_half_up(0.45, 1) == pytest.approx(0.5)
    assert round_half_up(0.44, 1) == pytest.approx(0.4)
    assert round_half_up(2.5, 0) == pytest.approx(3.0)
    assert round_half_up(-0.45, 1) == pytest.approx(-0.5)
    assert round_half_up(66.66666, 1) == pytest.approx(66.7)


def test_pct_zero_and_normal():
    assert pct(1, 3) == pytest.approx(33.3)
    assert pct(2, 3) == pytest.approx(66.7)
    assert pct(5, 0) == 0.0
    assert pct(0, 10) == 0.0


def test_seconds_to_days_exact_and_none():
    assert seconds_to_days(155520) == pytest.approx(1.8)
    assert seconds_to_days(86400) == pytest.approx(1.0)
    assert seconds_to_days(None) is None
    assert seconds_to_days(0) == 0.0


def test_timezone_normalisation_and_iso():
    naive = datetime(2026, 9, 1, 8, 0, 0)
    assert iso(naive) == "2026-09-01T08:00:00+08:00"
    assert iso(None) is None
    shifted = to_biz(datetime(2026, 9, 1, 0, 0, 0, tzinfo=BIZ_TZ) - timedelta(days=1))
    assert shifted.utcoffset() == timedelta(hours=8)


def test_humanize_duration_boundaries():
    assert humanize_duration(None) == "—"
    assert humanize_duration(45) == "45 秒"
    assert humanize_duration(90) == "1.5 分钟"
    assert humanize_duration(7200) == "2.0 小时"
    assert humanize_duration(155520) == "1.80 天"


# --------------------------------------------------------------- 路径压缩 / 树 (3)


def test_compress_events_merges_noise_and_terminal():
    events = [
        ("register", "t0"),
        ("register", "t1"),
        ("noise_event", "t2"),
        ("browse_course", "t3"),
        ("exit", "t4"),
    ]
    vocabulary = {"register", "browse_course", "exit"}
    compressed = compress_events(events, vocabulary, depth=6)
    assert [item["event"] for item in compressed] == ["register", "browse_course", "exit"]
    assert [item["label"] for item in compressed] == ["注册", "浏览课程", "退出"]
    assert path_label(compressed) == "注册 → 浏览课程 → 退出"


def test_compress_events_keeps_single_terminal_at_end_only():
    events = [
        ("register", "t0"),
        ("exit", "t1"),
        ("pay", "t2"),
        ("exit", "t3"),
    ]
    compressed = compress_events(events, {"register", "pay", "exit"}, depth=6)
    assert [item["event"] for item in compressed] == ["register", "pay", "exit"]
    # 深度截断作用在压缩后的序列上
    truncated = compress_events(events, {"register", "pay", "exit"}, depth=2)
    assert [item["event"] for item in truncated] == ["register", "pay"]


def test_prefix_tree_counts_children_ordering_and_flatten():
    tree = build_prefix_tree(
        [
            ["register", "browse_course"],
            ["register", "pay"],
            ["register", "pay"],
        ],
        depth=6,
    )
    assert tree["count"] == 3
    register = tree["children"][0]
    assert register["event"] == "register" and register["count"] == 3
    # 按人数降序：pay(2) 在 browse_course(1) 前
    assert [child["event"] for child in register["children"]] == ["pay", "browse_course"]
    flat = flatten_tree(tree)
    assert [(row["path"], row["count"], row["depth"]) for row in flat] == [
        ("注册", 3, 1),
        ("注册 → 付费", 2, 2),
        ("注册 → 浏览课程", 1, 2),
    ]
    assert flat[0]["terminal"] is False
    assert flat[1]["terminal"] is True


# --------------------------------------------------------------- 分群归一 (1)


def test_build_segments_hand_calculated_gap_pp():
    segment_reached = {
        ("feed", "ios"): [40, 30, 10],
        ("organic", "android"): [60, 30, 20],
        # 渠道汇总行（build_segments 会额外读 (channel, None) 的分桶）
        ("feed", None): [40, 30, 10],
        ("organic", None): [60, 30, 20],
    }
    result = build_segments(
        segment_reached,
        STEPS_LABELS,
        step_index=1,
        channel_order=["organic", "feed"],
        device_order=["ios", "android"],
    )
    assert result["overall_users"] == 100
    assert result["overall_dropped"] == 40
    assert result["overall_drop_rate"] == pytest.approx(40.0)
    assert result["max_gap_pp"] == pytest.approx(10.0)
    assert result["top_segment"]["channel"] == "organic"
    assert result["top_segment"]["device"] == "android"

    feed = next(row for row in result["rows"] if row["channel"] == "feed")
    assert (feed["users"], feed["dropped"]) == (40, 10)
    assert feed["drop_rate"] == pytest.approx(25.0)
    assert feed["gap_pp"] == pytest.approx(-15.0)
    assert feed["channel_label"] == "信息流"

    organic_channel = next(row for row in result["channel_rows"] if row["channel"] == "organic")
    assert organic_channel["level"] == "channel"
    assert organic_channel["device_label"] == "全部设备"
    assert organic_channel["gap_pp"] == pytest.approx(10.0)

    # 越界 step_index → 回落到最大流失步（len-1），不抛异常
    fallback = build_segments(segment_reached, STEPS_LABELS, 9, ["organic", "feed"], ["ios", "android"])
    assert fallback["step_index"] == 2
    assert fallback["from_label"] == "试听完成"
