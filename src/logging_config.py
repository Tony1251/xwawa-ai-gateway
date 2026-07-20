"""结构化日志配置

生产级特性：
- JSON 输出（适合 Loki / ELK 聚合）
- 控制台输出（开发友好）
- 自动注入 request_id / user_id
- 支持 Sentry 集成（可选）
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, Processor

# Context variables for request-scoped data
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[int | None] = ContextVar("user_id", default=None)


def _add_context(_, __, event_dict: EventDict) -> EventDict:
    """注入 request_id / user_id 到每条日志"""
    request_id = request_id_ctx.get()
    user_id = user_id_ctx.get()
    if request_id:
        event_dict["request_id"] = request_id
    if user_id:
        event_dict["user_id"] = user_id
    return event_dict


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """配置全局日志

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        fmt: 输出格式 (json/console)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors (note: add_logger_name removed - requires stdlib logger with .name attr)
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        _add_context,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.format_exc_info,
    ]

    if fmt == "json":
        # Production: JSON
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: pretty console
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging for uvicorn/SQLAlchemy
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    # Quiet noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """获取 logger"""
    return structlog.get_logger(name)


__all__ = [
    "configure_logging",
    "get_logger",
    "request_id_ctx",
    "user_id_ctx",
]
