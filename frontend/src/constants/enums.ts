/** 共享枚举（前端侧）：与 backend/src/constants/enums.py 一一对应。 */
import type { Channel, Device, FunnelStatus, ReportStatus, Role, RunStatus } from '../types/models';

export const ROLES: Role[] = ['admin', 'analyst', 'viewer'];

export const CHANNELS: Channel[] = ['organic', 'feed', 'social', 'referral'];
export const DEVICES: Device[] = ['ios', 'android'];

export const CHANNEL_LABELS: Record<Channel, string> = {
  organic: '自然搜索',
  feed: '信息流',
  social: '私域社群',
  referral: '转介绍',
};

export const DEVICE_LABELS: Record<Device, string> = {
  ios: 'iOS',
  android: 'Android',
};

export const FUNNEL_STATUS_LABELS: Record<FunnelStatus, string> = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档',
};

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  queued: '排队中',
  running: '计算中',
  succeeded: '已完成',
  failed: '失败',
};

export const REPORT_STATUS_LABELS: Record<ReportStatus, string> = {
  draft: '草稿',
  reviewed: '已复核',
  published: '已发布',
};

/** 事件 -> 地铁站名（与后端 EVENT_LABELS 同源） */
export const EVENT_LABELS: Record<string, string> = {
  register: '注册',
  browse_course: '浏览课程',
  trial_start: '试听开始',
  trial_short_stay: '试听页停留<30s',
  trial_incomplete: '试听未完成',
  trial_complete: '试听完成',
  pricing_view: '价格页',
  consult_chat: '顾问咨询',
  course_compare: '课程对比',
  pay: '付费',
  exit: '退出',
  browse_item: '浏览商品',
  add_cart: '加购',
  order: '下单',
  claim_coupon: '领券',
  redeem_coupon: '核销',
};

export const TERMINAL_EVENTS = ['exit'] as const;

export const LINE_COLORS = ['line-a', 'line-b', 'line-c', 'line-d'] as const;

export function eventLabel(event: string): string {
  return EVENT_LABELS[event] ?? event;
}

export function lineVar(color: string): string {
  return color.startsWith('--') ? `var(${color})` : `var(--${color})`;
}
