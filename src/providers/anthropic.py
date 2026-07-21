"""Anthropic Provider"""

from __future__ import annotations

from typing import Any

import httpx

from .base import BaseProvider, ProviderResponse
from ..exceptions import ProviderError


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
