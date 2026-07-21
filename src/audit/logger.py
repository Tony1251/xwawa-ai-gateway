"""审计日志：记录所有关键业务操作（可观测性）"""

from __future__ import annotations

from typing import Any

from ..logging_config import get_logger

audit_log = get_logger("audit")


class AuditLogger:
    """审计日志记录器

    记录所有关键业务操作，用于：
    - 合规审计
    - 安全分析
    - 用量追踪
    """

    @staticmethod
    def log_auth(user_id: int | None, action: str, success: bool, **kwargs: Any) -> None:
        audit_log.info(
            event="auth",
            user_id=user_id,
            action=action,
            success=success,
            **kwargs,
        )

    @staticmethod
    def log_api_key_created(user_id: int, key_id: int, name: str) -> None:
        audit_log.info(
            event="api_key_create",
            user_id=user_id,
            key_id=key_id,
            name=name,
        )

    @staticmethod
    def log_api_key_used(user_id: int, key_id: int, provider: str, model: str, cost: float) -> None:
        audit_log.info(
            event="api_key_use",
            user_id=user_id,
            key_id=key_id,
            provider=provider,
            model=model,
            cost=cost,
        )

    @staticmethod
    def log_payment(user_id: int, order_id: str, amount: float, status: str) -> None:
        audit_log.info(
            event="payment",
            user_id=user_id,
            order_id=order_id,
            amount=amount,
            status=status,
        )

    @staticmethod
    def log_risk_triggered(user_id: int, reason: str, details: dict[str, Any]) -> None:
        audit_log.warning(
            event="risk_triggered",
            user_id=user_id,
            reason=reason,
            **details,
        )

    @staticmethod
    def log_anomaly(user_id: int, provider: str, reason: str, details: dict[str, Any]) -> None:
        audit_log.warning(
            event="anomaly",
            user_id=user_id,
            provider=provider,
            reason=reason,
            **details,
        )

    @staticmethod
    def log_wallet_update(
        user_id: int, balance_before: float, balance_after: float, tx_type: str
    ) -> None:
        audit_log.info(
            event="wallet_update",
            user_id=user_id,
            balance_before=balance_before,
            balance_after=balance_after,
            tx_type=tx_type,
        )

    @staticmethod
    def log_risk_alert(
        user_id: int,
        risk_level: str,
        risk_score: float,
        factors: list[str],
        **kwargs: Any,
    ) -> None:
        """记录高风险告警"""
        audit_log.error(
            event="risk_alert",
            user_id=user_id,
            risk_level=risk_level,
            risk_score=risk_score,
            factors=factors,
            **kwargs,
        )

    @staticmethod
    def log_batch_anomaly(
        provider: str,
        user_count: int,
        call_count: int,
        reason: str,
        **kwargs: Any,
    ) -> None:
        """记录批量协同攻击异常"""
        audit_log.critical(
            event="batch_anomaly",
            provider=provider,
            user_count=user_count,
            call_count=call_count,
            reason=reason,
            **kwargs,
        )
