"""角色 -> 权限点映射（与 frontend/src/constants/roles.ts 同步）。"""
from __future__ import annotations

from src.constants.enums import Role

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "funnel:read", "funnel:write", "funnel:publish",
        "run:execute", "run:read",
        "event:read",
        "report:read", "report:write", "report:review",
        "export:read",
        "cache:refresh",
        "audit:read",
    },
    Role.ANALYST.value: {
        "funnel:read", "run:execute", "run:read", "event:read",
        "report:read", "report:write", "export:read", "cache:refresh",
    },
    Role.VIEWER.value: {
        "funnel:read", "run:read", "event:read", "report:read",
    },
}

# route/controller 层直接用的角色组
ADMIN_ONLY = (Role.ADMIN.value,)
EDITOR_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
ALL_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.VIEWER.value)

FUNNEL_WRITE_ROLES = ADMIN_ONLY
FUNNEL_PUBLISH_ROLES = ADMIN_ONLY
RUN_ROLES = EDITOR_ROLES
REPORT_WRITE_ROLES = EDITOR_ROLES
REPORT_REVIEW_ROLES = ADMIN_ONLY
EXPORT_ROLES = EDITOR_ROLES
CACHE_ROLES = EDITOR_ROLES
AUDIT_ROLES = ADMIN_ONLY


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
