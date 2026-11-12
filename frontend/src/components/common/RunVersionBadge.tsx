import type { FunnelRun } from '../../types/models';
import { RUN_TRIGGER_LABELS } from '../../constants/enums';

/** 运行的版本/校正/当前结论徽章 + 数据版本与配置指纹。 */
export function RunVersionBadge({ run }: { run: FunnelRun }) {
  return (
    <div className="tiny" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
      {run.is_current ? (
        <span className="pill ok" data-testid="run-current-pill">
          当前结论
        </span>
      ) : (
        <span className="pill" data-testid="run-archived-pill">
          历史归档 · 非当前
        </span>
      )}
      {run.is_correction ? (
        <span className="pill warn" data-testid="run-correction-pill">
          校正运行 · {RUN_TRIGGER_LABELS.correction}
        </span>
      ) : (
        <span className="pill">{RUN_TRIGGER_LABELS[run.trigger] ?? run.trigger}</span>
      )}
      <span className="mono muted">
        数据版本 v{run.data_version_no ?? '—'} · 指纹 {run.data_fingerprint_short || '—'}
      </span>
      {run.config_frozen ? <span className="mono muted">配置已冻结</span> : null}
    </div>
  );
}
