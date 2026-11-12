"""DropReport 服务：从 run 生成归因报告、复核流转、序列化。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import ReportStatus, label_of_channel, label_of_device
from src.models.drop_report import DropReport
from src.models.funnel import FunnelDef
from src.models.funnel_run import FunnelRun
from src.services import path_engine, run_service, segment_service
from src.utils.errors import conflict, not_found
from src.utils.timeutil import BIZ_TZ, iso


def serialize(report: DropReport, funnel: FunnelDef | None = None) -> dict:
    return {
        "id": report.id,
        "code": report.code,
        "funnel_id": report.funnel_id,
        "funnel_code": funnel.code if funnel else None,
        "funnel_name": funnel.name if funnel else None,
        "run_id": report.run_id,
        "title": report.title,
        "drop_step_index": report.drop_step_index,
        "drop_step_label": report.drop_step_label,
        "cohort_users": report.cohort_users,
        "top_paths": report.top_paths or [],
        "choke_points": report.choke_points or [],
        "segment_gap": report.segment_gap or {},
        "conclusion": report.conclusion,
        "status": report.status,
        "author_email": report.author_email,
        "reviewer_email": report.reviewer_email,
        "version": report.version,
        "created_at": iso(report.created_at),
        "updated_at": iso(report.updated_at),
    }


def build_payload(db: Session, run: FunnelRun, funnel: FunnelDef, step_index: int | None) -> dict:
    steps = run.step_counts or []
    if step_index is None or step_index < 1 or step_index > len(steps) - 1:
        step_index = run_service.max_loss_step(steps)
    outcomes = run_service.outcomes_for_run(db, run)
    cohort = path_engine.analyze_cohort(outcomes, steps, step_index)
    top_paths = path_engine.report_paths(outcomes, steps, top_k=8)
    segment_gap = segment_service.build_segments(
        {(row["channel"], row["device"]): row["reached"] for row in (run.segment_rows or [])},
        steps,
        step_index,
        run_service.CHANNEL_ORDER,
        run_service.DEVICE_ORDER,
    )
    return {
        "step_index": step_index,
        "step_label": steps[step_index]["label"],
        "cohort_users": cohort["cohort_users"],
        "top_paths": top_paths,
        "choke_points": cohort["choke_points"],
        "segment_gap": segment_gap,
        "cohort": cohort,
    }


def create(db: Session, run: FunnelRun, funnel: FunnelDef, payload, author_email: str) -> DropReport:
    built = build_payload(db, run, funnel, payload.drop_step_index)
    # 与运行单号一致：带微秒，避免同一秒内连续生成两份报告时
    # 撞上 code 的 UNIQUE 约束（此前会直接 500 IntegrityError）。
    code = f"RPT-{funnel.code.upper()}-{datetime.now(BIZ_TZ).strftime('%Y%m%d%H%M%S%f')}"
    now = datetime.now(BIZ_TZ).replace(tzinfo=None)
    report = DropReport(
        code=code,
        funnel_id=funnel.id,
        run_id=run.id,
        title=payload.title,
        drop_step_index=built["step_index"],
        drop_step_label=built["step_label"],
        cohort_users=built["cohort_users"],
        top_paths=built["top_paths"],
        choke_points=built["choke_points"],
        segment_gap=built["segment_gap"],
        conclusion=payload.conclusion,
        status=ReportStatus.DRAFT.value,
        author_email=author_email,
        created_at=now,
        updated_at=now,
    )
    db.add(report)
    db.flush()
    return report


def list_reports(db: Session, funnel_id: int | None = None) -> list[dict]:
    stmt = select(DropReport).order_by(DropReport.id.desc())
    if funnel_id:
        stmt = select(DropReport).where(DropReport.funnel_id == funnel_id).order_by(DropReport.id.desc())
    rows = db.scalars(stmt).all()
    funnels = {funnel.id: funnel for funnel in db.scalars(select(FunnelDef)).all()}
    return [serialize(row, funnels.get(row.funnel_id)) for row in rows]


def get(db: Session, report_id: int) -> DropReport:
    report = db.get(DropReport, report_id)
    if report is None:
        raise not_found({"report_id": report_id})
    return report


def patch(db: Session, report: DropReport, payload, actor_role: str, actor_email: str) -> DropReport:
    data = payload.model_dump(exclude_unset=True)
    status = data.get("status")
    if status is not None:
        if status in (ReportStatus.REVIEWED, ReportStatus.PUBLISHED) and actor_role != "admin":
            raise conflict({"reason": "只有增长负责人可以复核/发布报告"})
        report.status = status.value if hasattr(status, "value") else str(status)
        if report.status in (ReportStatus.REVIEWED.value, ReportStatus.PUBLISHED.value):
            report.reviewer_email = actor_email
    if data.get("title"):
        report.title = data["title"]
    if data.get("conclusion") is not None:
        report.conclusion = data["conclusion"]
    report.version = (report.version or 1) + 1
    db.flush()
    return report


def segment_label(row: dict) -> str:
    return f"{label_of_channel(row['channel'])} · {label_of_device(row['device'])}"
