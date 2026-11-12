"""领域异常：由全局错误处理中间件翻译成 {code,message,detail}。"""
from __future__ import annotations

from src.constants import error_codes


class AppError(Exception):
    def __init__(self, code: str, status_code: int = 400, detail: object | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.detail = detail
        self.message = error_codes.MESSAGES.get(code, "请求处理失败")


def not_found(detail: object | None = None) -> AppError:
    return AppError(error_codes.NOT_FOUND, 404, detail)


def forbidden(detail: object | None = None) -> AppError:
    return AppError(error_codes.FORBIDDEN, 403, detail)


def conflict(detail: object | None = None) -> AppError:
    return AppError(error_codes.CONFLICT, 409, detail)


def validation(detail: object | None = None) -> AppError:
    return AppError(error_codes.VALIDATION, 422, detail)
