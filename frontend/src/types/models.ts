/** 与后端 schemas 对齐的领域类型。 */

export type Role = 'admin' | 'analyst' | 'viewer';
export type Channel = 'organic' | 'feed' | 'social' | 'referral';
export type Device = 'ios' | 'android';
export type FunnelStatus = 'draft' | 'published' | 'archived';
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed';
export type ReportStatus = 'draft' | 'reviewed' | 'published';

export interface UserInfo {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  team: string;
}

export interface FunnelStep {
  key: string;
  label: string;
  event: string;
}

export interface FunnelDef {
  id: number;
  code: string;
  name: string;
  description: string;
  line_no: string;
  line_color: string;
  steps: FunnelStep[];
  noise_events: string[];
  window_days: number;
  cross_session: boolean;
  status: FunnelStatus;
  version: number;
  owner_email: string;
  step_count: number;
  updated_at: string | null;
}

export interface StepResult {
  index: number;
  key: string;
  event: string;
  label: string;
  users: number;
  rate_from_prev: number;
  rate_from_entry: number;
  lost: number;
  lost_share: number;
  p50_seconds: number | null;
  p50_days: number | null;
}

export interface TransitionRow {
  from_index: number;
  to_index: number;
  from_label: string;
  to_label: string;
  samples: number;
  p50_seconds: number | null;
  p50_days: number | null;
  p90_seconds: number | null;
  p90_days: number | null;
  mean_seconds: number | null;
}

export interface DurationStats {
  samples: number;
  p50_seconds: number | null;
  p50_days: number | null;
  p90_seconds: number | null;
  p90_days: number | null;
  mean_seconds: number | null;
}

export interface FunnelRun {
  id: number;
  code: string;
  funnel_id: number;
  funnel_code: string | null;
  funnel_name: string | null;
  line_no: string | null;
  line_color: string | null;
  trigger: 'seed' | 'manual' | 'scheduled';
  status: RunStatus;
  window_days: number;
  entry_users: number;
  converted_users: number;
  conversion_rate: number;
  steps: StepResult[];
  transitions: TransitionRow[];
  duration: DurationStats;
  discard: Record<string, number>;
  segments: SegmentRow[];
  lost_steps: LostStep[];
  max_loss_step: number;
  engine_version: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface LostStep {
  index: number;
  label: string;
  event: string;
  lost: number;
  lost_share: number;
  from_label: string;
}

export interface SegmentRow {
  level: 'device' | 'channel';
  channel: Channel;
  channel_label: string;
  device: Device | null;
  device_label: string;
  users: number;
  dropped: number;
  drop_rate: number;
  gap_pp: number;
  reached: number[];
}

export interface PathEntry {
  rank: number;
  path: string;
  path_events: string[];
  depth: number;
  count: number;
  share_pct: number;
  terminal_event: string;
  terminal_label: string;
  top_channel: string;
  cohort_index?: number;
  cohort_label?: string;
  cohort_users?: number;
}

export interface ChokePoint {
  event: string;
  label: string;
  count: number;
  share_pct: number;
}

export interface TreeNode {
  event: string;
  label: string;
  count: number;
  children: TreeNode[];
}

export interface CohortResult {
  step_index: number;
  step_label: string;
  from_label: string;
  cohort_users: number;
  distinct_paths: number;
  paths: PathEntry[];
  choke_points: ChokePoint[];
  prefix_tree: TreeNode;
  top_path: PathEntry | null;
  top_choke: ChokePoint | null;
}

export interface SegmentBlock {
  step_index: number;
  step_label: string;
  from_label: string;
  overall_drop_rate: number;
  overall_users: number;
  overall_dropped: number;
  rows: SegmentRow[];
  channel_rows: SegmentRow[];
  ranked: SegmentRow[];
  top_segment: SegmentRow | null;
  max_gap_pp: number;
}

export interface PathAnalysis {
  run: FunnelRun;
  lost_steps: LostStep[];
  selected_step: number;
  cohort: CohortResult;
  segments: SegmentBlock;
}

export interface DropReport {
  id: number;
  code: string;
  funnel_id: number;
  funnel_code: string | null;
  funnel_name: string | null;
  run_id: number;
  title: string;
  drop_step_index: number;
  drop_step_label: string;
  cohort_users: number;
  top_paths: PathEntry[];
  choke_points: ChokePoint[];
  segment_gap: SegmentBlock;
  conclusion: string;
  status: ReportStatus;
  author_email: string;
  reviewer_email: string;
  version: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface EventRow {
  id: number;
  user_key: string;
  event_name: string;
  event_label: string;
  event_ts: string;
  seq: number;
  session_id: string;
  channel: Channel;
  channel_label: string;
  device: Device;
  device_label: string;
}

export interface EventStat {
  event: string;
  label: string;
  count: number;
}

export interface CacheStatus {
  funnel_id: number;
  status: 'idle' | 'queued' | 'running' | 'ready' | 'failed';
  refreshed_at: string | null;
  top_path: string | null;
  cohort_users: number | null;
  source_run: string | null;
}
