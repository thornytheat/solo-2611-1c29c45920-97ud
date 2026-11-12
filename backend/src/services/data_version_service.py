"""数据版本服务：配置快照 / 事件指纹 / 版本链 / 当前 run 翻转。

口径：
- 配置快照冻结 funnel 的 steps / noise_events / window / cross_session / version + 引擎版本，
  保证任何一次 run 都能回答「当时按什么配置算的」；
- 事件指纹只纳入该漏斗白名单（vocabulary）内的事件，与 funnel_engine 的输入口径一致；
- 每个漏斗维护一条线性版本链（parent_version_id），基线版本 version_no=1。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import DataVersionStatus, RunStatus
from src.models.data_version import DataVersion
from src.models.event import EventLog
from src.models.funnel import FunnelDef
from src.models.funnel_run import FunnelRun
from src.utils.timeutil import BIZ_TZ, iso

# 与 run_service.ENGINE_VERSION 保持一致；直接写字面量以避免循环导入。
ENGINE_VERSION = "1.0.0"


def config_snapshot(funnel: FunnelDef, window_days: int) -> dict:
    """冻结当时的漏斗配置（深拷贝，避免后续定义变更污染历史 run）。"""
    return {
        "funnel_code": funnel.code,
        "funnel_version": funnel.version,
        "steps": [dict(step) for step in funnel.steps],
        "noise_events": list(funnel.noise_events or []),
        "window_days": window_days,
        "cross_session": bool(funnel.cross_session),
        "engine_version": ENGINE_VERSION,
    }


def fingerprint_rows(rows) -> str:
    """对一组事件行计算稳定指纹：同集合必同值，集合变化（增/改）必变化。"""
    payload = [
        {
            "u": row.user_key,
            "e": row.event_name,
            "t": row.event_ts.replace(microsecond=0).isoformat() if row.event_ts else None,
            "s": int(row.seq),
        }
        for row in rows
    ]
    payload.sort(key=lambda item: (item["u"], item["t"] or "", item["s"], item["e"]))
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def vocabulary_events(db: Session, vocabulary: set[str]) -> list[EventLog]:
    if not vocabulary:
        return []
    return db.scalars(
        select(EventLog)
        .where(EventLog.event_name.in_(list(vocabulary)))
        .order_by(EventLog.user_key, EventLog.event_ts, EventLog.seq)
    ).all()


def watermark_of(rows) -> dict:
    """基线水位线：最大事件时间 + 最大 seq，用于迟到判定。"""
    if not rows:
        return {"max_event_ts": None, "max_seq": 0}
    return {
        "max_event_ts": iso(max(row.event_ts for row in rows)),
        "max_seq": int(max(int(row.seq) for row in rows)),
    }


def ensure_baseline(
    db: Session,
    funnel: FunnelDef,
    run: FunnelRun,
    *,
    created_by: str = "system",
) -> DataVersion:
    """为普通 run 兜底创建/复用基线数据版本（version_no=1）。

    同一漏斗已有 active 版本则复用并把该 run 绑上去；否则用当前事件集合建 v1。
    """
    existing = db.scalar(
        select(DataVersion)
        .where(DataVersion.funnel_id == funnel.id, DataVersion.status == DataVersionStatus.ACTIVE.value)
        .order_by(DataVersion.id.desc())
        .limit(1)
    )
    window = run.window_days or funnel.window_days
    if existing is not None:
        run.data_version_id = existing.id
        run.config_snapshot = existing.config_snapshot or config_snapshot(funnel, window)
        run.data_fingerprint = existing.fingerprint
        db.flush()
        return existing

    rows = vocabulary_events(db, funnel.vocabulary)
    now = datetime.now(BIZ_TZ).replace(tzinfo=None)
    version = DataVersion(
        code=f"DV-{funnel.code.upper()}-V1-{run.id}",
        funnel_id=funnel.id,
        version_no=1,
        status=DataVersionStatus.ACTIVE.value,
        config_snapshot=config_snapshot(funnel, window),
        window_days=window,
        fingerprint=fingerprint_rows(rows),
        event_count=len(rows),
        watermark=watermark_of(rows),
        note="基线数据版本（首次运行时自动建立）",
        created_by=created_by,
        activated_at=now,
    )
    db.add(version)
    db.flush()
    run.data_version_id = version.id
    run.config_snapshot = version.config_snapshot
    run.data_fingerprint = version.fingerprint
    db.flush()
    return version


def create_correction_version(
    db: Session,
    funnel: FunnelDef,
    baseline_version: DataVersion,
    baseline_run: FunnelRun,
    *,
    window_days: int,
    note: str,
    created_by: str,
) -> DataVersion:
    """校正事务开始时建立 building 版本（失败回滚则不会留下 active 新版）。"""
    next_no = int(
        db.scalar(
            select(func.coalesce(func.max(DataVersion.version_no), 0)).where(
                DataVersion.funnel_id == funnel.id
            )
        ) or 0
    ) + 1
    version = DataVersion(
        code=f"DV-{funnel.code.upper()}-V{next_no}-{datetime.now(BIZ_TZ).strftime('%H%M%S%f')}",
        funnel_id=funnel.id,
        version_no=next_no,
        status=DataVersionStatus.BUILDING.value,
        parent_version_id=baseline_version.id,
        baseline_run_id=baseline_run.id,
        config_snapshot=config_snapshot(funnel, window_days),
        window_days=window_days,
        fingerprint="",
        watermark=dict(baseline_version.watermark or {}),
        note=note,
        created_by=created_by,
    )
    db.add(version)
    db.flush()
    return version


def activate(
    db: Session,
    version: DataVersion,
    correction_run: FunnelRun,
    rows,
    *,
    ingested: int,
    rejected: int,
    late: int,
) -> DataVersion:
    """校正计算成功后激活新版本并写回指纹/水位/统计。"""
    now = datetime.now(BIZ_TZ).replace(tzinfo=None)
    version.status = DataVersionStatus.ACTIVE.value
    version.correction_run_id = correction_run.id
    version.fingerprint = fingerprint_rows(rows)
    version.event_count = len(rows)
    version.ingested_count = ingested
    version.rejected_duplicate_count = rejected
    version.late_count = late
    version.watermark = watermark_of(rows)
    version.activated_at = now
    db.flush()
    return version


def current_version(db: Session, funnel_id: int) -> DataVersion | None:
    return db.scalar(
        select(DataVersion)
        .where(DataVersion.funnel_id == funnel_id, DataVersion.status == DataVersionStatus.ACTIVE.value)
        .order_by(DataVersion.id.desc())
        .limit(1)
    )


def serialize(version: DataVersion) -> dict:
    return {
        "id": version.id,
        "code": version.code,
        "funnel_id": version.funnel_id,
        "version_no": version.version_no,
        "status": version.status,
        "parent_version_id": version.parent_version_id,
        "baseline_run_id": version.baseline_run_id,
        "correction_run_id": version.correction_run_id,
        "config_snapshot": version.config_snapshot or {},
        "window_days": version.window_days,
        "fingerprint": version.fingerprint,
        "fingerprint_short": (version.fingerprint or "")[:12],
        "event_count": version.event_count,
        "ingested_count": version.ingested_count,
        "rejected_duplicate_count": version.rejected_duplicate_count,
        "late_count": version.late_count,
        "watermark": version.watermark or {},
        "note": version.note,
        "created_by": version.created_by,
        "created_at": iso(version.created_at),
        "activated_at": iso(version.activated_at),
    }


def list_versions(db: Session, funnel_id: int) -> list[dict]:
    rows = db.scalars(
        select(DataVersion)
        .where(DataVersion.funnel_id == funnel_id)
        .order_by(DataVersion.id.desc())
    ).all()
    return [serialize(row) for row in rows]


def demote_current_runs(db: Session, funnel_id: int, new_run_id: int) -> int:
    """把同漏斗其它成功 run 置为非当前，仅新 run 保持 current。返回被降级条数。

    走 ORM 逐行更新（而非 Core 批量 UPDATE），保证会话内已加载对象的状态同步，
    序列化旧 run 时能立刻读到 is_current=False。
    """
    rows = db.scalars(
        select(FunnelRun).where(
            FunnelRun.funnel_id == funnel_id,
            FunnelRun.id != new_run_id,
            FunnelRun.status == RunStatus.SUCCEEDED.value,
            FunnelRun.is_current.is_(True),
        )
    ).all()
    for row in rows:
        row.is_current = False
    db.flush()
    return len(rows)
