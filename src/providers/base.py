"""AI Provider 抽象层 + 各 Provider 实现"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import settings
from ..exceptions import ProviderError


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

    @abstractmethod
    async def embeddings(
        self,
        model: str,
        input: str | list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        """向量嵌入"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """清理资源"""
        ...


class OpenAIProvider(BaseProvider):
    """OpenAI Provider"""

    name = "openai"

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError("OpenAI API Key 未配置", details={"provider": "openai"})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            **{k: v for k, v in kwargs.items() if v is not None},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            raise ProviderError(
                f"OpenAI API 错误: {resp.status_code}",
                details={"status": resp.status_code, "body": resp.text[:500]},
            )

        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return ProviderResponse(
            content=choice["message"]["content"],
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", model),
            raw=data,
        )

    async def embeddings(
        self,
        model: str,
        input: str | list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "input": input,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            raise ProviderError(f"OpenAI Embeddings 错误: {resp.status_code}")

        data = resp.json()
        return [item["embedding"] for item in data["data"]]


class AnthropicProvider(BaseProvider):
    """Anthropic Provider"""

    name = "anthropic"

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError("Anthropic API Key 未配置")

        # Anthropic 使用不同的消息格式
        system_msg = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        if system_msg:
            payload["system"] = system_msg
        if temperature := kwargs.get("temperature"):
            payload["temperature"] = temperature

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            raise ProviderError(
                f"Anthropic API 错误: {resp.status_code}",
                details={"body": resp.text[:500]},
            )

        data = resp.json()
        return ProviderResponse(
            content=data["content"][0]["text"],
            input_tokens=data.get("usage", {}).get("input_tokens", 0),
            output_tokens=data.get("usage", {}).get("output_tokens", 0),
            model=model,
            raw=data,
        )

    async def embeddings(
        self, model: str, input: str | list[str], **kwargs: Any
    ) -> list[list[float]]:
        raise ProviderError("Anthropic 不支持 embeddings")


class DoubaoProvider(BaseProvider):
    """字节豆包 Provider"""

    name = "doubao"

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError("豆包 API Key 未配置")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            **{k: v for k, v in kwargs.items() if v is not None},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            raise ProviderError(f"豆包 API 错误: {resp.status_code}")

        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return ProviderResponse(
            content=choice["message"]["content"],
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", model),
            raw=data,
        )

    async def embeddings(
        self,
        model: str,
        input: str | list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        # 豆包 embedding
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "input": input}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            raise ProviderError(f"豆包 Embeddings 错误: {resp.status_code}")

        data = resp.json()
        return [item["embedding"] for item in data["data"]]


class MidjourneyProvider(BaseProvider):
    """Midjourney 图片生成 Provider"""

    name = "midjourney"

    async def chat(
        self, model: str, messages: list[dict[str, str]], **kwargs: Any
    ) -> ProviderResponse:
        raise ProviderError("Midjourney 不支持 chat 接口，请使用 images 接口")

    async def images(
        self,
        model: str,
        prompt: str,
        *,
        size: str = "1024x1024",
        quality: str = "standard",
        **kwargs: Any,
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError("Midjourney API Key 未配置")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/images/generations",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            raise ProviderError(f"Midjourney API 错误: {resp.status_code}")

        data = resp.json()
        image_url = data["data"][0]["url"]

        return ProviderResponse(
            content=image_url,
            input_tokens=0,
            output_tokens=0,
            model=model,
            raw=data,
        )


class DeepseekProvider(BaseProvider):
    """DeepSeek Provider"""

    name = "deepseek"

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError("DeepSeek API Key 未配置")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            **{k: v for k, v in kwargs.items() if v is not None},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            raise ProviderError(f"DeepSeek API 错误: {resp.status_code}")

        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return ProviderResponse(
            content=choice["message"]["content"],
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", model),
            raw=data,
        )

    async def embeddings(
        self, model: str, input: str | list[str], **kwargs: Any
    ) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "input": input}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            raise ProviderError(f"DeepSeek Embeddings 错误: {resp.status_code}")

        data = resp.json()
        return [item["embedding"] for item in data["data"]]


# ===== Provider Factory =====

_provider_instances: dict[str, BaseProvider] = {}


def get_provider(name: str) -> BaseProvider:
    """获取 Provider 实例（全局单例）"""
    if name in _provider_instances:
        return _provider_instances[name]

    if name == "openai":
        inst = OpenAIProvider(settings.openai_api_key, settings.openai_base_url)
    elif name == "anthropic":
        inst = AnthropicProvider(settings.anthropic_api_key, settings.anthropic_base_url)
    elif name == "doubao":
        inst = DoubaoProvider(settings.doubao_api_key, settings.doubao_base_url)
    elif name == "midjourney":
        inst = MidjourneyProvider(settings.midjourney_api_key, settings.midjourney_base_url)
    elif name == "deepseek":
        inst = DeepseekProvider(settings.deepseek_api_key, settings.deepseek_base_url)
    else:
        raise ProviderError(f"未知 Provider: {name}", details={"provider": name})

    _provider_instances[name] = inst
    return inst
