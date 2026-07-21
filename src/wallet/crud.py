"""Wallet CRUD 操作"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Agent, ApiKey, Transaction, UsageLog, User, Wallet

# ===== User =====


async def create_user(
    session: AsyncSession,
    email: str,
    password_hash: str,
    *,
    phone: str | None = None,
    nickname: str | None = None,
) -> User:
    """创建用户"""
    user = User(
        email=email,
        phone=phone,
        password_hash=password_hash,
        nickname=nickname,
    )
    session.add(user)
    await session.flush()
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_phone(session: AsyncSession, phone: str) -> User | None:
    result = await session.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


async def update_user(
    session: AsyncSession,
    user_id: int,
    *,
    nickname: str | None = None,
    kyc_level: str | None = None,
    is_active: bool | None = None,
) -> User | None:
    user = await session.get(User, user_id)
    if not user:
        return None
    if nickname is not None:
        user.nickname = nickname
    if kyc_level is not None:
        user.kyc_level = kyc_level  # type: ignore
    if is_active is not None:
        user.is_active = is_active
    user.updated_at = datetime.utcnow()
    await session.flush()
    return user


async def lock_user(session: AsyncSession, user_id: int, reason: str) -> User | None:
    user = await session.get(User, user_id)
    if not user:
        return None
    user.is_locked = True
    user.locked_reason = reason
    user.updated_at = datetime.utcnow()
    await session.flush()
    return user


async def unlock_user(session: AsyncSession, user_id: int) -> User | None:
    user = await session.get(User, user_id)
    if not user:
        return None
    user.is_locked = False
    user.locked_reason = None
    user.updated_at = datetime.utcnow()
    await session.flush()
    return user


# ===== Wallet =====


async def create_wallet(session: AsyncSession, user_id: int) -> Wallet:
    """为用户创建钱包"""
    wallet = Wallet(user_id=user_id)
    session.add(wallet)
    await session.flush()
    return wallet


async def get_wallet_by_user_id(session: AsyncSession, user_id: int) -> Wallet | None:
    result = await session.execute(select(Wallet).where(Wallet.user_id == user_id))
    return result.scalar_one_or_none()


async def update_wallet_balance(
    session: AsyncSession,
    wallet_id: int,
    new_balance: Decimal,
) -> Wallet | None:
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        return None
    wallet.balance = new_balance
    wallet.updated_at = datetime.utcnow()
    await session.flush()
    return wallet


# ===== Transaction =====


async def create_transaction(
    session: AsyncSession,
    wallet_id: int,
    tx_type: str,
    amount: Decimal,
    balance_after: Decimal,
    *,
    reference: str | None = None,
    note: str | None = None,
) -> Transaction:
    """创建交易记录"""
    tx = Transaction(
        wallet_id=wallet_id,
        type=tx_type,
        amount=amount,
        balance_after=balance_after,
        reference=reference,
        note=note,
    )
    session.add(tx)
    await session.flush()
    return tx


async def get_transactions(
    session: AsyncSession,
    wallet_id: int,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Transaction]:
    result = await session.execute(
        select(Transaction)
        .where(Transaction.wallet_id == wallet_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


# ===== ApiKey =====


def generate_api_key(length: int = 43) -> tuple[str, str]:
    """生成 API Key，返回 (raw_key, key_hash)

    raw_key: 用户看到的密钥（只显示一次）
    key_hash: 存储的哈希值（用于验证）
    """
    raw_key = secrets.token_urlsafe(length)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def create_api_key(
    session: AsyncSession,
    user_id: int,
    name: str,
    *,
    scope_chat: bool = True,
    scope_images: bool = True,
    scope_music: bool = False,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """创建 API Key，返回 (ApiKey, raw_key)"""
    raw_key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(
        user_id=user_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
        scope_chat=scope_chat,
        scope_images=scope_images,
        scope_music=scope_music,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.flush()
    return api_key, raw_key


async def get_api_keys(session: AsyncSession, user_id: int) -> Sequence[ApiKey]:
    result = await session.execute(
        select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    )
    return result.scalars().all()


async def get_api_key_by_hash(session: AsyncSession, key_hash: str) -> ApiKey | None:
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    return result.scalar_one_or_none()


async def deactivate_api_key(session: AsyncSession, key_id: int) -> bool:
    result = await session.execute(
        update(ApiKey).where(ApiKey.id == key_id).values(is_active=False)
    )
    await session.flush()
    return result.rowcount > 0


# ===== Agent =====


async def create_agent(
    session: AsyncSession,
    user_id: int,
    did: str,
    name: str,
    agent_type: str,
    *,
    per_call_limit: Decimal = Decimal("0.50"),
    daily_limit: Decimal = Decimal("10"),
) -> Agent:
    agent = Agent(
        user_id=user_id,
        did=did,
        name=name,
        agent_type=agent_type,
        per_call_limit=per_call_limit,
        daily_limit=daily_limit,
    )
    session.add(agent)
    await session.flush()
    return agent


async def get_agents(session: AsyncSession, user_id: int) -> Sequence[Agent]:
    result = await session.execute(
        select(Agent).where(Agent.user_id == user_id).order_by(Agent.created_at.desc())
    )
    return result.scalars().all()


async def get_agent_by_did(session: AsyncSession, did: str) -> Agent | None:
    result = await session.execute(select(Agent).where(Agent.did == did))
    return result.scalar_one_or_none()


async def update_agent(
    session: AsyncSession,
    agent_id: int,
    *,
    name: str | None = None,
    per_call_limit: Decimal | None = None,
    daily_limit: Decimal | None = None,
    is_active: bool | None = None,
) -> Agent | None:
    agent = await session.get(Agent, agent_id)
    if not agent:
        return None
    if name is not None:
        agent.name = name
    if per_call_limit is not None:
        agent.per_call_limit = per_call_limit
    if daily_limit is not None:
        agent.daily_limit = daily_limit
    if is_active is not None:
        agent.is_active = is_active
    await session.flush()
    return agent


# ===== UsageLog =====


async def create_usage_log(
    session: AsyncSession,
    user_id: int,
    provider: str,
    model: str,
    endpoint: str,
    input_tokens: int,
    output_tokens: int,
    cost_provider: Decimal,
    cost_user: Decimal,
    request_id: str,
    *,
    agent_id: int | None = None,
    is_anomalous: bool = False,
    anomaly_reason: str | None = None,
    client_ip: str | None = None,
    duration_ms: int | None = None,
) -> UsageLog:
    log = UsageLog(
        user_id=user_id,
        agent_id=agent_id,
        provider=provider,
        model=model,
        endpoint=endpoint,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_provider=cost_provider,
        cost_user=cost_user,
        is_anomalous=is_anomalous,
        anomaly_reason=anomaly_reason,
        request_id=request_id,
        client_ip=client_ip,
        duration_ms=duration_ms,
    )
    session.add(log)
    await session.flush()
    return log


async def get_usage_logs(
    session: AsyncSession,
    user_id: int,
    limit: int = 100,
    offset: int = 0,
    provider: str | None = None,
    anomalous: bool | None = None,
) -> Sequence[UsageLog]:
    query = select(UsageLog).where(UsageLog.user_id == user_id)
    if provider:
        query = query.where(UsageLog.provider == provider)
    if anomalous is not None:
        query = query.where(UsageLog.is_anomalous == anomalous)
    query = query.order_by(UsageLog.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return result.scalars().all()


# ===== Payment Helpers =====


async def get_or_create_wallet(session: AsyncSession, user_id: int) -> Wallet:
    """获取或创建用户钱包"""
    wallet = await get_wallet_by_user_id(session, user_id)
    if wallet is None:
        wallet = await create_wallet(session, user_id)
    return wallet


async def check_balance(session: AsyncSession, wallet_id: int) -> Decimal:
    """检查钱包余额"""
    wallet = await session.get(Wallet, wallet_id)
    if wallet is None:
        return Decimal("0")
    return wallet.balance


async def deduct_credit(
    session: AsyncSession,
    user_id: int,
    amount: Decimal,
    tx_type: str,
    reference: str,
    description: str = "",
) -> Transaction:
    """扣减信用额度（原子操作）"""
    wallet = await get_or_create_wallet(session, user_id)

    if wallet.balance < amount:
        from ..exceptions import BusinessError

        raise BusinessError(
            f"余额不足: 需要 {amount}, 当前 {wallet.balance}",
            details={"required": str(amount), "available": str(wallet.balance)},
        )

    new_balance = wallet.balance - amount
    await update_wallet_balance(session, wallet.id, new_balance)

    tx = await create_transaction(
        session=session,
        wallet_id=wallet.id,
        tx_type=tx_type,
        amount=-amount,
        balance_after=new_balance,
        reference=reference,
        note=description,
    )
    await session.commit()
    return tx


async def record_usage(
    session: AsyncSession,
    user_id: int,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_provider: Decimal,
    cost_user: Decimal,
    agent_id: int | None,
) -> UsageLog:
    """记录 API 使用量"""
    log = UsageLog(
        user_id=user_id,
        agent_id=agent_id,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_provider=cost_provider,
        cost_user=cost_user,
    )
    session.add(log)
    await session.flush()
    return log
