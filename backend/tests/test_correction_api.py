"""校正功能的 HTTP 层测试：路由 / JWT 鉴权 / RBAC 403 / 409 回滚 / 响应序列化。

用 FastAPI TestClient + 内存 SQLite，override get_db；不依赖 MySQL / Redis。
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import AuthMiddleware
from src.middlewares.error_handler import register_exception_handlers
from src.routes.corrections import router as corrections_router
from src.utils.security import create_access_token
from tests._correction_fixtures import backfill_event, build_baseline


def _make_client(engine) -> TestClient:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    register_exception_handlers(app)
    app.include_router(corrections_router)

    def _override_get_db():
        session = Session(bind=engine, autoflush=False, expire_on_commit=False)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


@pytest.fixture()
def client(engine_factory, seed_session, funnel):
    build_baseline(seed_session, funnel)
    return _make_client(engine_factory)


def _token(role: str) -> str:
    token, _ = create_access_token(f"{role}@funnelpath.io", role)
    return token


def test_analyst_can_apply_correction_and_response_is_serialized(client, funnel):
    res = client.post(
        f"/funnels/{funnel.id}/corrections",
        json={
            "note": "http 校正",
            "events": [
                backfill_event("u3", "trial_complete", 24),
                backfill_event("u3", "pay", 48),
                backfill_event("u1", "register", 0),  # 重复，被拒绝
            ],
        },
        headers={"Authorization": f"Bearer {_token('analyst')}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["batch"]["ingested"] == 2
    assert body["batch"]["rejected_duplicate"] == 1
    assert body["correction_run"]["is_correction"] is True
    assert body["correction_run"]["is_current"] is True
    assert body["baseline_run"]["is_current"] is False
    assert body["data_version"]["version_no"] == 2
    assert body["correction_meta"]["step_deltas"][0]["unchanged"] is True


def test_viewer_gets_403_on_correction_write(client, funnel):
    res = client.post(
        f"/funnels/{funnel.id}/corrections",
        json={"note": "x", "events": [backfill_event("u3", "trial_complete", 24)]},
        headers={"Authorization": f"Bearer {_token('viewer')}"},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_unauthenticated_request_is_rejected(client, funnel):
    res = client.get(f"/funnels/{funnel.id}/data-versions")
    assert res.status_code == 401


def test_all_duplicate_returns_409_and_keeps_previous_current(client, funnel, engine_factory):
    res = client.post(
        f"/funnels/{funnel.id}/corrections",
        json={"note": "全重复", "events": [backfill_event("u1", "register", 0)]},
        headers={"Authorization": f"Bearer {_token('analyst')}"},
    )
    assert res.status_code == 409
    # 数据版本与运行仍只有基线一版
    versions = client.get(
        f"/funnels/{funnel.id}/data-versions",
        headers={"Authorization": f"Bearer {_token('analyst')}"},
    ).json()["items"]
    assert len(versions) == 1 and versions[0]["version_no"] == 1

    from src.models.funnel_run import FunnelRun

    with Session(bind=engine_factory) as session:
        runs = session.query(FunnelRun).filter(FunnelRun.funnel_id == funnel.id).all()
        assert len(runs) == 1 and runs[0].is_current is True


def test_list_corrections_and_versions_endpoints(client, funnel):
    # 先产生一个批次
    client.post(
        f"/funnels/{funnel.id}/corrections",
        json={"note": "列表", "events": [backfill_event("u3", "pay", 48), backfill_event("u3", "trial_complete", 24)]},
        headers={"Authorization": f"Bearer {_token('analyst')}"},
    )
    headers = {"Authorization": f"Bearer {_token('analyst')}"}

    batches = client.get(f"/corrections?funnel_id={funnel.id}", headers=headers).json()
    assert batches["total"] == 1
    batch_code = batches["items"][0]["batch_code"]

    detail = client.get(f"/corrections/{batch_code}", headers=headers).json()["batch"]
    assert detail["status"] == "applied"
    assert detail["ingested"] == 2

    versions = client.get(f"/funnels/{funnel.id}/data-versions", headers=headers).json()["items"]
    assert [v["version_no"] for v in versions] == [2, 1]
    assert versions[0]["status"] == "active"
    assert versions[1]["status"] == "active"  # 基线版本仍保留可查
