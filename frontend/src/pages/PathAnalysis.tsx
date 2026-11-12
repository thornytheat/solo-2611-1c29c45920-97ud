import { useEffect, useMemo, useState } from 'react';
import { funnelApi } from '../api/funnels';
import { runApi } from '../api/runs';
import { useAsync } from '../hooks/useAsync';
import { useCachePoll } from '../hooks/useCachePoll';
import { useAuth } from '../router/guards';
import { uiStore } from '../stores/uiStore';
import { can } from '../constants/roles';
import { CHANNEL_LABELS, lineVar } from '../constants/enums';
import { num, pct } from '../utils/format';
import { errorMessage } from '../utils/errorMessage';
import ChokeBars from '../components/common/ChokeBars';
import EmptyState from '../components/common/EmptyState';
import PathTree from '../components/common/PathTree';
import SegmentTable from '../components/common/SegmentTable';
import StationStrip from '../components/common/StationStrip';

export default function PathAnalysis() {
  const { user } = useAuth();
  const role = user?.role;
  const canRefresh = can(role, 'cache:refresh');

  const funnels = useAsync(() => funnelApi.list(), []);
  const [funnelId, setFunnelId] = useState<number | null>(null);
  const [step, setStep] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const list = funnels.data?.items ?? [];
  const selected = useMemo(() => list.find((item) => item.id === funnelId) ?? list[0], [list, funnelId]);

  useEffect(() => {
    if (selected) {
      setFunnelId(selected.id);
      uiStore.selectFunnel(selected.id);
    }
  }, [selected?.id]);

  const runs = useAsync(
    () => (selected ? runApi.list(selected.id) : Promise.resolve({ items: [], total: 0 })),
    [selected?.id],
  );
  const run = runs.data?.items?.[0] ?? null;

  const analysis = useAsync(
    () => (run ? runApi.paths(run.id, step ?? undefined) : Promise.resolve(null)),
    [run?.id, step],
  );

  const { snapshot } = useCachePoll(selected?.id ?? null, polling);

  useEffect(() => {
    if (analysis.data && step === null) setStep(analysis.data.selected_step);
  }, [analysis.data?.selected_step]);

  useEffect(() => {
    if (snapshot?.status === 'ready') {
      uiStore.toast(`worker 已刷新路径缓存（${snapshot.cohort_users ?? 0} 人队列）`, 'ok');
      setPolling(false);
    }
    if (snapshot?.status === 'failed') {
      uiStore.toast('worker 刷新失败，稍后重试', 'warn');
      setPolling(false);
    }
  }, [snapshot?.status]);

  async function refreshCache() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await funnelApi.cacheRefresh(selected.id);
      setPolling(true);
      uiStore.toast('已投递 Celery 任务，等待 worker 回写 …', 'info');
    } catch (err) {
      setError(errorMessage(err, role));
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
            <h2>{selected ? `${selected.name} · 路径分析` : '路径分析'}</h2>
            <div className="tiny muted">
              前缀树深度 ≤6 · Top-8 前置路径 · 卡点按末事件聚合（同一条路径只算一次）
            </div>
          </div>
          <div className="btn-row">
            {list.map((funnel) => (
              <button
                key={funnel.id}
                className={`btn btn-sm ${selected?.id === funnel.id ? 'btn-primary' : ''}`}
                onClick={() => {
                  setFunnelId(funnel.id);
                  setStep(null);
                }}
                data-testid={`path-funnel-${funnel.code}`}
              >
                {funnel.line_no}
              </button>
            ))}
          </div>
        </div>
        <div className="tiny muted">
          运行 {run ? `${run.code} · ${num(run.entry_users)} 人` : '—'} ·
          {snapshot ? ` worker 缓存 ${snapshot.status}` : ' worker 缓存 idle'}
        </div>
        {error ? (
          <div className="error-box" style={{ marginTop: 12 }}>
            <span>{error}</span>
            <button className="btn btn-sm" onClick={() => setError(null)}>
              知道了
            </button>
          </div>
        ) : null}
      </div>

      {!run ? (
        <div style={{ marginTop: 20 }}>
          <EmptyState
            eyebrow="NO RUN"
            title="还没有可分析的运行"
            hint="先到「漏斗结果」跑一次漏斗，路径与卡点都基于那次运行物化出来的会话路径。"
            action={
              <button className="btn btn-sm" onClick={runs.reload}>
                刷新
              </button>
            }
          />
        </div>
      ) : analysis.loading && !analysis.data ? (
        <div className="loading">展开前缀树 …</div>
      ) : analysis.data ? (
        <>
          <div className="panel line-b" style={{ marginTop: 20 }}>
            <div className="panel-head">
              <h3>选择流失队列</h3>
              <span className="eyebrow">CLICK A STATION</span>
            </div>
            <StationStrip
              steps={analysis.data.run.steps}
              lostSteps={analysis.data.run.lost_steps}
              lineColor={selected?.line_color ?? 'line-a'}
              selectedStep={analysis.data.selected_step}
              onSelectStep={(index) => {
                if (index > 0) setStep(index);
              }}
            />
            <div className="btn-row" style={{ marginTop: 12 }}>
              {analysis.data.lost_steps.map((row) => (
                <button
                  key={row.index}
                  className={`btn btn-sm ${analysis.data?.selected_step === row.index ? 'btn-primary' : ''}`}
                  onClick={() => setStep(row.index)}
                  data-testid={`cohort-${row.index}`}
                >
                  未到达「{row.label}」· {num(row.lost)} 人
                </button>
              ))}
              <button className="btn btn-sm btn-ghost" onClick={refreshCache} disabled={!canRefresh || busy || polling}>
                {polling ? 'worker 刷新中 …' : '让 worker 刷新路径缓存'}
              </button>
            </div>
            {!canRefresh ? <div className="tiny muted">运营只读：可以看路径，不能触发缓存刷新。</div> : null}
          </div>

          <div className="panel line-d" style={{ marginTop: 20 }}>
            <div className="panel-head">
              <h3>前缀树 · 换乘结构</h3>
              <span className="eyebrow">
                队列 {num(analysis.data.cohort.cohort_users)} 人 · {analysis.data.cohort.distinct_paths} 条不同路径 · 深度 ≤6
              </span>
            </div>
            <PathTree tree={analysis.data.cohort.prefix_tree} total={analysis.data.cohort.cohort_users} />
          </div>

          <div className="grid-2" style={{ marginTop: 20 }}>
            <div className="panel">
              <div className="panel-head">
                <h3>Top-8 前置路径</h3>
                <span className="eyebrow">SHARE IN COHORT</span>
              </div>
              <div className="path-list" data-testid="path-list">
                {analysis.data.cohort.paths.map((path) => (
                  <div key={path.rank} className={`path-item ${path.rank === 1 ? 'top' : ''}`}>
                    <span className="rank">{String(path.rank).padStart(2, '0')}</span>
                    <span className="path-text">
                      {path.path.split(' → ').map((segment, index) => (
                        <span key={`${path.rank}-${segment}-${index}`}>
                          {index > 0 ? <span className="muted"> → </span> : null}
                          <em>{segment}</em>
                        </span>
                      ))}
                      <span className="tiny muted" style={{ display: 'block' }}>
                        卡点 {path.terminal_label} · 主要来源{' '}
                        {CHANNEL_LABELS[path.top_channel as keyof typeof CHANNEL_LABELS] ?? path.top_channel}
                      </span>
                    </span>
                    <span className="num-cell">{num(path.count)}</span>
                    <span className="num-cell share" style={{ color: path.rank === 1 ? 'var(--signal)' : undefined }}>
                      {pct(path.share_pct)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel line-c">
              <div className="panel-head">
                <h3>卡点事件</h3>
                <span className="eyebrow">TERMINAL EVENT</span>
              </div>
              <ChokeBars points={analysis.data.cohort.choke_points} />
              <div className="tiny muted" style={{ marginTop: 14 }}>
                卡点按「该队列末事件」聚合：同一个卡点往往由多条前置路径共同贡献，
                所以它的占比会高于任何单条路径。
              </div>
            </div>
          </div>

          <div className="panel" style={{ marginTop: 20 }}>
            <div className="panel-head">
              <h3>分群流失率差 · 渠道 × 设备</h3>
              <span className="eyebrow">GAP IN PP</span>
            </div>
            <SegmentTable block={analysis.data.segments} compact />
          </div>
        </>
      ) : (
        <div className="loading">跳过</div>
      )}
    </div>
  );
}
