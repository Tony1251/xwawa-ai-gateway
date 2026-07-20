"""模型路由：根据请求特征选择最优 Provider + Model"""

from __future__ import annotations

from dataclasses import dataclass

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


# 路由偏好（可配置）
ROUTING_PRIORITY: list[str] = [
    "minimax",  # 优先 MiniMax（已配置）
    "doubao",  # 性价比
    "deepseek",
    "openai",  # 质量优先
    "anthropic",
    "midjourney",
]


@dataclass
class RoutingDecision:
    """路由决策结果"""

    provider: str
    model: str
    endpoint: str
    reason: str


class ModelRouter:
    """模型路由器"""

    def __init__(self):
        self.supported = SUPPORTED_MODELS
        self.priority = ROUTING_PRIORITY

    def route(self, model: str) -> RoutingDecision:
        """根据模型名路由到对应 Provider

        支持模糊匹配：
        - gpt-4* → openai
        - claude-* → anthropic
        - doubao-* → doubao
        """
        # 精确匹配
        if model in self.supported:
            provider = self.supported[model]
            return RoutingDecision(
                provider=provider,
                model=model,
                endpoint=self._get_endpoint(provider, model),
                reason="exact_match",
            )

        # 模糊匹配
        for prefix, provider in [
            ("gpt-", "openai"),
            ("claude-", "anthropic"),
            ("doubao-", "doubao"),
            ("deepseek-", "deepseek"),
            ("midjourney-", "midjourney"),
            ("MiniMax-", "minimax"),
        ]:
            if model.startswith(prefix):
                return RoutingDecision(
                    provider=provider,
                    model=model,
                    endpoint=self._get_endpoint(provider, model),
                    reason=f"prefix_match:{prefix}",
                )

        # 默认路由到 minimax（如果已配置）
        if settings.minimax_api_key:
            return RoutingDecision(
                provider="minimax",
                model=model,
                endpoint="/v1/chat/completions",
                reason="default_fallback",
            )
        if settings.openai_api_key:
            return RoutingDecision(
                provider="openai",
                model=model,
                endpoint="/v1/chat/completions",
                reason="default_fallback",
            )

        raise ProviderError(
            f"无法路由模型: {model}",
            details={"model": model, "supported": list(self.supported.keys())},
        )

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


# 全局单例
_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
