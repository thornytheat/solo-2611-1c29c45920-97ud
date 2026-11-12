from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import funnel_controller
from src.middlewares.rbac import require_permission
from src.schemas.funnel import FunnelIn, FunnelPatch, TrialIn

router = APIRouter(prefix="/funnels", tags=["funnels"])


@router.get("")
def list_funnels(
    status: str | None = Query(default=None),
    principal: dict = Depends(require_permission("funnel:read")),
    db: Session = Depends(get_db),
) -> dict:
    return funnel_controller.list_funnels(db, status)


@router.post("/trial")
def trial(
    payload: TrialIn,
    principal: dict = Depends(require_permission("run:execute")),
    db: Session = Depends(get_db),
) -> dict:
    return funnel_controller.trial(db, payload)


@router.post("")
def create_funnel(
    payload: FunnelIn,
    principal: dict = Depends(require_permission("funnel:write")),
    db: Session = Depends(get_db),
) -> dict:
    return funnel_controller.create_funnel(db, payload, principal)


@router.get("/{funnel_id}")
def get_funnel(
    funnel_id: int,
    principal: dict = Depends(require_permission("funnel:read")),
    db: Session = Depends(get_db),
) -> dict:
    return funnel_controller.get_funnel(db, funnel_id)


@router.patch("/{funnel_id}")
def update_funnel(
    funnel_id: int,
    payload: FunnelPatch,
    principal: dict = Depends(require_permission("funnel:write")),
    db: Session = Depends(get_db),
) -> dict:
    return funnel_controller.update_funnel(db, funnel_id, payload, principal)


@router.post("/{funnel_id}/publish")
def publish_funnel(
    funnel_id: int,
    principal: dict = Depends(require_permission("funnel:publish")),
    db: Session = Depends(get_db),
) -> dict:
    return funnel_controller.publish_funnel(db, funnel_id, principal)


@router.post("/{funnel_id}/cache-refresh")
def refresh_cache(
    funnel_id: int,
    principal: dict = Depends(require_permission("cache:refresh")),
    db: Session = Depends(get_db),
) -> dict:
    return funnel_controller.refresh_cache(db, funnel_id, principal)


@router.get("/{funnel_id}/cache-status")
def cache_status(
    funnel_id: int,
    principal: dict = Depends(require_permission("funnel:read")),
    db: Session = Depends(get_db),
) -> dict:
    return funnel_controller.cache_status(db, funnel_id)
