"""事件补录与校正运行：分类（迟到/重复）→ 校正计算 → 前后差异 → 原子切换。

一次校正（单个事务，失败整体回滚，上一版保持 current）：
1. 定位基线运行（当前 run）与其数据版本、水位线；
2. 逐行判定补录：与既有事件「同用户同事件同秒」=> 重复拒绝；早于水位线 => 迟到；
   批内自身重复也拒绝；通过者写入 event_logs，data_version_id 指向新版本；
3. 用与基线完全相同的漏斗配置（config_snapshot）重跑状态机，生成 correction run；
4. 对比基线/校正两版 outcome：受影响用户、各流失队列前后人数差、各步骤人数差，
   未变化区间的步骤人数必须保持不变（build_correction 会显式标注 unchanged）；
5. 原子翻转：新 run 置 current，旧 run 与旧报告置 is_current=False，新版本激活；
   任一步抛错 => 事务回滚，旧 run/旧版本继续 current（“切换失败保留上一版”）。
"""
from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    CorrectionKind,
    CorrectionRowStatus,
    CorrectionStatus,
    RunTrigger,
    label_of_event,
)
from src.models.data_version import DataVersion
from src.models.drop_report import DropReport
from src.models.event import EventLog
from src.models.event_correction import EventCorrection
from src.models.funnel import FunnelDef
from src.models.funnel_run import FunnelRun
from src.services import data_version_service, run_service
from src.utils.errors import conflict, not_found, validation
from src.utils.timeutil import BIZ_TZ, iso


# --------------------------------------------------------------------------- 工具


def fingerprint_of(user_key: str, event_name: str, event_ts: datetime, seq: int) -> str:
    """补录行的自然身份：用户 + 事件 + 秒级时间 + 入库序号。"""
    second = event_ts.replace(microsecond=0).isoformat()
    blob = f"{user_key}|{event_name}|{second}|{int(seq)}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def natural_key(user_key: str, event_name: str, event_ts: datetime) -> tuple[str, str, str]:
    """去重口径与 funnel_engine._dedupe_and_sort 完全一致：同用户同事件同秒即同一事件。"""
    return (user_key, event_name, event_ts.replace(microsecond=0).isoformat())


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise validation({"event_ts": value, "reason": "无法解析的时间（需要 ISO 8601）"}) from exc
    if parsed.tzinfo is not None:
        # event_logs 存 naive（业务时区 UTC+8），统一去掉时区信息
        parsed = parsed.replace(tzinfo=None)
    return parsed


class _FrozenFunnel:
    """以基线 run 冻结的配置呈现的只读漏斗（校正必须按当时口径重算）。

    只暴露引擎/服务实际访问的属性；vocabulary 与基线快照完全一致，
    因此校正期间即便有人改了 FunnelDef，也不会改变本次校正口径。
    """

    def __init__(self, funnel: FunnelDef, snapshot: dict, window_days: int):
        self.id = funnel.id
        self.code = snapshot.get("funnel_code", funnel.code)
        self.name = funnel.name
        self.line_no = funnel.line_no
        self.line_color = funnel.line_color
        self.version = snapshot.get("funnel_version", funnel.version)
        self.steps = [dict(step) for step in snapshot.get("steps", funnel.steps)]
        self.noise_events = list(snapshot.get("noise_events", funnel.noise_events or []))
        self.window_days = window_days
        self.cross_session = snapshot.get("cross_session", funnel.cross_session)

    @property
    def vocabulary(self) -> set[str]:
        names = {step["event"] for step in self.steps}
        names.update(self.noise_events)
        return names


# --------------------------------------------------------------------------- 主流程


def apply_correction(
    db: Session,
    funnel: FunnelDef,
    events: list[dict],
    *,
    note: str,
    actor_email: str,
) -> dict:
    if not events:
        raise validation({"events": "补录事件不能为空"})

    baseline_run = run_service.current_run(db, funnel.id)
    if baseline_run is None:
        raise conflict({"reason": "该漏斗还没有成功运行，无法校正；请先运行一次基线漏斗。"})
    baseline_version = db.get(DataVersion, baseline_run.data_version_id) if baseline_run.data_version_id else None
    if baseline_version is None:
        # 兼容更早的无版本数据：现场补建基线版本
        baseline_version = data_version_service.ensure_baseline(db, funnel, baseline_run)

    window_days = baseline_run.window_days or funnel.window_days
    # 校正口径锁定为基线 run 冻结的配置（步骤 / 白名单 / 窗口 / 跨会话）
    snapshot = baseline_run.config_snapshot or baseline_version.config_snapshot or {}
    frozen = _FrozenFunnel(funnel, snapshot, window_days)
    vocabulary = frozen.vocabulary

    # 词表校验：补录事件必须属于该漏斗的步骤事件或去噪白名单，否则口径无法纳入状态机
    unknown = sorted({str(item["event_name"]).strip() for item in events
                      if str(item["event_name"]).strip() not in vocabulary})
    if unknown:
        raise validation({"unknown_events": unknown, "vocabulary": sorted(vocabulary)})

    watermark = dict(baseline_version.watermark or {})
    baseline_max_ts = _parse_watermark_ts(watermark.get("max_event_ts"))
    batch_code = f"CRR-{funnel.code.upper()}-{datetime.now(BIZ_TZ).strftime('%Y%m%d%H%M%S%f')}"

    # 既有事件的自然键集合（同用户同事件同秒）→ 用于重复判定
    existing_keys = _existing_natural_keys(db, events)
    seen_in_batch: set[tuple[str, str, str]] = set()
    seen_fingerprints: set[str] = set()

    version = data_version_service.create_correction_version(
        db,
        funnel,
        baseline_version,
        baseline_run,
        window_days=window_days,
        note=note,
        created_by=actor_email,
    )

    ingested_rows: list[dict] = []
    correction_rows: list[EventCorrection] = []
    counters = Counter()
    next_seq = int(db.scalar(select(func.coalesce(func.max(EventLog.seq), 0))) or 0)

    for index, item in enumerate(events):
        user_key = str(item["user_key"]).strip()
        event_name = str(item["event_name"]).strip()
        event_ts = _parse_ts(item["event_ts"])
        seq = int(item.get("seq") or 0)
        channel = item.get("channel") or "organic"
        device = item.get("device") or "ios"
        session_id = item.get("session_id") or ""
        base_fp = fingerprint_of(user_key, event_name, event_ts, seq)
        nkey = natural_key(user_key, event_name, event_ts)

        is_late = baseline_max_ts is not None and event_ts < baseline_max_ts
        duplicate_of = existing_keys.get(nkey)
        is_batch_dup = nkey in seen_in_batch or base_fp in seen_fingerprints
        is_duplicate = duplicate_of is not None or is_batch_dup

        if is_duplicate:
            kind = CorrectionKind.DUPLICATE.value if not is_late else CorrectionKind.LATE_DUPLICATE.value
            status = CorrectionRowStatus.REJECTED_DUPLICATE.value
            reason = "与既有事件同用户同事件同秒" if duplicate_of is not None else "补录批次内重复"
            counters["rejected_duplicate"] += 1
            # 重复行不参与入库；指纹加确定性后缀以满足 UNIQUE，原事件身份保留在 base 指纹里
            fp = f"{base_fp}:dup{index}"
        else:
            kind = CorrectionKind.LATE.value if is_late else CorrectionKind.NORMAL.value
            status = CorrectionRowStatus.INGESTED.value
            reason = ""
            fp = base_fp
            counters["ingested"] += 1
            if is_late:
                counters["late"] += 1

        correction = EventCorrection(
            batch_code=batch_code,
            funnel_id=funnel.id,
            data_version_id=version.id,
            user_key=user_key,
            event_name=event_name,
            event_ts=event_ts,
            seq=seq,
            session_id=session_id,
            channel=channel,
            device=device,
            source=item.get("source") or "backfill",
            status=status,
            kind=kind,
            is_late=bool(is_late),
            is_duplicate=bool(is_duplicate),
            duplicate_of_event_id=duplicate_of,
            fingerprint=fp,
            reason=reason,
            detail={
                "watermark_max_event_ts": watermark.get("max_event_ts"),
                "in_batch_duplicate": is_batch_dup,
            },
        )
        correction_rows.append(correction)

        if not is_duplicate:
            next_seq += 10
            seen_in_batch.add(nkey)
            seen_fingerprints.add(fp)
            ingested_rows.append(
                {
                    "seed_key": None,
                    "user_key": user_key,
                    "event_name": event_name,
                    "event_ts": event_ts,
                    # seq 全局单调递增，仅在同秒时作为稳定次序兜底；迟到与否都按 event_ts 排序纠正
                    "seq": next_seq,
                    "session_id": session_id,
                    "channel": channel,
                    "device": device,
                    "source": item.get("source") or "backfill",
                    "data_version_id": version.id,
                }
            )

    db.add_all(correction_rows)
    db.flush()

    if not ingested_rows:
        # 全部被判重复：没有任何新数据，拒绝切换并回滚，避免产生无意义的校正版本
        raise conflict({
            "reason": "全部补录记录均为重复，未产生新事件，已取消校正（上一版保留）。",
            "rejected_duplicate": counters["rejected_duplicate"],
        })

    if ingested_rows:
        db.bulk_insert_mappings(EventLog, ingested_rows)
        db.flush()

    # ---- 用基线冻结的同一份配置重跑（口径锁定，不受校正期间定义变更影响）----
    vocabulary_rows = data_version_service.vocabulary_events(db, vocabulary)
    correction_meta = build_correction(
        db,
        frozen,
        baseline_run=baseline_run,
        baseline_version=baseline_version,
        vocabulary_rows=vocabulary_rows,
        window_days=window_days,
        counters=counters,
        batch_code=batch_code,
    )

    run_code = f"RUN-CRR-{funnel.code.upper()}-{datetime.now(BIZ_TZ).strftime('%Y%m%d%H%M%S%f')}"
    correction_run = run_service.execute(
        db,
        frozen,
        trigger=RunTrigger.CORRECTION.value,
        code=run_code,
        window_days=window_days,
        data_version=version,
        baseline_run_id=baseline_run.id,
        correction_meta=correction_meta,
        is_current=True,
        bind_baseline_version=False,
    )

    # ---- 激活新版本（写回指纹 / 水位 / 统计）----
    data_version_service.activate(
        db,
        version,
        correction_run,
        vocabulary_rows,
        ingested=counters["ingested"],
        rejected=counters["rejected_duplicate"],
        late=counters["late"],
    )
    correction_run.data_fingerprint = version.fingerprint
    db.flush()

    # ---- 原子翻转当前结论：旧 run 与旧报告降级，新 run 保持 current ----
    demoted_runs = data_version_service.demote_current_runs(db, funnel.id, correction_run.id)
    demoted_reports = _demote_reports(db, funnel.id, baseline_run.id)

    db.flush()
    return {
        "batch_code": batch_code,
        "data_version": version,
        "baseline_run": baseline_run,
        "correction_run": correction_run,
        "correction_meta": correction_meta,
        "counters": dict(counters),
        "demoted_runs": demoted_runs,
        "demoted_reports": demoted_reports,
        "correction_rows": correction_rows,
    }


# --------------------------------------------------------------------------- 差异计算


def build_correction(
    db: Session,
    funnel,
    *,
    baseline_run: FunnelRun,
    baseline_version: DataVersion,
    vocabulary_rows,
    window_days: int,
    counters: Counter,
    batch_code: str,
) -> dict:
    """对比基线/校正两版：受影响用户、流失队列前后差、步骤人数差。

    ``funnel`` 可以是 FunnelDef 或 _FrozenFunnel；校正场景传冻结配置，
    保证「按当时口径重算」。未变化区间（步骤人数相同）显式标 unchanged=True，
    满足「未变化区间的步骤人数保持不变」的可核验要求。
    """
    baseline_outcomes = run_service.outcomes_for_run(db, baseline_run)

    # 在内存里重跑一次校正后的状态机（不写库），拿到用户级 outcome 做逐户对比
    from collections import defaultdict

    from src.services import funnel_engine

    grouped: dict[str, list] = defaultdict(list)
    for row in vocabulary_rows:
        grouped[row.user_key].append(row)
    fresh = funnel_engine.run_funnel(grouped, funnel.steps, window_days, funnel.vocabulary)
    new_outcomes = fresh["outcomes"]

    affected_users = _affected_user_diffs(baseline_outcomes, new_outcomes)
    step_deltas = _step_deltas(baseline_run.step_counts or [], fresh["steps"])
    cohort_deltas = _cohort_deltas(baseline_outcomes, new_outcomes, funnel.steps)

    return {
        "batch_code": batch_code,
        "baseline_run_id": baseline_run.id,
        "baseline_run_code": baseline_run.code,
        "baseline_version_id": baseline_version.id,
        "baseline_version_no": baseline_version.version_no,
        "generated_at": iso(datetime.now(BIZ_TZ).replace(tzinfo=None)),
        "ingested": counters["ingested"],
        "rejected_duplicate": counters["rejected_duplicate"],
        "late": counters["late"],
        "affected_user_count": len(affected_users),
        "affected_users": affected_users,
        "step_deltas": step_deltas,
        "cohort_deltas": cohort_deltas,
        "totals": {
            "baseline_entry": baseline_run.entry_users,
            "corrected_entry": fresh["entry_users"],
            "baseline_converted": baseline_run.converted_users,
            "corrected_converted": fresh["converted_users"],
        },
    }


def _affected_user_diffs(baseline_outcomes: dict, new_outcomes: dict) -> list[dict]:
    keys = sorted(set(baseline_outcomes) | set(new_outcomes))
    rows = []
    for key in keys:
        old = baseline_outcomes.get(key)
        new = new_outcomes.get(key)
        old_step = getattr(old, "reached_step", 0) if old else 0
        new_step = getattr(new, "reached_step", 0) if new else 0
        old_conv = bool(getattr(old, "converted", False)) if old else False
        new_conv = bool(getattr(new, "converted", False)) if new else False
        old_path = getattr(old, "path_label", "") if old else ""
        new_path = getattr(new, "path_label", "") if new else ""
        if old_step == new_step and old_conv == new_conv and old_path == new_path and old is not None and new is not None:
            continue
        change_type = "unchanged"
        if old is None and new is not None:
            change_type = "newly_entered"
        elif old is not None and new is None:
            change_type = "removed"
        elif new_step > old_step:
            change_type = "advanced"
        elif new_step < old_step:
            change_type = "regressed"
        elif old_path != new_path:
            change_type = "path_changed"
        rows.append(
            {
                "user_key": key,
                "change_type": change_type,
                "baseline_reached_step": old_step,
                "corrected_reached_step": new_step,
                "baseline_converted": old_conv,
                "corrected_converted": new_conv,
                "baseline_path": old_path,
                "corrected_path": new_path,
                "channel": getattr(new, "channel", None) or getattr(old, "channel", None),
                "device": getattr(new, "device", None) or getattr(old, "device", None),
            }
        )
    return rows


def _step_deltas(baseline_steps: list[dict], corrected_steps: list[dict]) -> list[dict]:
    rows = []
    for index, new_step in enumerate(corrected_steps):
        old_step = baseline_steps[index] if index < len(baseline_steps) else None
        old_users = old_step["users"] if old_step else 0
        new_users = new_step["users"]
        rows.append(
            {
                "index": index,
                "key": new_step.get("key", new_step["event"]),
                "event": new_step["event"],
                "label": new_step["label"],
                "baseline_users": old_users,
                "corrected_users": new_users,
                "delta": new_users - old_users,
                "unchanged": old_users == new_users,
            }
        )
    return rows


def _cohort_deltas(baseline_outcomes: dict, new_outcomes: dict, steps: list[dict]) -> list[dict]:
    """每个流失队列（未到达第 i 步）的前后人数与差异，只列受影响队列。"""
    rows = []
    for index in range(1, len(steps)):
        def _cohort_size(outcomes: dict) -> int:
            return sum(
                1
                for o in outcomes.values()
                if not getattr(o, "converted", False)
                and getattr(o, "drop_step", -1) == index
                and getattr(o, "reached_step", 0) > 0
            )

        before = _cohort_size(baseline_outcomes)
        after = _cohort_size(new_outcomes)
        if before == after:
            continue
        rows.append(
            {
                "step_index": index,
                "event": steps[index]["event"],
                "label": steps[index]["label"],
                "baseline_cohort_users": before,
                "corrected_cohort_users": after,
                "delta": after - before,
            }
        )
    return rows


# --------------------------------------------------------------------------- 辅助查询


def _parse_watermark_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return _parse_ts(value)
    except Exception:
        return None


def _existing_natural_keys(db: Session, events: list[dict]) -> dict[tuple, int]:
    """只查询补录涉及到的用户，拉回其事件构造自然键 -> event_id 映射。"""
    user_keys = {str(item["user_key"]).strip() for item in events}
    if not user_keys:
        return {}
    rows = db.scalars(select(EventLog).where(EventLog.user_key.in_(list(user_keys)))).all()
    return {
        natural_key(row.user_key, row.event_name, row.event_ts): row.id
        for row in rows
    }


def _demote_reports(db: Session, funnel_id: int, baseline_run_id: int) -> int:
    """旧 run 关联的、仍 current 的报告降级（内容保留，只是不再充当当前结论）。

    走 ORM 逐行更新，保证会话内已加载的报告对象状态同步。
    """
    rows = db.scalars(
        select(DropReport).where(
            DropReport.funnel_id == funnel_id,
            DropReport.run_id == baseline_run_id,
            DropReport.is_current.is_(True),
        )
    ).all()
    for row in rows:
        row.is_current = False
    db.flush()
    return len(rows)


# --------------------------------------------------------------------------- 只读查询


def list_corrections(db: Session, funnel_id: int | None = None, limit: int = 20) -> list[dict]:
    stmt = (
        select(EventCorrection.batch_code, EventCorrection.funnel_id)
        .group_by(EventCorrection.batch_code, EventCorrection.funnel_id)
        .order_by(func.max(EventCorrection.id).desc())
        .limit(limit)
    )
    if funnel_id:
        stmt = (
            select(EventCorrection.batch_code, EventCorrection.funnel_id)
            .where(EventCorrection.funnel_id == funnel_id)
            .group_by(EventCorrection.batch_code, EventCorrection.funnel_id)
            .order_by(func.max(EventCorrection.id).desc())
            .limit(limit)
        )
    batches = db.execute(stmt).all()
    return [get_batch(db, batch_code, fid) for batch_code, fid in batches]


def get_batch(db: Session, batch_code: str, funnel_id: int | None = None) -> dict:
    stmt = select(EventCorrection).where(EventCorrection.batch_code == batch_code)
    if funnel_id:
        stmt = stmt.where(EventCorrection.funnel_id == funnel_id)
    rows = db.scalars(stmt.order_by(EventCorrection.id)).all()
    if not rows:
        raise not_found({"batch_code": batch_code})

    # 通过数据版本关联到校正 run（DataVersion.correction_run_id）
    first = rows[0]
    version = db.get(DataVersion, first.data_version_id) if first.data_version_id else None
    correction_run = (
        db.get(FunnelRun, version.correction_run_id)
        if version is not None and version.correction_run_id
        else None
    )
    ingested = sum(1 for r in rows if r.status == CorrectionRowStatus.INGESTED.value)
    rejected = sum(1 for r in rows if r.status == CorrectionRowStatus.REJECTED_DUPLICATE.value)
    late = sum(1 for r in rows if r.is_late and r.status == CorrectionRowStatus.INGESTED.value)
    status = (
        CorrectionStatus.APPLIED.value
        if ingested
        else CorrectionStatus.FAILED.value
    )
    return {
        "batch_code": batch_code,
        "funnel_id": first.funnel_id,
        "data_version_id": first.data_version_id,
        "data_version_no": getattr(version, "version_no", None),
        "status": status,
        "total_rows": len(rows),
        "ingested": ingested,
        "rejected_duplicate": rejected,
        "late": late,
        "correction_run_id": getattr(correction_run, "id", None),
        "correction_run_code": getattr(correction_run, "code", None),
        "rows": [serialize_correction_row(r) for r in rows],
    }


def serialize_correction_row(row: EventCorrection) -> dict:
    return {
        "id": row.id,
        "batch_code": row.batch_code,
        "user_key": row.user_key,
        "event_name": row.event_name,
        "event_label": label_of_event(row.event_name),
        "event_ts": iso(row.event_ts),
        "seq": row.seq,
        "session_id": row.session_id,
        "channel": row.channel,
        "device": row.device,
        "source": row.source,
        "status": row.status,
        "kind": row.kind,
        "is_late": bool(row.is_late),
        "is_duplicate": bool(row.is_duplicate),
        "duplicate_of_event_id": row.duplicate_of_event_id,
        "reason": row.reason,
        "detail": row.detail or {},
    }
