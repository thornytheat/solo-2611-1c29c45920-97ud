import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import { authStore } from '../stores/authStore';
import { BRAND, DEMO_ACCOUNTS, DEMO_PASSWORD } from '../constants/ui';
import { errorMessage } from '../utils/errorMessage';
import { useAuth } from '../router/guards';

const DIAGRAM = [
  { color: 'line-a', nodes: [1, 1, 1, 0, 1, 1], cap: 'L1 注册 → 试听完成 → 付费' },
  { color: 'line-b', nodes: [1, 1, 1, 0], cap: 'L2 浏览商品 → 加购 → 下单' },
  { color: 'line-c', nodes: [1, 1], cap: 'L3 领券 → 核销' },
  { color: 'line-d', nodes: [1, 0, 1, 0, 1], cap: 'L4 跨会话拼接（乱序/重复上报）' },
];

export default function Login() {
  const [email, setEmail] = useState('admin@funnelpath.io');
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const state = useAuth();

  useEffect(() => {
    if (state.token) navigate('/funnels', { replace: true });
  }, [state.token, navigate]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await authApi.login(email.trim(), password);
      authStore.setSession(result.access_token, result.user);
      navigate('/funnels', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="hall">
      <section className="hall-brand">
        <div>
          <div className="eyebrow">行知教育 · 增长产品组 · 内部工具</div>
          <h1>
            漏斗不是一张表，
            <br />
            是一张线路图。
          </h1>
          <p className="muted" style={{ maxWidth: '42ch', fontSize: '0.9rem' }}>
            跨会话、乱序上报、同日重复埋点，都会让「注册 → 试听 → 付费」的口径每次都不一样。
            这里把每个用户在每一站的上车与换乘都摊开：谁在哪一站下车、下车前最后停在哪、哪个渠道的站台更挤。
          </p>
        </div>

        <div className="hall-diagram" aria-hidden>
          {DIAGRAM.map((line) => (
            <div className="hall-line" key={line.color} style={{ ['--line-color' as string]: `var(--${line.color})` }}>
              {line.nodes.map((filled, index) => (
                <span key={index} style={{ display: 'flex', alignItems: 'center', flex: index === line.nodes.length - 1 ? 'none' : 1 }}>
                  <span className={`node ${filled ? 'filled' : ''}`} />
                  {index < line.nodes.length - 1 ? <span className="link" /> : null}
                </span>
              ))}
              <span className="cap">{line.cap}</span>
            </div>
          ))}
        </div>

        <div className="tiny muted mono">
          {BRAND.client} · {BRAND.scale}
        </div>
      </section>

      <section className="hall-form">
        <div>
          <div className="eyebrow">STAFF ENTRANCE · 员工通道</div>
          <h2>刷工牌进站</h2>
          <p className="muted" style={{ fontSize: '0.84rem', marginTop: 6 }}>
            三个角色的站台权限不同：负责人改线路，分析师跑车次，运营只看站牌。
          </p>
        </div>

        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div className="field">
            <label htmlFor="email">邮箱</label>
            <input
              id="email"
              className="input"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              data-testid="login-email"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">密码</label>
            <input
              id="password"
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              data-testid="login-password"
              required
            />
          </div>
          {error ? (
            <div className="error-box" data-testid="login-error">
              <span>{error}</span>
            </div>
          ) : null}
          <button className="btn btn-primary" type="submit" disabled={busy} data-testid="login-submit">
            {busy ? '验证工牌 …' : '进站'}
          </button>
        </form>

        <div className="demo-accounts">
          <div className="eyebrow">DEMO · 一键填充（密码 {DEMO_PASSWORD}）</div>
          {DEMO_ACCOUNTS.map((account) => (
            <button
              key={account.email}
              type="button"
              className="demo-account"
              onClick={() => {
                setEmail(account.email);
                setPassword(DEMO_PASSWORD);
              }}
              data-testid={`quick-${account.role}`}
            >
              <span>{account.email}</span>
              <span className="mono tiny muted">{account.label}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
