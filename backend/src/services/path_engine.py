"""算法 2：会话路径压缩 + 前缀树频次归因（深度 ≤6，Top-K=8）。

口径：
1. 路径 = 该漏斗白名单事件在用户流中的压缩序列（连续同类合并、结束标记只保留末尾）；
2. 前缀树深度 ≤6，节点计数 = 经过该前缀的用户数；
3. Top-K 前置路径 = 在「未到达某步骤」的队列里按人数降序取前 K 条；
4. 卡点事件 = 该队列末事件（去掉退出标记）分布；
5. 分群差值 gap_pp = 该分群流失率 − 整体流失率（百分点）。
"""
from __future__ import annotations

from collections import Counter, defaultdict

from src.constants.enums import label_of_event
from src.utils.stats import round_half_up
from src.utils.pathutil import build_prefix_tree


def drop_steps(steps: list[dict]) -> list[dict]:
    """每个「未到达」步骤的流失队列规模。"""
    rows = []
    for index in range(1, len(steps)):
        lost = steps[index - 1]["users"] - steps[index]["users"]
        rows.append(
            {
                "index": index,
                "label": steps[index]["label"],
                "event": steps[index]["event"],
                "lost": lost,
                "lost_share": round_half_up(lost * 100.0 / steps[0]["users"], 1) if steps[0]["users"] else 0.0,
                "from_label": steps[index - 1]["label"],
            }
        )
    return rows


def analyze_cohort(
    outcomes: dict,
    steps: list[dict],
    step_index: int,
    depth: int = 6,
    top_k: int = 8,
) -> dict:
    """某个流失步骤队列的 Top 路径 / 卡点 / 前缀树。"""
    cohort = [
        outcome
        for outcome in outcomes.values()
        if not outcome.converted and outcome.drop_step == step_index and outcome.reached_step > 0
    ]
    total = len(cohort)
    counter: Counter[str] = Counter(outcome.path_label for outcome in cohort)
    event_map: dict[str, list[str]] = {}
    segment_counter: dict[str, Counter[str]] = defaultdict(Counter)
    terminal_counter: Counter[str] = Counter()

    for outcome in cohort:
        event_map.setdefault(outcome.path_label, [item["event"] for item in outcome.path_events])
        segment_counter[outcome.path_label][f"{outcome.channel}"] += 1
        terminal_counter[outcome.terminal_event] += 1

    paths = []
    for rank, (label, count) in enumerate(counter.most_common(top_k), start=1):
        terminal_event = ""
        for event in reversed(event_map.get(label, [])):
            if event != "exit":
                terminal_event = event
                break
        paths.append(
            {
                "rank": rank,
                "path": label,
                "path_events": event_map.get(label, []),
                "depth": len(event_map.get(label, [])),
                "count": count,
                "share_pct": round_half_up(count * 100.0 / total, 1) if total else 0.0,
                "terminal_event": terminal_event,
                "terminal_label": label_of_event(terminal_event) if terminal_event else "—",
                "top_channel": _top_key(segment_counter[label]),
            }
        )

    choke_points = [
        {
            "event": event,
            "label": label_of_event(event),
            "count": count,
            "share_pct": round_half_up(count * 100.0 / total, 1) if total else 0.0,
        }
        for event, count in terminal_counter.most_common()
    ]

    tree = build_prefix_tree(
        ([item["event"] for item in outcome.path_events] for outcome in cohort),
        depth=depth,
    )

    return {
        "step_index": step_index,
        "step_label": steps[step_index]["label"] if step_index < len(steps) else "",
        "from_label": steps[step_index - 1]["label"] if step_index > 0 else "",
        "cohort_users": total,
        "distinct_paths": len(counter),
        "paths": paths,
        "choke_points": choke_points,
        "prefix_tree": tree,
        "top_path": paths[0] if paths else None,
        "top_choke": choke_points[0] if choke_points else None,
    }


def report_paths(outcomes: dict, steps: list[dict], depth: int = 6, top_k: int = 8) -> list[dict]:
    """报告用的 Top-K 流失路径：按流失队列合并，各条自带宽口径 share。"""
    merged: list[dict] = []
    for index in range(1, len(steps)):
        cohort = analyze_cohort(outcomes, steps, index, depth=depth, top_k=top_k)
        for item in cohort["paths"]:
            merged.append(
                {
                    **item,
                    "cohort_index": index,
                    "cohort_label": cohort["step_label"],
                    "cohort_users": cohort["cohort_users"],
                }
            )
    # 先按流失队列（主队列在前），再按人数 —— 报告 Top1 永远是「主队列 Top1」
    merged.sort(key=lambda item: (item["cohort_index"], -item["count"]))
    return merged[:top_k]


def _top_key(counter: Counter[str]) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]
