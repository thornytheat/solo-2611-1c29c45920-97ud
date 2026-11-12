-- funnelpath 初始表结构（与 src/models/*.py 对应，供人工审阅）
-- 引擎自动建表：SQLAlchemy Base.metadata.create_all()

CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  email         VARCHAR(160) NOT NULL UNIQUE,
  password_hash VARCHAR(200) NOT NULL,
  display_name  VARCHAR(80)  NOT NULL,
  role          VARCHAR(24)  NOT NULL DEFAULT 'viewer',
  team          VARCHAR(80)  NOT NULL DEFAULT '增长产品组',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS funnel_defs (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  code          VARCHAR(64)  NOT NULL UNIQUE,
  name          VARCHAR(120) NOT NULL,
  description   TEXT         NOT NULL,
  line_no       VARCHAR(8)   NOT NULL DEFAULT 'L1',
  line_color    VARCHAR(32)  NOT NULL DEFAULT 'line-a',
  steps         JSON         NOT NULL,
  noise_events  JSON         NOT NULL,
  window_days   INT          NOT NULL DEFAULT 7,
  cross_session TINYINT(1)   NOT NULL DEFAULT 1,
  status        VARCHAR(24)  NOT NULL DEFAULT 'draft',
  version       INT          NOT NULL DEFAULT 1,
  owner_email   VARCHAR(160) NOT NULL DEFAULT '',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS event_logs (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  seed_key    VARCHAR(64)  NULL UNIQUE,
  user_key    VARCHAR(24)  NOT NULL,
  event_name  VARCHAR(48)  NOT NULL,
  event_ts    DATETIME     NOT NULL,
  seq         BIGINT       NOT NULL,
  session_id  VARCHAR(48)  NOT NULL DEFAULT '',
  channel     VARCHAR(24)  NOT NULL DEFAULT 'organic',
  device      VARCHAR(16)  NOT NULL DEFAULT 'ios',
  source      VARCHAR(24)  NOT NULL DEFAULT 'fixture',
  data_version_id INT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY ix_event_logs_user_ts (user_key, event_ts),
  KEY ix_event_logs_event (event_name),
  KEY ix_event_logs_channel (channel, device),
  KEY ix_event_logs_data_version_id (data_version_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 数据版本：每次运行绑定当时的漏斗配置快照与事件指纹，校正版本串成版本链
CREATE TABLE IF NOT EXISTS data_versions (
  id                       INT AUTO_INCREMENT PRIMARY KEY,
  code                     VARCHAR(64) NOT NULL UNIQUE,
  funnel_id                INT NOT NULL,
  version_no               INT NOT NULL DEFAULT 1,
  status                   VARCHAR(16) NOT NULL DEFAULT 'building',
  parent_version_id        INT NULL,
  baseline_run_id          INT NULL,
  correction_run_id        INT NULL,
  config_snapshot          JSON NOT NULL,
  window_days              INT NOT NULL DEFAULT 7,
  fingerprint              VARCHAR(64) NOT NULL DEFAULT '',
  event_count              INT NOT NULL DEFAULT 0,
  ingested_count           INT NOT NULL DEFAULT 0,
  rejected_duplicate_count INT NOT NULL DEFAULT 0,
  late_count               INT NOT NULL DEFAULT 0,
  watermark                JSON NOT NULL,
  note                     TEXT NOT NULL,
  created_by               VARCHAR(160) NOT NULL DEFAULT '',
  created_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
  activated_at             DATETIME NULL,
  CONSTRAINT fk_dv_funnel FOREIGN KEY (funnel_id) REFERENCES funnel_defs (id),
  CONSTRAINT fk_dv_parent FOREIGN KEY (parent_version_id) REFERENCES data_versions (id),
  CONSTRAINT fk_dv_baseline_run FOREIGN KEY (baseline_run_id) REFERENCES funnel_runs (id),
  CONSTRAINT fk_dv_correction_run FOREIGN KEY (correction_run_id) REFERENCES funnel_runs (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 事件补录批次逐行登记：迟到/重复判定、拒绝原因、自然指纹防重放
CREATE TABLE IF NOT EXISTS event_corrections (
  id                     INT AUTO_INCREMENT PRIMARY KEY,
  batch_code             VARCHAR(64) NOT NULL,
  funnel_id              INT NOT NULL,
  data_version_id        INT NULL,
  user_key               VARCHAR(24) NOT NULL,
  event_name             VARCHAR(48) NOT NULL,
  event_ts               DATETIME NOT NULL,
  seq                    INT NOT NULL DEFAULT 0,
  session_id             VARCHAR(48) NOT NULL DEFAULT '',
  channel                VARCHAR(24) NOT NULL DEFAULT 'organic',
  device                 VARCHAR(16) NOT NULL DEFAULT 'ios',
  source                 VARCHAR(24) NOT NULL DEFAULT 'backfill',
  status                 VARCHAR(24) NOT NULL DEFAULT 'staged',
  kind                   VARCHAR(24) NOT NULL DEFAULT 'normal',
  is_late                TINYINT(1) NOT NULL DEFAULT 0,
  is_duplicate           TINYINT(1) NOT NULL DEFAULT 0,
  duplicate_of_event_id  INT NULL,
  fingerprint            VARCHAR(64) NOT NULL UNIQUE,
  reason                 TEXT NOT NULL,
  detail                 JSON NOT NULL,
  created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY ix_event_correction_batch (batch_code),
  KEY ix_event_correction_funnel (funnel_id),
  CONSTRAINT fk_ec_funnel FOREIGN KEY (funnel_id) REFERENCES funnel_defs (id),
  CONSTRAINT fk_ec_version FOREIGN KEY (data_version_id) REFERENCES data_versions (id),
  CONSTRAINT fk_ec_duplicate_event FOREIGN KEY (duplicate_of_event_id) REFERENCES event_logs (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS funnel_runs (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  code           VARCHAR(64) NOT NULL UNIQUE,
  funnel_id      INT NOT NULL,
  `trigger`      VARCHAR(16) NOT NULL DEFAULT 'manual',
  status         VARCHAR(16) NOT NULL DEFAULT 'queued',
  window_days    INT NOT NULL DEFAULT 7,
  step_counts    JSON NOT NULL,
  duration_stats JSON NOT NULL,
  discard        JSON NOT NULL,
  segment_rows   JSON NOT NULL,
  entry_users    INT NOT NULL DEFAULT 0,
  converted_users INT NOT NULL DEFAULT 0,
  engine_version VARCHAR(16) NOT NULL DEFAULT '1.0.0',
  data_version_id INT NULL,
  baseline_run_id INT NULL,
  config_snapshot JSON NOT NULL,
  data_fingerprint VARCHAR(64) NOT NULL DEFAULT '',
  is_current     TINYINT(1) NOT NULL DEFAULT 1,
  correction_meta JSON NOT NULL,
  started_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  finished_at    DATETIME NULL,
  KEY ix_funnel_runs_data_version_id (data_version_id),
  KEY ix_funnel_runs_baseline_run_id (baseline_run_id),
  KEY ix_funnel_runs_is_current (is_current),
  CONSTRAINT fk_runs_funnel FOREIGN KEY (funnel_id) REFERENCES funnel_defs (id),
  CONSTRAINT fk_runs_data_version FOREIGN KEY (data_version_id) REFERENCES data_versions (id),
  CONSTRAINT fk_runs_baseline FOREIGN KEY (baseline_run_id) REFERENCES funnel_runs (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS session_paths (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  funnel_id       INT NOT NULL,
  run_id          INT NOT NULL,
  user_key        VARCHAR(24) NOT NULL,
  channel         VARCHAR(24) NOT NULL,
  device          VARCHAR(16) NOT NULL,
  path_key        VARCHAR(480) NOT NULL,
  path_json       JSON NOT NULL,
  depth           INT NOT NULL DEFAULT 0,
  drop_step_index INT NOT NULL DEFAULT 0,
  terminal_event  VARCHAR(48) NOT NULL DEFAULT '',
  is_converted    TINYINT(1) NOT NULL DEFAULT 0,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_session_path_user_run (funnel_id, run_id, user_key),
  CONSTRAINT fk_paths_funnel FOREIGN KEY (funnel_id) REFERENCES funnel_defs (id),
  CONSTRAINT fk_paths_run FOREIGN KEY (run_id) REFERENCES funnel_runs (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS drop_reports (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  code            VARCHAR(64) NOT NULL UNIQUE,
  funnel_id       INT NOT NULL,
  run_id          INT NOT NULL,
  title           VARCHAR(160) NOT NULL,
  drop_step_index INT NOT NULL DEFAULT 1,
  drop_step_label VARCHAR(60) NOT NULL DEFAULT '',
  cohort_users    INT NOT NULL DEFAULT 0,
  top_paths       JSON NOT NULL,
  choke_points    JSON NOT NULL,
  segment_gap     JSON NOT NULL,
  conclusion      TEXT NOT NULL,
  status          VARCHAR(16) NOT NULL DEFAULT 'draft',
  author_email    VARCHAR(160) NOT NULL DEFAULT '',
  reviewer_email  VARCHAR(160) NOT NULL DEFAULT '',
  version         INT NOT NULL DEFAULT 1,
  is_current      TINYINT(1) NOT NULL DEFAULT 1,
  data_version_id INT NULL,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY ix_drop_reports_is_current (is_current),
  CONSTRAINT fk_reports_funnel FOREIGN KEY (funnel_id) REFERENCES funnel_defs (id),
  CONSTRAINT fk_reports_run FOREIGN KEY (run_id) REFERENCES funnel_runs (id),
  CONSTRAINT fk_reports_version FOREIGN KEY (data_version_id) REFERENCES data_versions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  seed_key    VARCHAR(64) NULL UNIQUE,
  actor_email VARCHAR(160) NOT NULL DEFAULT 'anonymous',
  actor_role  VARCHAR(24)  NOT NULL DEFAULT 'anonymous',
  action      VARCHAR(64)  NOT NULL,
  entity      VARCHAR(48)  NOT NULL DEFAULT 'api',
  entity_id   VARCHAR(64)  NULL,
  layer       VARCHAR(16)  NOT NULL DEFAULT 'domain',
  detail      JSON         NOT NULL,
  ip          VARCHAR(64)  NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
