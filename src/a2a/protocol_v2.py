"""A2A 协议增强：Agent 自我发现 + 原子化支付 + 服务注册表"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

from ..config import settings
from ..exceptions import BusinessError, ProviderError
from ..routing.router import get_router
from ..wallet.crud import (
    check_balance,
    deduct_credit,
    get_or_create_wallet,
    record_usage,
)
from .protocol import (
    A2AMessage,
    A2AMessageType,
    A2ARequest,
    A2AResponse,
    a2a_pay,
    discover_services,
    register_service,
)


# ===== A2A 身份（DID）=====
def generate_did(public_key: str) -> str:
    """从公钥生成 DID（简化版）"""
    key_hash = hashlib.sha256(public_key.encode()).hexdigest()[:16]
    return f"did:xwawa:{key_hash}"


@dataclass
class AgentIdentity:
    """Agent 身份"""

    did: str
    name: str
    public_key: str = ""
    endpoint: str = ""
    services: list[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=datetime.utcnow)


# ===== A2A 服务发现增强 =====
class A2ADiscovery:
    """A2A 服务发现，支持多维度查询"""

    # 内存注册表（生产应该用 Redis）
    _registry: dict[str, AgentIdentity] = {}
    _service_index: dict[str, set[str]] = {}  # service_name -> set of dids
    _lock = asyncio.Lock()

    @classmethod
    async def register_agent(
        cls,
        did: str,
        name: str,
        endpoint: str,
        services: list[str],
        public_key: str = "",
    ) -> dict[str, Any]:
        """注册 Agent 到发现表"""
        async with cls._lock:
            identity = AgentIdentity(
                did=did,
                name=name,
                public_key=public_key,
                endpoint=endpoint,
                services=services,
            )
            cls._registry[did] = identity

            for svc in services:
                if svc not in cls._service_index:
                    cls._service_index[svc] = set()
                cls._service_index[svc].add(did)

            return {
                "did": did,
                "name": name,
                "services": services,
                "registered_at": identity.registered_at.isoformat(),
            }

    @classmethod
    async def discover_by_service(cls, service: str) -> list[dict[str, Any]]:
        """按服务类型发现 Agent"""
        async with cls._lock:
            dids = cls._service_index.get(service, set())
            return [
                {
                    "did": did,
                    "name": cls._registry[did].name,
                    "endpoint": cls._registry[did].endpoint,
                    "services": cls._registry[did].services,
                }
                for did in dids
                if did in cls._registry
            ]

    @classmethod
    async def discover_all(cls) -> list[dict[str, Any]]:
        """发现所有已注册 Agent"""
        async with cls._lock:
            return [
                {
                    "did": did,
                    "name": identity.name,
                    "endpoint": identity.endpoint,
                    "services": identity.services,
                    "registered_at": identity.registered_at.isoformat(),
                }
                for did, identity in cls._registry.items()
            ]

    @classmethod
    async def lookup_agent(cls, did: str) -> dict[str, Any] | None:
        """按 DID 查找 Agent"""
        async with cls._lock:
            if did not in cls._registry:
                return None
            identity = cls._registry[did]
            return {
                "did": did,
                "name": identity.name,
                "endpoint": identity.endpoint,
                "services": identity.services,
                "public_key": identity.public_key,
                "registered_at": identity.registered_at.isoformat(),
            }


# ===== A2A 支付流程增强 =====
@dataclass
class A2APaymentContext:
    """A2A 支付上下文"""

    from_did: str
    to_did: str
    amount: float
    service: str
    action: str
    estimated_cost: float = 0.0
    actual_cost: float = 0.0


class A2APaymentManager:
    """A2A 支付管理器：原子化扣款 + 确认"""

    @classmethod
    async def prepare_payment(
        cls,
        from_user_id: int,
        to_user_id: int,
        amount: float,
        service: str,
        model: str,
    ) -> dict[str, Any]:
        """准备支付：检查余额 + 预留金额"""
        # 获取发送方钱包
        async with AsyncSessionLocal() as session:
            wallet = await get_or_create_wallet(session, from_user_id)
            balance = await check_balance(session, wallet.id)

            if balance < amount:
                raise BusinessError(
                    f"余额不足: 需要 {amount:.4f}, 当前 {balance:.4f}",
                    details={"required": amount, "available": balance},
                )

            return {
                "status": "ready",
                "from_user_id": from_user_id,
                "to_user_id": to_user_id,
                "estimated_cost": amount,
                "balance_before": balance,
            }

    @classmethod
    async def execute_payment(
        cls,
        context: A2APaymentContext,
        input_tokens: int,
        output_tokens: int,
        provider: str,
        model: str,
        success: bool = True,
    ) -> A2AResponse:
        """执行支付：扣款 + 记录用量"""
        async with AsyncSessionLocal() as session:
            try:
                # 扣款
                tx = await deduct_credit(
                    session=session,
                    user_id=context.from_user_id,
                    amount=context.amount,
                    tx_type="a2a_payment",
                    reference=f"a2a:{context.to_did}:{context.service}",
                    description=f"A2A调用 {context.service}/{context.action}",
                )

                # 记录用量
                await record_usage(
                    session=session,
                    user_id=context.from_user_id,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_provider=context.actual_cost,
                    cost_user=context.amount,
                    agent_id=None,
                )

                return A2AResponse(
                    success=True,
                    result={
                        "status": "paid",
                        "tx_id": tx.id,
                        "amount": context.amount,
                        "from": context.from_did,
                        "to": context.to_did,
                    },
                    payment_confirmation={
                        "amount": context.amount,
                        "tx_id": tx.id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    },
                )

            except Exception as e:
                return A2AResponse(
                    success=False,
                    error=f"支付失败: {str(e)}",
                )


# ===== A2A 请求处理器 =====
class A2ARequestHandler:
    """处理传入的 A2A 请求"""

    def __init__(self, my_did: str, my_user_id: int, endpoint: str):
        self.my_did = my_did
        self.my_user_id = my_user_id
        self.endpoint = endpoint

    async def handle_message(self, msg: A2AMessage) -> A2AResponse:
        """处理 A2A 消息"""
        if msg.type == A2AMessageType.DISCOVER:
            return await self._handle_discover(msg)
        elif msg.type == A2AMessageType.REQUEST:
            return await self._handle_request(msg)
        else:
            return A2AResponse(success=False, error=f"未知消息类型: {msg.type}")

    async def _handle_discover(self, msg: A2AMessage) -> A2AResponse:
        """处理发现请求"""
        return A2AResponse(
            success=True,
            result={
                "did": self.my_did,
                "name": "xwawa-gateway",
                "endpoint": self.endpoint,
                "services": ["chat", "embeddings", "a2a_relay"],
                "capabilities": {
                    "models": ["gpt-4o-mini", "MiniMax-Text-01", "deepseek-chat"],
                    "max_context": 128000,
                    "streaming": True,
                },
            },
        )

    async def _handle_request(self, msg: A2AMessage) -> A2AResponse:
        """处理服务请求"""
        payload = msg.payload
        request_data = payload.get("request", {})
        payment_data = payload.get("payment", {})

        service = request_data.get("service")
        action = request_data.get("action")
        params = request_data.get("params", {})
        payment_amount = payment_data.get("amount", 0)

        # 使用 router 获取最优路由
        router = get_router()
        model = params.get("model", "gpt-4o-mini")
        routing_decision = router.get_cheapest_route(model)

        # 执行实际的 AI 调用
        try:
            from ..providers import get_provider

            provider = get_provider(routing_decision.provider)
            messages = params.get("messages", [])

            response = await provider.chat(
                model=model,
                messages=messages,
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 4096),
            )

            # 计算实际费用
            estimated = routing_decision.estimated_cost * (
                (response.input_tokens + response.output_tokens) / 1000
            )

            # A2A 支付
            context = A2APaymentContext(
                from_did=msg.from_did,
                to_did=self.my_did,
                amount=payment_amount or estimated,
                service=service,
                action=action,
                actual_cost=estimated,
            )

            payment_result = await A2APaymentManager.execute_payment(
                context=context,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                provider=routing_decision.provider,
                model=model,
                success=True,
            )

            return A2AResponse(
                success=True,
                result={
                    "content": response.content,
                    "model": response.model,
                    "usage": {
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                    },
                },
                payment_confirmation=payment_result.payment_confirmation,
            )

        except ProviderError as e:
            return A2AResponse(success=False, error=f"Provider error: {str(e)}")
        except Exception as e:
            return A2AResponse(success=False, error=f"Internal error: {str(e)}")


# 简化导入
from ..db import AsyncSessionLocal
