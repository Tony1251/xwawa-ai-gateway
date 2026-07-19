"""Chat 路由：AI 对话 + 扣费"""
from __future__ import annotations

import time
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...billing import PricingEngine
from ...config import settings
from ...db import get_db
from ...exceptions import ProviderError, RiskLimitExceededError, InsufficientBalanceError
from ...providers import get_provider
from ...routing import get_router
from ...wallet.credit import CreditService
from ...wallet.models import User
from ...audit.ml_detector import MLAnomalyDetector
from ...logging_config import get_logger, user_id_ctx
from .auth import get_current_user
from .schemas import ApiResponse, ChatRequest, ChatResponse

router = APIRouter()
log = get_logger(__name__)


@router.post("/chat", response_model=ApiResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 对话（自动扣费 + 路由）"""
    request_id = str(uuid.uuid4())
    token = user_id_ctx.set(current_user.id)
    start_ms = int(time.time() * 1000)

    try:
        # ---- 路由决策 ----
        router_instance = get_router()
        decision = router_instance.route(req.model)
        provider_name = decision.provider

        # ---- 调用上游 Provider ----
        provider = get_provider(provider_name)
        try:
            upstream = await provider.chat(
                model=req.model,
                messages=req.messages,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
        except ProviderError as e:
            log.error("ProviderError", provider=provider_name, model=req.model, error=str(e))
            raise

        # ---- 定价计算 ----
        pricing = PricingEngine()
        cost_breakdown = pricing.calculate(
            provider=provider_name,
            model=req.model,
            input_tokens=upstream.input_tokens,
            output_tokens=upstream.output_tokens,
        )

        # ---- 扣费（异步，不阻塞响应）----
        deduct_result = None
        try:
            credit_svc = CreditService(db, pricing)
            deduct_result = await credit_svc.check_and_deduct(
                user_id=current_user.id,
                provider=provider_name,
                model=req.model,
                input_tokens=upstream.input_tokens,
                output_tokens=upstream.output_tokens,
                request_id=request_id,
                client_ip=request.client.host if request.client else None,
                duration_ms=int(time.time() * 1000) - start_ms,
            )
        except (InsufficientBalanceError, RiskLimitExceededError) as e:
            # 扣费失败但请求已成功，告警但不阻断返回
            log.error("CreditDeductionFailed", user_id=current_user.id, error=str(e))

        # ---- 异常检测 ----
        if deduct_result:
            detection = MLAnomalyDetector.detect(
                user_id=current_user.id,
                provider=provider_name,
                model=req.model,
                cost_user=float(deduct_result.cost_user),
            )
            if detection.is_anomalous:
                log.warning("AnomalyDetected", user_id=current_user.id, reason=detection.reason)

        return ApiResponse(data=ChatResponse(
            id=request_id,
            model=upstream.model,
            content=upstream.content,
            input_tokens=upstream.input_tokens,
            output_tokens=upstream.output_tokens,
            cost_user=cost_breakdown.cost_user,
            cost_provider=cost_breakdown.cost_provider,
            provider=provider_name,
        ))

    finally:
        user_id_ctx.reset(token)


@router.get("/models", response_model=ApiResponse)
async def list_models(provider: str | None = None):
    """列出支持的模型"""
    router_instance = get_router()
    if provider:
        models = router_instance.list_models(provider)
    else:
        models = router_instance.list_models()
    return ApiResponse(data={
        "models": models,
        "providers": router_instance.list_providers(),
    })
