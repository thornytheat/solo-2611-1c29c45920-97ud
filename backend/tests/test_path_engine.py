"""算法 2：会话路径压缩 + 前缀树频次归因（path_engine）纯函数单测。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.constants.enums import label_of_event
from src.services import funnel_engine, path_engine
from src.utils.pathutil import build_prefix_tree
from tests._helpers import ANCHOR, STEPS3, VOCAB_A, Event, ev

STEPS = [
    {"key": "register", "label": "注册", "event": "register"},
    {"key": "trial", "label": "试听完成", "event": "trial_complete"},
    {"key": "pay", "label": "付费", "event": "pay"},
]


def _outcome(
    user_key: str,
    events: list[str],
    *,
    label: str | None = None,
    channel: str = "feed",
    device: str = "ios",
    converted: bool = False,
    drop_step: int = 1,
    terminal_event: str = "",
) -> SimpleNamespace:
    path_events = [{"event": name, "label": label_of_event(name)} for name in events]
    return SimpleNamespace(
        user_key=user_key,
        channel=channel,
        device=device,
        converted=converted,
        drop_step=drop_step,
        reached_step=drop_step,
        path_label=label if label is not None else " → ".join(item["label"] for item in path_events),
        path_events=path_events,
        terminal_event=terminal_event,
    )


def _tree_depth(node: dict, depth: int = 0) -> int:
    if not node.get("children"):
        return depth
    return max(_tree_depth(child, depth + 1) for child in node["children"])


# --------------------------------------------------------------- 正常路径 (3+)


def test_cohort_top_paths_and_choke_points_hand_calculated():
    outcomes = {
        "u1": _outcome(
            "u1",
            ["register", "browse_course", "exit"],
            terminal_event="browse_course",
        ),
        "u2": _outcome(
            "u2",
            ["register", "browse_course", "exit"],
            terminal_event="browse_course",
        ),
        "u3": _outcome(
            "u3",
            ["register", "trial_short_stay", "exit"],
            terminal_event="trial_short_stay",
        ),
    }
    cohort = path_engine.analyze_cohort(outcomes, STEPS, 1)

    assert cohort["cohort_users"] == 3
    assert cohort["distinct_paths"] == 2
    assert cohort["step_label"] == "试听完成"
    assert cohort["from_label"] == "注册"
    assert len(cohort["paths"]) == 2

    top, second = cohort["paths"]
    assert top["rank"] == 1
    assert top["path"] == "注册 → 浏览课程 → 退出"
    assert top["count"] == 2
    assert top["share_pct"] == pytest.approx(66.7)
    assert top["terminal_event"] == "browse_course"
    assert top["terminal_label"] == "浏览课程"
    assert top["top_channel"] == "feed"
    assert second["rank"] == 2
    assert second["count"] == 1
    assert second["share_pct"] == pytest.approx(33.3)

    # 卡点 = 末事件（去掉 exit）分布：浏览课程 2 / 试听页停留<30s 1
    assert [item["event"] for item in cohort["choke_points"]] == ["browse_course", "trial_short_stay"]
    assert cohort["choke_points"][0]["count"] == 2
    assert cohort["choke_points"][0]["share_pct"] == pytest.approx(66.7)
    assert cohort["top_choke"] == cohort["choke_points"][0]
    assert cohort["top_path"] == cohort["paths"][0]

    # 前缀树：根 3，第一层 register 3，第二层按人数排序
    tree = cohort["prefix_tree"]
    assert tree["count"] == 3
    assert [child["event"] for child in tree["children"]] == ["register"]
    register = tree["children"][0]
    assert register["count"] == 3
    assert [child["event"] for child in register["children"]] == ["browse_course", "trial_short_stay"]
    assert [child["count"] for child in register["children"]] == [2, 1]


def test_prefix_tree_depth_capped_and_counts_exact():
    paths = [
        ["register", "browse_course", "trial_start", "trial_complete", "pay", "exit", "pay"],
        ["register", "browse_course", "trial_complete"],
    ]
    tree = build_prefix_tree(paths, depth=3)
    assert tree["count"] == 2
    assert _tree_depth(tree) <= 3
    register = tree["children"][0]
    assert register["event"] == "register" and register["count"] == 2
    assert register["children"][0]["event"] == "browse_course"
    assert register["children"][0]["count"] == 2


def test_report_paths_merges_cohorts_in_declared_order():
    outcomes = {
        "a": _outcome(
            "a",
            ["register", "browse_course", "exit"],
            label="注册 → 浏览课程 → 退出",
            terminal_event="browse_course",
            drop_step=1,
        ),
        "b": _outcome(
            "b",
            ["register", "browse_course", "exit"],
            label="注册 → 浏览课程 → 退出",
            terminal_event="browse_course",
            drop_step=1,
        ),
        "c": _outcome(
            "c",
            ["register", "browse_course", "trial_complete", "pricing_view", "exit"],
            label="注册 → 浏览课程 → 试听完成 → 价格页 → 退出",
            terminal_event="pricing_view",
            drop_step=2,
        ),
        "d": _outcome(
            "d",
            ["register", "trial_short_stay", "exit"],
            label="注册 → 试听页停留<30s → 退出",
            terminal_event="trial_short_stay",
            drop_step=2,
        ),
    }
    merged = path_engine.report_paths(outcomes, STEPS, top_k=8)

    assert [item["cohort_index"] for item in merged] == [1, 2, 2]
    assert merged[0]["cohort_label"] == "试听完成"
    assert merged[0]["count"] == 2
    assert [item["count"] for item in merged[1:]] == [1, 1]
    assert all(item["cohort_users"] > 0 for item in merged)


# --------------------------------------------------------------- 边界 (3+)


def test_empty_cohort_returns_zeroed_view():
    cohort = path_engine.analyze_cohort({}, STEPS, 1)
    assert cohort["cohort_users"] == 0
    assert cohort["distinct_paths"] == 0
    assert cohort["paths"] == []
    assert cohort["choke_points"] == []
    assert cohort["top_path"] is None
    assert cohort["top_choke"] is None
    assert cohort["prefix_tree"]["count"] == 0
    assert cohort["prefix_tree"]["children"] == []


def test_single_user_cohort_share_is_100_percent():
    outcomes = {
        "u1": _outcome(
            "u1",
            ["register", "browse_course", "exit"],
            terminal_event="browse_course",
        )
    }
    cohort = path_engine.analyze_cohort(outcomes, STEPS, 1)
    assert cohort["cohort_users"] == 1
    assert [item["share_pct"] for item in cohort["paths"]] == [100.0]
    assert [item["share_pct"] for item in cohort["choke_points"]] == [100.0]
    assert cohort["prefix_tree"]["count"] == 1


def test_top_k_truncates_paths_but_keeps_distinct_count():
    outcomes = {
        f"u{index}": _outcome(
            f"u{index}",
            ["register", ["browse_course", "trial_short_stay", "trial_incomplete"][index], "exit"],
            terminal_event=["browse_course", "trial_short_stay", "trial_incomplete"][index],
        )
        for index in range(3)
    }
    cohort = path_engine.analyze_cohort(outcomes, STEPS, 1, top_k=2)
    assert cohort["distinct_paths"] == 3
    assert len(cohort["paths"]) == 2
    assert [item["share_pct"] for item in cohort["paths"]] == [33.3, 33.3]
    assert sum(item["share_pct"] for item in cohort["paths"]) == pytest.approx(66.6, abs=0.11)


def test_cohort_excludes_converted_and_other_drop_steps():
    outcomes = {
        "drop1": _outcome("drop1", ["register", "exit"], drop_step=1, terminal_event="register"),
        "drop2": _outcome("drop2", ["register", "trial_complete", "exit"], drop_step=2,
                          terminal_event="trial_complete"),
        "conv": _outcome("conv", ["register", "trial_complete", "pay", "exit"],
                         converted=True, drop_step=3, terminal_event="pay"),
    }
    cohort = path_engine.analyze_cohort(outcomes, STEPS, 2)
    assert cohort["cohort_users"] == 1
    assert cohort["paths"][0]["count"] == 1
    assert cohort["paths"][0]["path"] == "注册 → 试听完成 → 退出"


# --------------------------------------------------------------- 真实 seed 切片


def test_real_seed_cohort_paths_and_choke():
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

    assert cohort["cohort_users"] == 4
    assert cohort["distinct_paths"] == 4
    assert all(item["count"] == 1 for item in cohort["paths"])
    assert [item["share_pct"] for item in cohort["paths"]] == [25.0, 25.0, 25.0, 25.0]
    # 4 条不同路径按字典序/插入序稳定输出，Top1 是「价格页」那条
    assert cohort["paths"][0]["path"] == "注册 → 浏览课程 → 试听完成 → 价格页 → 退出"
    assert cohort["paths"][1]["path"] == "注册 → 浏览课程 → 试听完成 → 顾问咨询 → 退出"

    # 卡点：课程对比 2 人（50%），价格页 / 顾问咨询 各 1 人
    choke = cohort["choke_points"]
    assert choke[0]["event"] == "course_compare"
    assert choke[0]["label"] == "课程对比"
    assert choke[0]["count"] == 2
    assert choke[0]["share_pct"] == pytest.approx(50.0)
    assert [item["count"] for item in choke] == [2, 1, 1]
    assert cohort["prefix_tree"]["count"] == 4
    assert _tree_depth(cohort["prefix_tree"]) <= 6
