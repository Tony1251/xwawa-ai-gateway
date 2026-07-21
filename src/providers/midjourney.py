"""Midjourney 图片生成 Provider"""

from __future__ import annotations

from typing import Any

import httpx

from .base import BaseProvider, ProviderResponse
from ..exceptions import ProviderError


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
