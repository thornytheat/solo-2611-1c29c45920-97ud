"""角色鉴权依赖：401 未登录 / 403 权限不足（真实 HTTP 状态码，不是前端藏按钮）。"""
from __future__ import annotations

from typing import Callable

from fastapi import Request

from src.constants import error_codes
from src.constants.roles import PERMISSIONS, has_permission
from src.utils.errors import AppError


def principal_of(request: Request) -> dict:
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise AppError(error_codes.AUTH_MISSING, 401)
    return {"email": principal["email"], "role": principal["role"]}


def require_permission(permission: str) -> Callable[[Request], dict]:
    def dependency(request: Request) -> dict:
        principal = principal_of(request)
        if not has_permission(principal["role"], permission):
            raise AppError(
                error_codes.FORBIDDEN,
                403,
                detail={
                    "permission": permission,
                    "role": principal["role"],
                    "granted": sorted(PERMISSIONS.get(principal["role"], set())),
                },
            )
        return principal

    return dependency


def require_roles(*roles: str) -> Callable[[Request], dict]:
    allowed = set(roles)

    def dependency(request: Request) -> dict:
        principal = principal_of(request)
        if principal["role"] not in allowed:
            raise AppError(
                error_codes.FORBIDDEN,
                403,
                detail={"role": principal["role"], "required": sorted(allowed)},
            )
        return principal

    return dependency
