"""不变量 / 性质测试：计数守恒、比率范围、顺序无关、窗口单调、路径份额守恒。"""
from __future__ import annotations

import json
import random

import pytest

from src.services import funnel_engine, path_engine
from src.utils.stats import percentile
from tests._helpers import STEPS2, STEPS3, VOCAB_A, Event, ev


def _run(rows, steps=STEPS3, window_days=7):
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.user_key, []).append(row)
    return funnel_engine.run_funnel(grouped, steps, window_days, VOCAB_A)


def _rows_for_five_users() -> list:
    rows = []
    plan = {
        "u1": ["register", "trial_complete", "pay"],
        "u2": ["register", "trial_complete"],
        "u3": ["register"],
        "u4": ["register", "browse_course", "trial_complete", "pay"],
        "u5": ["trial_complete"],
    }
    for user, events in plan.items():
        for index, name in enumerate(events):
            rows.append(ev(user, name, index * 24, seq=index + 1))
    return rows


def test_count_conservation_and_ratio_ranges():
    result = _run(_rows_for_five_users())
    steps = result["steps"]

    assert result["entry_users"] == 4  # u5 无首步
    assert sum(step["lost"] for step in steps[1:]) == result["entry_users"] - steps[-1]["users"]
    assert steps[-1]["users"] == result["converted_users"]
    assert [step["users"] for step in steps] == sorted([step["users"] for step in steps], reverse=True)
    for step in steps:
        assert 0.0 <= step["rate_from_prev"] <= 100.0
        assert 0.0 <= step["rate_from_entry"] <= 100.0
        assert 0.0 <= step["lost_share"] <= 100.0
        assert step["lost"] >= 0
    assert result["converted_users"] <= result["entry_users"]
    assert result["discard"]["users"] == result["entry_users"]
    assert result["discard"]["converted"] == result["converted_users"]


def test_same_input_is_deterministic_and_row_order_independent():
    rows = _rows_for_five_users()
    first = _run(rows)
    shuffled = list(rows)
    random.Random(20261112).shuffle(shuffled)
    second = _run(shuffled)

    def payload(result: dict) -> str:
        return json.dumps(
            {
                "steps": result["steps"],
                "transitions": result["transitions"],
                "duration": result["duration"],
                "discard": result["discard"],
                "entry_users": result["entry_users"],
                "converted_users": result["converted_users"],
            },
            sort_keys=True,
            ensure_ascii=False,
        )

    assert payload(first) == payload(second)


def test_tighter_window_never_increases_conversions():
    rows = [
        ev("fast", "register", 0, seq=1),
        ev("fast", "trial_complete", 12, seq=2),      # 0.5 天
        ev("slow", "register", 0, seq=1),
        ev("slow", "trial_complete", 72, seq=2),      # 3 天
        ev("late", "register", 0, seq=1),
        ev("late", "trial_complete", 240, seq=2),     # 10 天
    ]
    windows = [1, 7, 30]
    results = [_run(rows, steps=STEPS2, window_days=days) for days in windows]

    assert [result["converted_users"] for result in results] == [1, 2, 3]
    assert [result["discard"]["expired"] for result in results] == [2, 1, 0]
    for tighter, looser in zip(results, results[1:]):
        assert tighter["converted_users"] <= looser["converted_users"]
        assert tighter["discard"]["expired"] >= looser["discard"]["expired"]


def test_path_and_choke_share_conservation_and_tree_identity():
    from scripts.fixture import build_fixture

    _, rows = build_fixture()
    picked = {"U0001", "U0141", "U0306", "U0401", "U0451",
              "U0581", "U0671", "U0864", "U0891"}
    grouped: dict[str, list] = {}
    for row in rows:
        if row["user_key"] not in picked or row["event_name"] not in VOCAB_A:
            continue
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
    result = funnel_engine.run_funnel(grouped, STEPS3, 7, VOCAB_A)
    cohort = path_engine.analyze_cohort(result["outcomes"], result["steps"], 2)

    shares = [item["share_pct"] for item in cohort["paths"]]
    assert all(0.0 <= share <= 100.0 for share in shares)
    assert sum(shares) == pytest.approx(100.0)
    choke_shares = [item["share_pct"] for item in cohort["choke_points"]]
    assert sum(choke_shares) == pytest.approx(100.0)
    assert cohort["prefix_tree"]["count"] == cohort["cohort_users"]
    assert sum(item["count"] for item in cohort["paths"]) == cohort["cohort_users"]


def test_percentile_is_monotone_and_bounded():
    values = [3, 41, 5, 17, 29, 88, 2, 64, 11, 53]
    previous = None
    for q in (0, 10, 25, 50, 75, 90, 100):
        value = percentile(values, q)
        assert min(values) <= value <= max(values)
        if previous is not None:
            assert value >= previous
        previous = value
    assert percentile(values, 0) == pytest.approx(float(min(values)))
    assert percentile(values, 100) == pytest.approx(float(max(values)))
