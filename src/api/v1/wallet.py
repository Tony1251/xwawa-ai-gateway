"""Wallet 路由：余额 / 充值 / 交易记录 / Agent / 用量"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit.logger import AuditLogger
from ...db import get_db
from ...wallet.crud import (
    create_agent,
    get_agents,
    get_transactions,
    get_usage_logs,
    get_wallet_by_user_id,
    update_agent,
)
from ...wallet.models import User
from .auth import get_current_user
from .schemas import (
    AgentResponse,
    ApiResponse,
    CreateAgentRequest,
    RechargeRequest,
    RechargeResponse,
    TransactionResponse,
    UsageLogResponse,
    WalletResponse,
)

router = APIRouter()


@router.get("/balance", response_model=ApiResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取钱包余额"""
    wallet = await get_wallet_by_user_id(db, current_user.id)
    if not wallet:
        raise HTTPException(status_code=404, detail="钱包不存在")
    return ApiResponse(data=WalletResponse.model_validate(wallet))


@router.post("/recharge", response_model=ApiResponse)
async def recharge(
    req: RechargeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """充值（MVP: Mock 直接到账）"""
    from ...payment.providers import get_payment_provider
    from ...wallet.crud import create_transaction, update_wallet_balance

    wallet = await get_wallet_by_user_id(db, current_user.id)
    if not wallet:
        raise HTTPException(status_code=404, detail="钱包不存在")

    provider = get_payment_provider()
    order = await provider.create_order(
        user_id=current_user.id,
        amount=req.amount,
        subject=f"充值-{req.amount}CNY",
    )

    # Mock 直接加余额
    new_balance = wallet.balance + req.amount
    await update_wallet_balance(db, wallet.id, new_balance)
    await create_transaction(
        db,
        wallet_id=wallet.id,
        tx_type="recharge",
        amount=req.amount,
        balance_after=new_balance,
        reference=order.order_id,
        note="充值",
    )
    await db.commit()

    AuditLogger.log_payment(current_user.id, order.order_id, float(req.amount), "success")

    return ApiResponse(
        data=RechargeResponse(
            order_id=order.order_id,
            amount=req.amount,
            status="success",
        )
    )


@router.get("/transactions", response_model=ApiResponse)
async def list_transactions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """交易记录"""
    wallet = await get_wallet_by_user_id(db, current_user.id)
    if not wallet:
        raise HTTPException(status_code=404, detail="钱包不存在")
    txs = await get_transactions(db, wallet.id, limit=limit, offset=offset)
    return ApiResponse(data=[TransactionResponse.model_validate(t) for t in txs])


@router.post("/agents", response_model=ApiResponse)
async def register_agent(
    req: CreateAgentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """注册 Agent"""
    agent = await create_agent(
        db,
        user_id=current_user.id,
        did=req.did,
        name=req.name,
        agent_type=req.agent_type,
        per_call_limit=req.per_call_limit,
        daily_limit=req.daily_limit,
    )
    await db.commit()
    return ApiResponse(data=AgentResponse.model_validate(agent))


@router.get("/agents", response_model=ApiResponse)
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出 Agent"""
    agents = await get_agents(db, current_user.id)
    return ApiResponse(data=[AgentResponse.model_validate(a) for a in agents])


@router.patch("/agents/{agent_id}", response_model=ApiResponse)
async def update_agent_endpoint(
    agent_id: int,
    req: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 Agent 配置"""
    agent = await update_agent(
        db,
        agent_id,
        name=req.get("name"),
        per_call_limit=Decimal(str(req["per_call_limit"])) if "per_call_limit" in req else None,
        daily_limit=Decimal(str(req["daily_limit"])) if "daily_limit" in req else None,
        is_active=req.get("is_active"),
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    await db.commit()
    return ApiResponse(data=AgentResponse.model_validate(agent))


@router.get("/usage", response_model=ApiResponse)
async def list_usage(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    provider: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用量记录"""
    logs = await get_usage_logs(db, current_user.id, limit=limit, offset=offset, provider=provider)
    return ApiResponse(data=[UsageLogResponse.model_validate(log) for log in logs])
