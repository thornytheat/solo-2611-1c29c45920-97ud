import { useEffect, useMemo, useState } from 'react';
import { funnelApi } from '../api/funnels';
import { reportApi } from '../api/reports';
import { runApi } from '../api/runs';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { uiStore } from '../stores/uiStore';
import { can } from '../constants/roles';
import { REPORT_STATUS_LABELS, lineVar } from '../constants/enums';
import { downloadText, num, pct, pp, shortDate, signedClass } from '../utils/format';
import { errorMessage } from '../utils/errorMessage';
import ChokeBars from '../components/common/ChokeBars';
import EmptyState from '../components/common/EmptyState';
import SegmentTable from '../components/common/SegmentTable';
import { ReportPill } from '../components/common/StatusPill';
import type { DropReport, ReportStatus } from '../types/models';

export default function Attribution() {
  const { user } = useAuth();
  const role = user?.role;
  const canWrite = can(role, 'report:write');
  const canReview = can(role, 'report:review');
  const canExport = can(role, 'export:read');

  const funnels = useAsync(() => funnelApi.list(), []);
  const [funnelId, setFunnelId] = useState<number | null>(null);
  const [reportId, setReportId] = useState<number | null>(null);
  const [conclusion, setConclusion] = useState('');
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const list = funnels.data?.items ?? [];
  const selected = useMemo(() => list.find((item) => item.id === funnelId) ?? list[0], [list, funnelId]);

  useEffect(() => {
    if (selected) {
      setFunnelId(selected.id);
      uiStore.selectFunnel(selected.id);
    }
  }, [selected?.id]);

  const reports = useAsync(
    () => (selected ? reportApi.list(selected.id) : Promise.resolve({ items: [], total: 0 })),
    [selected?.id],
  );
  const runs = useAsync(
    () => (selected ? runApi.list(selected.id) : Promise.resolve({ items: [], total: 0 })),
    [selected?.id],
  );

  const currentReport: DropReport | null =
    (reports.data?.items ?? []).find((item) => item.id === reportId) ?? reports.data?.items?.[0] ?? null;

  useEffect(() => {
    if (!currentReport) return;
    setReportId(currentReport.id);
    setConclusion(currentReport.conclusion ?? '');
    setTitle(currentReport.title ?? '');
  }, [currentReport?.id]);

  async function createReport() {
    const run = runs.data?.items?.[0];
    if (!run) {
      uiStore.toast('先到「漏斗结果」跑一次漏斗', 'warn');
      return;
    }
    setBusy('create');
    setError(null);
    try {
      const result = await reportApi.create({
        run_id: run.id,
        title: `${run.funnel_name ?? '漏斗'} · ${run.steps[run.max_loss_step]?.label ?? ''} 流失归因`,
        conclusion: '',
      });
      setReportId(result.report.id);
      uiStore.toast('已生成草稿归因报告（派生指标自动回填）', 'ok');
      reports.reload();
    } catch (err) {
      setError(errorMessage(err, role));
    } finally {
      setBusy(null);
    }
  }

  async function patch(payload: Record<string, unknown>, label: string) {
    if (!currentReport) return;
    setBusy(label);
    setError(null);
    try {
      await reportApi.patch(currentReport.id, payload);
      uiStore.toast(`已更新：${label}`, 'ok');
      reports.reload();
    } catch (err) {
      setError(errorMessage(err, role));
    } finally {
      setBusy(null);
    }
  }

  async function exportReport(format: 'md' | 'csv') {
    if (!currentReport) return;
    setBusy(`export-${format}`);
    setError(null);
    try {
      const result = await reportApi.export({ report_id: currentReport.id, format });
      downloadText(result.filename, result.content, result.media_type);
      uiStore.toast(`已导出 ${result.filename}（${result.path_count} 条路径）`, 'ok');
    } catch (err) {
      setError(errorMessage(err, role));
    } finally {
      setBusy(null);
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
            <h2>{selected ? `${selected.name} · 归因报告` : '归因报告'}</h2>
            <div className="tiny muted">
              卡点事件 + Top 路径 + 分群差 → 结论 → 增长负责人复核 → 导出 MD / CSV
            </div>
          </div>
          <div className="btn-row">
            {list.map((funnel) => (
              <button
                key={funnel.id}
                className={`btn btn-sm ${selected?.id === funnel.id ? 'btn-primary' : ''}`}
                onClick={() => {
                  setFunnelId(funnel.id);
                  setReportId(null);
                }}
                data-testid={`report-funnel-${funnel.code}`}
              >
                {funnel.line_no}
              </button>
            ))}
          </div>
        </div>
        <div className="btn-row">
          <button className="btn btn-sm" onClick={createReport} disabled={!canWrite || busy !== null} data-testid="create-report">
            {busy === 'create' ? '生成中 …' : '从最新运行生成报告'}
          </button>
          <button className="btn btn-sm" onClick={() => reports.reload()}>
            刷新列表
          </button>
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

      {!reports.data?.items?.length ? (
        <div style={{ marginTop: 20 }}>
          <EmptyState
            eyebrow="NO REPORT"
            title="还没有归因报告"
            hint="分析师可以基于最近一次运行生成草稿：流失队列、Top-8 路径、卡点事件与分群差都会自动回填。"
            action={
              <button className="btn btn-sm" onClick={createReport} disabled={!canWrite}>
                生成草稿
              </button>
            }
          />
        </div>
      ) : (
        <div className="grid-2" style={{ marginTop: 20 }}>
          <section>
            <div className="panel">
              <div className="panel-head">
                <h3>报告队列</h3>
                <span className="eyebrow">{reports.data?.total ?? 0} REPORTS</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {(reports.data?.items ?? []).map((report) => {
                  const active = currentReport?.id === report.id;
                  return (
                    <button
                      key={report.id}
                      className="demo-account"
                      onClick={() => setReportId(report.id)}
                      style={{
                        borderColor: active ? 'var(--signal)' : undefined,
                        background: active ? 'oklch(0.26 0.024 256 / 0.6)' : undefined,
                        alignItems: 'flex-start',
                      }}
                      data-testid={`report-code-${report.code}`}
                    >
                      <span>
                        <b style={{ fontWeight: 500 }}>{report.title}</b>
                        <span className="mono tiny muted" style={{ display: 'block' }}>
                          {report.code} · 未到达「{report.drop_step_label}」{num(report.cohort_users)} 人 · {shortDate(report.updated_at)}
                        </span>
                      </span>
                      <ReportPill status={report.status} />
                    </button>
                  );
                })}
              </div>
            </div>

            {currentReport ? (
              <div className="panel line-b" style={{ marginTop: 20 }}>
                <div className="panel-head">
                  <h3>卡点分布</h3>
                  <span className="eyebrow">COHORT {num(currentReport.cohort_users)}</span>
                </div>
                <ChokeBars points={currentReport.choke_points} />
              </div>
            ) : null}
          </section>

          <section>
            {currentReport ? (
              <>
                <div className="panel" style={{ borderLeftColor: lineVar(selected?.line_color ?? 'line-a') }}>
                  <div className="panel-head">
                    <div>
                      <div className="eyebrow">{currentReport.code} · v{currentReport.version}</div>
                      <h2 style={{ marginTop: 4 }}>{currentReport.title}</h2>
                    </div>
                    <ReportPill status={currentReport.status} />
                  </div>

                  <div className="metric-row">
                    <div className="metric">
                      <span className="label">流失队列</span>
                      <b>{num(currentReport.cohort_users)}</b>
                      <small>未到达「{currentReport.drop_step_label}」</small>
                    </div>
                    <div className="metric">
                      <span className="label">Top1 路径占比</span>
                      <b>{pct(currentReport.top_paths[0]?.share_pct ?? 0)}</b>
                      <small>{num(currentReport.top_paths[0]?.count ?? 0)} 人</small>
                    </div>
                    <div className="metric">
                      <span className="label">最大卡点</span>
                      <b>{pct(currentReport.choke_points[0]?.share_pct ?? 0)}</b>
                      <small>{currentReport.choke_points[0]?.label ?? '—'}</small>
                    </div>
                    <div className="metric">
                      <span className="label">最大分群差</span>
                      <b className={signedClass(currentReport.segment_gap?.max_gap_pp ?? 0)}>
                        {pp(currentReport.segment_gap?.max_gap_pp ?? 0)}
                      </b>
                      <small>
                        {currentReport.segment_gap?.top_segment
                          ? `${currentReport.segment_gap.top_segment.channel_label} · ${currentReport.segment_gap.top_segment.device_label}`
                          : '—'}
                      </small>
                    </div>
                  </div>

                  <div className="field" style={{ marginTop: 14 }}>
                    <label htmlFor="report-title">报告标题</label>
                    <input
                      id="report-title"
                      className="input"
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      disabled={!canWrite}
                      data-testid="report-title"
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="conclusion">结论（分析师写，负责人复核）</label>
                    <textarea
                      id="conclusion"
                      className="textarea"
                      value={conclusion}
                      onChange={(event) => setConclusion(event.target.value)}
                      disabled={!canWrite}
                      placeholder="哪一站最漏、漏在路径的哪一步、哪个渠道要优先改？"
                      data-testid="report-conclusion"
                    />
                  </div>

                  <div className="btn-row">
                    <button
                      className="btn"
                      onClick={() => patch({ title, conclusion }, '保存结论')}
                      disabled={!canWrite || busy !== null}
                      data-testid="save-report"
                    >
                      保存草稿
                    </button>
                    <button
                      className="btn"
                      onClick={() => patch({ status: 'reviewed' as ReportStatus }, '复核')}
                      disabled={!canReview || busy !== null}
                      data-testid="review-report"
                    >
                      标记已复核
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={() => patch({ status: 'published' as ReportStatus }, '发布')}
                      disabled={!canReview || busy !== null}
                      data-testid="publish-report"
                    >
                      发布报告
                    </button>
                    <button
                      className="btn"
                      onClick={() => exportReport('md')}
                      disabled={!canExport || busy !== null}
                      data-testid="export-md"
                    >
                      {busy === 'export-md' ? '渲染中 …' : `导出 MD（${currentReport.top_paths.length} 条路径）`}
                    </button>
                    <button
                      className="btn btn-ghost"
                      onClick={() => exportReport('csv')}
                      disabled={!canExport || busy !== null}
                      data-testid="export-csv"
                    >
                      导出 CSV
                    </button>
                  </div>
                  {!canReview ? (
                    <div className="tiny muted" style={{ marginTop: 8 }}>
                      复核与发布只能由增长负责人执行；分析师可以写结论并导出。
                    </div>
                  ) : null}
                </div>

                <div className="panel line-c" style={{ marginTop: 20 }}>
                  <div className="panel-head">
                    <h3>Top-8 前置路径</h3>
                    <span className="eyebrow">报告正文</span>
                  </div>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>队列</th>
                        <th>路径</th>
                        <th className="num-cell">人数</th>
                        <th className="num-cell">占该队列</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentReport.top_paths.map((path) => (
                        <tr key={`${path.cohort_index}-${path.rank}`}>
                          <td className="mono tiny muted">{path.rank}</td>
                          <td className="tiny">{path.cohort_label ?? currentReport.drop_step_label}</td>
                          <td style={{ fontSize: '0.84rem' }}>{path.path}</td>
                          <td className="num-cell">{num(path.count)}</td>
                          <td className="num-cell">{pct(path.share_pct)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="panel" style={{ marginTop: 20 }}>
                  <div className="panel-head">
                    <h3>分群差</h3>
                    <span className="eyebrow">
                      整体 {pct(currentReport.segment_gap?.overall_drop_rate ?? 0)}
                    </span>
                  </div>
                  {currentReport.segment_gap?.rows?.length ? (
                    <SegmentTable block={currentReport.segment_gap} compact />
                  ) : (
                    <div className="loading">没有分群数据</div>
                  )}
                </div>
              </>
            ) : (
              <EmptyState
                eyebrow="SELECT"
                title="选一份报告"
                hint={`当前状态：${REPORT_STATUS_LABELS.draft} 可以由分析师编辑，已复核 / 已发布只能由增长负责人推进。`}
              />
            )}
          </section>
        </div>
      )}
    </div>
  );
}
