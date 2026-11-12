import type { FunnelRun, PathAnalysis } from '../types/models';
import { http } from './client';

export const runApi = {
  execute: (funnelId: number, windowDays: number) =>
    http.post<{ run: FunnelRun }>(`/funnels/${funnelId}/runs`, { window_days: windowDays, note: 'manual run' }),
  list: (funnelId?: number) =>
    http.get<{ items: FunnelRun[]; total: number }>(
      funnelId ? `/runs?funnel_id=${funnelId}` : '/runs',
    ),
  detail: (runId: number) => http.get<{ run: FunnelRun }>(`/runs/${runId}`),
  paths: (runId: number, stepIndex?: number) =>
    http.get<PathAnalysis>(
      stepIndex ? `/runs/${runId}/paths?step_index=${stepIndex}` : `/runs/${runId}/paths`,
    ),
};
