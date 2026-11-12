import type { CorrectionApplyResult, CorrectionBatch, CorrectionEventInput, DataVersion } from '../types/models';
import { http } from './client';

export const correctionApi = {
  /** 事件补录 + 校正运行 + 原子切换（后端单事务，失败回滚保留上一版）。 */
  apply: (funnelId: number, payload: { note: string; events: CorrectionEventInput[] }) =>
    http.post<CorrectionApplyResult>(`/funnels/${funnelId}/corrections`, payload),
  list: (funnelId?: number) =>
    http.get<{ items: CorrectionBatch[]; total: number }>(
      funnelId ? `/corrections?funnel_id=${funnelId}` : '/corrections',
    ),
  detail: (batchCode: string) =>
    http.get<{ batch: CorrectionBatch }>(`/corrections/${encodeURIComponent(batchCode)}`),
  versions: (funnelId: number) =>
    http.get<{ items: DataVersion[] }>(`/funnels/${funnelId}/data-versions`),
};
