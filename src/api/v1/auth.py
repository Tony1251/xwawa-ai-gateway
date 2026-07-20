"""认证路由：注册 / 登录 / JWT / API Key"""

from __future__ import annotations

from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...db import get_db
from ...wallet.crud import (
    create_api_key,
    create_user,
    create_wallet,
    deactivate_api_key,
    get_api_key_by_hash,
    get_api_keys,
    get_user_by_email,
    hash_api_key,
)
from ...wallet.models import User
from .schemas import (
    ApiKeyResponse,
    ApiResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode()


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    expire = datetime.utcnow() + (
        expires_delta or timedelta(hours=settings.jwt_access_token_expire_hours)
    )
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的 Token") from None


def _extract_bearer_token(request: Request) -> str | None:
    """从 Authorization: Bearer <token> header 提取 token"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT 或 API Key 获取当前用户"""
    token = _extract_bearer_token(request)
    api_key = request.headers.get("X-API-Key", "")

    if token:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="无效的 Token 类型")
        user_id = int(payload["sub"])
        from ...wallet.crud import get_user_by_id

        user = await get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="用户不存在或已禁用")
        if user.is_locked:
            raise HTTPException(status_code=403, detail=f"账户已锁定: {user.locked_reason}")
        return user

    if api_key:
        key_hash = hash_api_key(api_key)
        api_key_obj = await get_api_key_by_hash(db, key_hash)
        if not api_key_obj or not api_key_obj.is_active:
            raise HTTPException(status_code=401, detail="无效的 API Key")
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="API Key 已过期")
        api_key_obj.last_used_at = datetime.utcnow()
        await db.commit()
        from ...wallet.crud import get_user_by_id

        user = await get_user_by_id(db, api_key_obj.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="用户不存在或已禁用")
        return user

    raise HTTPException(status_code=401, detail="未提供认证凭证")


@router.post("/register", response_model=ApiResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    existing = await get_user_by_email(db, req.email)
    if existing:
        raise HTTPException(status_code=409, detail="邮箱已被注册")

    user = await create_user(
        db,
        email=req.email,
        password_hash=hash_password(req.password),
        phone=req.phone,
        nickname=req.nickname,
    )
    await create_wallet(db, user_id=user.id)
    await db.commit()

    return ApiResponse(data={"user_id": user.id, "email": user.email})


@router.post("/login", response_model=ApiResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录（获取 JWT）"""
    user = await get_user_by_email(db, req.email)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    if user.is_locked:
        raise HTTPException(status_code=403, detail=f"账户已锁定: {user.locked_reason}")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return ApiResponse(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_expire_hours * 3600,
        )
    )


@router.post("/refresh", response_model=ApiResponse)
async def refresh_token(req: dict, db: AsyncSession = Depends(get_db)):
    """刷新 Access Token"""
    refresh = req.get("refresh_token")
    if not refresh:
        raise HTTPException(status_code=400, detail="refresh_token 为空")

    payload = decode_token(refresh)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="无效的 Refresh Token")

    user_id = int(payload["sub"])
    from ...wallet.crud import get_user_by_id

    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    new_access = create_access_token(user.id)
    return ApiResponse(data={"access_token": new_access, "token_type": "bearer"})


@router.post("/api-keys", response_model=ApiResponse)
async def create_key(
    req: CreateApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建 API Key"""
    api_key_obj, raw_key = await create_api_key(
        db,
        user_id=current_user.id,
        name=req.name,
        scope_chat=req.scope_chat,
        scope_images=req.scope_images,
        scope_music=req.scope_music,
        expires_at=req.expires_at,
    )
    await db.commit()
    return ApiResponse(
        data=CreateApiKeyResponse(
            id=api_key_obj.id,
            name=api_key_obj.name,
            api_key=raw_key,
            key_prefix=api_key_obj.key_prefix,
        )
    )


@router.get("/api-keys", response_model=ApiResponse)
async def list_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的 API Keys"""
    keys = await get_api_keys(db, current_user.id)
    return ApiResponse(data=[ApiKeyResponse.model_validate(k) for k in keys])


@router.delete("/api-keys/{key_id}", response_model=ApiResponse)
async def delete_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除 API Key"""
    ok = await deactivate_api_key(db, key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    await db.commit()
    return ApiResponse(data={"deleted": True})
