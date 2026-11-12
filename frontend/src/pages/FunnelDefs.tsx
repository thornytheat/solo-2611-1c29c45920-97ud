import { useEffect, useMemo, useState } from 'react';
import { funnelApi, type TrialResult } from '../api/funnels';
import { eventApi } from '../api/events';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { uiStore } from '../stores/uiStore';
import { can } from '../constants/roles';
import { CHANNEL_LABELS, CHANNELS, DEVICES, lineVar } from '../constants/enums';
import { days, num, pct, shortDate } from '../utils/format';
import { errorMessage } from '../utils/errorMessage';
import EmptyState from '../components/common/EmptyState';
import { FunnelPill } from '../components/common/StatusPill';
import type { FunnelStep, EventRow } from '../types/models';

export default function FunnelDefs() {
  const { user } = useAuth();
  const role = user?.role;
  const canEdit = can(role, 'funnel:write');
  const canPublish = can(role, 'funnel:publish');
  const canRun = can(role, 'run:execute');

  const funnels = useAsync(() => funnelApi.list(), []);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [steps, setSteps] = useState<FunnelStep[]>([]);
  const [windowDays, setWindowDays] = useState(7);
  const [crossSession, setCrossSession] = useState(true);
  const [noise, setNoise] = useState<string[]>([]);
  const [trial, setTrial] = useState<TrialResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  const list = funnels.data?.items ?? [];
  const selected = useMemo(() => list.find((item) => item.id === selectedId) ?? list[0], [list, selectedId]);

  useEffect(() => {
    if (!selected) return;
    if (!selectedId) setSelectedId(selected.id);
    uiStore.selectFunnel(selected.id);
    setSteps(selected.steps.map((step) => ({ ...step })));
    setWindowDays(selected.window_days);
    setCrossSession(selected.cross_session);
    setNoise(selected.noise_events ?? []);
    setTrial(null);
    setError(null);
  }, [selected?.id]);

  const events = useAsync(
    () =>
      selected
        ? eventApi.list({ funnel_id: selected.id, limit: 8 })
        : Promise.resolve({ items: [] as EventRow[], total: 0, stats: [] }),
    [selected?.id],
  );

  async function runTrial() {
    setBusy('trial');
    setError(null);
    try {
      const result = await funnelApi.trial({ steps, window_days: windowDays, noise_events: noise });
      setTrial(result);
      uiStore.toast(`试算完成：${num(result.entry_users)} 人进入，${num(result.converted_users)} 人到终点`, 'ok');
    } catch (err) {
      setError(errorMessage(err, role));
    } finally {
      setBusy(null);
    }
  }

  async function save(extra: Record<string, unknown> = {}) {
    if (!selected) return;
    setBusy('save');
    setError(null);
    try {
      await funnelApi.update(selected.id, {
        steps,
        window_days: windowDays,
        cross_session: crossSession,
        ...extra,
      });
      uiStore.toast('漏斗定义已保存（版本 +1）', 'ok');
      funnels.reload();
    } catch (err) {
      setError(errorMessage(err, role));
    } finally {
      setBusy(null);
    }
  }

  async function publish() {
    if (!selected) return;
    setBusy('publish');
    setError(null);
    try {
      await funnelApi.publish(selected.id);
      uiStore.toast('已发布：其他页面会读取新版本', 'ok');
      funnels.reload();
    } catch (err) {
      setError(errorMessage(err, role));
    } finally {
      setBusy(null);
    }
  }

  function move(from: number, to: number) {
    if (to < 0 || to >= steps.length) return;
    const next = [...steps];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    setSteps(next);
    setTrial(null);
  }

  if (funnels.error) {
    return (
      <div className="error-box">
        <span>{errorMessage(funnels.error, role)}</span>
        <button className="btn btn-sm" onClick={funnels.reload}>
          重试
        </button>
      </div>
    );
  }

  return (
    <div className="grid-2">
      <section>
        <div className="panel">
          <div className="panel-head">
            <h2>线路表 · 3 条漏斗</h2>
            <span className="eyebrow">{list.length} LINES</span>
          </div>

          {funnels.loading && !list.length ? <div className="loading">读取线路表 …</div> : null}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {list.map((funnel) => {
              const active = selected?.id === funnel.id;
              return (
                <button
                  key={funnel.id}
                  onClick={() => setSelectedId(funnel.id)}
                  className="demo-account"
                  style={{
                    borderColor: active ? lineVar(funnel.line_color) : undefined,
                    background: active ? 'oklch(0.26 0.024 256 / 0.6)' : undefined,
                  }}
                  data-testid={`funnel-${funnel.code}`}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <i
                      style={{
                        width: 12,
                        height: 12,
                        borderRadius: '50%',
                        border: `3px solid ${lineVar(funnel.line_color)}`,
                        display: 'inline-block',
                      }}
                    />
                    <span>
                      <b style={{ fontWeight: 500 }}>{funnel.name}</b>
                      <span className="mono tiny muted" style={{ display: 'block' }}>
                        {funnel.line_no} · {funnel.code} · v{funnel.version}
                      </span>
                    </span>
                  </span>
                  <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span className="mono tiny muted">窗口 {funnel.window_days}d</span>
                    <FunnelPill status={funnel.status} />
                  </span>
                </button>
              );
            })}
          </div>

          <div className="tiny muted" style={{ marginTop: 14 }}>
            最近更新 {shortDate(selected?.updated_at)} · 负责人 {selected?.owner_email}
          </div>
        </div>

        <div className="panel line-c" style={{ marginTop: 20 }}>
          <div className="panel-head">
            <h3>埋点流 · 采集口径</h3>
            <span className="eyebrow">{selected ? selected.noise_events.length + steps.length : 0} EVENTS</span>
          </div>
          <p className="tiny muted" style={{ marginTop: 0 }}>
            事件按 <span className="mono">(event_ts, seq)</span> 入站：seq 是入库先后，乱序上报靠事件时间纠正；
            同事件同秒视为重复上报，只计一次。
          </p>
          {events.data?.items?.length ? (
            <table className="table">
              <thead>
                <tr>
                  <th>用户</th>
                  <th>站名</th>
                  <th>时间</th>
                  <th>渠道</th>
                  <th className="num-cell">seq</th>
                </tr>
              </thead>
              <tbody>
                {events.data.items.slice(0, 6).map((row) => (
                  <tr key={row.id}>
                    <td className="mono tiny">{row.user_key}</td>
                    <td>{row.event_label}</td>
                    <td className="mono tiny muted">{row.event_ts.slice(5, 16).replace('T', ' ')}</td>
                    <td className="tiny">{row.channel_label}</td>
                    <td className="num-cell tiny muted">{row.seq}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="loading">读取事件流 …</div>
          )}
          <div className="tiny muted" style={{ marginTop: 10 }}>
            共 {num(events.data?.total ?? 0)} 条事件进入本漏斗白名单
            {CHANNELS.map((channel) => (
              <span key={channel} className="mono" style={{ marginLeft: 10 }}>
                {CHANNEL_LABELS[channel]}
              </span>
            ))}
            {DEVICES.map((device) => (
              <span key={device} className="mono" style={{ marginLeft: 8 }}>
                {device}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section>
        {!selected ? (
          <EmptyState
            title="还没有漏斗"
            hint="用增长负责人的账号新建一条线路，或先确认 seed 是否跑过。"
            action={
              <button className="btn btn-sm" onClick={funnels.reload}>
                重新读取
              </button>
            }
          />
        ) : (
          <>
            <div className="panel" style={{ ['--line-color' as string]: lineVar(selected.line_color) }}>
              <div className="panel-head">
                <h2>{selected.name}</h2>
                <span className="line-badge" style={{ color: lineVar(selected.line_color) }}>
                  <i />
                  {selected.line_no}
                </span>
              </div>
              <p className="muted tiny" style={{ marginTop: 0 }}>
                {selected.description}
              </p>

              <div className="eyebrow" style={{ margin: '14px 0 8px' }}>
                站点顺序（拖动排序 / 上下按钮）
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {steps.map((step, index) => (
                  <div
                    key={step.key}
                    draggable={canEdit}
                    onDragStart={() => setDragIndex(index)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => {
                      if (dragIndex !== null && dragIndex !== index) move(dragIndex, index);
                      setDragIndex(null);
                    }}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '26px minmax(0,1fr) minmax(0,1fr) auto',
                      alignItems: 'center',
                      gap: 10,
                      padding: '8px 10px',
                      border: '1px solid var(--hair-soft)',
                      borderLeft: `3px solid ${lineVar(selected.line_color)}`,
                      opacity: dragIndex === index ? 0.5 : 1,
                      cursor: canEdit ? 'grab' : 'default',
                    }}
                    data-testid={`step-${index}`}
                  >
                    <span className="mono tiny muted">{index + 1}</span>
                    <span>
                      <b style={{ fontWeight: 500 }}>{step.label}</b>
                      <span className="mono tiny muted" style={{ display: 'block' }}>
                        {step.event}
                      </span>
                    </span>
                    <span className="tiny muted">
                      {index === 0 ? '入口站' : index === steps.length - 1 ? '终点站' : '换乘站'}
                    </span>
                    {canEdit ? (
                      <span style={{ display: 'flex', gap: 4 }}>
                        <button className="btn btn-sm btn-ghost" onClick={() => move(index, index - 1)} disabled={index === 0}>
                          ↑
                        </button>
                        <button
                          className="btn btn-sm btn-ghost"
                          onClick={() => move(index, index + 1)}
                          disabled={index === steps.length - 1}
                        >
                          ↓
                        </button>
                      </span>
                    ) : (
                      <span className="tiny muted">只读</span>
                    )}
                  </div>
                ))}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginTop: 16 }}>
                <div className="field" style={{ marginBottom: 0 }}>
                  <label htmlFor="window">窗口（天，从首步起算）</label>
                  <input
                    id="window"
                    className="input mono"
                    type="number"
                    min={1}
                    max={30}
                    value={windowDays}
                    disabled={!canEdit}
                    onChange={(event) => {
                      setWindowDays(Number(event.target.value) || 1);
                      setTrial(null);
                    }}
                    data-testid="window-input"
                  />
                </div>
                <div className="field" style={{ marginBottom: 0, justifyContent: 'flex-end' }}>
                  <label>跨会话拼接</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={crossSession}
                      disabled={!canEdit}
                      onChange={(event) => {
                        setCrossSession(event.target.checked);
                        setTrial(null);
                      }}
                    />
                    <span className="tiny muted">{crossSession ? '允许跨会话/跨天命中' : '仅单会话内命中'}</span>
                  </label>
                </div>
              </div>

              <div className="btn-row" style={{ marginTop: 18 }}>
                <button className="btn" onClick={runTrial} disabled={!canRun || busy !== null} data-testid="trial-btn">
                  {busy === 'trial' ? '试算中 …' : '试算人数'}
                </button>
                <button className="btn" onClick={() => save()} disabled={!canEdit || busy !== null} data-testid="save-btn">
                  {busy === 'save' ? '保存中 …' : '保存定义'}
                </button>
                <button
                  className="btn btn-primary"
                  onClick={publish}
                  disabled={!canPublish || busy !== null}
                  data-testid="publish-btn"
                >
                  {busy === 'publish' ? '发布中 …' : '发布版本'}
                </button>
              </div>
              {!canEdit ? (
                <div className="tiny muted" style={{ marginTop: 8 }}>
                  当前角色只能查看；改线路与发布需要「增长负责人」。
                </div>
              ) : null}
              {error ? (
                <div className="error-box" style={{ marginTop: 12 }}>
                  <span>{error}</span>
                  <button className="btn btn-sm" onClick={() => setError(null)}>
                    知道了
                  </button>
                </div>
              ) : null}
            </div>

            <div className="panel line-b" style={{ marginTop: 20 }}>
              <div className="panel-head">
                <h3>试算结果 · 未落库</h3>
                <span className="eyebrow">{trial ? `窗口 ${trial.window_days}d` : 'PENDING'}</span>
              </div>
              {!trial ? (
                <EmptyState
                  eyebrow="TRIAL · 试算"
                  title="还没试算"
                  hint="先按当前步骤顺序与窗口跑一次状态机，看看每站人数是否合理，再决定是否保存 / 发布。"
                  action={
                    <button className="btn btn-sm" onClick={runTrial} disabled={!canRun}>
                      跑一次试算
                    </button>
                  }
                />
              ) : (
                <>
                  <div className="metric-row">
                    <div className="metric">
                      <span className="label">进入</span>
                      <b>{num(trial.entry_users)}</b>
                    </div>
                    <div className="metric">
                      <span className="label">到达终点</span>
                      <b>{num(trial.converted_users)}</b>
                    </div>
                    <div className="metric">
                      <span className="label">整体转化</span>
                      <b>{pct((trial.converted_users / Math.max(trial.entry_users, 1)) * 100)}</b>
                    </div>
                    <div className="metric">
                      <span className="label">步间 P50</span>
                      <b>{days(trial.duration.p50_days)}</b>
                    </div>
                  </div>
                  <table className="table" style={{ marginTop: 10 }}>
                    <thead>
                      <tr>
                        <th>站</th>
                        <th className="num-cell">人数</th>
                        <th className="num-cell">较上一步</th>
                        <th className="num-cell">步间 P50</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trial.steps.map((step) => (
                        <tr key={step.index}>
                          <td>
                            {step.index + 1}. {step.label}
                          </td>
                          <td className="num-cell">{num(step.users)}</td>
                          <td className="num-cell">{pct(step.rate_from_prev)}</td>
                          <td className="num-cell">{days(step.p50_days)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="tiny muted" style={{ marginTop: 8 }}>
                    折叠重复上报 {num(trial.discard.duplicates_collapsed ?? 0)} 条 · 超窗丢弃{' '}
                    {num(trial.discard.expired ?? 0)} 人 · 乱序修复 {num(trial.discard.out_of_order_events ?? 0)} 处
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
