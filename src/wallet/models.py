"""Wallet 数据模型（与 alembic 迁移保持一致）"""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """所有模型的基类"""
    pass


class KycLevel(str, enum.Enum):
    """KYC 等级"""
    NONE = "none"
    PHONE = "phone"
    ID_CARD = "id_card"
    FULL = "full"
    ENTERPRISE = "enterprise"


class TransactionType(str, enum.Enum):
    """交易类型"""
    RECHARGE = "recharge"           # 充值
    CONSUME = "consume"             # 消费
    REFUND = "refund"               # 退款
    CREDIT_grant = "credit_grant"   # 授信
    CREDIT_REPAY = "credit_repay"   # 还款
    BONUS = "bonus"                 # 赠送


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kyc_level: Mapped[KycLevel] = mapped_column(
        Enum(KycLevel, name="kyclevel", create_type=False),
        nullable=False,
        default=KycLevel.NONE,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    wallet: Mapped[Wallet | None] = relationship("Wallet", back_populates="user", uselist=False)
    api_keys: Mapped[list[ApiKey]] = relationship("ApiKey", back_populates="user")
    agents: Mapped[list[Agent]] = relationship("Agent", back_populates="user")
    usage_logs: Mapped[list[UsageLog]] = relationship("UsageLog", back_populates="user")


class Wallet(Base):
    """钱包表"""
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"))
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"))
    used_this_month: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"))
    daily_limit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("10"))
    per_call_limit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0.50"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="wallet")
    transactions: Mapped[list[Transaction]] = relationship("Transaction", back_populates="wallet")


class Transaction(Base):
    """交易记录表"""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    wallet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("wallets.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    wallet: Mapped[Wallet] = relationship("Wallet", back_populates="transactions")

    __table_args__ = (
        Index("ix_transactions_wallet_id", "wallet_id"),
        Index("ix_transactions_created_at", "created_at"),
        Index("ix_transactions_type", "type"),
    )


class ApiKey(Base):
    """API Key 表"""
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_chat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scope_images: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scope_music: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_user_id", "user_id"),
        Index("ix_api_keys_key_prefix", "key_prefix"),
    )


class Agent(Base):
    """Agent 表"""
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    did: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    per_call_limit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0.50"))
    daily_limit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("10"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="agents")
    usage_logs: Mapped[list[UsageLog]] = relationship("UsageLog", back_populates="agent")

    __table_args__ = (
        Index("ix_agents_user_id", "user_id"),
        Index("ix_agents_did", "did", unique=True),
    )


class UsageLog(Base):
    """用量日志表"""
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("agents.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_provider: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    cost_user: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    is_anomalous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    anomaly_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="usage_logs")
    agent: Mapped[Agent | None] = relationship("Agent", back_populates="usage_logs")

    __table_args__ = (
        Index("ix_usage_logs_user_id", "user_id"),
        Index("ix_usage_logs_agent_id", "agent_id"),
        Index("ix_usage_logs_provider", "provider"),
        Index("ix_usage_logs_created_at", "created_at"),
        Index("ix_usage_logs_anomalous", "is_anomalous"),
        Index("ix_usage_logs_request_id", "request_id"),
    )
