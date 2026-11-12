import { useSyncExternalStore } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { authStore } from '../../stores/authStore';
import { uiStore } from '../../stores/uiStore';
import { NAV_ITEMS, BRAND } from '../../constants/ui';
import { ROLE_LABELS, ROLE_TEAM, can } from '../../constants/roles';
import Toasts from '../common/Toasts';

const LINE_STRIP = ['line-a', 'line-b', 'line-c', 'line-d'];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const state = useSyncExternalStore(authStore.subscribe, authStore.getState);
  const location = useLocation();
  const navigate = useNavigate();
  const role = state.user?.role;
  const navItems = NAV_ITEMS.filter((item) => can(role, item.permission));
  const current = NAV_ITEMS.find((item) => location.pathname.startsWith(item.to));

  function logout() {
    authStore.logout();
    uiStore.toast('已退出，回到站厅', 'info');
    navigate('/login', { replace: true });
  }

  return (
    <div className="shell">
      <aside className="rail">
        <div>
          <div className="rail-mark">
            funnelpath
            <small>METRO</small>
          </div>
          <div className="rail-sub">
            {BRAND.client}
            <br />
            漏斗 · 路径 · 归因
          </div>
        </div>

        <div className="rail-lines" aria-hidden>
          {LINE_STRIP.map((color) => (
            <span key={color} className="rail-line-pill" style={{ background: `var(--${color})` }} />
          ))}
        </div>

        <nav className="rail-nav">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'active' : '')}>
              <span className="nav-label">
                <span className="mono tiny" style={{ color: 'var(--paper-mute)', marginRight: 8 }}>
                  {item.code}
                </span>
                {item.label}
              </span>
              <span className="nav-hint">{item.hint}</span>
            </NavLink>
          ))}
        </nav>

        <div className="rail-foot">
          {role ? ROLE_LABELS[role] : '未登录'}
          <br />
          {role ? ROLE_TEAM[role] : '—'}
          <br />
          <span className="mono">{state.user?.email ?? ''}</span>
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <div>
            <div className="eyebrow">
              {current ? `${current.line} · ${current.code} STATION` : 'FUNNELPATH'} · 行知教育增长组
            </div>
            <h1>{current ? current.label : BRAND.name}</h1>
          </div>
          <div className="topbar-meta">
            <div>
              <div className="tiny muted">{BRAND.scale}</div>
              <div className="who">
                <b>{state.user?.display_name}</b>
                <span className="mono tiny" style={{ color: 'var(--paper-mute)', marginLeft: 8 }}>
                  {role ? ROLE_LABELS[role] : ''}
                </span>
              </div>
            </div>
            <button className="btn btn-sm" onClick={logout} data-testid="logout">
              退出
            </button>
          </div>
        </div>
        {children}
      </div>
      <Toasts />
    </div>
  );
}
