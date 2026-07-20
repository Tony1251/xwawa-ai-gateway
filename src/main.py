"""FastAPI 应用入口（生产级）

按以下顺序构建：
1. 日志配置（最早）
2. Sentry 集成（可选）
3. FastAPI 实例 + lifespan
4. Prometheus 指标
5. 中间件（CORS / Request ID / Logging）
6. 异常处理器
7. 路由
8. 启动校验
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import sentry_sdk
import uvicorn
from fastapi import FastAPI
from prometheus_client import make_asgi_app

from .api.v1 import a2a, admin, auth, chat, payment, wallet, ws
from .config import settings, validate_production_safety
from .db import init_db
from .exceptions import register_exception_handlers
from .logging_config import configure_logging, get_logger
from .middlewares import register_middlewares

# ===== 1. 日志 =====
configure_logging(level=settings.log_level, fmt=settings.log_format)
log = get_logger(__name__)

# ===== 2. Sentry =====
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        integrations=[],
    )
    log.info("✅ Sentry initialized", environment=settings.sentry_environment)


# ===== 3. Lifespan =====


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    log.info("🚀 Application starting", env=settings.app_env, version=app.version)

    # 启动
    if not settings.is_test:
        await init_db()
        log.info("✅ Database initialized")

    validate_production_safety()

    yield

    # 关闭
    from .db import close_db, close_redis

    await close_db()
    await close_redis()
    log.info("👋 Application shutdown complete")


# ===== 4. FastAPI 实例 =====
app = FastAPI(
    title=settings.app_name,
    description="AI Agent 信用支付网关 - 让 AI 帮人类管钱、调 API、按用量扣费",
    version="0.2.0",
    docs_url="/docs" if not settings.is_production else None,  # 生产关闭 Swagger UI
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

# ===== 5. Prometheus 指标 =====
if settings.prometheus_enabled:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    log.info("✅ Prometheus metrics mounted at /metrics")

# ===== 6. 中间件 =====
register_middlewares(app)

# ===== 7. 异常处理 =====
register_exception_handlers(app)

# ===== 8. 路由 =====
app.include_router(chat.router, prefix="/v1", tags=["chat"])
app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(wallet.router, prefix="/v1/wallet", tags=["wallet"])
app.include_router(ws.router, prefix="/v1", tags=["websocket"])
app.include_router(a2a.router, prefix="/v1/a2a", tags=["a2a"])
app.include_router(payment.router, prefix="/v1/payment", tags=["payment"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


# ===== 9. 健康检查 =====


@app.get("/", tags=["meta"])
async def root():
    """根路径"""
    return {
        "service": settings.app_name,
        "version": app.version,
        "env": settings.app_env,
        "docs": "/docs" if not settings.is_production else "disabled",
    }


@app.get("/health", tags=["meta"])
async def health():
    """健康检查（用于 k8s liveness probe）"""
    return {"status": "ok", "version": app.version}


@app.get("/health/ready", tags=["meta"])
async def health_ready():
    """就绪检查（用于 k8s readiness probe）"""
    # TODO: 检查数据库连接、Redis 连接
    return {"status": "ready"}


# ===== 10. 启动 =====


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
        workers=1 if settings.is_development else 4,
        access_log=False,  # 用 RequestLoggingMiddleware 替代
    )
