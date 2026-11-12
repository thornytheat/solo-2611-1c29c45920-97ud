import type { DropReport, FunnelRun } from '../types/models';
import { http } from './client';

export const reportApi = {
  list: (funnelId?: number) =>
    http.get<{ items: DropReport[]; total: number }>(
      funnelId ? `/reports?funnel_id=${funnelId}` : '/reports',
    ),
  detail: (id: number) => http.get<{ report: DropReport; run: FunnelRun }>(`/reports/${id}`),
  create: (payload: { run_id: number; drop_step_index?: number; title: string; conclusion: string }) =>
    http.post<{ report: DropReport }>('/reports', payload),
  patch: (id: number, payload: Record<string, unknown>) =>
    http.patch<{ report: DropReport }>(`/reports/${id}`, payload),
  export: (payload: { report_id: number; format: 'md' | 'csv' }) =>
    http.post<{ filename: string; media_type: string; content: string; path_count: number }>(
      '/exports',
      payload,
    ),
};
