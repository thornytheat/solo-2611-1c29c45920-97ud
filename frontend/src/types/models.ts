/** 与后端 schemas 对齐的领域类型。 */

export type Role = 'admin' | 'analyst' | 'viewer';
export type Channel = 'organic' | 'feed' | 'social' | 'referral';
export type Device = 'ios' | 'android';
export type FunnelStatus = 'draft' | 'published' | 'archived';
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed';
export type RunTrigger = 'seed' | 'manual' | 'scheduled' | 'correction';
export type ReportStatus = 'draft' | 'reviewed' | 'published';
export type CorrectionStatus = 'staged' | 'applied' | 'failed';
export type CorrectionRowStatus = 'staged' | 'ingested' | 'rejected_duplicate';
export type CorrectionKind = 'normal' | 'late' | 'duplicate' | 'late_duplicate';
export type DataVersionStatus = 'building' | 'active' | 'failed';

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
  trigger: RunTrigger;
  trigger_label: string;
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
  // 版本绑定与校正信息
  is_current: boolean;
  data_version_id: number | null;
  data_version_no: number | null;
  data_version_code: string | null;
  data_fingerprint: string;
  data_fingerprint_short: string;
  config_snapshot: ConfigSnapshot;
  config_frozen: boolean;
  baseline_run_id: number | null;
  correction_meta: CorrectionMeta;
  is_correction: boolean;
  started_at: string | null;
  finished_at: string | null;
}

export interface ConfigSnapshot {
  funnel_code?: string;
  funnel_version?: number;
  steps: FunnelStep[];
  noise_events?: string[];
  window_days: number;
  cross_session?: boolean;
  engine_version?: string;
}

export interface StepDelta {
  index: number;
  key: string;
  event: string;
  label: string;
  baseline_users: number;
  corrected_users: number;
  delta: number;
  unchanged: boolean;
}

export interface CohortDelta {
  step_index: number;
  event: string;
  label: string;
  baseline_cohort_users: number;
  corrected_cohort_users: number;
  delta: number;
}

export interface AffectedUser {
  user_key: string;
  change_type: string;
  baseline_reached_step: number;
  corrected_reached_step: number;
  baseline_converted: boolean;
  corrected_converted: boolean;
  baseline_path: string;
  corrected_path: string;
  channel: string | null;
  device: string | null;
}

export interface CorrectionMeta {
  batch_code?: string;
  baseline_run_id?: number;
  baseline_run_code?: string;
  baseline_version_no?: number;
  generated_at?: string;
  ingested?: number;
  rejected_duplicate?: number;
  late?: number;
  affected_user_count?: number;
  affected_users?: AffectedUser[];
  step_deltas?: StepDelta[];
  cohort_deltas?: CohortDelta[];
  totals?: {
    baseline_entry: number;
    corrected_entry: number;
    baseline_converted: number;
    corrected_converted: number;
  };
}

export interface CorrectionEventInput {
  user_key: string;
  event_name: string;
  event_ts: string;
  seq?: number;
  session_id?: string;
  channel?: string;
  device?: string;
  source?: string;
}

export interface CorrectionRow {
  id: number;
  batch_code: string;
  user_key: string;
  event_name: string;
  event_label: string;
  event_ts: string;
  seq: number;
  session_id: string;
  channel: string;
  device: string;
  source: string;
  status: CorrectionRowStatus;
  kind: CorrectionKind;
  is_late: boolean;
  is_duplicate: boolean;
  duplicate_of_event_id: number | null;
  reason: string;
  detail: Record<string, unknown>;
}

export interface CorrectionBatch {
  batch_code: string;
  funnel_id: number;
  data_version_id: number | null;
  data_version_no: number | null;
  status: CorrectionStatus;
  total_rows: number;
  ingested: number;
  rejected_duplicate: number;
  late: number;
  correction_run_id: number | null;
  correction_run_code: string | null;
  rows: CorrectionRow[];
}

export interface DataVersion {
  id: number;
  code: string;
  funnel_id: number;
  version_no: number;
  status: DataVersionStatus;
  parent_version_id: number | null;
  baseline_run_id: number | null;
  correction_run_id: number | null;
  config_snapshot: ConfigSnapshot;
  window_days: number;
  fingerprint: string;
  fingerprint_short: string;
  event_count: number;
  ingested_count: number;
  rejected_duplicate_count: number;
  late_count: number;
  watermark: { max_event_ts: string | null; max_seq: number };
  note: string;
  created_by: string;
  created_at: string | null;
  activated_at: string | null;
}

export interface CorrectionApplyResult {
  batch: CorrectionBatch;
  data_version: DataVersion;
  baseline_run: FunnelRun;
  correction_run: FunnelRun;
  correction_meta: CorrectionMeta;
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
  is_current: boolean;
  superseded: boolean;
  data_version_id: number | null;
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
