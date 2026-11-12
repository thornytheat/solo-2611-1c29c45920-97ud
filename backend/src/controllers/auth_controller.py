"""登录控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, auth_service


def login(db: Session, email: str, password: str, request: Request) -> dict:
    token, expires_in, user = auth_service.authenticate(db, email, password)
    audit_service.record(
        db,
        actor_email=user.email,
        actor_role=user.role,
        action="auth.login",
        entity="user",
        entity_id=user.id,
        detail={"role": user.role, "display_name": user.display_name},
        layer="domain",
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user.as_public(),
    }


def me(db: Session, email: str) -> dict:
    user = auth_service.get_user(db, email)
    return {"user": user.as_public()}
