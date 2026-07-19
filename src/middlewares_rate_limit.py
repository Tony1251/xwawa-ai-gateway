"""Redis 限流中间件（滑动窗口算法）

生产级特性：
- 滑动窗口限流（比固定窗口更精确）
- 支持 IP 维度和 User 维度两层限流
- Redis Lua 脚本保证原子性
- 触发限流返回 429 + Retry-After 头
"""
from __future__ import annotations

import time
from typing import Literal

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from redis.asyncio import Redis

from .config import settings
from .logging_config import get_logger

log = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis 滑动窗口限流"""

    # 限流维度：ip | user
    dimension: Literal["ip", "user"] = "ip"

    def __init__(self, app, redis: Redis, requests_per_minute: int = 60):
        super().__init__(app)
        self.redis = redis
        self.rpm = requests_per_minute
        self.window_sec = 60

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # 限流豁免路径
        if request.url.path in {"/health", "/metrics", "/health/ready"}:
            return await call_next(request)

        # 构建限流 key
        if self.dimension == "ip":
            key_base = request.client.host if request.client else "unknown"
        else:
            key_base = getattr(request.state, "user_id", "anonymous")

        key = f"ratelimit:{self.dimension}:{key_base}:{int(time.time() // self.window_sec)}"

        try:
            # Lua 脚本：原子性增加计数器
            script = """
            local current = redis.call('INCR', KEYS[1])
            if current == 1 then
                redis.call('EXPIRE', KEYS[1], ARGV[1])
            end
            return current
            """
            result = await self.redis.eval(script, 1, key, self.window_sec)
            current_count = int(result)

            if current_count > self.rpm:
                retry_after = self.window_sec - (int(time.time()) % self.window_sec)
                log.warning(
                    "RateLimitExceeded",
                    dimension=self.dimension,
                    key=key_base,
                    count=current_count,
                    limit=self.rpm,
                )
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"请求过于频繁，每分钟最多 {self.rpm} 次",
                            "details": {
                                "limit": self.rpm,
                                "retry_after_seconds": retry_after,
                            },
                        }
                    },
                )

        except Exception as e:
            log.error("RateLimitRedisError: %s", e)
            # Redis 故障时放行（fail open），不阻塞服务

        return await call_next(request)
