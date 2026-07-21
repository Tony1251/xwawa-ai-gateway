"""Provider 抽象基类 + Factory"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderResponse:
    """Provider 标准响应"""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    raw: dict[str, Any]


class BaseProvider(ABC):
    """Provider 抽象基类"""

    name: str = "base"

    def __init__(self, api_key: str, base_url: str, timeout: float = 60.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """聊天补全"""
        ...

    async def embeddings(
        self,
        model: str,
        input: str | list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        """向量嵌入（默认不支持）"""
        raise NotImplementedError(f"{self.name} does not support embeddings")

    async def close(self) -> None:
        """清理资源（默认无操作）"""
        pass


# ===== Provider Factory =====

_provider_instances: dict[str, BaseProvider] = {}


def get_provider(name: str) -> BaseProvider:
    """获取 Provider 实例（全局单例）"""
    if name in _provider_instances:
        return _provider_instances[name]

    # 动态导入避免循环依赖
    if name == "openai":
        from .openai import OpenAIProvider
        from ..config import settings

        inst = OpenAIProvider(settings.openai_api_key, settings.openai_base_url)
    elif name == "anthropic":
        from .anthropic import AnthropicProvider
        from ..config import settings

        inst = AnthropicProvider(settings.anthropic_api_key, settings.anthropic_base_url)
    elif name == "doubao":
        from .doubao import DoubaoProvider
        from ..config import settings

        inst = DoubaoProvider(settings.doubao_api_key, settings.doubao_base_url)
    elif name == "midjourney":
        from .midjourney import MidjourneyProvider
        from ..config import settings

        inst = MidjourneyProvider(settings.midjourney_api_key, settings.midjourney_base_url)
    elif name == "deepseek":
        from .deepseek import DeepseekProvider
        from ..config import settings

        inst = DeepseekProvider(settings.deepseek_api_key, settings.deepseek_base_url)
    elif name == "minimax":
        from .minimax import MiniMaxProvider
        from ..config import settings

        inst = MiniMaxProvider(settings.minimax_api_key, settings.minimax_base_url)
    else:
        from ..exceptions import ProviderError

        raise ProviderError(f"未知 Provider: {name}", details={"provider": name})

    _provider_instances[name] = inst
    return inst
