"""API v1 共享 Pydantic Schemas"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


# ===== 通用 =====
class ApiResponse(BaseModel):
    code: str = "SUCCESS"
    message: str = "OK"
    data: Any = None


# ===== Auth =====
class RegisterRequest(BaseModel):
    email: str = Field(..., format="email")
    password: str = Field(..., min_length=8)
    nickname: str | None = None
    phone: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ===== Wallet =====
class WalletResponse(BaseModel):
    balance: Decimal
    credit_limit: Decimal
    used_this_month: Decimal
    daily_limit: Decimal
    per_call_limit: Decimal

    class Config:
        from_attributes = True


class RechargeRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)


class RechargeResponse(BaseModel):
    order_id: str
    amount: Decimal
    status: str


class TransactionResponse(BaseModel):
    id: int
    type: str
    amount: Decimal
    balance_after: Decimal
    reference: str | None
    note: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ===== API Key =====
class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    scope_chat: bool = True
    scope_images: bool = True
    scope_music: bool = False
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: int
    key_prefix: str
    name: str
    scope_chat: bool
    scope_images: bool
    scope_music: bool
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class CreateApiKeyResponse(BaseModel):
    id: int
    name: str
    api_key: str  # raw key, only shown once
    key_prefix: str


# ===== Agent =====
class CreateAgentRequest(BaseModel):
    did: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=64)
    agent_type: str = Field(..., min_length=1, max_length=32)
    per_call_limit: Decimal = Decimal("0.50")
    daily_limit: Decimal = Decimal("10")


class AgentResponse(BaseModel):
    id: int
    did: str
    name: str
    agent_type: str
    per_call_limit: Decimal
    daily_limit: Decimal
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Chat =====
class ChatRequest(BaseModel):
    model: str = Field(..., description="模型名，如 gpt-4o")
    messages: list[dict[str, str]] = Field(..., description="消息列表")
    temperature: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=1, le=128000)
    stream: bool = False


class ChatResponse(BaseModel):
    id: str
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    cost_user: Decimal
    cost_provider: Decimal
    provider: str


# ===== Payment =====
class CreatePaymentOrderRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    subject: str = Field(..., min_length=1, max_length=256)
    metadata: dict[str, Any] | None = None


class PaymentOrderResponse(BaseModel):
    order_id: str
    amount: Decimal
    currency: str
    status: str
    provider: str
    subject: str
    created_at: datetime
    paid_at: datetime | None


class PaymentCallbackRequest(BaseModel):
    order_id: str
    status: str
    signature: str | None = None


# ===== Usage =====
class UsageLogResponse(BaseModel):
    id: int
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_provider: Decimal
    cost_user: Decimal
    is_anomalous: bool
    anomaly_reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ===== A2A =====
class A2ARequestSchema(BaseModel):
    from_did: str
    to_did: str
    service: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    amount: float = 0.0


class A2AResponseSchema(BaseModel):
    success: bool
    result: Any = None
    error: str = ""
    payment_confirmation: dict[str, Any] = Field(default_factory=dict)
