/** 角色 -> 权限点（与 backend/src/constants/roles.py 同步）。 */
import type { Role } from '../types/models';

export const ROLE_LABELS: Record<Role, string> = {
  admin: '增长负责人',
  analyst: '产品分析师',
  viewer: '运营（只读）',
};

export const ROLE_TEAM: Record<Role, string> = {
  admin: '口径、窗口与发布',
  analyst: '跑漏斗、看路径、写归因',
  viewer: '只看结果，不带操作',
};

export const PERMISSIONS: Record<Role, string[]> = {
  admin: [
    'funnel:read',
    'funnel:write',
    'funnel:publish',
    'run:execute',
    'run:read',
    'event:read',
    'report:read',
    'report:write',
    'report:review',
    'export:read',
    'cache:refresh',
    'audit:read',
  ],
  analyst: [
    'funnel:read',
    'run:execute',
    'run:read',
    'event:read',
    'report:read',
    'report:write',
    'export:read',
    'cache:refresh',
  ],
  viewer: ['funnel:read', 'run:read', 'event:read', 'report:read'],
};

export function can(role: Role | undefined, permission: string): boolean {
  if (!role) return false;
  return PERMISSIONS[role]?.includes(permission) ?? false;
}
