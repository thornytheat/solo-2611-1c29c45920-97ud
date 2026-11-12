"""全局错误处理：统一 {code,message,detail} 响应。"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.constants import error_codes
from src.utils.errors import AppError

logger = logging.getLogger("funnelpath.errors")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = error_codes.NOT_FOUND if exc.status_code == 404 else error_codes.INTERNAL
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message": str(exc.detail), "detail": None},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        # pydantic v2 的 error["ctx"] 可能包含 ValueError 实例（自定义 validator），
        # 直接 json.dumps 会抛 TypeError 并退化成 500；这里只保留可序列化的定位信息。
        detail = []
        for error in exc.errors()[:4]:
            item = {
                "loc": [str(part) for part in error.get("loc", [])],
                "msg": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
            ctx = error.get("ctx")
            if isinstance(ctx, dict):
                item["ctx"] = {str(key): str(value) for key, value in ctx.items()}
            detail.append(item)
        return JSONResponse(
            status_code=422,
            content={
                "code": error_codes.VALIDATION,
                "message": "请求参数不合法",
                "detail": detail,
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"code": error_codes.INTERNAL, "message": "服务内部错误", "detail": None},
        )
