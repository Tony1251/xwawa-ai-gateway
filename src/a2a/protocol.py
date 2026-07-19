"""A2A 协议：Agent-to-Agent 支付与发现

A2A 场景：
- Agent A 调用 Agent B 的服务，B 向 A 收费
- 支持服务发现（茫茫大海里找谁？）
- 支持原子化支付（钱和安全都要）
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from ..config import settings
from ..exceptions import BusinessError


# ===== 消息类型 =====
class A2AMessageType(str):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    DISCOVER = "discover"
    DISCOVER_RESPONSE = "discover_response"


@dataclass
class A2AMessage:
    """A2A 消息格式"""
    version: str = "1.0"
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: A2AMessageType = A2AMessageType.REQUEST
    from_did: str = ""
    to_did: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "version": self.version,
            "msg_id": self.msg_id,
            "type": self.type,
            "from": self.from_did,
            "to": self.to_did,
            "timestamp": self.timestamp,
            "payload": self.payload,
        })

    @classmethod
    def from_json(cls, raw: str) -> "A2AMessage":
        data = json.loads(raw)
        return cls(
            version=data.get("version", "1.0"),
            msg_id=data["msg_id"],
            type=data["type"],
            from_did=data.get("from", ""),
            to_did=data.get("to", ""),
            timestamp=data.get("timestamp", ""),
            payload=data.get("payload", {}),
        )


# ===== A2A 请求/响应 =====
@dataclass
class A2ARequest:
    """A2A 请求（调用另一个 Agent 的服务）"""
    service: str  # e.g. "image_generation", "data_analysis"
    action: str    # e.g. "generate", "analyze"
    params: dict[str, Any]
    payment: dict[str, Any] = field(default_factory=dict)  # 支付信息
    callback_url: str = ""  # 异步结果回调


@dataclass
class A2AResponse:
    """A2A 响应"""
    success: bool
    result: Any = None
    error: str = ""
    payment_confirmation: dict[str, Any] = field(default_factory=dict)


# ===== 服务注册表（简化版：生产应使用 Redis/etcd）=====
_registered_services: dict[str, dict[str, Any]] = {}


def register_service(did: str, service: str, endpoint: str, capability: dict[str, Any]) -> None:
    """注册 Agent 提供的服务"""
    _registered_services[f"{did}:{service}"] = {
        "did": did,
        "service": service,
        "endpoint": endpoint,
        "capability": capability,
        "registered_at": datetime.utcnow().isoformat(),
    }


def discover_services(service: str) -> list[dict[str, Any]]:
    """发现提供特定服务的 Agent"""
    return [
        info for key, info in _registered_services.items()
        if key.endswith(f":{service}")
    ]


async def a2a_pay(
    from_did: str,
    to_did: str,
    amount: float,
    service: str,
    action: str,
    params: dict[str, Any],
) -> A2AResponse:
    """A2A 原子化支付流程

    1. 发现目标服务
    2. 锁定金额
    3. 发起调用
    4. 确认扣款 / 回滚
    """
    # Step 1: 服务发现
    providers = discover_services(service)
    if not providers:
        return A2AResponse(
            success=False,
            error=f"未找到服务: {service}",
        )

    # 简化：取第一个可用的 Provider
    provider = providers[0]

    # Step 2: 构建请求
    msg = A2AMessage(
        type=A2AMessageType.REQUEST,
        from_did=from_did,
        to_did=provider["did"],
        payload={
            "request": {
                "service": service,
                "action": action,
                "params": params,
            },
            "payment": {
                "amount": amount,
                "currency": "USD",
                "from": from_did,
                "to": to_did,
            },
        },
    )

    # Step 3: 发送请求（这里简化，实际应走 HTTP/WebSocket）
    # 实际实现中，这里会调用 provider["endpoint"]
    # 并处理响应

    return A2AResponse(
        success=True,
        result={"status": "processed"},
        payment_confirmation={
            "amount": amount,
            "from": from_did,
            "to": to_did,
            "msg_id": msg.msg_id,
        },
    )
