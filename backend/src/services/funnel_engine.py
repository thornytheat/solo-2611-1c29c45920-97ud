"""算法 1：用户级漏斗状态机（纯 Python，无第三方统计库依赖）。

口径（与 README「算法口径」一节逐条对应）：
1. 按 user_key 分组，事件按 (event_ts, seq) 稳定排序 —— seq 是入库先后，
   埋点乱序时靠 event_ts 纠正，同秒再退化成 seq；
2. 同事件同秒重复上报只计一次（duplicates_collapsed 计数）；
3. 严格顺序推进：只认 steps[idx] 对应事件，跳步不算；命中后 idx += 1；
4. 窗口 = window_days 天，从首步命中时刻起算；超窗即中止并计 expired；
5. 输出每步人数、较上一步/较首步转化率、步间耗时 P50/P90、丢弃原因计数。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.constants.enums import label_of_event
from src.utils.stats import percentile, round_half_up
from src.utils.pathutil import compress_events, path_label


@dataclass
class UserOutcome:
    user_key: str
    channel: str
    device: str
    reached_step: int            # 已完成的步数（0 = 连首步都没到，1 = 完成第 1 步 …）
    converted: bool
    expired: bool
    timings: list[int] = field(default_factory=list)
    path_events: list[dict] = field(default_factory=list)
    path_label: str = ""
    drop_step: int = 0           # 未到达的步骤下标；converted 时为 len(steps)
    terminal_event: str = ""
    duplicates: int = 0
    inversions: int = 0


def _dedupe_and_sort(rows: list) -> tuple[list, int, int]:
    """返回 (按时间排好且去重的事件, 折叠的重复数, 乱序反转数)。"""
    ordered = sorted(rows, key=lambda row: (row.event_ts, row.seq))
    seen: set[tuple[str, datetime]] = set()
    deduped: list = []
    duplicates = 0
    for row in ordered:
        key = (row.event_name, row.event_ts.replace(microsecond=0))
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        deduped.append(row)

    # 入库顺序 vs 事件时间顺序：统计反转对数（只用于展示「乱序修复」计数）
    by_seq = sorted(rows, key=lambda row: (row.seq, row.event_ts))
    inversions = 0
    for index in range(len(by_seq) - 1):
        if by_seq[index].event_ts > by_seq[index + 1].event_ts:
            inversions += 1
    return deduped, duplicates, inversions


def evaluate_user(
    rows: list,
    steps: list[dict],
    window_seconds: int,
    vocabulary: set[str],
    depth: int,
) -> UserOutcome | None:
    """单用户状态机；返回 None 表示该用户没有命中首步（never_entered）。"""
    vocabulary_rows = [row for row in rows if row.event_name in vocabulary]
    ordered, duplicates, inversions = _dedupe_and_sort(vocabulary_rows)
    if not ordered:
        return None

    idx = 0
    t0: datetime | None = None
    last_ts: datetime | None = None
    timings: list[int] = []
    path_events: list[tuple[str, str]] = []
    expired = False
    started = False

    for row in ordered:
        if idx >= len(steps):
            break
        expected = steps[idx]["event"]
        if row.event_name != expected:
            if started:
                path_events.append((row.event_name, row.event_ts.isoformat()))
            continue
        if idx == 0:
            started = True
            t0 = row.event_ts
            last_ts = row.event_ts
            path_events.append((row.event_name, row.event_ts.isoformat()))
            idx = 1
            continue
        assert t0 is not None and last_ts is not None
        if (row.event_ts - t0).total_seconds() > window_seconds:
            expired = True
            break
        path_events.append((row.event_name, row.event_ts.isoformat()))
        timings.append(int((row.event_ts - last_ts).total_seconds()))
        last_ts = row.event_ts
        idx += 1

    if not started:
        return None

    compressed = compress_events(path_events, vocabulary, depth)
    terminal = ""
    for item in reversed(compressed):
        if item["event"] != "exit":
            terminal = item["event"]
            break

    return UserOutcome(
        user_key=ordered[0].user_key,
        channel=ordered[0].channel,
        device=ordered[0].device,
        reached_step=idx,
        converted=idx >= len(steps),
        expired=expired,
        timings=timings,
        path_events=compressed,
        path_label=path_label(compressed),
        drop_step=idx,
        terminal_event=terminal,
        duplicates=duplicates,
        inversions=inversions,
    )


def run_funnel(
    events_by_user: dict[str, list],
    steps: list[dict],
    window_days: int,
    vocabulary: set[str],
    depth: int = 6,
) -> dict:
    """跑一次完整漏斗，返回步骤表 / 耗时 / 丢弃原因 / 用户级结果。"""
    window_seconds = int(window_days) * 86400
    outcomes: dict[str, UserOutcome] = {}
    never_entered = 0
    duplicates = 0
    inversions = 0
    out_of_order_users = 0

    for user_key, rows in events_by_user.items():
        outcome = evaluate_user(rows, steps, window_seconds, vocabulary, depth)
        if outcome is None:
            if any(row.event_name in vocabulary for row in rows):
                never_entered += 1
            continue
        outcomes[user_key] = outcome
        duplicates += outcome.duplicates
        inversions += outcome.inversions
        if outcome.inversions:
            out_of_order_users += 1

    total = len(outcomes)
    reached = [0] * len(steps)
    transition_timings: list[list[int]] = [[] for _ in range(max(len(steps) - 1, 0))]
    for outcome in outcomes.values():
        for index in range(min(outcome.reached_step, len(steps))):
            reached[index] += 1
        for index, seconds in enumerate(outcome.timings):
            if index < len(transition_timings):
                transition_timings[index].append(seconds)

    step_rows: list[dict] = []
    for index, step in enumerate(steps):
        users = reached[index]
        previous = reached[index - 1] if index > 0 else users
        lost = (reached[index - 1] - users) if index > 0 else (total - users)
        timings = transition_timings[index - 1] if index > 0 else []
        step_rows.append(
            {
                "index": index,
                "key": step.get("key", step["event"]),
                "event": step["event"],
                "label": step.get("label", label_of_event(step["event"])),
                "users": users,
                "rate_from_prev": round_half_up(users * 100.0 / previous, 1) if previous else 0.0,
                "rate_from_entry": round_half_up(users * 100.0 / total, 1) if total else 0.0,
                "lost": lost,
                "lost_share": round_half_up(lost * 100.0 / total, 1) if total else 0.0,
                "p50_seconds": percentile(timings, 50),
                "p50_days": _days(percentile(timings, 50)),
            }
        )

    all_timings = [value for group in transition_timings for value in group]
    transitions = []
    for index, timings in enumerate(transition_timings):
        transitions.append(
            {
                "from_index": index,
                "to_index": index + 1,
                "from_label": step_rows[index]["label"],
                "to_label": step_rows[index + 1]["label"],
                "samples": len(timings),
                "p50_seconds": percentile(timings, 50),
                "p50_days": _days(percentile(timings, 50)),
                "p90_seconds": percentile(timings, 90),
                "p90_days": _days(percentile(timings, 90)),
                "mean_seconds": round_half_up(sum(timings) / len(timings), 0) if timings else None,
            }
        )

    expired = sum(1 for outcome in outcomes.values() if outcome.expired)
    converted = sum(1 for outcome in outcomes.values() if outcome.converted)

    # 分群到达矩阵：渠道×设备 + 渠道汇总
    segment_reached: dict[tuple[str, str | None], list[int]] = {}
    for outcome in outcomes.values():
        for segment in ((outcome.channel, outcome.device), (outcome.channel, None)):
            bucket = segment_reached.setdefault(segment, [0] * len(steps))
            for index in range(min(outcome.reached_step, len(steps))):
                bucket[index] += 1

    return {
        "steps": step_rows,
        "transitions": transitions,
        "duration": {
            "samples": len(all_timings),
            "p50_seconds": percentile(all_timings, 50),
            "p50_days": _days(percentile(all_timings, 50)),
            "p90_seconds": percentile(all_timings, 90),
            "p90_days": _days(percentile(all_timings, 90)),
            "mean_seconds": round_half_up(sum(all_timings) / len(all_timings), 0) if all_timings else None,
        },
        "discard": {
            "expired": expired,
            "duplicates_collapsed": duplicates,
            "never_entered": never_entered,
            "converted": converted,
            "out_of_order_events": inversions,
            "out_of_order_users": out_of_order_users,
            "users": total,
        },
        "entry_users": total,
        "converted_users": converted,
        "outcomes": outcomes,
        "segment_reached": segment_reached,
    }


def _days(seconds: float | None) -> float | None:
    if seconds is None:
        return None
    return round_half_up(seconds / 86400.0, 2)
