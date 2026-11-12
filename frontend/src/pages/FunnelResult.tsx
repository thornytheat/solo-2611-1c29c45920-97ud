import { useEffect, useMemo, useState } from 'react';
import { funnelApi } from '../api/funnels';
import { runApi } from '../api/runs';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { uiStore } from '../stores/uiStore';
import { can } from '../constants/roles';
import { lineVar, RUN_TRIGGER_LABELS } from '../constants/enums';
import { days, num, pct, seconds, shortDate } from '../utils/format';
import { errorMessage } from '../utils/errorMessage';
import EmptyState from '../components/common/EmptyState';
import { RunVersionBadge } from '../components/common/RunVersionBadge';
import SegmentTable from '../components/common/SegmentTable';
import StationStrip from '../components/common/StationStrip';
import type { FunnelRun } from '../types/models';

export default function FunnelResult() {
  const { user } = useAuth();
  const role = user?.role;
  const canRun = can(role, 'run:execute');

  const funnels = useAsync(() => funnelApi.list(), []);
  const [funnelId, setFunnelId] = useState<number | null>(null);
  const [windowDays, setWindowDays] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const list = funnels.data?.items ?? [];
  const selected = useMemo(() => list.find((item) => item.id === funnelId) ?? list[0], [list, funnelId]);

  useEffect(() => {
    if (selected) {
      setFunnelId(selected.id);
      uiStore.selectFunnel(selected.id);
      if (windowDays === null) setWindowDays(selected.window_days);
    }
  }, [selected?.id]);

  const runs = useAsync(
    () => (selected ? runApi.list(selected.id) : Promise.resolve({ items: [], total: 0 })),
    [selected?.id],
  );

  const runItems = runs.data?.items ?? [];
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  // 默认展示当前结论 run；用户可切换查看任意历史 run（旧 run 只读可查）
  const run: FunnelRun | null =
    runItems.find((item) => item.id === selectedRunId) ??
    runItems.find((item) => item.is_current) ??
    runItems[0] ??
    null;

  useEffect(() => {
    setSelectedRunId(null);
  }, [selected?.id]);

  async function execute() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const result = await runApi.execute(selected.id, windowDays ?? selected.window_days);
      setSelectedRunId(result.run.id);
      uiStore.selectRun(result.run.id);
      uiStore.toast(`运行完成：${num(result.run.entry_users)} 人进入，转化 ${pct(result.run.conversion_rate)}`, 'ok');
      runs.reload();
    } catch (err) {
      setError(errorMessage(err, role));
    } finally {
      setBusy(false);
    }
  }

  if (funnels.error || runs.error) {
    const err = funnels.error ?? runs.error;
    return (
      <div className="error-box">
        <span>{errorMessage(err, role)}</span>
        <button className="btn btn-sm" onClick={() => (funnels.error ? funnels.reload() : runs.reload())}>
          重试
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="panel" style={{ borderLeftColor: selected ? lineVar(selected.line_color) : undefined }}>
        <div className="panel-head" style={{ marginBottom: 10 }}>
          <div>
            <h2>{selected ? selected.name : '漏斗结果'}</h2>
            <div className="tiny muted">
              {selected ? `${selected.code} · ${selected.line_no} · 定义 v${selected.version}` : ''} · 每次运行都真跑状态机
            </div>
          </div>
          <div className="btn-row">
            {list.map((funnel) => (
              <button
                key={funnel.id}
                className={`btn btn-sm ${selected?.id === funnel.id ? 'btn-primary' : ''}`}
                onClick={() => {
                  setFunnelId(funnel.id);
                  setWindowDays(funnel.window_days);
                }}
                data-testid={`result-funnel-${funnel.code}`}
              >
                {funnel.line_no}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div className="field" style={{ marginBottom: 0, width: 150 }}>
            <label htmlFor="run-window">本次窗口（天）</label>
            <input
              id="run-window"
              className="input mono"
              type="number"
              min={1}
              max={30}
              value={windowDays ?? 7}
              onChange={(event) => setWindowDays(Number(event.target.value) || 1)}
              data-testid="run-window"
            />
          </div>
          <button className="btn btn-primary" onClick={execute} disabled={!canRun || busy || !selected} data-testid="run-btn">
            {busy ? '计算中 …' : '运行漏斗'}
          </button>
          <div className="tiny muted">
            最近一次运行 {run ? `${run.code} · ${shortDate(run.finished_at)}` : '—'}
          </div>
        </div>

        {error ? (
          <div className="error-box" style={{ marginTop: 12 }}>
            <span>{error}</span>
            <button className="btn btn-sm" onClick={() => setError(null)}>
              知道了
            </button>
          </div>
        ) : null}
        {!canRun ? <div className="tiny muted" style={{ marginTop: 8 }}>运营角色只读：可以看结果，不能触发计算。</div> : null}
      </div>

      {!run ? (
        <div style={{ marginTop: 20 }}>
          <EmptyState
            eyebrow="NO RUN · 还没有运行"
            title="这条线路还没有车次"
            hint="点上面的「运行漏斗」跑一次：会按用户级状态机重算每站人数、步间耗时与分群流失率。"
            action={
              <button className="btn btn-sm" onClick={execute} disabled={!canRun}>
                运行漏斗
              </button>
            }
          />
        </div>
      ) : (
        <>
          <div className="panel" style={{ marginTop: 12 }} data-testid="run-history">
            <div className="panel-head" style={{ marginBottom: 8 }}>
              <h3>运行版本（旧运行可查，不再充当当前结论）</h3>
              <span className="eyebrow">{runItems.length} RUNS</span>
            </div>
            <div className="btn-row" style={{ flexWrap: 'wrap' }}>
              {runItems.map((item) => (
                <button
                  key={item.id}
                  className={`btn btn-sm ${run?.id === item.id ? 'btn-primary' : ''}`}
                  onClick={() => setSelectedRunId(item.id)}
                  data-testid={`run-pick-${item.id}`}
                >
                  {item.is_correction ? '校正 ' : ''}
                  {item.code}
                  {item.is_current ? ' · 当前' : ''} · v{item.data_version_no ?? '—'}
                </button>
              ))}
            </div>
            {run ? (
              <div style={{ marginTop: 10 }}>
                <RunVersionBadge run={run} />
              </div>
            ) : null}
            {run && !run.is_current ? (
              <div className="tiny muted" style={{ marginTop: 8 }} data-testid="run-not-current-note">
                正在查看历史运行 {run.code}（触发：{RUN_TRIGGER_LABELS[run.trigger] ?? run.trigger}），
                其结论已被后续校正替代，仅作归档可查；页面数字不会覆盖当前结论。
              </div>
            ) : null}
          </div>

          {run?.is_correction && run.correction_meta?.step_deltas ? (
            <div className="panel line-d" style={{ marginTop: 12 }} data-testid="run-correction-diff">
              <div className="panel-head">
                <h3>校正前后差异 · {run.correction_meta.batch_code}</h3>
                <span className="eyebrow">
                  基线 {run.correction_meta.baseline_run_code} · 受影响{' '}
                  {num(run.correction_meta.affected_user_count ?? 0)} 人
                </span>
              </div>
              <table className="table">
                <thead>
                  <tr>
                    <th>步骤</th>
                    <th className="num-cell">校正前</th>
                    <th className="num-cell">校正后</th>
                    <th className="num-cell">差异</th>
                    <th>区间</th>
                  </tr>
                </thead>
                <tbody>
                  {run.correction_meta.step_deltas.map((d) => (
                    <tr key={d.index}>
                      <td>{d.label}</td>
                      <td className="num-cell">{num(d.baseline_users)}</td>
                      <td className="num-cell">{num(d.corrected_users)}</td>
                      <td className={`num-cell ${d.delta > 0 ? 'better' : d.delta < 0 ? 'worse' : 'flat'}`}>
                        {d.delta > 0 ? '+' : ''}
                        {d.delta}
                      </td>
                      <td>{d.unchanged ? <span className="pill">未变化</span> : <span className="pill warn">受影响</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <div className="panel line-b" style={{ marginTop: 20 }} data-testid="run-strip">
            <div className="panel-head">
              <h3>步骤条 · 站点与换乘</h3>
              <span className="eyebrow">
                窗口 {run.window_days}d · 引擎 v{run.engine_version} · 触发 {run.trigger}
              </span>
            </div>
            <StationStrip
              steps={run.steps}
              lostSteps={run.lost_steps}
              lineColor={selected?.line_color ?? 'line-a'}
            />
            <div className="metric-row" style={{ marginTop: 18 }}>
              <div className="metric">
                <span className="label">进入</span>
                <b>{num(run.entry_users)}</b>
                <small>去重后命中首站</small>
              </div>
              <div className="metric">
                <span className="label">转化到终点</span>
                <b>{pct(run.conversion_rate)}</b>
                <small>{num(run.converted_users)} 人</small>
              </div>
              <div className="metric">
                <span className="label">步间 P50</span>
                <b>{days(run.duration.p50_days)}</b>
                <small>P90 {days(run.duration.p90_days)}</small>
              </div>
              <div className="metric">
                <span className="label">超窗丢弃</span>
                <b>{num(run.discard.expired ?? 0)}</b>
                <small>折叠重复 {num(run.discard.duplicates_collapsed ?? 0)}</small>
              </div>
              <div className="metric">
                <span className="label">乱序修复</span>
                <b>{num(run.discard.out_of_order_events ?? 0)}</b>
                <small>{num(run.discard.out_of_order_users ?? 0)} 个用户</small>
              </div>
            </div>
          </div>

          <div className="grid-2" style={{ marginTop: 20 }}>
            <div className="panel line-c">
              <div className="panel-head">
                <h3>步间耗时</h3>
                <span className="eyebrow">{num(run.duration.samples)} SAMPLES</span>
              </div>
              <table className="table">
                <thead>
                  <tr>
                    <th>区间</th>
                    <th className="num-cell">样本</th>
                    <th className="num-cell">P50</th>
                    <th className="num-cell">P90</th>
                <th className="num-cell">均值</th>
                  </tr>
                </thead>
                <tbody>
                  {run.transitions.map((row) => (
                    <tr key={`${row.from_index}-${row.to_index}`}>
                      <td>
                        {row.from_label} → {row.to_label}
                      </td>
                      <td className="num-cell">{num(row.samples)}</td>
                      <td className="num-cell">{days(row.p50_days)}</td>
                      <td className="num-cell">{days(row.p90_days)}</td>
                      <td className="num-cell">{seconds(row.mean_seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="tiny muted" style={{ marginTop: 10 }}>
                整体 {num(run.duration.samples)} 个跨步样本合并后的 P50 = <b className="mono">{days(run.duration.p50_days)}</b>
                ；窗口从首站时刻起算，超窗即中止（计 expired）。
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h3>流失队列</h3>
                <span className="eyebrow">DROP COHORTS</span>
              </div>
              <table className="table">
                <thead>
                  <tr>
                    <th>未到达站</th>
                    <th className="num-cell">流失</th>
                    <th className="num-cell">占进入</th>
                  </tr>
                </thead>
                <tbody>
                  {run.lost_steps.map((row) => (
                    <tr key={row.index}>
                      <td>
                        {row.label}
                        <span className="mono tiny muted" style={{ display: 'block' }}>
                          从 {row.from_label} 出发
                        </span>
                      </td>
                      <td className="num-cell">{num(row.lost)}</td>
                      <td className="num-cell">{pct(row.lost_share)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="tiny muted" style={{ marginTop: 10 }}>
                最大单点流失在「{run.steps[run.max_loss_step]?.label ?? '—'}」。
              </div>
            </div>
          </div>

          <div className="panel" style={{ marginTop: 20 }}>
            <div className="panel-head">
              <h3>分群对比 · 渠道 × 设备</h3>
              <span className="eyebrow">
                STEP {run.max_loss_step + 1} · {run.steps[run.max_loss_step]?.label ?? ''}
              </span>
            </div>
            {run.segments.length ? (
              <SegmentTable
                block={{
                  step_index: run.max_loss_step,
                  step_label: run.steps[run.max_loss_step]?.label ?? '',
                  from_label: run.steps[run.max_loss_step - 1]?.label ?? '',
                  overall_drop_rate:
                    run.steps[run.max_loss_step - 1]?.users
                      ? (run.steps[run.max_loss_step - 1].users - run.steps[run.max_loss_step].users) * 100 /
                        run.steps[run.max_loss_step - 1].users
                      : 0,
                  overall_users: run.steps[run.max_loss_step - 1]?.users ?? 0,
                  overall_dropped: run.steps[run.max_loss_step]?.lost ?? 0,
                  rows: run.segments.filter((row) => row.level === 'device'),
                  channel_rows: run.segments.filter((row) => row.level === 'channel'),
                  ranked: run.segments.filter((row) => row.level === 'device'),
                  top_segment:
                    run.segments
                      .filter((row) => row.level === 'device')
                      .slice()
                      .sort((a, b) => b.gap_pp - a.gap_pp)[0] ?? null,
                  max_gap_pp: Math.max(
                    0,
                    ...run.segments.filter((row) => row.level === 'device').map((row) => row.gap_pp),
                  ),
                }}
              />
            ) : (
              <div className="loading">没有分群数据</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
