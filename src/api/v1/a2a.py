"""A2A 路由：Agent-to-Agent 通信"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ...a2a.protocol import a2a_pay, discover_services, register_service
from ...a2a.protocol_v2 import A2ADiscovery, A2ARequestHandler, generate_did
from ...wallet.models import User
from .auth import get_current_user
from .schemas import A2ARequestSchema, A2AResponseSchema, ApiResponse

router = APIRouter()


@router.post("/pay", response_model=ApiResponse)
async def a2a_pay_endpoint(
    req: A2ARequestSchema,
    current_user: User = Depends(get_current_user),
):
    """A2A 支付调用"""
    result = await a2a_pay(
        from_did=req.from_did,
        to_did=req.to_did,
        amount=req.amount,
        service=req.service,
        action=req.action,
        params=req.params,
    )
    return ApiResponse(
        data=A2AResponseSchema(
            success=result.success,
            result=result.result,
            error=result.error,
            payment_confirmation=result.payment_confirmation,
        )
    )


@router.get("/discover/{service}", response_model=ApiResponse)
async def discover(service: str):
    """发现提供特定服务的 Agent"""
    providers = discover_services(service)
    return ApiResponse(data={"service": service, "providers": providers})


@router.post("/register", response_model=ApiResponse)
async def register_service_endpoint(
    did: str,
    service: str,
    endpoint: str,
    capability: dict,
    current_user: User = Depends(get_current_user),
):
    """注册 Agent 提供的服务"""
    register_service(did, service, endpoint, capability)
    return ApiResponse(data={"registered": True})


# ===== 增强的 A2A v2 端点 =====


@router.get("/discover", response_model=ApiResponse)
async def a2a_discover_all(request: Request):
    """发现所有已注册的 Agent（增强版）"""
    agents = await A2ADiscovery.discover_all()
    return ApiResponse(data={"agents": agents, "count": len(agents)})


@router.get("/discover/service/{service}", response_model=ApiResponse)
async def a2a_discover_by_service(service: str):
    """按服务类型发现 Agent（增强版）"""
    agents = await A2ADiscovery.discover_by_service(service)
    return ApiResponse(data={"service": service, "agents": agents, "count": len(agents)})


@router.post("/register/agent", response_model=ApiResponse)
async def a2a_register_agent(
    request: Request,
    name: str,
    services: list[str],
    endpoint: str = "",
    public_key: str = "",
    current_user: User = Depends(get_current_user),
):
    """注册 Agent 身份（增强版）

    Agent 注册自己，获得 DID，可用于后续 A2A 调用计费
    """
    # 生成 DID
    key = public_key or f"user_{current_user.id}_{name}"
    did = generate_did(key)

    result = await A2ADiscovery.register_agent(
        did=did,
        name=name,
        endpoint=endpoint or str(request.base_url).rstrip("/"),
        services=services,
        public_key=public_key,
    )

    return ApiResponse(data={**result, "user_id": current_user.id})


@router.get("/lookup/{did}", response_model=ApiResponse)
async def a2a_lookup_agent(did: str):
    """按 DID 查找 Agent 详情"""
    agent = await A2ADiscovery.lookup_agent(did)
    if agent is None:
        return ApiResponse(data={"found": False, "did": did})
    return ApiResponse(data={"found": True, **agent})


@router.post("/message", response_model=ApiResponse)
async def a2a_handle_message(
    raw_message: dict,
    current_user: User = Depends(get_current_user),
):
    """处理传入的 A2A 消息（增强版）"""
    from ...a2a.protocol import A2AMessage

    msg = A2AMessage.from_json(raw_message.get("message", "{}"))
    handler = A2ARequestHandler(
        my_did=f"did:xwawa:user_{current_user.id}",
        my_user_id=current_user.id,
        endpoint=str(request.base_url).rstrip("/") if request else "",
    )
    result = await handler.handle_message(msg)
    return ApiResponse(data={"success": result.success, "result": result.result, "error": result.error})
