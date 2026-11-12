import type { EventRow, EventStat } from '../types/models';
import { http } from './client';

export interface EventQuery {
  funnel_id?: number;
  user_key?: string;
  event_name?: string;
  channel?: string;
  device?: string;
  limit?: number;
  offset?: number;
}

export const eventApi = {
  list: (query: EventQuery) => {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
    });
    return http.get<{ items: EventRow[]; total: number; stats: EventStat[] }>(`/events?${params.toString()}`);
  },
};
