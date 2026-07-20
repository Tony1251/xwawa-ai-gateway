"""支付 Provider 抽象 + Mock 实现"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"


@dataclass
class PaymentOrder:
    order_id: str
    user_id: int
    amount: Decimal
    currency: str = "CNY"
    status: PaymentStatus = PaymentStatus.PENDING
    provider: str = "mock"
    subject: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    paid_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "amount": str(self.amount),
            "currency": self.currency,
            "status": self.status.value,
            "provider": self.provider,
            "subject": self.subject,
            "created_at": self.created_at.isoformat(),
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }


class PaymentProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def create_order(
        self,
        user_id: int,
        amount: Decimal,
        subject: str,
        metadata: dict[str, Any] | None = None,
    ) -> PaymentOrder: ...

    @abstractmethod
    async def query_order(self, order_id: str) -> PaymentOrder: ...

    @abstractmethod
    async def refund(self, order_id: str, reason: str = "") -> bool: ...

    @abstractmethod
    async def callback(self, callback_data: dict[str, Any]) -> PaymentOrder: ...


class MockPaymentProvider(PaymentProvider):
    name = "mock"

    def __init__(self):
        self._orders: dict[str, PaymentOrder] = {}

    async def create_order(
        self,
        user_id: int,
        amount: Decimal,
        subject: str,
        metadata: dict[str, Any] | None = None,
    ) -> PaymentOrder:
        order_id = f"MOCK-{uuid.uuid4().hex[:16].upper()}"
        order = PaymentOrder(
            order_id=order_id,
            user_id=user_id,
            amount=amount,
            currency="CNY",
            status=PaymentStatus.SUCCESS,
            provider="mock",
            subject=subject,
            metadata=metadata or {},
            paid_at=datetime.utcnow(),
        )
        self._orders[order_id] = order
        return order

    async def query_order(self, order_id: str) -> PaymentOrder:
        if order_id not in self._orders:
            raise ValueError(f"订单不存在: {order_id}")
        return self._orders[order_id]

    async def refund(self, order_id: str, reason: str = "") -> bool:
        if order_id not in self._orders:
            return False
        order = self._orders[order_id]
        order.status = PaymentStatus.REFUNDED
        order.updated_at = datetime.utcnow()
        return True

    async def callback(self, callback_data: dict[str, Any]) -> PaymentOrder:
        order_id = callback_data.get("order_id", "")
        return await self.query_order(order_id)


_payment_provider: PaymentProvider | None = None


def get_payment_provider() -> PaymentProvider:
    global _payment_provider
    if _payment_provider is None:
        _payment_provider = MockPaymentProvider()
    return _payment_provider
