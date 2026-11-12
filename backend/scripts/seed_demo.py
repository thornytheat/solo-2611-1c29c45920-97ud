"""幂等 seed：3 漏斗 / 6,000 用户 / 36,000 埋点 / 4 渠道 / 3 账号。

幂等策略（自然键）：
  users.email
  funnel_defs.code
  event_logs.seed_key = "seed:e000001"（按生成顺序编号，重复执行只补缺失）
  funnel_runs.code    = "seed-run-<funnel code>"（重跑覆盖指标 + 重建会话路径）
  drop_reports.code   = "seed-report-<funnel code>"

fixture 全部确定性（无随机数）：见 scripts/demo_config.py。
"""
from __future__ import annotations

from datetime import datetime


from sqlalchemy import func, select

from src.config.database import session_scope
from src.constants.enums import ReportStatus, RunTrigger
from src.models.audit import AuditLog
from src.models.drop_report import DropReport
from src.models.event import EventLog
from src.models.funnel import FunnelDef
from src.models.user import User
from src.utils.security import hash_password
from src.utils.timeutil import BIZ_TZ
from scripts import demo_config as cfg
from scripts.fixture import build_fixture, build_user_rows


# --------------------------------------------------------------------------- seed


def ensure_users(db) -> dict[str, User]:
    users: dict[str, User] = {}
    for email, display_name, role in cfg.DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(cfg.DEMO_PASSWORD),
                display_name=display_name,
                role=role,
                team="增长产品组",
            )
            db.add(user)
            db.flush()
        users[email] = user
    return users


def ensure_funnels(db) -> dict[str, FunnelDef]:
    result: dict[str, FunnelDef] = {}
    for spec in cfg.FUNNELS:
        funnel = db.scalar(select(FunnelDef).where(FunnelDef.code == spec["code"]))
        if funnel is None:
            funnel = FunnelDef(
                code=spec["code"],
                name=spec["name"],
                description=spec["description"],
                line_no=spec["line_no"],
                line_color=spec["line_color"],
                steps=[dict(step) for step in spec["steps"]],
                noise_events=list(spec["noise_events"]),
                window_days=spec["window_days"],
                cross_session=spec["cross_session"],
                status=spec["status"],
                version=1,
                owner_email=cfg.DEMO_USERS[0][0],
            )
            db.add(funnel)
            db.flush()
        result[spec["code"]] = funnel
    return result


def ensure_events(db, rows: list[dict]) -> int:
    existing = set(db.scalars(select(EventLog.seed_key)).all())
    pending = [
        {
            "seed_key": row["seed_key"],
            "user_key": row["user_key"],
            "event_name": row["event_name"],
            "event_ts": row["event_ts"],
            "seq": row["seq"],
            "session_id": row["session_id"],
            "channel": row["channel"],
            "device": row["device"],
            "source": row["source"],
        }
        for row in rows
        if row["seed_key"] not in existing
    ]
    if pending:
        db.bulk_insert_mappings(EventLog, pending)
        db.flush()
    return len(pending)


def ensure_reports(db, funnels: dict[str, FunnelDef]) -> list[DropReport]:
    """固定 code 的两份报告：L1 已发布（8 条路径），L2 草稿。"""
    from src.models.funnel_run import FunnelRun
    from src.services import report_service, run_service

    created: list[DropReport] = []
    specs = (
        ("signup-trial-pay", "seed-report-l1", "试听完成步流失归因：卡在试听页，不是价格",
         ReportStatus.PUBLISHED.value, 1),
        ("browse-cart-order", "seed-report-l2", "加购到下单：3 天窗口内超窗丢单初查",
         ReportStatus.DRAFT.value, 2),
    )
    for funnel_code, code, title, status, step_index in specs:
        funnel = funnels[funnel_code]
        run = db.scalar(select(FunnelRun).where(FunnelRun.code == f"seed-run-{funnel_code}"))
        if run is None:  # pragma: no cover - 防御
            continue
        payload = report_service.build_payload(db, run, funnel, step_index)
        report = db.scalar(select(DropReport).where(DropReport.code == code))
        if report is None:
            report = DropReport(
                code=code,
                funnel_id=funnel.id,
                run_id=run.id,
                title=title,
                drop_step_index=payload["step_index"],
                drop_step_label=payload["step_label"],
                cohort_users=payload["cohort_users"],
                top_paths=payload["top_paths"],
                choke_points=payload["choke_points"],
                segment_gap=payload["segment_gap"],
                conclusion=cfg.SEED_REPORT_CONCLUSION if funnel_code == "signup-trial-pay" else "",
                status=status,
                author_email=cfg.DEMO_USERS[1][0],
                reviewer_email=cfg.DEMO_USERS[0][0] if status == ReportStatus.PUBLISHED.value else "",
                version=1,
                created_at=datetime.now(BIZ_TZ).replace(tzinfo=None),
                updated_at=datetime.now(BIZ_TZ).replace(tzinfo=None),
            )
            db.add(report)
        else:
            # 只刷新派生指标，保留用户改过的标题 / 结论 / 状态
            report.run_id = run.id
            report.drop_step_index = payload["step_index"]
            report.drop_step_label = payload["step_label"]
            report.cohort_users = payload["cohort_users"]
            report.top_paths = payload["top_paths"]
            report.choke_points = payload["choke_points"]
            report.segment_gap = payload["segment_gap"]
        db.flush()
        created.append(report)
    return created


def ensure_audit(db) -> None:
    seeds = [
        ("seed:audit:1", cfg.DEMO_USERS[0][0], "admin", "funnel.publish", "funnel", "1",
         {"code": "signup-trial-pay", "version": 1}),
        ("seed:audit:2", cfg.DEMO_USERS[1][0], "analyst", "report.create", "report", "1",
         {"funnel": "signup-trial-pay", "paths": 8}),
    ]
    existing = set(db.scalars(select(AuditLog.seed_key)).all())
    for seed_key, email, role, action, entity, entity_id, detail in seeds:
        if seed_key in existing:
            continue
        db.add(
            AuditLog(
                seed_key=seed_key,
                actor_email=email,
                actor_role=role,
                action=action,
                entity=entity,
                entity_id=entity_id,
                detail=detail,
                layer="seed",
            )
        )
    db.flush()


def seed_all() -> str:
    from src.services import run_service

    users, rows = build_fixture()
    expected = cfg.EXPECTED
    assert len(users) == expected["users"], f"fixture users {len(users)}"
    assert len(rows) == expected["events"], f"fixture events {len(rows)}"

    with session_scope() as db:
        ensure_users(db)
        funnels = ensure_funnels(db)
        inserted = ensure_events(db, rows)
        db.flush()

        for funnel in funnels.values():
            run = run_service.execute(
                db,
                funnel,
                trigger=RunTrigger.SEED.value,
                code=f"seed-run-{funnel.code}",
            )
            db.flush()
            print(
                f"[SEED] funnel={funnel.code} entry={run.entry_users} converted={run.converted_users} "
                f"window={run.window_days}d",
                flush=True,
            )

        reports = ensure_reports(db, funnels)
        ensure_audit(db)
        db.flush()

        funnel_count = db.scalar(select(func.count()).select_from(FunnelDef)) or 0
        event_count = db.scalar(select(func.count()).select_from(EventLog)) or 0
        member_count = db.scalar(select(func.count(func.distinct(EventLog.user_key)))) or 0
        channel_count = db.scalar(select(func.count(func.distinct(EventLog.channel)))) or 0
        account_count = db.scalar(select(func.count()).select_from(User)) or 0
        report_count = db.scalar(select(func.count()).select_from(DropReport)) or 0

    print(
        f"[SEED] inserted_events={inserted} reports={report_count} "
        f"first_report_paths={len(reports[0].top_paths or []) if reports else 0}",
        flush=True,
    )
    summary = (
        f"SEED_SUMMARY brand=funnelpath funnels={funnel_count} members={member_count} "
        f"events={event_count} channels={channel_count} accounts={account_count}"
    )
    print(summary, flush=True)
    return summary


if __name__ == "__main__":  # pragma: no cover
    seed_all()
