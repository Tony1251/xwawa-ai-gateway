"""Xwawa Chat LLM - LangChain BaseChatModel compatible"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Iterator

import httpx
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, SecretStr


class XwawaChatLLM(BaseChatModel):
    api_key: SecretStr = Field(default_factory=lambda: os.getenv("XWAWA_API_KEY", ""))
    base_url: str = Field(default_factory=lambda: os.getenv("XWAWA_BASE_URL", "https://api.xwawa.ai/v1"))
    model: str = Field(default_factory=lambda: os.getenv("XWAWA_MODEL", "gpt-4o-mini"))
    timeout: float = Field(default=60.0)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)

    @property
    def _llm_type(self) -> str:
        return "xwawa-chat"

    def _format_message(self, message: BaseMessage) -> dict[str, str]:
        role = "user"
        if isinstance(message, AIMessage):
            role = "assistant"
        elif isinstance(message, SystemMessage):
            role = "system"
        content = message.content if isinstance(message.content, str) else ""
        return {"role": role, "content": content}

    def _convert_messages(self, messages: list[BaseMessage]) -> list[dict[str, str]]:
        return [self._format_message(msg) for msg in messages]

    def _create_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            loop = asyncio.get_running_loop()
            future = loop.create_task(self._agenerate(messages, stop, **kwargs))
            return future.result()
        except RuntimeError:
            return asyncio.run(self._agenerate(messages, stop, **kwargs))

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        api_messages = self._convert_messages(messages)
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": api_messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        if stop:
            payload["stop"] = stop

        client = self._create_client()
        try:
            response = await client.post("/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            ai_message = AIMessage(content=content)
            generation = ChatGeneration(message=ai_message, generation_info={"usage": usage})
            return ChatResult(generations=[generation])
        finally:
            await client.aclose()

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> Any:
        from langchain_core.utils.function_calling import convert_to_openai_function
        functions = [convert_to_openai_function(tool) for tool in tools]
        bound = self.copy()
        bound._bound_tools = tools  # type: ignore
        bound._bound_functions = functions  # type: ignore
        return bound
