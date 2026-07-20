"""WebSocket 路由：实时 AI 对话"""

from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...audit.ml_detector import MLAnomalyDetector
from ...billing import PricingEngine
from ...config import settings
from ...db import AsyncSessionLocal
from ...exceptions import InsufficientBalanceError, RiskLimitExceededError
from ...logging_config import get_logger
from ...providers import get_provider
from ...routing import get_router
from ...wallet.credit import CreditService
from ...wallet.crud import get_api_key_by_hash, get_user_by_id, hash_api_key
from ...wallet.models import User

router = APIRouter()
log = get_logger(__name__)


class ConnectionManager:
    """WebSocket 连接管理"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)


manager = ConnectionManager()


async def authenticate_websocket(websocket: WebSocket) -> User | None:
    """WebSocket 认证（Token 或 API Key）"""
    auth_header = websocket.headers.get("Authorization", "")
    token = None
    api_key = None

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif auth_header.startswith("ApiKey "):
        api_key = auth_header[7:]

    if not token and not api_key:
        return None

    async with AsyncSessionLocal() as session:
        if token:
            import jwt

            try:
                payload = jwt.decode(
                    token, settings.app_secret_key, algorithms=[settings.jwt_algorithm]
                )
                if payload.get("type") != "access":
                    return None
                user = await get_user_by_id(session, int(payload["sub"]))
            except Exception:
                return None
        elif api_key:
            key_hash = hash_api_key(api_key)
            api_key_obj = await get_api_key_by_hash(session, key_hash)
            if not api_key_obj or not api_key_obj.is_active:
                return None
            user = await get_user_by_id(session, api_key_obj.user_id)
            api_key_obj.last_used_at = time.time()
            await session.commit()

        if not user or not user.is_active or user.is_locked:
            return None
        return user


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 实时对话"""
    client_id = str(uuid.uuid4())
    user = await authenticate_websocket(websocket)

    if not user:
        await websocket.close(code=4001, reason="认证失败")
        return

    await manager.connect(websocket, client_id)

    try:
        # 接收消息
        data = await websocket.receive_text()
        msg = json.loads(data)

        model = msg.get("model")
        messages = msg.get("messages", [])
        temperature = msg.get("temperature")

        # 路由
        router_instance = get_router()
        decision = router_instance.route(model)

        # 调用 Provider
        provider = get_provider(decision.provider)
        upstream = await provider.chat(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        # 定价
        pricing = PricingEngine()
        cost_breakdown = pricing.calculate(
            provider=decision.provider,
            model=model,
            input_tokens=upstream.input_tokens,
            output_tokens=upstream.output_tokens,
        )

        # 扣费
        request_id = str(uuid.uuid4())
        try:
            async with AsyncSessionLocal() as session:
                credit_svc = CreditService(session, pricing)
                await credit_svc.check_and_deduct(
                    user_id=user.id,
                    provider=decision.provider,
                    model=model,
                    input_tokens=upstream.input_tokens,
                    output_tokens=upstream.output_tokens,
                    request_id=request_id,
                )
        except (InsufficientBalanceError, RiskLimitExceededError):
            pass  # MVP 阶段忽略扣费失败

        # 异常检测
        MLAnomalyDetector.detect(
            user_id=user.id,
            provider=decision.provider,
            model=model,
            cost_user=float(cost_breakdown.cost_user),
        )

        # 返回结果
        await websocket.send_json(
            {
                "id": request_id,
                "model": upstream.model,
                "content": upstream.content,
                "input_tokens": upstream.input_tokens,
                "output_tokens": upstream.output_tokens,
                "cost_user": str(cost_breakdown.cost_user),
                "provider": decision.provider,
            }
        )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("WebSocketError", client_id=client_id, error=str(e))
        await websocket.close(code=4000, reason=str(e)[:100])
    finally:
        manager.disconnect(client_id)
