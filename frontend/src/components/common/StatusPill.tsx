import type { FunnelStatus, ReportStatus } from '../../types/models';
import { FUNNEL_STATUS_LABELS, REPORT_STATUS_LABELS } from '../../constants/enums';

export function FunnelPill({ status }: { status: FunnelStatus }) {
  const tone = status === 'published' ? 'ok' : status === 'draft' ? 'warn' : '';
  return <span className={`pill ${tone}`}>{FUNNEL_STATUS_LABELS[status] ?? status}</span>;
}

export function ReportPill({ status }: { status: ReportStatus }) {
  const tone = status === 'published' ? 'ok' : status === 'reviewed' ? 'warn' : '';
  return <span className={`pill ${tone}`}>{REPORT_STATUS_LABELS[status] ?? status}</span>;
}

export function GapPill({ value }: { value: number }) {
  const tone = value > 0 ? 'danger' : value < 0 ? 'ok' : '';
  return (
    <span className={`pill ${tone}`}>
      {value > 0 ? '+' : ''}
      {value.toFixed(1)}pp
    </span>
  );
}
