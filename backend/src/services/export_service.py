"""导出：把归因报告渲染成 Markdown / CSV，并落一份到共享产物卷。"""
from __future__ import annotations

import csv
import io
import os
from datetime import datetime

from src.config.settings import settings
from src.models.drop_report import DropReport
from src.models.funnel import FunnelDef
from src.utils.timeutil import BIZ_TZ


def _fmt_pct(value: float | None) -> str:
    return f"{value:.1f}%" if value is not None else "—"


def _fmt_days(value: float | None) -> str:
    return f"{value:.2f} 天" if value is not None else "—"


def render_markdown(report: DropReport, funnel: FunnelDef, run_payload: dict) -> str:
    steps = run_payload.get("steps", [])
    duration = run_payload.get("duration", {})
    discard = run_payload.get("discard", {})
    paths = report.top_paths or []
    chokes = report.choke_points or []
    gap = report.segment_gap or {}
    lines: list[str] = []
    lines.append(f"# {report.title}")
    lines.append("")
    lines.append(f"- 漏斗：{funnel.name}（{funnel.code} · {funnel.line_no}）")
    lines.append(f"- 运行：`{run_payload.get('code')}` · 窗口 {run_payload.get('window_days')} 天 · 引擎 v{run_payload.get('engine_version')}")
    lines.append(f"- 流失队列：未到达「{report.drop_step_label}」共 {report.cohort_users:,} 人")
    lines.append(f"- 步间耗时 P50：{_fmt_days(duration.get('p50_days'))}（P90 {_fmt_days(duration.get('p90_days'))}）")
    lines.append(f"- 丢弃原因：超窗 {discard.get('expired', 0)} · 重复折叠 {discard.get('duplicates_collapsed', 0)} · 乱序修复 {discard.get('out_of_order_events', 0)} 处")
    lines.append(f"- 报告状态：{report.status} · 作者 {report.author_email or '—'} · 复核 {report.reviewer_email or '—'}")
    lines.append("")
    lines.append("## 步骤转化")
    lines.append("")
    lines.append("| # | 站点 | 人数 | 较上一步 | 较首步 | 流失 | 步间 P50 |")
    lines.append("|---|---|---|---|---|---|---|")
    for step in steps:
        lines.append(
            "| {idx} | {label} | {users} | {prev} | {entry} | {lost} | {p50} |".format(
                idx=step["index"] + 1,
                label=step["label"],
                users=f"{step['users']:,}",
                prev=_fmt_pct(step.get("rate_from_prev")),
                entry=_fmt_pct(step.get("rate_from_entry")),
                lost=f"{step.get('lost', 0):,}",
                p50=_fmt_days(step.get("p50_days")),
            )
        )
    lines.append("")
    lines.append(f"## Top {len(paths)} 流失前置路径")
    lines.append("")
    lines.append("| 排名 | 队列 | 路径 | 人数 | 占该队列 | 卡点事件 |")
    lines.append("|---|---|---|---|---|---|")
    for path in paths:
        lines.append(
            "| {rank} | {cohort} | {path} | {count} | {share} | {terminal} |".format(
                rank=path.get("rank"),
                cohort=path.get("cohort_label", report.drop_step_label),
                path=path.get("path", ""),
                count=f"{path.get('count', 0):,}",
                share=_fmt_pct(path.get("share_pct")),
                terminal=path.get("terminal_label", "—"),
            )
        )
    lines.append("")
    lines.append("## 卡点事件")
    lines.append("")
    for choke in chokes:
        lines.append(f"- {choke['label']}：{choke['count']:,} 人 · {_fmt_pct(choke.get('share_pct'))}")
    lines.append("")
    lines.append("## 分群差（渠道 × 设备）")
    lines.append("")
    lines.append(f"整体流失率 {_fmt_pct(gap.get('overall_drop_rate'))}；最大差值 {gap.get('max_gap_pp', 0)}pp")
    lines.append("")
    lines.append("| 渠道 | 设备 | 进入 | 流失 | 流失率 | 差值 |")
    lines.append("|---|---|---|---|---|---|")
    for row in gap.get("rows", []):
        lines.append(
            "| {c} | {d} | {u:,} | {x:,} | {r} | {g} |".format(
                c=row.get("channel_label", ""),
                d=row.get("device_label", ""),
                u=row.get("users", 0),
                x=row.get("dropped", 0),
                r=_fmt_pct(row.get("drop_rate")),
                g=f"{row.get('gap_pp', 0):+.1f}pp",
            )
        )
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(report.conclusion or "（待补充）")
    lines.append("")
    lines.append(f"_生成时间 {datetime.now(BIZ_TZ).strftime('%Y-%m-%d %H:%M')} · funnelpath_")
    return "\n".join(lines)


def render_csv(report: DropReport) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "report_code",
            "drop_step",
            "rank",
            "cohort",
            "path",
            "users",
            "share_pct",
            "terminal_event",
        ]
    )
    for path in report.top_paths or []:
        writer.writerow(
            [
                report.code,
                report.drop_step_label,
                path.get("rank"),
                path.get("cohort_label", report.drop_step_label),
                path.get("path", ""),
                path.get("count", 0),
                path.get("share_pct", 0),
                path.get("terminal_label", ""),
            ]
        )
    return buffer.getvalue()


def persist(filename: str, content: str) -> str:
    os.makedirs(settings.export_dir, exist_ok=True)
    path = os.path.join(settings.export_dir, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path
