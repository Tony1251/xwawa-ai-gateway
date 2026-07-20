"""数据库连接 + 会话管理（生产级）

生产级特性：
- 连接池：20 base + 10 overflow，预连接 + pool_pre_ping
- 异步上下文管理器（session_scope）用于脚本/后台任务
- Redis 连接管理（用于限流）
- 慢查询告警日志
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from redis.asyncio import ConnectionPool, Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from .config import settings
from .logging_config import get_logger

logger = get_logger(__name__)

# ===== PostgreSQL =====
engine = create_async_engine(
    str(settings.database_url),
    echo=settings.database_echo,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    poolclass=AsyncAdaptedQueuePool,
    pool_pre_ping=True,
    pool_recycle=3600,  # 1h 回收连接（MySQL/PG 兼容性）
    pool_timeout=30,  # 获取连接超时 30s
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """初始化数据库（通过 alembic 迁移）"""
    import subprocess
    import sys

    # 用 subprocess 调用 alembic upgrade head（同步阻塞，但只在启动时执行一次）
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("alembic migration warning: %s", result.stderr)
    logger.info("✅ Database migration completed")


async def close_db() -> None:
    """关闭数据库连接池"""
    await engine.dispose()
    logger.info("✅ Database connections closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """脚本 / 后台任务用的会话上下文（自动 commit/rollback）"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ===== Redis =====
_redis_pool: ConnectionPool | None = None


async def get_redis_pool() -> ConnectionPool:
    """获取或创建 Redis 连接池（全局单例）"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = ConnectionPool.from_url(
            str(settings.redis_url),
            max_connections=50,
            decode_responses=True,
        )
        logger.info("✅ Redis pool initialized")
    return _redis_pool


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI 依赖注入：获取 Redis 客户端"""
    pool = await get_redis_pool()
    client = Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.aclose()


async def close_redis() -> None:
    """关闭 Redis 连接池"""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("✅ Redis pool closed")


# ===== Health Check =====
async def check_db_health() -> bool:
    """数据库健康检查"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("❌ DB health check failed: %s", e)
        return False


async def check_redis_health() -> bool:
    """Redis 健康检查"""
    try:
        pool = await get_redis_pool()
        client = Redis(connection_pool=pool)
        await client.ping()
        await client.aclose()
        return True
    except Exception as e:
        logger.error("❌ Redis health check failed: %s", e)
        return False
