"""模型路由：根据请求特征 + 成本 + 健康状态选择最优 Provider + Model"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..config import settings
from ..exceptions import ProviderError

# ===== 路由规则 =====

# 支持的模型列表
SUPPORTED_MODELS: dict[str, str] = {
    # OpenAI
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "gpt-4-turbo": "openai",
    "gpt-3.5-turbo": "openai",
    # Anthropic
    "claude-3-5-sonnet": "anthropic",
    "claude-3-opus": "anthropic",
    "claude-3-sonnet": "anthropic",
    "claude-3-haiku": "anthropic",
    # 豆包
    "doubao-pro-32k": "doubao",
    "doubao-pro-128k": "doubao",
    "doubao-lite-32k": "doubao",
    # DeepSeek
    "deepseek-chat": "deepseek",
    "deepseek-coder": "deepseek",
    # Midjourney（图片）
    "midjourney-v6": "midjourney",
    # MiniMax
    "MiniMax-Text-01": "minimax",
}


# 成本矩阵（$/1M tokens），用于智能路由
COST_MATRIX: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4o": {"input": 2.5, "output": 10.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.6},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    },
    "anthropic": {
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
    },
    "doubao": {
        "doubao-pro-32k": {"input": 0.8, "output": 2.0},
        "doubao-pro-128k": {"input": 1.0, "output": 4.0},
        "doubao-lite-32k": {"input": 0.3, "output": 0.6},
    },
    "deepseek": {
        "deepseek-chat": {"input": 0.1, "output": 0.3},
        "deepseek-coder": {"input": 0.1, "output": 0.3},
    },
    "minimax": {
        "MiniMax-Text-01": {"input": 0.01, "output": 0.10},
    },
    "midjourney": {
        "midjourney-v6": {"input": 0.0, "output": 4.0},  # 按张计费
    },
}


# 路由偏好（可配置）
ROUTING_PRIORITY: list[str] = [
    "minimax",  # 优先 MiniMax（已配置）
    "doubao",  # 性价比
    "deepseek",
    "openai",  # 质量优先
    "anthropic",
    "midjourney",
]


# ===== 数据结构 =====


class ProviderHealth(Enum):
    """Provider 健康状态"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit_open"
    UNKNOWN = "unknown"


@dataclass
class RoutingDecision:
    """路由决策结果"""

    provider: str
    model: str
    endpoint: str
    reason: str
    estimated_cost: float = 0.0
    provider_health: str = "unknown"


@dataclass
class ProviderStats:
    """Provider 统计信息"""

    total_calls: int = 0
    success_calls: int = 0
    failure_calls: int = 0
    total_latency: float = 0.0  # ms
    last_failure: float = 0.0  # timestamp
    circuit_open_since: float | None = None
    recent_latencies: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    recent_outcomes: deque[bool] = field(default_factory=lambda: deque(maxlen=10))


# ===== 健康追踪器 =====


class ProviderHealthTracker:
    """Provider 健康追踪 + 熔断器"""

    _stats: dict[str, ProviderStats] = {}
    _lock = threading.Lock()

    # 熔断配置
    FAILURE_RATE_THRESHOLD = 0.5  # 50% 失败率触发熔断
    CIRCUIT_BREAK_WINDOW = 60  # 熔断窗口秒数
    MIN_CALLS_FOR_JUDGMENT = 10  # 最少调用次数才判断

    @classmethod
    def get_stats(cls, provider: str) -> ProviderStats:
        with cls._lock:
            if provider not in cls._stats:
                cls._stats[provider] = ProviderStats()
            return cls._stats[provider]

    @classmethod
    def record_success(cls, provider: str, latency_ms: float) -> None:
        stats = cls.get_stats(provider)
        with cls._lock:
            stats.total_calls += 1
            stats.success_calls += 1
            stats.total_latency += latency_ms
            stats.recent_latencies.append(latency_ms)
            stats.recent_outcomes.append(True)

    @classmethod
    def record_failure(cls, provider: str, latency_ms: float = 0) -> None:
        stats = cls.get_stats(provider)
        with cls._lock:
            stats.total_calls += 1
            stats.failure_calls += 1
            stats.last_failure = time.time()
            if latency_ms > 0:
                stats.total_latency += latency_ms
                stats.recent_latencies.append(latency_ms)
            stats.recent_outcomes.append(False)

            # 检查是否需要熔断
            cls._check_circuit_breaker(provider, stats)

    @classmethod
    def _check_circuit_breaker(cls, provider: str, stats: ProviderStats) -> None:
        """检查是否需要熔断"""
        recent = list(stats.recent_outcomes)
        if len(recent) < cls.MIN_CALLS_FOR_JUDGMENT:
            return

        failures = sum(1 for x in recent if not x)
        failure_rate = failures / len(recent)

        if failure_rate >= cls.FAILURE_RATE_THRESHOLD:
            stats.circuit_open_since = time.time()

    @classmethod
    def get_health(cls, provider: str) -> ProviderHealth:
        stats = cls.get_stats(provider)
        with cls._lock:
            if stats.circuit_open_since is not None:
                # 检查熔断是否超时
                if time.time() - stats.circuit_open_since > cls.CIRCUIT_BREAK_WINDOW:
                    stats.circuit_open_since = None  # 尝试恢复
                    return ProviderHealth.DEGRADED
                return ProviderHealth.CIRCUIT_OPEN

            if stats.total_calls < cls.MIN_CALLS_FOR_JUDGMENT:
                return ProviderHealth.UNKNOWN

            recent = list(stats.recent_outcomes)
            failures = sum(1 for x in recent if not x)
            failure_rate = failures / len(recent)

            if failure_rate >= cls.FAILURE_RATE_THRESHOLD:
                return ProviderHealth.DEGRADED

            return ProviderHealth.HEALTHY

    @classmethod
    def get_healthy_providers(cls, providers: list[str]) -> list[str]:
        """返回健康的 provider 列表"""
        return [
            p for p in providers
            if cls.get_health(p) in (ProviderHealth.HEALTHY, ProviderHealth.UNKNOWN)
        ]

    @classmethod
    def get_avg_latency(cls, provider: str) -> float:
        stats = cls.get_stats(provider)
        with cls._lock:
            if not stats.recent_latencies:
                return 0.0
            return sum(stats.recent_latencies) / len(stats.recent_latencies)


# ===== 模型路由器 =====


class ModelRouter:
    """模型路由器，支持成本路由 + 健康检查"""

    def __init__(self):
        self.supported = SUPPORTED_MODELS
        self.priority = ROUTING_PRIORITY
        self.health_tracker = ProviderHealthTracker

    def route(self, model: str) -> RoutingDecision:
        """根据模型名路由到对应 Provider（默认走成本最优）"""
        # 获取成本最优路由
        return self.get_cheapest_route(model)

    def get_cheapest_route(self, model: str) -> RoutingDecision:
        """获取最低成本路由"""
        provider = self._find_cheapest_provider(model)
        health = self.health_tracker.get_health(provider)

        # 获取成本估算
        estimated_cost = self._estimate_cost(model, provider)

        return RoutingDecision(
            provider=provider,
            model=model,
            endpoint=self._get_endpoint(provider, model),
            reason="cheapest",
            estimated_cost=estimated_cost,
            provider_health=health.value,
        )

    def get_fastest_route(self, model: str) -> RoutingDecision:
        """获取最低延迟路由"""
        provider = self._find_fastest_provider(model)
        health = self.health_tracker.get_health(provider)
        estimated_cost = self._estimate_cost(model, provider)

        return RoutingDecision(
            provider=provider,
            model=model,
            endpoint=self._get_endpoint(provider, model),
            reason="fastest",
            estimated_cost=estimated_cost,
            provider_health=health.value,
        )

    def _find_cheapest_provider(self, model: str) -> str:
        """找到支持该模型的最便宜 provider"""
        candidates = []

        for p, models in COST_MATRIX.items():
            if model in models:
                cost = models[model]
                total = cost.get("input", 0) + cost.get("output", 0)
                candidates.append((p, total))

        if candidates:
            # 按成本排序
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]

        # 兜底：使用 SUPPORTED_MODELS
        if model in self.supported:
            return self.supported[model]

        # 模糊匹配
        for prefix, prov in [
            ("gpt-", "openai"),
            ("claude-", "anthropic"),
            ("doubao-", "doubao"),
            ("deepseek-", "deepseek"),
            ("midjourney-", "midjourney"),
            ("MiniMax-", "minimax"),
        ]:
            if model.startswith(prefix):
                return prov

        # 默认兜底
        if settings.minimax_api_key:
            return "minimax"
        if settings.openai_api_key:
            return "openai"

        raise ProviderError(
            f"无法路由模型: {model}",
            details={"model": model, "supported": list(self.supported.keys())},
        )

    def _find_fastest_provider(self, model: str) -> str:
        """找到支持该模型中延迟最低的 provider"""
        candidates = []

        for p in self.supported.values():
            if p == self._find_cheapest_provider(model):
                continue  # 跳过已选的
            if model in COST_MATRIX.get(p, {}):
                candidates.append(p)

        # 加入最低成本选项
        cheapest = self._find_cheapest_provider(model)
        if cheapest not in candidates:
            candidates.insert(0, cheapest)

        # 按延迟排序
        candidates_with_latency = []
        for p in candidates:
            avg_lat = self.health_tracker.get_avg_latency(p)
            # 未知延迟的排在最后
            candidates_with_latency.append((p, avg_lat if avg_lat > 0 else float("inf")))

        candidates_with_latency.sort(key=lambda x: x[1])
        return candidates_with_latency[0][0]

    def _estimate_cost(self, model: str, provider: str) -> float:
        """估算单次调用成本（基于平均输入1000 tokens，输出500 tokens）"""
        if provider in COST_MATRIX and model in COST_MATRIX[provider]:
            cost = COST_MATRIX[provider][model]
            return (cost.get("input", 0) * 1 + cost.get("output", 0) * 0.5) / 1_000_000
        return 0.0

    def _get_endpoint(self, provider: str, model: str) -> str:
        """获取 Provider 的 API 端点"""
        if provider == "midjourney":
            return "/v1/images/generations"
        return "/v1/chat/completions"

    def list_models(self, provider: str | None = None) -> dict[str, str]:
        """列出支持的模型，可按 provider 过滤"""
        if provider:
            return {m: p for m, p in self.supported.items() if p == provider}
        return dict(self.supported)

    def list_providers(self) -> list[str]:
        """列出已配置的 Provider"""
        return settings.configured_providers

    def get_provider_health(self, provider: str) -> ProviderHealth:
        """获取 Provider 健康状态"""
        return self.health_tracker.get_health(provider)


# 全局单例
_router: ModelRouter | None = None
_router_lock = threading.Lock()


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                _router = ModelRouter()
    return _router
