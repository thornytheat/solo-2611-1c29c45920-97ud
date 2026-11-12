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
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY ix_event_logs_user_ts (user_key, event_ts),
  KEY ix_event_logs_event (event_name),
  KEY ix_event_logs_channel (channel, device)
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
  started_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  finished_at    DATETIME NULL,
  CONSTRAINT fk_runs_funnel FOREIGN KEY (funnel_id) REFERENCES funnel_defs (id)
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
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_reports_funnel FOREIGN KEY (funnel_id) REFERENCES funnel_defs (id),
  CONSTRAINT fk_reports_run FOREIGN KEY (run_id) REFERENCES funnel_runs (id)
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
