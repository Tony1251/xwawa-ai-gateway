"""Agent Discovery 端点：提供 /.well-known/agent.json"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...config import settings
from ...billing.pricing import PRICING
from ...routing.router import SUPPORTED_MODELS, COST_MATRIX

router = APIRouter(tags=["Agent Discovery"])


def build_agent_discovery(request: Request) -> dict[str, Any]:
    """构建 Agent Discovery 文档（符合 Agent Protocol 规范）"""
    base_url = str(request.base_url).rstrip("/")

    # 构建模型能力列表（带定价）
    models = []
    for model, provider in SUPPORTED_MODELS.items():
        if provider in COST_MATRIX and model in COST_MATRIX[provider]:
            cost = COST_MATRIX[provider][model]
            models.append({
                "model": model,
                "provider": provider,
                "input_cost_per_million": cost.get("input", 0),
                "output_cost_per_million": cost.get("output", 0),
                "context_window": _get_context_window(model),
                "capabilities": _get_model_capabilities(model),
            })

    # 构建 Provider 列表
    providers = []
    for p in settings.configured_providers:
        health_url = f"{base_url}/v1/providers/{p}/health"
        providers.append({
            "name": p,
            "status": "available",
            "health_check_url": health_url,
        })

    return {
        "name": "xwawa-ai-gateway",
        "version": "0.2.0",
        "description": "AI Agent Credit Payment Gateway - Pay per token, multi-provider routing",
        "api_version": "v1",
        "base_url": f"{base_url}/v1",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "authentication": {
            "type": "api_key",
            "header": "X-API-Key",
            "description": "Register at /v1/auth/register to get an API key",
            "scopes": ["chat", "embeddings", "images"],
        },
        "capabilities": {
            "providers": providers,
            "models": models,
            "routing": {
                "strategy": "cost_optimal",
                "supports_cheapest_route": True,
                "supports_fastest_route": True,
                "circuit_breaker": True,
            },
            "billing": {
                "currency": "USD",
                "markup_rate": settings.markup_rate,
                "tax_rate": settings.tax_rate,
            },
            "a2a_protocol": {
                "enabled": True,
                "endpoint": f"{base_url}/v1/a2a",
                "version": "1.0",
            },
        },
        "endpoints": {
            "chat": f"{base_url}/v1/chat",
            "auth_register": f"{base_url}/v1/auth/register",
            "auth_login": f"{base_url}/v1/auth/login",
            "wallet_balance": f"{base_url}/v1/wallet/balance",
            "wallet_recharge": f"{base_url}/v1/payment/recharge",
            "usage_history": f"{base_url}/v1/wallet/usage",
            "a2a_discovery": f"{base_url}/v1/a2a/discover",
            "health": f"{base_url}/health/ready",
            "metrics": f"{base_url}/metrics",
        },
        "pricing_example": {
            "model": "gpt-4o-mini",
            "input_tokens": 1000,
            "output_tokens": 500,
            "estimated_cost_usd": round(
                (0.15 * 1 + 0.6 * 0.5) / 1_000_000 * 1000 * settings.markup_rate * (1 + settings.tax_rate),
                6,
            ),
        },
    }


def _get_context_window(model: str) -> int:
    """获取模型上下文窗口大小"""
    windows = {
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4-turbo": 128000,
        "gpt-3.5-turbo": 16385,
        "claude-3-5-sonnet": 200000,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "deepseek-chat": 64000,
        "deepseek-coder": 64000,
        "doubao-pro-128k": 128000,
        "doubao-pro-32k": 32000,
        "doubao-lite-32k": 32000,
        "MiniMax-Text-01": 1000000,
    }
    return windows.get(model, 32000)


def _get_model_capabilities(model: str) -> list[str]:
    """获取模型支持的能力"""
    caps = ["chat", "streaming"]
    if "embedding" not in model.lower():
        caps.append("embeddings")
    if "midjourney" in model.lower():
        caps = ["images"]
    if model.startswith("claude-"):
        caps.append("vision")
    return caps


@router.get(
    "/.well-known/agent.json",
    summary="Agent Discovery Document",
    description="Returns machine-readable agent capabilities, pricing, and endpoints. Agents use this to self-discover and auto-integrate.",
    response_class=JSONResponse,
)
async def get_agent_discovery(request: Request) -> JSONResponse:
    """Agent Discovery 端点

    GET /.well-known/agent.json

    符合 Agent Protocol 规范的发现文档，Agent 可自动：
    1. 发现支持的模型和定价
    2. 了解认证方式
    3. 注册并获取 API Key
    4. 开始计费调用
    """
    return JSONResponse(content=build_agent_discovery(request))


@router.get(
    "/.well-known/openapi.json",
    summary="OpenAPI Spec for Agents",
    description="Returns OpenAPI 3.1 spec for programmatic client generation",
    response_class=JSONResponse,
)
async def get_openapi_spec(request: Request) -> JSONResponse:
    """返回 OpenAPI 规范，方便 Agent 生成客户端"""
    from fastapi.openapi.spec import OpenAPI

    # 动态生成精简的 OpenAPI spec（仅含 Agent 关键端点）
    base_url = str(request.base_url).rstrip("/")

    spec: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": "xwawa-ai-gateway Agent API",
            "version": "0.2.0",
            "description": "AI Agent Credit Payment Gateway - Self-discoverable API for AI Agents",
        },
        "servers": [{"url": base_url}],
        "paths": {
            "/v1/chat": {
                "post": {
                    "summary": "Chat Completion",
                    "description": "Send a chat completion request. Requires X-API-Key header.",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "model": {"type": "string", "example": "gpt-4o-mini"},
                                        "messages": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "role": {"type": "string", "enum": ["user", "assistant", "system"]},
                                                    "content": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "Chat response"},
                        "401": {"description": "Invalid API key"},
                        "402": {"description": "Insufficient balance"},
                    },
                }
            },
            "/v1/auth/register": {
                "post": {
                    "summary": "Register new Agent",
                    "description": "Register to get an API key. No authentication required.",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["email", "password"],
                                    "properties": {
                                        "email": {"type": "string", "format": "email"},
                                        "password": {"type": "string", "minLength": 8},
                                        "name": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "Registration successful"}},
                }
            },
        },
    }

    return JSONResponse(content=spec)
