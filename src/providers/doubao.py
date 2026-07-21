"""字节豆包 Provider"""

from __future__ import annotations

from typing import Any

import httpx

from .base import BaseProvider, ProviderResponse
from ..exceptions import ProviderError


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
