"""算法 1：用户级漏斗状态机（run_funnel / evaluate_user）纯函数单测。

覆盖：正常计数与转化率、手算分位耗时、窗口边界、零方差、重复折叠、
乱序纠正、never_entered、空输入、单条、空步骤、畸形行、真实 seed 切片。
"""
from __future__ import annotations

import pytest

from src.services import funnel_engine
from tests._helpers import STEPS2, STEPS3, VOCAB_A, Event, ev

D1 = 86400  # 一天的秒数


def _run(rows, steps=STEPS3, window_days=7, vocabulary=VOCAB_A):
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.user_key, []).append(row)
    return funnel_engine.run_funnel(grouped, steps, window_days, vocabulary)


# --------------------------------------------------------------- 正常路径 (3+)


def test_counts_rates_loss_and_hand_calculated_percentiles():
    """4 个用户：1 转化、1 停在试听、1 停在注册、1 从未进入首站。"""
    rows = [
        ev("u1", "register", 0, seq=1),
        ev("u1", "trial_complete", 24, seq=2),
        ev("u1", "pay", 48, seq=3),
        ev("u2", "register", 0, seq=1),
        ev("u2", "trial_complete", 48, seq=2),
        ev("u3", "register", 0, seq=1),
        ev("u4", "trial_complete", 24, seq=1),
        ev("u4", "pay", 48, seq=2),
    ]
    result = _run(rows)

    assert result["entry_users"] == 3
    assert result["converted_users"] == 1
    assert [step["users"] for step in result["steps"]] == [3, 2, 1]

    step0, step1, step2 = result["steps"]
    assert step0["rate_from_prev"] == pytest.approx(100.0)
    assert step0["rate_from_entry"] == pytest.approx(100.0)
    assert step1["rate_from_prev"] == pytest.approx(66.7)
    assert step1["rate_from_entry"] == pytest.approx(66.7)
    assert step1["lost"] == 1 and step1["lost_share"] == pytest.approx(33.3)
    assert step2["rate_from_prev"] == pytest.approx(50.0)
    assert step2["rate_from_entry"] == pytest.approx(33.3)
    assert step2["lost"] == 1 and step2["lost_share"] == pytest.approx(33.3)

    # 手算：注册→试听样本 [86400, 172800]；试听→付费样本 [86400]
    assert result["transitions"][0]["samples"] == 2
    assert result["transitions"][0]["p50_seconds"] == pytest.approx(129600.0)
    assert result["transitions"][0]["p50_days"] == pytest.approx(1.5)
    assert result["transitions"][0]["p90_seconds"] == pytest.approx(164160.0)
    assert result["transitions"][0]["p90_days"] == pytest.approx(1.9)
    assert result["transitions"][0]["mean_seconds"] == pytest.approx(129600.0)
    assert result["transitions"][1]["samples"] == 1
    assert result["transitions"][1]["p50_seconds"] == pytest.approx(float(D1))

    # 全部步间样本 [86400, 172800, 86400] → p50=86400, p90=155520, mean=115200
    assert result["duration"]["samples"] == 3
    assert result["duration"]["p50_seconds"] == pytest.approx(86400.0)
    assert result["duration"]["p50_days"] == pytest.approx(1.0)
    assert result["duration"]["p90_seconds"] == pytest.approx(155520.0)
    assert result["duration"]["p90_days"] == pytest.approx(1.8)
    assert result["duration"]["mean_seconds"] == pytest.approx(115200.0)

    assert result["discard"] == {
        "expired": 0,
        "duplicates_collapsed": 0,
        "never_entered": 1,
        "converted": 1,
        "out_of_order_events": 0,
        "out_of_order_users": 0,
        "users": 3,
    }


def test_seed_slice_matches_hand_counted_archetypes():
    """真实 seed 的一小段：9 个原型用户 → 9 进 / 5 试听 / 1 付费。"""
    from scripts.fixture import build_fixture
    from scripts import demo_config as cfg

    _, rows = build_fixture()
    picked = {"U0001", "U0141", "U0306", "U0401", "U0451",
              "U0581", "U0671", "U0864", "U0891"}
    slice_rows = [row for row in rows if row["user_key"] in picked and row["event_name"] in VOCAB_A]
    assert len(slice_rows) > 0

    grouped: dict[str, list] = {}
    for row in slice_rows:
        grouped.setdefault(row["user_key"], []).append(
            Event(
                user_key=row["user_key"],
                event_name=row["event_name"],
                event_ts=row["event_ts"],
                seq=row["seq"],
                channel=row["channel"],
                device=row["device"],
            )
        )
    result = funnel_engine.run_funnel(grouped, [dict(s) for s in cfg.FUNNELS[0]["steps"]], 7, VOCAB_A)

    assert result["entry_users"] == 9
    assert [step["users"] for step in result["steps"]] == [9, 5, 1]
    assert result["converted_users"] == 1
    assert result["steps"][1]["rate_from_prev"] == pytest.approx(55.6)
    assert result["steps"][2]["rate_from_prev"] == pytest.approx(20.0)
    assert result["discard"]["expired"] == 0
    assert result["discard"]["never_entered"] == 0
    # 试听→付费队列 4 人（price/consult/consult_compare/compare）
    assert result["steps"][1]["lost"] == 4


def test_step_labels_and_keys_come_from_definition():
    result = _run([ev("u1", "register", 0, seq=1), ev("u1", "pay", 1, seq=2)])
    assert [step["label"] for step in result["steps"]] == ["注册", "试听完成", "付费"]
    assert [step["key"] for step in result["steps"]] == ["register", "trial", "pay"]
    assert [step["event"] for step in result["steps"]] == ["register", "trial_complete", "pay"]
    # 只有首步：step1/step2 人数为 0，不是 None
    assert result["steps"][1]["users"] == 0
    assert result["steps"][2]["users"] == 0


# --------------------------------------------------------------- 边界 (3+)


def test_window_boundary_is_strictly_greater_than_window():
    """恰好 7 天算窗口内；7 天 + 1 秒才算超窗。"""
    rows = [
        ev("in", "register", 0, seq=1),
        ev("in", "trial_complete", 168, seq=2),
        ev("out", "register", 0, seq=1),
        ev("out", "trial_complete", 168 + 1 / 3600, seq=2),  # +1 秒
    ]
    result = _run(rows, steps=STEPS2, window_days=7)
    assert [step["users"] for step in result["steps"]] == [2, 1]
    assert result["converted_users"] == 1
    assert result["discard"]["expired"] == 1
    assert result["steps"][1]["rate_from_prev"] == pytest.approx(50.0)


def test_zero_window_allows_same_second_only():
    """window_days=0：同秒完成算成功，晚 1 秒即超窗（明确降级，不静默脏值）。"""
    rows = [
        ev("same", "register", 0, seq=1),
        ev("same", "trial_complete", 0, seq=2),
        ev("late", "register", 0, seq=1),
        ev("late", "trial_complete", 1 / 3600, seq=2),
    ]
    result = _run(rows, steps=STEPS2, window_days=0)
    assert [step["users"] for step in result["steps"]] == [2, 1]
    assert result["converted_users"] == 1
    assert result["discard"]["expired"] == 1


def test_zero_variance_identical_timings():
    """3 个用户耗时完全相同 → 零方差，p50 == p90 == mean。"""
    rows = []
    for index in range(3):
        rows.append(ev(f"u{index}", "register", 0, seq=1))
        rows.append(ev(f"u{index}", "trial_complete", 24, seq=2))
    result = _run(rows, steps=STEPS2)
    timing = result["transitions"][0]
    assert timing["samples"] == 3
    assert timing["p50_seconds"] == pytest.approx(float(D1))
    assert timing["p90_seconds"] == pytest.approx(float(D1))
    assert timing["mean_seconds"] == pytest.approx(float(D1))
    assert timing["p50_days"] == pytest.approx(1.0)
    assert result["duration"]["p50_seconds"] == pytest.approx(result["duration"]["p90_seconds"])


def test_duplicate_same_event_same_second_collapsed():
    rows = [
        ev("u1", "register", 0, seq=1),
        ev("u1", "register", 0, seq=2),
        ev("u1", "trial_complete", 24, seq=3),
        ev("u1", "trial_complete", 24, seq=4),
    ]
    result = _run(rows, steps=STEPS2)
    assert result["discard"]["duplicates_collapsed"] == 2
    assert [step["users"] for step in result["steps"]] == [1, 1]
    assert result["converted_users"] == 1


def test_out_of_order_insertion_is_corrected_by_event_ts():
    """seq 1 的记录事件时间晚于 seq 2：按 (ts, seq) 排序后仍能正确推进。"""
    rows = [
        ev("u1", "trial_complete", 24, seq=1),
        ev("u1", "register", 0, seq=2),
    ]
    result = _run(rows, steps=STEPS2)
    assert result["converted_users"] == 1
    assert result["discard"]["out_of_order_events"] == 1
    assert result["discard"]["out_of_order_users"] == 1


def test_never_entered_counts_users_with_vocabulary_but_no_first_step():
    result = _run([ev("u1", "trial_complete", 1, seq=1), ev("u1", "pay", 2, seq=2)])
    assert result["entry_users"] == 0
    assert result["discard"]["never_entered"] == 1
    assert [step["users"] for step in result["steps"]] == [0, 0, 0]


def test_single_user_single_event_has_none_percentiles():
    result = _run([ev("u1", "register", 0, seq=1)])
    assert result["entry_users"] == 1
    assert result["steps"][0]["users"] == 1
    assert result["steps"][0]["rate_from_prev"] == pytest.approx(100.0)
    assert result["steps"][1]["users"] == 0
    assert result["steps"][1]["rate_from_prev"] == pytest.approx(0.0)
    assert result["steps"][1]["lost"] == 1
    assert result["steps"][1]["lost_share"] == pytest.approx(100.0)
    assert result["transitions"][0]["samples"] == 0
    assert result["transitions"][0]["p50_seconds"] is None
    assert result["transitions"][0]["mean_seconds"] is None
    assert result["duration"]["p50_seconds"] is None


def test_empty_input_returns_zeroed_structure():
    result = _run([])
    assert result["entry_users"] == 0
    assert result["converted_users"] == 0
    assert [(step["users"], step["rate_from_prev"], step["lost"]) for step in result["steps"]] == [
        (0, 0.0, 0),
        (0, 0.0, 0),
        (0, 0.0, 0),
    ]
    assert result["duration"] == {
        "samples": 0,
        "p50_seconds": None,
        "p50_days": None,
        "p90_seconds": None,
        "p90_days": None,
        "mean_seconds": None,
    }
    assert result["discard"]["users"] == 0


# --------------------------------------------------------------- 异常输入 (2)


def test_empty_steps_is_defined_degradation_not_crash():
    result = _run([ev("u1", "register", 0, seq=1), ev("u1", "pay", 1, seq=2)], steps=[])
    assert result["entry_users"] == 0
    assert result["steps"] == []
    assert result["transitions"] == []
    assert result["duration"]["samples"] == 0
    assert result["discard"]["never_entered"] == 1


def test_malformed_row_raises_explicit_attribute_error():
    broken = type("BrokenRow", (), {"user_key": "u1", "event_name": "register", "seq": 1})()
    with pytest.raises(AttributeError):
        funnel_engine.run_funnel({"u1": [broken]}, STEPS3, 7, VOCAB_A)
