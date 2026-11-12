/** 轮询 worker 的路径缓存状态（异步任务只有 worker 能写）。 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { funnelApi } from '../api/funnels';

export interface CacheSnapshot {
  status: string;
  refreshed_at: string | null;
  top_path: string | null;
  cohort_users: number | null;
  source_run: string | null;
}

export function useCachePoll(funnelId: number | null, active: boolean) {
  const [snapshot, setSnapshot] = useState<CacheSnapshot | null>(null);
  const timer = useRef<number | null>(null);

  const stop = useCallback(() => {
    if (timer.current !== null) {
      window.clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => {
    if (!active || !funnelId) {
      stop();
      return;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await funnelApi.cacheStatus(funnelId);
        if (cancelled) return;
        setSnapshot(data as CacheSnapshot);
        if (data.status === 'ready' || data.status === 'failed') stop();
      } catch {
        if (!cancelled) setSnapshot(null);
      }
    };
    poll();
    timer.current = window.setInterval(poll, 1500);
    return () => {
      cancelled = true;
      stop();
    };
  }, [funnelId, active, stop]);

  return { snapshot, stop };
}
