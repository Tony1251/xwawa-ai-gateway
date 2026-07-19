"""中间件：CORS / Request ID / 请求日志 / 性能监控"""
from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

from .config import settings
from .logging_config import get_logger, request_id_ctx, user_id_ctx

log = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Request ID 中间件

    - 接收客户端 X-Request-ID，没有就生成 UUID
    - 注入到上下文（结构化日志自动带上）
    - 响应头返回 X-Request-ID
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志 + 性能监控

    - 记录 method / path / status / duration
    - 慢请求告警（> 1s）
    - 不记录敏感路径（/metrics, /health）
    """

    SKIP_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000

            log.info(
                "Request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round(duration_ms, 2),
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:100],
            )

            # 慢请求告警
            if duration_ms > 1000:
                log.warning(
                    "SlowRequest",
                    method=request.method,
                    path=request.url.path,
                    duration_ms=round(duration_ms, 2),
                )

            return response
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            log.exception(
                "RequestFailed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error=str(e),
            )
            raise


def register_middlewares(app: FastAPI) -> None:
    """注册所有中间件"""
    # Parse app_cors_origins from string to list
    cors_origins = settings.app_cors_origins
    if isinstance(cors_origins, str):
        cors_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Request ID 必须在最外层
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    log.info(
        "✅ Middlewares registered",
        cors_origins=cors_origins,
    )


__all__ = [
    "RequestIDMiddleware",
    "RequestLoggingMiddleware",
    "register_middlewares",
]