"""分群（渠道 × 设备）流失率与百分点差。"""
from __future__ import annotations

from src.constants.enums import CHANNEL_LABELS, DEVICE_LABELS
from src.utils.stats import round_half_up


def build_segments(
    segment_reached: dict,
    steps: list[dict],
    step_index: int,
    channel_order: list[str],
    device_order: list[str],
) -> dict:
    """返回 {"rows": 渠道×设备, "channel_rows": 渠道汇总, "overall": {...}}。"""
    if step_index <= 0 or step_index >= len(steps):
        step_index = max(1, len(steps) - 1)
    previous_index = step_index - 1
    overall_reached = steps[previous_index]["users"]
    overall_dropped = steps[previous_index]["users"] - steps[step_index]["users"]
    overall_rate = round_half_up(overall_dropped * 100.0 / overall_reached, 1) if overall_reached else 0.0

    def _row(level: str, channel: str, device: str | None, reached: list[int]) -> dict:
        users = reached[previous_index]
        dropped = users - reached[step_index] if users else 0
        rate = round_half_up(dropped * 100.0 / users, 1) if users else 0.0
        return {
            "level": level,
            "channel": channel,
            "channel_label": CHANNEL_LABELS.get(channel, channel),
            "device": device,
            "device_label": DEVICE_LABELS.get(device, device) if device else "全部设备",
            "users": users,
            "dropped": dropped,
            "drop_rate": rate,
            "gap_pp": round_half_up(rate - overall_rate, 1),
            "reached": reached,
        }

    rows = []
    for channel in channel_order:
        for device in device_order:
            reached = segment_reached.get((channel, device))
            if reached:
                rows.append(_row("device", channel, device, reached))
    channel_rows = []
    for channel in channel_order:
        reached = segment_reached.get((channel, None))
        if reached:
            channel_rows.append(_row("channel", channel, None, reached))

    # 同差值时优先「流失人数更多」的分群，其次 iOS/Android 固定顺序
    ranked = sorted(
        rows,
        key=lambda item: (-item["gap_pp"], -item["dropped"], item["channel"], item["device"] or ""),
    )
    return {
        "step_index": step_index,
        "step_label": steps[step_index]["label"],
        "from_label": steps[previous_index]["label"],
        "overall_drop_rate": overall_rate,
        "overall_users": overall_reached,
        "overall_dropped": overall_dropped,
        "rows": rows,
        "channel_rows": channel_rows,
        "ranked": ranked,
        "top_segment": ranked[0] if ranked else None,
        "max_gap_pp": ranked[0]["gap_pp"] if ranked else 0.0,
    }
