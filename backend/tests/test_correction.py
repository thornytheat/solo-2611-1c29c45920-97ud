"""校正运行端到端测试（SQLite + 真实服务层）。

覆盖需求逐条：
- 旧 run / 旧报告保留可查但不再 current；
- 未变化区间步骤人数不变，受补录影响的流失队列给出前后差异；
- 重复 / 迟到记录不会让同一事件多算；
- run 绑定当时配置与数据版本；
- 切换失败回滚，上一版保持 current；成功后结果页 / 路径 / 导出口径一致。
"""
from __future__ import annotations

import pytest

from src.constants.enums import (
    CorrectionKind,
    CorrectionRowStatus,
    DataVersionStatus,
    RunTrigger,
)
from src.models.data_version import DataVersion
from src.models.drop_report import DropReport
from src.models.event import EventLog
from src.models.funnel_run import FunnelRun
from src.schemas.correction import CorrectionIn
from src.services import correction_service, export_service, report_service, run_service
from src.utils.errors import AppError
from tests._correction_fixtures import backfill_event


def _run(db, baseline):
    return db.get(FunnelRun, baseline["run_id"])


def _report(db, baseline):
    return db.get(DropReport, baseline["report_id"])


# ----------------------------------------------------------- 基线口径与版本绑定


def test_baseline_run_counts_and_binds_data_version(db, funnel, baseline):
    run = _run(db, baseline)
    assert [s["users"] for s in run.step_counts] == [3, 2, 1]
    assert run.entry_users == 3 and run.converted_users == 1
    # 同事件同秒重复被折叠，没有多算
    assert run.discard["duplicates_collapsed"] == 1
    # 自动建立基线数据版本并冻结配置
    assert run.data_version_id is not None
    version = db.get(DataVersion, run.data_version_id)
    assert version.version_no == 1
    assert version.status == DataVersionStatus.ACTIVE.value
    snap = run.config_snapshot
    assert snap["window_days"] == 7
    assert [s["event"] for s in snap["steps"]] == ["register", "trial_complete", "pay"]
    assert run.data_fingerprint == version.fingerprint
    assert run.is_current is True


# ----------------------------------------------------------- 校正：新增转化


def test_correction_advances_user_and_flips_current(db, funnel, baseline):
    old_run = _run(db, baseline)
    old_report = _report(db, baseline)

    # 给 u3 补录试听完成 + 付费（窗口内），u3 从“仅注册”推进到转化
    events = [
        backfill_event("u3", "trial_complete", 24),
        backfill_event("u3", "pay", 48),
    ]
    result = correction_service.apply_correction(
        db, funnel, events, note="补录 u3 后续转化", actor_email="analyst@funnelpath.io"
    )
    db.flush()

    new_run = result["correction_run"]
    # 新 run 是校正类型并指向基线
    assert new_run.trigger == RunTrigger.CORRECTION.value
    assert new_run.baseline_run_id == old_run.id
    assert new_run.is_current is True

    # 旧 run 保留可查，但不再是当前结论
    assert old_run.is_current is False
    assert old_run.id != new_run.id
    assert run_service.current_run(db, funnel.id).id == new_run.id

    # 口径变化：试听 2->3，付费 1->2；首步进入人数不变（未变化区间保持）
    assert [s["users"] for s in new_run.step_counts] == [3, 3, 2]
    step_deltas = result["correction_meta"]["step_deltas"]
    assert step_deltas[0]["unchanged"] is True and step_deltas[0]["delta"] == 0
    assert step_deltas[1]["delta"] == 1 and step_deltas[2]["delta"] == 1

    # 受影响用户只有 u3
    affected = result["correction_meta"]["affected_users"]
    assert [u["user_key"] for u in affected] == ["u3"]
    assert affected[0]["change_type"] == "advanced"
    assert affected[0]["baseline_reached_step"] == 1
    assert affected[0]["corrected_reached_step"] == 3

    # 试听完成流失队列从 1 降到 0（u3 离开该队列并转化）；
    # 付费流失队列仍是 u2（1 人），u3 本就是直接转化、不属于任何流失队列，故不产生付费队列差
    cohort = result["correction_meta"]["cohort_deltas"]
    assert {(c["label"], c["delta"]) for c in cohort} == {("试听完成", -1)}

    # 数据版本链：v2 active，parent=v1
    v2 = db.get(DataVersion, new_run.data_version_id)
    assert v2.version_no == 2
    assert v2.status == DataVersionStatus.ACTIVE.value
    assert v2.parent_version_id == old_run.data_version_id
    assert v2.baseline_run_id == old_run.id and v2.correction_run_id == new_run.id
    assert v2.fingerprint != db.get(DataVersion, old_run.data_version_id).fingerprint

    # 旧报告降级但仍在库里可查
    assert old_report.is_current is False
    assert db.get(DropReport, old_report.id) is not None


def test_unchanged_step_counts_are_explicitly_marked(db, funnel, baseline):
    # 补录一个全新用户的完整漏斗（新进入者），首步人数变化，验证 delta 标注
    events = [
        backfill_event("u9", "register", 0),
        backfill_event("u9", "trial_complete", 12),
        backfill_event("u9", "pay", 24),
    ]
    result = correction_service.apply_correction(
        db, funnel, events, note="补录新用户 u9", actor_email="analyst@funnelpath.io"
    )
    deltas = result["correction_meta"]["step_deltas"]
    # 所有步骤都 +1，没有 unchanged；进入 3->4，转化 1->2
    assert all(d["delta"] == 1 for d in deltas)
    assert result["correction_meta"]["totals"] == {
        "baseline_entry": 3,
        "corrected_entry": 4,
        "baseline_converted": 1,
        "corrected_converted": 2,
    }


# ----------------------------------------------------------- 重复 / 迟到不多算


def test_all_duplicate_rolls_back_and_keeps_previous_current(db, funnel, baseline):
    old_run_id = baseline["run_id"]
    dup = backfill_event("u1", "register", 0)
    with pytest.raises(AppError) as exc:
        correction_service.apply_correction(
            db, funnel, [dup], note="全重复", actor_email="analyst@funnelpath.io"
        )
    assert exc.value.status_code == 409
    db.rollback()
    # 回滚后 ORM 对象已过期，重新查询验证：上一版仍是当前
    old_run = db.get(FunnelRun, old_run_id)
    assert old_run.is_current is True
    assert run_service.current_run(db, funnel.id).id == old_run_id
    active_versions = (
        db.query(DataVersion)
        .filter(DataVersion.funnel_id == funnel.id, DataVersion.status == DataVersionStatus.ACTIVE.value)
        .count()
    )
    assert active_versions == 1
    correction_runs = (
        db.query(FunnelRun).filter(FunnelRun.trigger == RunTrigger.CORRECTION.value).count()
    )
    assert correction_runs == 0


def test_mixed_duplicate_and_new_event_counts_once(db, funnel, baseline):
    events = [
        backfill_event("u2", "register", 0),                       # 重复：拒绝
        backfill_event("u2", "pay", 48),                           # 新增：u2 推进到付费
    ]
    result = correction_service.apply_correction(
        db, funnel, events, note="混合补录", actor_email="analyst@funnelpath.io"
    )
    counters = result["counters"]
    assert counters["rejected_duplicate"] == 1
    assert counters["ingested"] == 1
    # 只有 pay 真正入库；register 没多算
    new_run = result["correction_run"]
    assert [s["users"] for s in new_run.step_counts] == [3, 2, 2]
    rows = result["correction_rows"]
    kinds = {r.event_name: r for r in rows}
    assert kinds["register"].status == CorrectionRowStatus.REJECTED_DUPLICATE.value
    assert kinds["register"].is_duplicate is True
    assert kinds["pay"].status == CorrectionRowStatus.INGESTED.value

    # 批次明细可查
    batch = correction_service.get_batch(db, result["batch_code"], funnel.id)
    assert batch["rejected_duplicate"] == 1 and batch["ingested"] == 1
    assert batch["status"] == "applied"


def test_late_event_is_flagged_but_still_ordered_by_event_ts(db, funnel, baseline):
    # 水位线是基线最大事件时间；补录 u3 的一条“更早”的试听开始（迟到但不重复）
    late = backfill_event("u3", "trial_complete", -5)  # 早于 ANCHOR => 迟到
    result = correction_service.apply_correction(
        db, funnel, [late], note="迟到补录", actor_email="analyst@funnelpath.io"
    )
    row = result["correction_rows"][0]
    assert row.is_late is True
    assert row.kind == CorrectionKind.LATE.value
    assert result["counters"]["late"] == 1
    # 迟到记录按事件时间参与状态机：u3 在 -5h 试听完成、0h 注册 => 注册仍是首步，
    # 试听发生在注册之前，严格顺序下不被认可，u3 仍停在注册（口径不被乱序污染）
    new_run = result["correction_run"]
    assert [s["users"] for s in new_run.step_counts] == [3, 2, 1]


def test_in_batch_duplicate_is_rejected(db, funnel, baseline):
    events = [
        backfill_event("u7", "register", 3),
        backfill_event("u7", "register", 3),  # 批内完全重复
    ]
    result = correction_service.apply_correction(
        db, funnel, events, note="批内重复", actor_email="analyst@funnelpath.io"
    )
    assert result["counters"]["ingested"] == 1
    assert result["counters"]["rejected_duplicate"] == 1
    # event_logs 里 u7 只有一条 register
    count = (
        db.query(EventLog)
        .filter(EventLog.user_key == "u7", EventLog.event_name == "register")
        .count()
    )
    assert count == 1


# ----------------------------------------------------------- 失败回滚保留上一版


def test_failure_midway_rolls_back_and_keeps_previous_version(db, funnel, baseline, monkeypatch):
    old_run_id = baseline["run_id"]

    def boom(*args, **kwargs):
        raise RuntimeError("模拟校正计算失败")

    # 让重跑阶段抛错，模拟切换失败
    monkeypatch.setattr(run_service, "execute", boom)
    with pytest.raises(RuntimeError):
        correction_service.apply_correction(
            db,
            funnel,
            [backfill_event("u3", "trial_complete", 24)],
            note="会失败的校正",
            actor_email="analyst@funnelpath.io",
        )
    db.rollback()

    old_run = db.get(FunnelRun, old_run_id)
    assert old_run.is_current is True
    # 没有 building/active 新版本残留，事件补录也随事务回滚
    assert (
        db.query(DataVersion)
        .filter(DataVersion.funnel_id == funnel.id)
        .count() == 1
    )
    assert db.query(EventLog).filter(EventLog.source == "backfill").count() == 0


# ----------------------------------------------------------- 结果页 / 路径 / 导出一致


def test_path_analysis_and_export_follow_current_run(db, funnel, baseline):
    events = [backfill_event("u3", "trial_complete", 24), backfill_event("u3", "pay", 48)]
    result = correction_service.apply_correction(
        db, funnel, events, note="u3 转化", actor_email="analyst@funnelpath.io"
    )
    new_run = result["correction_run"]

    # 路径分析基于当前校正 run 的物化 session_paths
    analysis = run_service.path_analysis(db, new_run, funnel, step_index=1)
    assert analysis["run"]["id"] == new_run.id
    assert analysis["run"]["is_correction"] is True
    # 试听完成流失队列已清空
    assert analysis["cohort"]["cohort_users"] == 0

    # 旧 run 仍可单独查询（归档可查）
    old_run = db.get(FunnelRun, baseline["run_id"])
    old_payload = run_service.serialize(old_run, funnel)
    assert old_payload["is_current"] is False
    assert old_payload["steps"][2]["users"] == 1  # 旧结论维持原样

    # 从校正 run 生成新报告并导出，导出含数据版本与校正说明
    class _P:
        drop_step_index = 1
        title = "校正后归因"
        conclusion = "新结论"

    new_report = report_service.create(db, new_run, funnel, _P(), "analyst@funnelpath.io")
    assert new_report.is_current is True
    assert new_report.data_version_id == new_run.data_version_id
    md = export_service.render_markdown(
        new_report, funnel, run_service.serialize(new_run, funnel, db.get(DataVersion, new_run.data_version_id))
    )
    assert "数据版本" in md and "校正运行" in md
    assert "校正前后流失队列差异" in md


def test_serialize_exposes_version_and_correction_fields(db, funnel, baseline):
    result = correction_service.apply_correction(
        db,
        funnel,
        [backfill_event("u3", "pay", 48), backfill_event("u3", "trial_complete", 24)],
        note="乱序补录",
        actor_email="analyst@funnelpath.io",
    )
    new_version = db.get(DataVersion, result["correction_run"].data_version_id)
    payload = run_service.serialize(result["correction_run"], funnel, new_version)
    assert payload["is_correction"] is True
    assert payload["baseline_run_id"] == baseline["run_id"]
    assert payload["data_version_no"] == 2
    assert payload["config_frozen"] is True
    assert len(payload["data_fingerprint_short"]) == 12
    assert payload["correction_meta"]["ingested"] == 2


def test_correction_requires_existing_baseline_run(db, funnel):
    # 没有任何 run 时校正应被拒绝
    with pytest.raises(AppError) as exc:
        correction_service.apply_correction(
            db, funnel, [backfill_event("u1", "register", 0)], note="无基线", actor_email="x@x.io"
        )
    assert exc.value.status_code == 409


def test_unknown_event_outside_vocabulary_is_rejected(db, funnel, baseline):
    # 不在漏斗步骤/白名单内的事件无法纳入状态机口径，返回 422
    with pytest.raises(AppError) as exc:
        correction_service.apply_correction(
            db,
            funnel,
            [backfill_event("u3", "not_a_real_event", 1)],
            note="词表外事件",
            actor_email="analyst@funnelpath.io",
        )
    assert exc.value.status_code == 422
    assert "unknown_events" in exc.value.detail


def test_correction_uses_frozen_baseline_config_even_if_definition_changes(db, funnel, baseline):
    from src.schemas.funnel import FunnelPatch
    from src.services import funnel_service

    # 在测试会话里重新获取漏斗（夹具对象属于 seed_session）
    target = funnel_service.get_by_id(db, funnel.id)
    # 基线后有人改了漏斗定义（窗口 7 -> 30 天、版本 +1）
    funnel_service.update(db, target, FunnelPatch(window_days=30))
    db.commit()

    result = correction_service.apply_correction(
        db,
        target,
        [backfill_event("u3", "trial_complete", 24), backfill_event("u3", "pay", 48)],
        note="定义变更后的校正",
        actor_email="analyst@funnelpath.io",
    )
    new_run = result["correction_run"]
    # 校正 run 仍按基线冻结的 7 天窗口与 v1 定义，而不是当前的 30 天 / v2
    assert new_run.window_days == 7
    assert new_run.config_snapshot["window_days"] == 7
    assert new_run.config_snapshot["funnel_version"] == 1
    assert new_run.data_version_id is not None


def test_pydantic_schema_validates_payload(db, funnel):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CorrectionIn(note="x", events=[])  # 至少一条
    payload = CorrectionIn(
        events=[backfill_event("u1", "register", 0)],
    )
    assert payload.events[0].channel.value == "organic"
