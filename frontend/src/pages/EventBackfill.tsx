import { useMemo, useState } from 'react';
import { funnelApi } from '../api/funnels';
import { correctionApi } from '../api/corrections';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { uiStore } from '../stores/uiStore';
import { can } from '../constants/roles';
import {
  CORRECTION_KIND_LABELS,
  CORRECTION_ROW_STATUS_LABELS,
  CHANNELS,
  CHANNEL_LABELS,
  DEVICES,
  DEVICE_LABELS,
  lineVar,
} from '../constants/enums';
import { num, pct, shortDate } from '../utils/format';
import { errorMessage } from '../utils/errorMessage';
import EmptyState from '../components/common/EmptyState';
import type {
  CorrectionApplyResult,
  CorrectionEventInput,
  FunnelDef,
  FunnelRun,
} from '../types/models';

interface DraftRow {
  user_key: string;
  event_name: string;
  event_ts: string;
  channel: string;
  device: string;
}

const EMPTY_ROW: DraftRow = { user_key: '', event_name: '', event_ts: '', channel: 'organic', device: 'ios' };

export default function EventBackfill() {
  const { user } = useAuth();
  const role = user?.role;
  const canRun = can(role, 'run:execute');

  const funnels = useAsync(() => funnelApi.list(), []);
  const list = funnels.data?.items ?? [];
  const [funnelId, setFunnelId] = useState<number | null>(null);
  const selected: FunnelDef | undefined = useMemo(
    () => list.find((item) => item.id === funnelId) ?? list[0],
    [list, funnelId],
  );

  const [note, setNote] = useState('事件补录校正');
  const [rows, setRows] = useState<DraftRow[]>([{ ...EMPTY_ROW }]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CorrectionApplyResult | null>(null);

  const batches = useAsync(
    () => (selected ? correctionApi.list(selected.id) : Promise.resolve({ items: [], total: 0 })),
    [selected?.id, result?.batch.batch_code],
  );
  const versions = useAsync(
    () => (selected ? correctionApi.versions(selected.id) : Promise.resolve({ items: [] })),
    [selected?.id, result?.data_version.id],
  );

  function updateRow(index: number, patch: Partial<DraftRow>) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function addRow() {
    setRows((prev) => [...prev, { ...EMPTY_ROW }]);
  }

  function removeRow(index: number) {
    setRows((prev) => (prev.length === 1 ? prev : prev.filter((_, i) => i !== index)));
  }

  function loadDemo() {
    // 给当前漏斗第一个用户补一条「试听完成」，便于快速体验
    const firstUser = `U0001`;
    const ts = new Date(Date.now() - 24 * 3600 * 1000).toISOString().slice(0, 19);
    setRows([
      { user_key: firstUser, event_name: selected?.steps?.[1]?.event ?? 'trial_complete', event_ts: ts, channel: 'organic', device: 'ios' },
    ]);
  }

  async function submit() {
    if (!selected) return;
    const events: CorrectionEventInput[] = rows
      .filter((r) => r.user_key.trim() && r.event_name.trim() && r.event_ts.trim())
      .map((r) => ({
        user_key: r.user_key.trim(),
        event_name: r.event_name.trim(),
        event_ts: r.event_ts.trim(),
        channel: r.channel,
        device: r.device,
        source: 'backfill',
      }));
    if (!events.length) {
      setError('至少填写一条完整的补录事件（用户 / 事件 / 时间）。');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await correctionApi.apply(selected.id, { note, events });
      setResult(res);
      uiStore.toast(
        `校正完成：入库 ${res.batch.ingested} 条 · 重复拒绝 ${res.batch.rejected_duplicate} 条 · 受影响 ${res.correction_meta.affected_user_count ?? 0} 人`,
        'ok',
      );
      batches.reload();
      versions.reload();
    } catch (err) {
      setError(errorMessage(err, role));
      uiStore.toast('切换失败，已回滚并保留上一版结论', 'warn');
    } finally {
      setBusy(false);
    }
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
    <div>
      <div className="panel" style={{ borderLeftColor: selected ? lineVar(selected.line_color) : undefined }}>
        <div className="panel-head" style={{ marginBottom: 8 }}>
          <div>
            <h2>{selected ? `${selected.name} · 事件补录` : '事件补录'}</h2>
            <div className="tiny muted">
              补录迟到/遗漏事件 → 同用户同事件同秒自动判重 → 校正运行 → 原子切换；旧运行与旧报告保留可查但不再是当前结论
            </div>
          </div>
          <div className="btn-row">
            {list.map((funnel) => (
              <button
                key={funnel.id}
                className={`btn btn-sm ${selected?.id === funnel.id ? 'btn-primary' : ''}`}
                onClick={() => {
                  setFunnelId(funnel.id);
                  setResult(null);
                }}
                data-testid={`backfill-funnel-${funnel.code}`}
              >
                {funnel.line_no}
              </button>
            ))}
          </div>
        </div>

        <div className="field" style={{ marginBottom: 10 }}>
          <label htmlFor="backfill-note">补录说明</label>
          <input
            id="backfill-note"
            className="input"
            value={note}
            maxLength={200}
            onChange={(e) => setNote(e.target.value)}
            data-testid="backfill-note"
          />
        </div>

        <table className="table" data-testid="backfill-grid">
          <thead>
            <tr>
              <th style={{ width: '18%' }}>用户 user_key</th>
              <th style={{ width: '22%' }}>事件 event_name</th>
              <th style={{ width: '24%' }}>事件时间（ISO 8601）</th>
              <th style={{ width: '14%' }}>渠道</th>
              <th style={{ width: '12%' }}>设备</th>
              <th style={{ width: '10%' }} />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                <td>
                  <input
                    className="input mono"
                    value={row.user_key}
                    placeholder="U0001"
                    onChange={(e) => updateRow(index, { user_key: e.target.value })}
                    data-testid={`bf-user-${index}`}
                  />
                </td>
                <td>
                  <input
                    className="input mono"
                    value={row.event_name}
                    placeholder="trial_complete"
                    list="event-vocab"
                    onChange={(e) => updateRow(index, { event_name: e.target.value })}
                    data-testid={`bf-event-${index}`}
                  />
                </td>
                <td>
                  <input
                    className="input mono"
                    value={row.event_ts}
                    placeholder="2026-09-02T10:00:00"
                    onChange={(e) => updateRow(index, { event_ts: e.target.value })}
                    data-testid={`bf-ts-${index}`}
                  />
                </td>
                <td>
                  <select className="input" value={row.channel} onChange={(e) => updateRow(index, { channel: e.target.value })}>
                    {CHANNELS.map((c) => (
                      <option key={c} value={c}>
                        {CHANNEL_LABELS[c]}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select className="input" value={row.device} onChange={(e) => updateRow(index, { device: e.target.value })}>
                    {DEVICES.map((d) => (
                      <option key={d} value={d}>
                        {DEVICE_LABELS[d]}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <button className="btn btn-sm btn-ghost" onClick={() => removeRow(index)} disabled={rows.length === 1}>
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <datalist id="event-vocab">
          {(selected?.steps ?? []).map((s) => (
            <option key={s.event} value={s.event} />
          ))}
          {(selected?.noise_events ?? []).map((e) => (
            <option key={e} value={e} />
          ))}
        </datalist>

        <div className="btn-row" style={{ marginTop: 12 }}>
          <button className="btn btn-sm" onClick={addRow} data-testid="bf-add-row">
            + 再加一条
          </button>
          <button className="btn btn-sm btn-ghost" onClick={loadDemo}>
            填一条示例
          </button>
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={!canRun || busy || !selected}
            data-testid="bf-submit"
          >
            {busy ? '校正计算中 …' : '提交补录并校正'}
          </button>
        </div>
        {!canRun ? <div className="tiny muted" style={{ marginTop: 8 }}>运营角色只读：可以看校正结果，不能提交补录。</div> : null}

        {error ? (
          <div className="error-box" style={{ marginTop: 12 }}>
            <span>{error}</span>
            <button className="btn btn-sm" onClick={() => setError(null)}>
              知道了
            </button>
          </div>
        ) : null}
      </div>

      {result ? <CorrectionResultPanel result={result} /> : null}

      <div className="grid-2" style={{ marginTop: 20 }}>
        <div className="panel line-b">
          <div className="panel-head">
            <h3>校正批次</h3>
            <span className="eyebrow">{batches.data?.total ?? 0} BATCHES</span>
          </div>
          <BatchList batches={batches.data?.items ?? []} />
        </div>
        <div className="panel line-c">
          <div className="panel-head">
            <h3>数据版本链</h3>
            <span className="eyebrow">CONFIG + DATA 绑定</span>
          </div>
          <VersionList versions={versions.data?.items ?? []} />
        </div>
      </div>
    </div>
  );
}

function CorrectionResultPanel({ result }: { result: CorrectionApplyResult }) {
  const meta = result.correction_meta;
  const newRun: FunnelRun = result.correction_run;
  const stepDeltas = meta.step_deltas ?? [];
  const cohortDeltas = meta.cohort_deltas ?? [];
  const rowKinds = result.batch.rows;

  return (
    <div className="panel line-d" style={{ marginTop: 20 }} data-testid="correction-result">
      <div className="panel-head">
        <div>
          <h3>校正结果 · {result.batch.batch_code}</h3>
          <div className="tiny muted">
            基线 {meta.baseline_run_code}（v{meta.baseline_version_no}）→ 校正 {newRun.code}（v{result.data_version.version_no}）
          </div>
        </div>
        <span className="pill ok">已切换为当前结论</span>
      </div>

      <div className="metric-row">
        <div className="metric">
          <span className="label">补录入库</span>
          <b>{num(result.batch.ingested)}</b>
          <small>迟到 {num(result.batch.late)} 条</small>
        </div>
        <div className="metric">
          <span className="label">重复拒绝</span>
          <b>{num(result.batch.rejected_duplicate)}</b>
          <small>同一事件不多算</small>
        </div>
        <div className="metric">
          <span className="label">受影响用户</span>
          <b>{num(meta.affected_user_count ?? 0)}</b>
          <small>状态机结果变化</small>
        </div>
        <div className="metric">
          <span className="label">转化人数</span>
          <b>
            {meta.totals?.baseline_converted ?? 0} → {meta.totals?.corrected_converted ?? 0}
          </b>
          <small>
            进入 {meta.totals?.baseline_entry ?? 0} → {meta.totals?.corrected_entry ?? 0}
          </small>
        </div>
      </div>

      <h4 style={{ margin: '16px 0 8px' }}>步骤人数前后差异（未变化区间保持不变）</h4>
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
          {stepDeltas.map((d) => (
            <tr key={d.index} data-testid={`step-delta-${d.index}`}>
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

      {cohortDeltas.length ? (
        <>
          <h4 style={{ margin: '16px 0 8px' }}>受补录影响的流失队列</h4>
          <table className="table">
            <thead>
              <tr>
                <th>未到达站</th>
                <th className="num-cell">校正前队列</th>
                <th className="num-cell">校正后队列</th>
                <th className="num-cell">差异</th>
              </tr>
            </thead>
            <tbody>
              {cohortDeltas.map((c) => (
                <tr key={c.step_index}>
                  <td>{c.label}</td>
                  <td className="num-cell">{num(c.baseline_cohort_users)}</td>
                  <td className="num-cell">{num(c.corrected_cohort_users)}</td>
                  <td className={`num-cell ${c.delta < 0 ? 'better' : 'worse'}`}>
                    {c.delta > 0 ? '+' : ''}
                    {c.delta}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <div className="tiny muted" style={{ marginTop: 10 }}>
          各流失队列人数均无变化。
        </div>
      )}

      <h4 style={{ margin: '16px 0 8px' }}>补录记录判定明细</h4>
      <table className="table">
        <thead>
          <tr>
            <th>用户</th>
            <th>事件</th>
            <th>事件时间</th>
            <th>判定</th>
            <th>状态</th>
            <th>原因</th>
          </tr>
        </thead>
        <tbody>
          {rowKinds.map((r) => (
            <tr key={r.id} data-testid={`bf-row-${r.id}`}>
              <td className="mono">{r.user_key}</td>
              <td>{r.event_label}</td>
              <td className="mono tiny">{shortDate(r.event_ts)}</td>
              <td>
                <span className={`pill ${r.is_late ? 'warn' : ''} ${r.is_duplicate ? 'danger' : 'ok'}`}>
                  {CORRECTION_KIND_LABELS[r.kind] ?? r.kind}
                </span>
              </td>
              <td>{CORRECTION_ROW_STATUS_LABELS[r.status] ?? r.status}</td>
              <td className="tiny muted">{r.reason || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BatchList({ batches }: { batches: import('../types/models').CorrectionBatch[] }) {
  if (!batches.length) {
    return <EmptyState eyebrow="NO BATCH" title="还没有补录批次" hint="在上方录入补录事件后提交，会生成一个校正批次。" />;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {batches.map((b) => (
        <div key={b.batch_code} className="demo-account" style={{ alignItems: 'flex-start' }}>
          <span>
            <b className="mono" style={{ fontWeight: 500 }}>
              {b.batch_code}
            </b>
            <span className="mono tiny muted" style={{ display: 'block' }}>
              入库 {num(b.ingested)} · 重复拒绝 {num(b.rejected_duplicate)} · 迟到 {num(b.late)} · 共 {num(b.total_rows)} 条
            </span>
            {b.correction_run_code ? (
              <span className="mono tiny muted" style={{ display: 'block' }}>
                校正运行 {b.correction_run_code}
              </span>
            ) : null}
          </span>
          <span className="pill ok">已校正</span>
        </div>
      ))}
    </div>
  );
}

function VersionList({ versions }: { versions: import('../types/models').DataVersion[] }) {
  if (!versions.length) {
    return <div className="loading">还没有数据版本（运行一次漏斗后自动建立基线版本）。</div>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {versions.map((v, idx) => (
        <div key={v.id} className="demo-account" style={{ alignItems: 'flex-start' }}>
          <span>
            <b style={{ fontWeight: 500 }}>
              v{v.version_no} ·{' '}
              {idx === 0 ? (
                <span className="pill ok">生效中 · 当前</span>
              ) : (
                <span className="pill">历史版本 · 可查</span>
              )}
            </b>
            <span className="mono tiny muted" style={{ display: 'block' }}>
              {v.code} · 指纹 {v.fingerprint_short}
            </span>
            <span className="tiny muted" style={{ display: 'block' }}>
              窗口 {v.window_days}d · 事件 {num(v.event_count)}
              {v.ingested_count ? ` · 补录 ${num(v.ingested_count)} / 重复拒 ${num(v.rejected_duplicate_count)}` : ''}
            </span>
            {v.note ? <span className="tiny muted" style={{ display: 'block' }}>{v.note}</span> : null}
          </span>
        </div>
      ))}
    </div>
  );
}
