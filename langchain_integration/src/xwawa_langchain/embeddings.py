"""Xwawa Embeddings - LangChain Embeddings compatible"""

from __future__ import annotations

import os
from typing import Any

import httpx
from langchain_core.embeddings import Embeddings
from pydantic import Field, SecretStr


class XwawaEmbeddings(Embeddings):
    api_key: SecretStr = Field(default_factory=lambda: os.getenv("XWAWA_API_KEY", ""))
    base_url: str = Field(default_factory=lambda: os.getenv("XWAWA_BASE_URL", "https://api.xwawa.ai/v1"))
    model: str = Field(default="text-embedding-3-small")
    timeout: float = Field(default=30.0)

    @property
    def _llm_type(self) -> str:
        return "xwawa-embeddings"

    def _create_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
        )

    def embed_query(self, text: str) -> list[float]:
        return self._run_sync(self._aembed_query(text))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._run_sync(self._aembed_documents(texts))

    async def _aembed_query(self, text: str) -> list[float]:
        results = await self._aembed_documents([text])
        return results[0]

    async def _aembed_documents(self, texts: list[str]) -> list[list[float]]:
        client = self._create_client()
        try:
            response = await client.post("/embeddings", json={"model": self.model, "input": texts})
            response.raise_for_status()
            data = response.json()
            embeddings = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
            return [item["embedding"] for item in embeddings]
        finally:
            await client.aclose()

    def _run_sync(self, coro):
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(asyncio.run, coro).result()
        except RuntimeError:
            return asyncio.run(coro)
