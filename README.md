# funnelpath · 多步漏斗转化与路径流失归因台

> 把「注册 → 试听 → 付费」这条链路摊成一张地铁线路图：谁在哪一站下车、下车前最后停在哪、哪个渠道的站台更挤，都能一次说清。

## 1. 真实场景

**模拟客户**：行知教育 · 增长产品组（9 人），主营 K12 素养课，月活 6 万。
**现有工作流**：把埋点表导 SQL 算「注册 → 试听 → 付费」，跨会话拼接常错；流失前用户干了什么只能靠猜，或者拉 10 个用户访谈。
**三个痛点**：

1. 跨会话 / 乱序上报的事件拼接口径每次都不一样，同一个漏斗两次跑出两个数；
2. 只看得到「流失了多少」，看不到「流失集中在哪一站、前一步卡在哪」；
3. 路径分支太多，无法归并成 Top 路径，也就没法排迭代优先级。

**上下游**：上游 = 埋点事件流（本地 fixture，含 5% 乱序、3% 重复上报、跨天会话）→ 本系统替代「手写 SQL + 访谈猜测」→ 下游 = 产品迭代排期与运营触达策略。

**一天的工作剧本（seed 与它一致）**：

| 时间 | 角色 | 动作 | 结果 |
|---|---|---|---|
| 09:20 | 林知远（admin） | 打开「漏斗定义」，把 L1 窗口从 7 天改成 7 天、确认站点顺序 | L1 v3 发布 |
| 09:40 | 苏澜（analyst） | 「试算人数」验证口径 → 「运行漏斗」 | 6,000 进入 / 3,180 试听完成 / 742 付费 |
| 10:05 | 苏澜 | 「路径分析」逐个流失队列看前缀树 | 试听完成队列 2,820 人，Top1 路径 31.4% |
| 10:30 | 苏澜 | 看卡点与分群差 | 试听未完成 58.2%；信息流 × iOS +12.6pp |
| 11:00 | 苏澜 | 「从最新运行生成报告」，写结论，导出 MD | 8 条路径的归因报告 |
| 14:10 | 林知远 | 复核 → 发布报告 | 报告状态 published |
| 16:00 | 周雨桐（viewer） | 只读看结果与报告 | 无写操作按钮，接口层 403 |

## 2. 主要功能（4 个可串成链路的业务模块）

1. **配置（漏斗定义）**：站点序列拖拽排序、窗口天数、跨会话开关、去噪白名单；admin 保存 / 发布，analyst 可试算。
2. **运行（采集→计算）**：analyst/admin 触发运行，后端按用户级状态机真算，落 `funnel_runs` 与 `session_paths`。
3. **解析（漏斗结果）**：步骤条 + 每步人数 / 转化率 / 步间耗时 P50·P90 + 分群（渠道 × 设备）对比。
4. **复核 / 归因（路径 + 报告）**：前缀树、Top-8 前置路径、卡点事件、分群差 → 生成 `drop_reports` → admin 复核发布。
5. **导出**：报告渲染 Markdown / CSV（8 条路径），同时落一份到 backend/worker 共享卷 `/app/var/exports`。

异步：worker（Celery）负责心跳、每 10 分钟的流失漂移巡检、以及按需「刷新路径缓存」（backend 投递任务 → worker 计算 → Redis 回写 → 前端轮询）。

## 3. 角色与权限

| 角色 | 账号 | 权限 |
|---|---|---|
| admin 增长负责人 | `admin@funnelpath.io` | 漏斗定义、发布、跑漏斗、写/复核/发布报告、导出、审计 |
| analyst 产品分析师 | `analyst@funnelpath.io` | 读定义、试算、跑漏斗、写归因草稿、导出、刷新缓存 |
| viewer 运营（只读） | `viewer@funnelpath.io` | 只读结果 / 路径 / 报告（**不能**跑漏斗、写报告、导出） |

密码统一 `Demo@2026`。低权角色调高权接口返回**真实 403**（后端 `require_permission` 拦截，不是前端藏按钮），审计日志会记录失败尝试。

## 4. 快速启动

```bash
cp .env.example .env
docker compose up -d --build          # 首次构建约 2-4 分钟
docker compose ps                     # 等 5 个服务全部 healthy
open http://localhost:18258
```

- 前端：<http://localhost:18258>
- 后端 API 文档：<http://localhost:19258/docs>
- 健康检查：`GET /api/health` → `{"status":"ok","db":true,"redis":true,...}`
- `SEED_DEMO=true` 时 backend 启动自动 seed 一次；也可手工：
  `docker compose exec backend python -m scripts.seed_demo`
- 离线自检（不连库，直接校验 fixture 与算法验收值）：
  `docker compose exec backend python -m scripts.verify_fixture`

## 5. 技术栈

| 层 | 选型 |
|---|---|
| frontend | React 18.3 + TypeScript 5.6 + Vite 5 + react-router 6，Nginx 托管 dist |
| backend | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 + PyMySQL |
| worker | Celery 5.4（Redis broker）+ celery beat |
| db | MySQL 8.0（utf8mb4） |
| cache/broker | Redis 7 |
| 鉴权 | PyJWT + passlib/bcrypt，JWT Bearer |
| 图表 | 全部 SVG / CSS 自绘（无图表 CDN） |

## 6. 目录

```
gb-585/
├── docker-compose.yml          # 5 服务：frontend/backend/worker/db/redis
├── .env / .env.example
├── backend/
│   ├── Dockerfile  requirements.txt
│   ├── migrations/0001_initial.sql      # 可读 DDL 存档（启动用 create_all）
│   ├── scripts/
│   │   ├── seed_demo.py        # 幂等 seed，打印 SEED_SUMMARY
│   │   ├── demo_config.py      # fixture 常量（渠道×设备×路径原型矩阵）
│   │   ├── fixture.py          # 确定性事件生成（乱序 seq / 重复上报）
│   │   ├── verify_fixture.py   # 离线验收自检
│   │   └── worker_healthcheck.sh
│   └── src/
│       ├── main.py  tasks.py
│       ├── config/       # settings / database / app / celery_app
│       ├── constants/    # enums（共享枚举）/ roles / limits / error_codes
│       ├── models/       # user / funnel / event / funnel_run / session_path / drop_report / audit
│       ├── schemas/      # pydantic 入参出参
│       ├── services/     # funnel_engine、path_engine、segment_service、run/report/export/cache…
│       ├── controllers/  # 业务编排 + 领域审计
│       ├── routes/       # /api/... 路由聚合
│       ├── middlewares/  # auth / rbac / audit_logger / rate_limit / error_handler
│       └── utils/        # security / stats / pathutil / timeutil / errors / logger
└── frontend/
    ├── Dockerfile  nginx.conf  vite.config.ts
    └── src/
        ├── api/          # client / auth / funnels / runs / reports / events
        ├── stores/       # authStore / uiStore
        ├── types/        # models.ts
        ├── constants/    # enums / roles / ui
        ├── components/   # common/{StationStrip,PathTree,SegmentTable,ChokeBars,EmptyState,StatusPill,Toasts} + layout/AppShell
        ├── hooks/        # useAsync / useCachePoll
        ├── pages/        # Login / FunnelDefs / FunnelResult / PathAnalysis / Attribution
        ├── router/       # index + guards
        ├── utils/        # format / errorMessage
        └── styles/       # tokens.css / global.css
```

## 7. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `funnelpath` | 容器名前缀 |
| `FRONTEND_PORT` | `18258` | 前端映射端口 |
| `BACKEND_PORT` | `19258` | 后端映射端口 |
| `DB_PORT` | `17758` | MySQL 映射端口 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_ROOT_PASSWORD` | `funnelpath` … | 数据库 |
| `JWT_SECRET` | 示例值 | JWT 签名密钥（生产必须替换） |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker + 限流 + 缓存 |
| `SEED_DEMO` | `true` | 启动时自动 seed |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_WRITE_PER_MINUTE` | 300 / 60 | Redis 固定窗口限流 |
| `APP_TIMEZONE_OFFSET_MINUTES` | 480 | 业务时区 UTC+8 |

## 8. Docker 说明

- 恰好 5 个服务，全部带 `healthcheck`：db（mysqladmin ping）、redis（redis-cli ping）、backend（`/api/health`）、worker（Redis 心跳 + Celery ping 双通道）、frontend（`wget --spider`）。
- 依赖链：db/redis `service_healthy` → backend → worker / frontend。
- 命名卷：`db_data`（MySQL）、`redis_data`（AOF）、`app_cache`（backend/worker 共享产物 `/app/var`）。
- 端口：`${FRONTEND_PORT:-18258}:80`、`${BACKEND_PORT:-19258}:8000`、`${DB_PORT:-17758}:3306`。
- 前端 Nginx：`location /api/ { proxy_pass http://backend:8000/; }` 剥掉 `/api` 前缀，SPA 回落 `try_files $uri $uri/ /index.html`；后端同时挂 `/api` 与根路径两套，直连 8000 也能用。
- 构建镜像只用本机已有 tag：`node:20-alpine`、`nginx:1.27-alpine`、`python:3.11-slim`、`mysql:8.0`、`redis:7-alpine`；npm 默认走 `registry.npmmirror.com`（可用 `--build-arg NPM_REGISTRY=` 覆盖），pip 走清华源。

## 9. 算法口径（后端真算，前端只展示）

**算法 1 · 用户级漏斗状态机**（`src/services/funnel_engine.py`）

1. 按 `user_key` 分组，事件按 `(event_ts, seq)` 稳定排序：`seq` 是入库先后，乱序上报靠事件时间纠正，同秒再退化成 `seq`；
2. 同事件同秒的重复上报只计一次（`duplicates_collapsed`）；
3. 严格顺序推进：只认当前步骤对应事件，跳步不算；
4. 窗口从首步命中时刻起算，超窗即中止并计 `expired`；
5. 输出每步人数、较上一步 / 较首步转化率、步间耗时 P50/P90（所有跨步样本合并 + 分区间各一份）、丢弃原因计数。

**算法 2 · 路径压缩与流失归因**（`src/services/path_engine.py` + `pathutil.py` + `segment_service.py`）

1. 会话内事件按漏斗白名单去噪；连续同类合并；会话结束标记只保留末尾一次；深度截断 ≤6；
2. 以「未到达某一步」的用户队列建前缀树（深度 ≤6），节点计数 = 经过该前缀的人数；
3. Top-K（K=8）前置路径按人数降序，`share_pct` = 该路径人数 / 该队列人数；
4. 卡点事件 = 队列末事件（去掉退出标记）分布 —— 所以同一个卡点可以由多条路径共同贡献；
5. 分群（渠道 × 设备）对比：`gap_pp = 该分群流失率 − 整体流失率`（百分点，1 位小数），另给渠道汇总。

**seed 验收值（由 fixture 构造，`scripts/verify_fixture.py` 可离线复算）**

| 指标 | 值 |
|---|---|
| L1 进入 / 试听完成 / 付费 | 6,000 → 3,180（53.0%）→ 742（23.3% 占试听） |
| 步间 P50 | 1.80 天（P90 3.08 天） |
| 试听完成队列 | 2,820 人 |
| Top1 前置路径 | `注册 → 浏览课程 → 试听页停留<30s → 退出` · 31.4% |
| 卡点事件 | 试听未完成 58.2%（1,641 人，跨 4 条路径） |
| 最大分群差 | 信息流 × iOS 59.6% vs 整体 47.0% = **+12.6pp** |
| 报告路径数 | 8 条（试听队列 7 条 + 付费队列 4 条取前 8） |

## 10. 共享枚举出现位置

**后端 `backend/src/constants/enums.py`**：`Role` / `Channel` / `Device` / `FunnelStatus` / `RunStatus` / `RunTrigger` / `DropReason` / `ReportStatus` / `ExportFormat` / `CacheJobStatus` + `EVENT_LABELS` / `CHANNEL_LABELS` / `DEVICE_LABELS` / `ROLE_LABELS` / `TERMINAL_EVENTS`。
引用点：`models/*.py`（列默认值）、`constants/roles.py`（权限矩阵）、`services/funnel_engine.py`、`services/path_engine.py`、`services/segment_service.py`、`services/run_service.py`、`services/report_service.py`、`services/export_service.py`、`controllers/*`、`routes/*`、`scripts/demo_config.py`、`scripts/seed_demo.py`。

**前端 `frontend/src/constants/enums.ts`**：同名枚举与标签表 `CHANNEL_LABELS` / `DEVICE_LABELS` / `FUNNEL_STATUS_LABELS` / `RUN_STATUS_LABELS` / `REPORT_STATUS_LABELS` / `EVENT_LABELS` / `TERMINAL_EVENTS` / `LINE_COLORS`。
引用点：`types/models.ts`、`constants/roles.ts`、`constants/ui.ts`、`components/common/StationStrip.tsx`、`PathTree.tsx`、`SegmentTable.tsx`、`ChokeBars.tsx`、`StatusPill.tsx`、`pages/{FunnelDefs,FunnelResult,PathAnalysis,Attribution,Login}.tsx`、`utils/format.ts`。

角色权限枚举两份：`backend/src/constants/roles.py` ↔ `frontend/src/constants/roles.ts`（`ROLE_LABELS` + `PERMISSIONS` 必须同步）。

## 11. License

MIT（演示项目，seed 数据为构造的模拟数据，不含真实用户信息）。
