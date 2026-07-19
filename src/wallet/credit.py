"""信用额度服务（扣费核心逻辑）"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import InsufficientBalanceError, RiskLimitExceededError
from .crud import create_transaction, create_usage_log, get_wallet_by_user_id, update_wallet_balance
from .models import Transaction, Wallet

if TYPE_CHECKING:
    from ..billing.pricing import PricingEngine


@dataclass
class DeductResult:
    """扣费结果"""
    success: bool
    transaction_id: int
    balance_after: Decimal
    cost_user: Decimal
    cost_provider: Decimal


class CreditService:
    """信用服务：检查余额/限额 → 扣费 → 记录日志"""

    def __init__(self, session: AsyncSession, pricing: "PricingEngine"):
        self.session = session
        self.pricing = pricing

    async def check_and_deduct(
        self,
        user_id: int,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        *,
        agent_id: int | None = None,
        request_id: str = "",
        client_ip: str | None = None,
        duration_ms: int | None = None,
    ) -> DeductResult:
        """执行检查 + 扣费，返回结果

        流程：
        1. 加载钱包
        2. 计算费用
        3. 检查日限额 / 单次限额
        4. 检查余额是否充足
        5. 原子扣费
        6. 记录 transaction + usage_log
        """
        wallet = await get_wallet_by_user_id(self.session, user_id)
        if not wallet:
            raise InsufficientBalanceError("钱包不存在")

        cost_provider = self.pricing.calculate_provider_cost(provider, model, input_tokens, output_tokens)
        cost_user = self.pricing.calculate_user_cost(cost_provider)

        # ---- 风险检查 ----
        daily_cost = await self._get_daily_cost(wallet.id)
        if daily_cost + cost_user > wallet.daily_limit:
            raise RiskLimitExceededError(
                f"日限额超限: 已用 {daily_cost}, 限额 {wallet.daily_limit}",
                details={
                    "daily_used": str(daily_cost),
                    "daily_limit": str(wallet.daily_limit),
                    "this_call_cost": str(cost_user),
                },
            )

        if cost_user > wallet.per_call_limit:
            raise RiskLimitExceededError(
                f"单次费用超限: {cost_user} > {wallet.per_call_limit}",
                details={
                    "this_call_cost": str(cost_user),
                    "per_call_limit": str(wallet.per_call_limit),
                },
            )

        available = wallet.balance + wallet.credit_limit - wallet.used_this_month
        if available < cost_user:
            raise InsufficientBalanceError(
                f"余额不足: 可用 {available}, 需要 {cost_user}",
                details={
                    "available": str(available),
                    "required": str(cost_user),
                },
            )

        # ---- 执行扣费 ----
        new_balance = wallet.balance - cost_user
        await update_wallet_balance(self.session, wallet.id, new_balance)

        tx = await create_transaction(
            self.session,
            wallet_id=wallet.id,
            tx_type="consume",
            amount=-cost_user,
            balance_after=new_balance,
            reference=f"usage:{request_id}",
            note=f"{provider}/{model}",
        )

        await create_usage_log(
            self.session,
            user_id=user_id,
            agent_id=agent_id,
            provider=provider,
            model=model,
            endpoint="chat/completions",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_provider=cost_provider,
            cost_user=cost_user,
            request_id=request_id,
            client_ip=client_ip,
            duration_ms=duration_ms,
        )

        return DeductResult(
            success=True,
            transaction_id=tx.id,
            balance_after=new_balance,
            cost_user=cost_user,
            cost_provider=cost_provider,
        )

    async def _get_daily_cost(self, wallet_id: int) -> Decimal:
        """获取今日已消费金额"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.session.execute(
            select(func.coalesce(func.sum(Transaction.amount), Decimal("0")))
            .where(
                and_(
                    Transaction.wallet_id == wallet_id,
                    Transaction.type == "consume",
                    Transaction.created_at >= today_start,
                )
            )
        )
        val = result.scalar_one_or_none()
        return (val if val is not None else Decimal("0")).quantize(Decimal("0.0001"))
