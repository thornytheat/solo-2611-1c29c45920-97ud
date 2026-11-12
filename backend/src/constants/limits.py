"""限流与分页等运行时上限。"""
RATE_WINDOW_SECONDS = 60
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200
MAX_STEPS = 8
MIN_STEPS = 2
MAX_EXPORT_PATHS = 40
RATE_SKIP_PATHS = frozenset({"/api/health", "/health"})
# 路由同时挂在 /api 与根路径（Nginx 反代会剥掉 /api）；限流按「归一化后的
# 根路径」匹配，否则经前端 18258 进来的写请求会全部落进默认桶，写限流形同虚设。
WRITE_BUCKET_PREFIXES = (
    "/funnels",
    "/reports",
    "/exports",
    "/runs",
)
