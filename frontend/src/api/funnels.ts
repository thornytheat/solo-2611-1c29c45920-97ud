import type { FunnelDef, FunnelStep } from '../types/models';
import { http } from './client';

export interface TrialPayload {
  steps: FunnelStep[];
  window_days: number;
  noise_events?: string[];
}

export interface TrialResult {
  steps: {
    index: number;
    label: string;
    event: string;
    users: number;
    rate_from_prev: number;
    rate_from_entry: number;
    lost: number;
    lost_share: number;
    p50_days: number | null;
  }[];
  duration: { p50_days: number | null; p90_days: number | null; samples: number };
  discard: Record<string, number>;
  entry_users: number;
  converted_users: number;
  window_days: number;
}

export const funnelApi = {
  list: () => http.get<{ items: FunnelDef[]; total: number }>('/funnels'),
  detail: (id: number) =>
    http.get<{ funnel: FunnelDef; latest_run: unknown; channels: { channel: string; label: string; users: number }[] }>(
      `/funnels/${id}`,
    ),
  create: (payload: Record<string, unknown>) => http.post<{ funnel: FunnelDef }>('/funnels', payload),
  update: (id: number, payload: Record<string, unknown>) =>
    http.patch<{ funnel: FunnelDef }>(`/funnels/${id}`, payload),
  publish: (id: number) => http.post<{ funnel: FunnelDef }>(`/funnels/${id}/publish`),
  trial: (payload: TrialPayload) => http.post<TrialResult>('/funnels/trial', payload),
  cacheRefresh: (id: number) =>
    http.post<{ task_id: string; status: string }>(`/funnels/${id}/cache-refresh`),
  cacheStatus: (id: number) =>
    http.get<{ status: string; refreshed_at: string | null; top_path: string | null; cohort_users: number | null; source_run: string | null }>(
      `/funnels/${id}/cache-status`,
    ),
};
