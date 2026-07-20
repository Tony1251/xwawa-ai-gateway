"""API v1 路由汇总"""

from fastapi import APIRouter

from . import a2a, admin, auth, chat, payment, wallet, ws

router = APIRouter()

__all__ = ["router", "auth", "chat", "wallet", "ws", "a2a", "payment", "admin"]
