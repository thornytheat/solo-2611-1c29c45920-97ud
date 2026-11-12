import { useSyncExternalStore } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { authStore } from '../stores/authStore';
import { ROLE_LABELS, can } from '../constants/roles';
import type { Role } from '../types/models';

export function useAuth() {
  return useSyncExternalStore(authStore.subscribe, authStore.getState);
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const state = useAuth();
  const location = useLocation();
  if (!state.bootstrapped) {
    return <div className="loading">正在恢复登录态 …</div>;
  }
  if (!state.token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function RequirePermission({
  permission,
  children,
}: {
  permission: string;
  children: React.ReactNode;
}) {
  const state = useAuth();
  if (!state.user || !can(state.user.role, permission)) {
    return (
      <div className="forbidden" data-testid="forbidden">
        <div className="eyebrow">403 · 站点封闭</div>
        <h1>这条线路不在你的通行范围</h1>
        <p className="muted" style={{ fontSize: '0.86rem', maxWidth: '48ch' }}>
          当前角色「{state.user ? ROLE_LABELS[state.user.role as Role] : '访客'}」没有 {permission} 权限。
          运营只能看结果；跑漏斗、写归因与导出由分析师/增长负责人完成。
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
