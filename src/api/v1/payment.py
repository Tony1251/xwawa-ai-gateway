"""Payment 路由：支付订单 / 充值 / 回调"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit.logger import AuditLogger
from ...db import get_db
from ...payment.providers import PaymentStatus, get_payment_provider
from ...wallet.crud import (
    create_transaction,
    get_wallet_by_user_id,
    update_wallet_balance,
)
from ...wallet.models import User
from .auth import get_current_user
from .schemas import (
    ApiResponse,
    CreatePaymentOrderRequest,
    PaymentCallbackRequest,
    PaymentOrderResponse,
)

router = APIRouter()


@router.post("/orders", response_model=ApiResponse)
async def create_order(
    req: CreatePaymentOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建支付订单"""
    provider = get_payment_provider()
    order = await provider.create_order(
        user_id=current_user.id,
        amount=req.amount,
        subject=req.subject,
        metadata=req.metadata,
    )
    return ApiResponse(
        data=PaymentOrderResponse(
            order_id=order.order_id,
            amount=order.amount,
            currency=order.currency,
            status=order.status.value,
            provider=order.provider,
            subject=order.subject,
            created_at=order.created_at,
            paid_at=order.paid_at,
        )
    )


@router.get("/orders/{order_id}", response_model=ApiResponse)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
):
    """查询订单"""
    provider = get_payment_provider()
    try:
        order = await provider.query_order(order_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="订单不存在") from None

    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此订单")

    return ApiResponse(
        data=PaymentOrderResponse(
            order_id=order.order_id,
            amount=order.amount,
            currency=order.currency,
            status=order.status.value,
            provider=order.provider,
            subject=order.subject,
            created_at=order.created_at,
            paid_at=order.paid_at,
        )
    )


@router.post("/callback/{provider}", response_model=ApiResponse)
async def payment_callback(
    provider: str,
    req: PaymentCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """接收第三方支付回调"""
    payment_provider = get_payment_provider()
    order = await payment_provider.callback(req.model_dump())

    if order.status == PaymentStatus.SUCCESS:
        # 充值到钱包
        wallet = await get_wallet_by_user_id(db, order.user_id)
        if wallet:
            new_balance = wallet.balance + order.amount
            await update_wallet_balance(db, wallet.id, new_balance)
            await create_transaction(
                db,
                wallet_id=wallet.id,
                tx_type="recharge",
                amount=order.amount,
                balance_after=new_balance,
                reference=order.order_id,
                note=f"支付回调充值-{provider}",
            )
            await db.commit()
            AuditLogger.log_payment(order.user_id, order.order_id, float(order.amount), "success")

    return ApiResponse(data={"order_id": order.order_id, "status": order.status.value})


@router.post("/refund/{order_id}", response_model=ApiResponse)
async def refund_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
):
    """申请退款（MVP: 仅限 Mock）"""
    provider = get_payment_provider()
    ok = await provider.refund(order_id)
    if not ok:
        raise HTTPException(status_code=404, detail="订单不存在")
    AuditLogger.log_payment(current_user.id, order_id, 0, "refund")
    return ApiResponse(data={"refunded": True})
