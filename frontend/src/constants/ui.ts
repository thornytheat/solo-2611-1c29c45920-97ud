/** 导航与页面元信息。 */
export const NAV_ITEMS = [
  { to: '/funnels', label: '漏斗定义', code: 'A', line: 'L1', permission: 'funnel:read', hint: '站点与窗口' },
  { to: '/results', label: '漏斗结果', code: 'B', line: 'L1', permission: 'run:read', hint: '转化与耗时' },
  { to: '/paths', label: '路径分析', code: 'C', line: 'L2', permission: 'run:read', hint: '前缀树与卡点' },
  { to: '/reports', label: '归因报告', code: 'D', line: 'L3', permission: 'report:read', hint: '复核与导出' },
] as const;

export const DEMO_ACCOUNTS = [
  { email: 'admin@funnelpath.io', role: 'admin', label: '增长负责人' },
  { email: 'analyst@funnelpath.io', role: 'analyst', label: '产品分析师' },
  { email: 'viewer@funnelpath.io', role: 'viewer', label: '运营（只读）' },
] as const;

export const DEMO_PASSWORD = 'Demo@2026';

export const BRAND = {
  short: 'funnelpath',
  name: '多步漏斗转化与路径流失归因台',
  client: '行知教育 · 增长产品组',
  scale: '月活 6 万 / 9 人小组 / K12 素养课',
};
