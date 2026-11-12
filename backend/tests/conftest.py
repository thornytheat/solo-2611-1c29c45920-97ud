"""pytest 引导：保证容器内(/app)与宿主机(backend/)两种 cwd 都能 import src/scripts。

校正集成测试的共享夹具也放在这里（pytest 只自动发现 conftest 里的 fixture）：
- engine_factory：StaticPool 内存库，多会话共享同一份已提交数据；
- seed_session：真实提交基线（漏斗 / 事件 / 基线 run / 旧报告）；
- db：测试会话，rollback 只回自身事务，基线已提交不受影响，可验证失败保留上一版。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.config.schema_evolution import evolve  # noqa: E402
from src.constants.enums import FunnelStatus  # noqa: E402
from src.models import Base  # noqa: E402
from src.models.funnel import FunnelDef  # noqa: E402
from tests._correction_fixtures import build_baseline  # noqa: E402


@pytest.fixture()
def engine_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    evolve(engine)
    yield engine
    engine.dispose()


def _new_session(engine) -> Session:
    return Session(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def seed_session(engine_factory):
    """独立会话：真实提交基线数据。"""
    session = _new_session(engine_factory)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture()
def db(engine_factory):
    """测试会话：与基线共享同一内存库连接；rollback 只回自身事务。"""
    session = _new_session(engine_factory)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def funnel(seed_session) -> FunnelDef:
    from tests._correction_fixtures import NOISE, STEPS3

    obj = FunnelDef(
        code="f-corr",
        name="校正测试漏斗",
        description="",
        line_no="L1",
        line_color="line-a",
        steps=[dict(s) for s in STEPS3],
        noise_events=list(NOISE),
        window_days=7,
        cross_session=True,
        status=FunnelStatus.PUBLISHED.value,
        version=1,
        owner_email="analyst@funnelpath.io",
    )
    seed_session.add(obj)
    seed_session.flush()
    return obj


@pytest.fixture()
def baseline(seed_session, funnel):
    return build_baseline(seed_session, funnel)
