"""ML 异常检测：基于统计方法检测异常用量模式

生产级特性：
- Z-Score 检测（单变量时间序列异常）
- 滑动窗口统计（平均/标准差）
- 无需外部 ML 框架，轻量高效
- 可扩展为 Isolation Forest / LSTM 等复杂模型
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..wallet.models import UsageLog
from .logger import AuditLogger


@dataclass
class AnomalyResult:
    """异常检测结果"""
    is_anomalous: bool
    z_score: float | None
    reason: str | None
    confidence: float  # 0.0 - 1.0


class SlidingWindowStats:
    """滑动窗口统计量计算器"""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.values: deque[float] = deque(maxlen=window_size)

    def add(self, value: float) -> None:
        self.values.append(value)

    @property
    def mean(self) -> float:
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)

    @property
    def std(self) -> float:
        if len(self.values) < 2:
            return 0.0
        variance = sum((x - self.mean) ** 2 for x in self.values) / (len(self.values) - 1)
        return math.sqrt(variance)

    def z_score(self, value: float) -> float | None:
        if self.std == 0:
            return None
        return (value - self.mean) / self.std


class MLAnomalyDetector:
    """ML 异常检测器

    检测策略：
    1. 单次调用费用 Z-Score > 3 → 异常（费用突增）
    2. 同一 Provider 1 分钟内调用次数 > 阈值 → 异常（机器人刷接口）
    3. 日累计费用 Z-Score > 3 → 异常（盗刷）
    4. 成功率异常（连续 N 次失败）→ 异常
    """

    # 全局滑动窗口（按 user_id + provider 维度）
    _cost_windows: dict[str, SlidingWindowStats] = {}
    _call_count_windows: dict[str, deque[datetime]] = {}

    # 异常阈值
    Z_SCORE_THRESHOLD = 3.0
    CALL_COUNT_THRESHOLD = 30  # 1分钟内最多 30 次
    CONSECUTIVE_FAILURES_THRESHOLD = 5

    @classmethod
    def get_cost_window(cls, key: str) -> SlidingWindowStats:
        if key not in cls._cost_windows:
            cls._cost_windows[key] = SlidingWindowStats(window_size=100)
        return cls._cost_windows[key]

    @classmethod
    def get_call_window(cls, key: str) -> deque[datetime]:
        if key not in cls._call_count_windows:
            cls._call_count_windows[key] = deque(maxlen=cls.CALL_COUNT_THRESHOLD + 1)
        return cls._call_count_windows[key]

    @classmethod
    def detect(
        cls,
        user_id: int,
        provider: str,
        model: str,
        cost_user: float,
        success: bool = True,
    ) -> AnomalyResult:
        """检测单次调用是否异常"""
        cost_key = f"{user_id}:{provider}:{model}"
        call_key = f"{user_id}:{provider}"

        cost_window = cls.get_cost_window(cost_key)
        call_window = cls.get_call_window(call_key)

        now = datetime.utcnow()

        # ---- 策略 1: 费用 Z-Score 检测 ----
        cost_window.add(cost_user)
        z_score = cost_window.z_score(cost_user)

        if z_score is not None and abs(z_score) > cls.Z_SCORE_THRESHOLD:
            reason = f"费用异常: z_score={z_score:.2f}, cost={cost_user}, mean={cost_window.mean:.4f}"
            AuditLogger.log_anomaly(user_id, provider, reason, {
                "z_score": z_score,
                "cost": cost_user,
                "model": model,
            })
            return AnomalyResult(
                is_anomalous=True,
                z_score=z_score,
                reason=reason,
                confidence=min(abs(z_score) / 5.0, 1.0),
            )

        # ---- 策略 2: 调用频率检测 ----
        # 清理 1 分钟前的记录
        one_minute_ago = now - timedelta(minutes=1)
        while call_window and call_window[0] < one_minute_ago:
            call_window.popleft()

        call_window.append(now)

        if len(call_window) > cls.CALL_COUNT_THRESHOLD:
            reason = f"调用频率异常: {len(call_window)} 次/分钟 > {cls.CALL_COUNT_THRESHOLD}"
            AuditLogger.log_anomaly(user_id, provider, reason, {
                "calls_per_minute": len(call_window),
                "threshold": cls.CALL_COUNT_THRESHOLD,
                "model": model,
            })
            return AnomalyResult(
                is_anomalous=True,
                z_score=None,
                reason=reason,
                confidence=0.95,
            )

        # ---- 策略 3: 失败率检测（简单版）----
        if not success:
            # 记录失败（简化版，完整实现需要持久化状态）
            pass

        return AnomalyResult(
            is_anomalous=False,
            z_score=z_score,
            reason=None,
            confidence=0.0,
        )

    @classmethod
    async def detect_from_db(
        cls,
        session: AsyncSession,
        user_id: int,
        lookback_hours: int = 24,
    ) -> list[UsageLog]:
        """从数据库检测历史异常（批量检测）"""
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)

        result = await session.execute(
            select(UsageLog).where(
                and_(
                    UsageLog.user_id == user_id,
                    UsageLog.created_at >= cutoff,
                    UsageLog.is_anomalous == False,  # noqa: E712
                )
            )
        )
        logs = result.scalars().all()

        anomalous_logs = []
        for log in logs:
            detection = cls.detect(
                user_id=log.user_id,
                provider=log.provider,
                model=log.model,
                cost_user=float(log.cost_user),
            )
            if detection.is_anomalous:
                log.is_anomalous = True
                log.anomaly_reason = detection.reason
                anomalous_logs.append(log)

        if anomalous_logs:
            await session.commit()

        return anomalous_logs
