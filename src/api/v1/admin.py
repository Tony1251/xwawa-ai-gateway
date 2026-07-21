"""Admin 路由：管理面板 API（需管理员权限）"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_db
from ...wallet.crud import (
    get_transactions,
    get_usage_logs,
    get_user_by_id,
    get_wallet_by_user_id,
    lock_user,
    unlock_user,
)
from ...wallet.models import UsageLog, User
from .auth import get_current_user
from .schemas import ApiResponse, TransactionResponse, UsageLogResponse, WalletResponse

router = APIRouter()


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """管理员权限检查（MVP: 简单 email 检查）"""
    admin_emails = ["admin@xwawa.ai"]
    if current_user.email not in admin_emails:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


@router.get("/users/{user_id}", response_model=ApiResponse)
async def get_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看用户信息"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    wallet = await get_wallet_by_user_id(db, user_id)
    return ApiResponse(
        data={
            "id": user.id,
            "email": user.email,
            "phone": user.phone,
            "nickname": user.nickname,
            "kyc_level": user.kyc_level.value,
            "is_active": user.is_active,
            "is_locked": user.is_locked,
            "created_at": user.created_at.isoformat(),
            "wallet": WalletResponse.model_validate(wallet) if wallet else None,
        }
    )


@router.get("/users/{user_id}/transactions", response_model=ApiResponse)
async def get_user_transactions(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看用户交易记录"""
    wallet = await get_wallet_by_user_id(db, user_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="钱包不存在")
    txs = await get_transactions(db, wallet.id, limit=limit, offset=offset)
    return ApiResponse(data=[TransactionResponse.model_validate(t) for t in txs])


@router.get("/users/{user_id}/usage", response_model=ApiResponse)
async def get_user_usage(
    user_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    provider: str | None = None,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看用户用量"""
    logs = await get_usage_logs(db, user_id, limit=limit, offset=offset, provider=provider)
    return ApiResponse(data=[UsageLogResponse.model_validate(log_item) for log_item in logs])


@router.post("/users/{user_id}/lock", response_model=ApiResponse)
async def lock_user_endpoint(
    user_id: int,
    body: dict,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """锁定用户"""
    reason = body.get("reason", "管理员操作")
    user = await lock_user(db, user_id, reason)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    await db.commit()
    return ApiResponse(data={"locked": True, "reason": reason})


@router.post("/users/{user_id}/unlock", response_model=ApiResponse)
async def unlock_user_endpoint(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """解锁用户"""
    user = await unlock_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    await db.commit()
    return ApiResponse(data={"unlocked": True})


@router.get("/stats/overview", response_model=ApiResponse)
async def stats_overview(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """全局统计概览"""
    # 用户数
    user_count = await db.scalar(select(func.count(User.id)))
    # 异常用量数
    anomaly_count = await db.scalar(
        select(func.count(UsageLog.id)).where(UsageLog.is_anomalous == True)  # noqa: E712
    )
    # 总用量
    total_cost = await db.scalar(select(func.coalesce(func.sum(UsageLog.cost_user), Decimal("0"))))

    return ApiResponse(
        data={
            "total_users": user_count or 0,
            "anomalous_logs": anomaly_count or 0,
            "total_cost": str(total_cost or Decimal("0")),
        }
    )


@router.get("/stats/providers", response_model=ApiResponse)
async def stats_by_provider(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """按 Provider 统计用量"""
    result = await db.execute(
        select(
            UsageLog.provider,
            func.count(UsageLog.id).label("call_count"),
            func.coalesce(func.sum(UsageLog.cost_user), Decimal("0")).label("total_cost"),
        ).group_by(UsageLog.provider)
    )
    rows = result.all()
    return ApiResponse(
        data=[
            {"provider": r.provider, "call_count": r.call_count, "total_cost": str(r.total_cost)}
            for r in rows
        ]
    )
