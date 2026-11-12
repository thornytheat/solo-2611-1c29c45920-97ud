"""手写统计量：中位数/分位/四舍五入到指定小数（不引入 scipy）。"""
from __future__ import annotations

from collections.abc import Sequence


def percentile(values: Sequence[float], q: float) -> float | None:
    """线性插值分位数（与 numpy 默认实现一致），空序列返回 None。"""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * (q / 100.0)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return float(ordered[low] * (1.0 - weight) + ordered[high] * weight)


def median(values: Sequence[float]) -> float | None:
    return percentile(values, 50.0)


def round_half_up(value: float, digits: int = 1) -> float:
    factor = 10 ** digits
    scaled = value * factor
    # 避免二进制浮点误差导致的 0.44999 问题
    if scaled >= 0:
        return (int(scaled + 0.5 + 1e-9)) / factor
    return -((int(-scaled + 0.5 + 1e-9)) / factor)


def pct(part: float, total: float, digits: int = 1) -> float:
    if not total:
        return 0.0
    return round_half_up(part * 100.0 / total, digits)


def seconds_to_days(seconds: float | None, digits: int = 2) -> float | None:
    if seconds is None:
        return None
    return round_half_up(seconds / 86400.0, digits)
