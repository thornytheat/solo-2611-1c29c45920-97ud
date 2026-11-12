"""校正端到端测试的数据构造辅助（夹具本身在 conftest.py）。

SQLite 内存库 + 真实服务层（不 mock 算法），覆盖：
- EventLog / FunnelDef / FunnelRun / DataVersion / EventCorrection / DropReport 全链路；
- 补录分类（迟到 / 重复 / 批内重复）、校正运行、前后差异、原子切换、失败回滚；
- 旧 run / 旧报告保留可查但 is_current=False。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.constants.enums import ReportStatus, RunTrigger
from src.models.drop_report import DropReport
from src.models.event import EventLog
from src.models.funnel import FunnelDef
from src.models.funnel_run import FunnelRun
from src.services import run_service

ANCHOR = datetime(2026, 9, 1, 8, 0, 0)

STEPS3 = [
    {"key": "register", "label": "注册", "event": "register"},
    {"key": "trial", "label": "试听完成", "event": "trial_complete"},
    {"key": "pay", "label": "付费", "event": "pay"},
]
NOISE = ["browse_course", "exit"]
VOCAB = {"register", "trial_complete", "pay", "browse_course", "exit"}


def _event(user, name, offset_hours, seq, channel="organic", device="ios", source="fixture"):
    return {
        "user_key": user,
        "event_name": name,
        "event_ts": ANCHOR + timedelta(hours=offset_hours),
        "seq": seq,
        "session_id": f"{user}-s1",
        "channel": channel,
        "device": device,
        "source": source,
    }


def seed_baseline_events(db: Session, funnel: FunnelDef) -> list[dict]:
    """5 个用户：u1 转化、u2 到试听、u3 仅注册；u5 不进漏斗。

    基线口径：进入 3（u1/u2/u3），试听完成 2（u1/u2），付费 1（u1）。
    另外埋一条重复上报（u1 register 同秒）验证折叠。
    """
    rows = [
        _event("u1", "register", 0, 10),
        _event("u1", "register", 0, 11),       # 同事件同秒重复 -> 折叠
        _event("u1", "trial_complete", 24, 20),
        _event("u1", "pay", 48, 30),
        _event("u2", "register", 0, 40),
        _event("u2", "trial_complete", 24, 50),
        _event("u3", "register", 0, 60),
        _event("u3", "browse_course", 1, 70),
        _event("u3", "exit", 2, 80),
        _event("u5", "browse_course", 1, 90),   # 无首步
    ]
    db.bulk_insert_mappings(EventLog, rows)
    db.flush()
    return rows


def make_baseline_run(db: Session, funnel: FunnelDef) -> FunnelRun:
    run = run_service.execute(db, funnel, trigger=RunTrigger.SEED.value, code="seed-run-f-corr")
    db.flush()
    return run


def make_published_report(db: Session, funnel: FunnelDef, run: FunnelRun) -> DropReport:
    report = DropReport(
        code="rpt-old",
        funnel_id=funnel.id,
        run_id=run.id,
        title="旧归因报告",
        drop_step_index=1,
        drop_step_label="试听完成",
        cohort_users=1,
        top_paths=[],
        choke_points=[],
        segment_gap={},
        conclusion="旧结论",
        status=ReportStatus.PUBLISHED.value,
        author_email="analyst@funnelpath.io",
        reviewer_email="admin@funnelpath.io",
        version=1,
        is_current=True,
        data_version_id=run.data_version_id,
    )
    db.add(report)
    db.flush()
    return report


def backfill_event(user, name, offset_hours, **kwargs):
    """构造补录入参（event_ts 用 ISO 字符串，模拟 HTTP 入参）。"""
    payload = _event(user, name, offset_hours, seq=0, source="backfill")
    payload.update(kwargs)
    payload["event_ts"] = payload["event_ts"].isoformat()
    return payload


def build_baseline(seed: Session, funnel: FunnelDef) -> dict:
    """在独立 seed 会话里真实提交基线（事件 + run + 旧报告），返回 id 字典。"""
    seed_baseline_events(seed, funnel)
    run = make_baseline_run(seed, funnel)
    report = make_published_report(seed, funnel, run)
    seed.commit()
    return {"run_id": run.id, "report_id": report.id, "funnel_id": funnel.id}
