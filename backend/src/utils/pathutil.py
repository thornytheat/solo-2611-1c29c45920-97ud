"""路径压缩与去噪：连续同类合并 + 结束标记只保留末尾 + 深度截断。"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from src.constants.enums import TERMINAL_EVENTS, label_of_event


def compress_events(
    events: Sequence[tuple[str, str]],
    vocabulary: set[str],
    depth: int = 6,
) -> list[dict]:
    """events: [(event_name, iso_ts)] 已按 (ts, seq) 排好。

    返回 [{"event": name, "label": 站名}]：
    - 只保留白名单内事件（去噪）
    - 连续同类合并
    - 会话结束标记最多出现一次且在末尾
    - 长度不超过 depth
    """
    kept: list[str] = []
    ended = False
    for name, _ts in events:
        if name not in vocabulary:
            continue
        if name in TERMINAL_EVENTS:
            ended = True
            continue
        if kept and kept[-1] == name:
            ended = False
            continue
        kept.append(name)
        ended = False
    if ended and kept:
        kept.append("exit")
    if len(kept) > depth:
        kept = kept[:depth]
    return [{"event": name, "label": label_of_event(name)} for name in kept]


def path_label(path: Sequence[dict]) -> str:
    return " → ".join(item["label"] for item in path)


def build_prefix_tree(paths: Iterable[Sequence[str]], depth: int = 6) -> dict:
    """前缀树：{"label": ..., "count": n, "children": [...]}，深度 ≤ depth。"""
    root: dict = {"event": "__root__", "label": "起步", "count": 0, "children": []}
    index: dict[str, dict] = {}

    for sequence in paths:
        node = root
        node["count"] += 1
        for event in list(sequence)[:depth]:
            key = f"{id(node)}:{event}"
            child = index.get(key)
            if child is None:
                child = {"event": event, "label": label_of_event(event), "count": 0, "children": []}
                node["children"].append(child)
                index[key] = child
            child["count"] += 1
            node = child

    def _sort(node: dict) -> None:
        node["children"].sort(key=lambda item: (-item["count"], item["label"]))
        for child in node["children"]:
            _sort(child)

    _sort(root)
    return root


def flatten_tree(node: dict, prefix: str = "", out: list | None = None) -> list[dict]:
    out = [] if out is None else out
    for order, child in enumerate(node.get("children", [])):
        label = child["label"] if not prefix else f"{prefix} → {child['label']}"
        out.append(
            {
                "path": label,
                "count": child["count"],
                "depth": label.count("→") + 1,
                "terminal": not child["children"],
            }
        )
        flatten_tree(child, label, out)
    return out
