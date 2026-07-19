"""API v1 路由汇总"""
from fastapi import APIRouter

from . import auth, chat, wallet, ws, a2a, payment, admin

router = APIRouter()

__all__ = ["router", "auth", "chat", "wallet", "ws", "a2a", "payment", "admin"]
