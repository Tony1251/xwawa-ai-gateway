"""A2A 路由：Agent-to-Agent 通信"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...a2a.protocol import a2a_pay, discover_services, register_service
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
