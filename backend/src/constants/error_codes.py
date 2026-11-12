"""错误码常量：与前端 utils/errorMessage.ts 的文案映射配合。"""
AUTH_MISSING = "AUTH_MISSING"
AUTH_INVALID = "AUTH_INVALID"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
VALIDATION = "VALIDATION"
RATE_LIMITED = "RATE_LIMITED"
CONFLICT = "CONFLICT"
INTERNAL = "INTERNAL"
SEED_FAILED = "SEED_FAILED"

MESSAGES: dict[str, str] = {
    AUTH_MISSING: "请先登录",
    AUTH_INVALID: "登录信息已失效，请重新登录",
    FORBIDDEN: "当前角色没有该操作的权限",
    NOT_FOUND: "对象不存在或已被归档",
    VALIDATION: "请求参数不合法",
    RATE_LIMITED: "请求过于频繁，请稍后再试",
    CONFLICT: "对象状态冲突，请刷新后重试",
    INTERNAL: "服务内部错误",
}
