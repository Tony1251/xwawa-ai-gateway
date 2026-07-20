"""自定义异常类 + 全局异常处理中间件

生产级特性：
- 统一的错误响应格式（code / message / request_id / details）
- 区分 4xx 客户端错误 vs 5xx 服务端错误
- 自动记录异常日志（含堆栈）
- 不泄漏敏感信息（数据库密码、API key 等）
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging_config import get_logger, request_id_ctx

log = get_logger(__name__)


# ===== Business Exceptions =====


class BusinessError(Exception):
    """业务异常基类"""

    status_code: int = 400
    code: str = "BUSINESS_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class InsufficientBalanceError(BusinessError):
    """余额不足"""

    status_code = 402
    code = "INSUFFICIENT_BALANCE"


class RiskLimitExceededError(BusinessError):
    """风控限额超限"""

    status_code = 429
    code = "RISK_LIMIT_EXCEEDED"


class ProviderError(BusinessError):
    """上游 Provider 错误"""

    status_code = 502
    code = "PROVIDER_ERROR"


class AuthenticationError(BusinessError):
    """认证失败"""

    status_code = 401
    code = "AUTHENTICATION_FAILED"


class AuthorizationError(BusinessError):
    """权限不足"""

    status_code = 403
    code = "AUTHORIZATION_FAILED"


class ResourceNotFoundError(BusinessError):
    """资源不存在"""

    status_code = 404
    code = "RESOURCE_NOT_FOUND"


class RateLimitError(BusinessError):
    """限流"""

    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"


# ===== Error Response Schema =====


def build_error_response(
    *,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """构造统一错误响应"""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id or request_id_ctx.get(),
        }
    }


# ===== Exception Handlers =====


async def business_exception_handler(request: Request, exc: BusinessError) -> JSONResponse:
    """业务异常处理"""
    log.warning(
        "BusinessException",
        code=exc.code,
        message=exc.message,
        status=exc.status_code,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        ),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """HTTP 异常处理"""
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    log.warning(
        "HTTPException",
        code=code,
        status=exc.status_code,
        message=str(exc.detail),
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            code=code,
            message=str(exc.detail),
            status_code=exc.status_code,
        ),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """请求验证异常处理"""
    errors = exc.errors()
    log.warning(
        "ValidationError",
        path=request.url.path,
        errors=errors[:5],  # 只记录前 5 条
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_error_response(
            code="VALIDATION_ERROR",
            message="请求参数验证失败",
            status_code=422,
            details={"errors": errors},
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未处理异常（500）"""
    log.exception(
        "UnhandledException",
        exc_type=type(exc).__name__,
        message=str(exc),
        path=request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=build_error_response(
            code="INTERNAL_ERROR",
            message="服务器内部错误",
            status_code=500,
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用"""
    app.add_exception_handler(BusinessError, business_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    log.info("✅ Exception handlers registered")


__all__ = [
    "BusinessError",
    "InsufficientBalanceError",
    "RiskLimitExceededError",
    "ProviderError",
    "AuthenticationError",
    "AuthorizationError",
    "ResourceNotFoundError",
    "RateLimitError",
    "register_exception_handlers",
]
