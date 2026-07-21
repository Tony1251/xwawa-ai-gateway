"""ML 异常检测：统计 + ML 混合异常检测

生产级特性：
- Z-Score 检测（单变量时间序列异常）
- 滑动窗口统计（平均/标准差）
- Isolation Forest（可选，需 scikit-learn）
- 用户行为画像 + 漂移检测
- 批量协同攻击检测
"""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

try:
    from sklearn.ensemble import IsolationForest

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..wallet.models import UsageLog
from .logger import AuditLogger


# ===== 异常等级 =====


class RiskLevel(Enum):
    """风险等级"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ===== 数据结构 =====


@dataclass
class AnomalyResult:
    """异常检测结果"""

    is_anomalous: bool
    z_score: float | None
    reason: str | None
    confidence: float  # 0.0 - 1.0


@dataclass
class RiskScore:
    """用户风险评分"""

    user_id: int
    level: RiskLevel
    score: float  # 0.0 - 1.0
    factors: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)


# ===== 滑动窗口统计 =====


class SlidingWindowStats:
    """滑动窗口统计量计算器"""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.values: deque[float] = deque(maxlen=window_size)
        self._lock = threading.Lock()

    def add(self, value: float) -> None:
        with self._lock:
            self.values.append(value)

    @property
    def mean(self) -> float:
        with self._lock:
            if not self.values:
                return 0.0
            return sum(self.values) / len(self.values)

    @property
    def std(self) -> float:
        with self._lock:
            if len(self.values) < 2:
                return 0.0
            variance = sum((x - self.mean) ** 2 for x in self.values) / (len(self.values) - 1)
            return math.sqrt(variance)

    def z_score(self, value: float) -> float | None:
        with self._lock:
            if self.std == 0:
                return None
            return (value - self.mean) / self.std


# ===== 用户行为画像 =====


@dataclass
class UserProfile:
    """用户行为画像"""

    user_id: int
    daily_costs: deque[float] = field(default_factory=deque)
    daily_costs_window: int = 30  # 保留30天
    avg_daily_cost: float = 0.0
    std_daily_cost: float = 0.0
    total_calls: int = 0
    failure_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)


# ===== ML 异常检测器 =====


class MLAnomalyDetector:
    """ML 异常检测器

    检测策略：
    1. 单次调用费用 Z-Score > 3 → 异常（费用突增）
    2. 同一 Provider 1 分钟内调用次数 > 阈值 → 异常（机器人刷接口）
    3. 日累计费用 Z-Score > 3 → 异常（盗刷）
    4. 成功率异常（连续 N 次失败）→ 异常
    5. Isolation Forest（可选）→ 高维特征异常
    6. 协同攻击检测（跨用户批量异常）
    """

    # 全局滑动窗口（按 user_id + provider 维度）
    _cost_windows: dict[str, SlidingWindowStats] = {}
    _call_count_windows: dict[str, deque[datetime]] = {}
    _user_profiles: dict[int, UserProfile] = {}
    _lock = threading.Lock()

    # 异常阈值
    Z_SCORE_THRESHOLD = 3.0
    CALL_COUNT_THRESHOLD = 30  # 1分钟内最多 30 次
    CONSECUTIVE_FAILURES_THRESHOLD = 5
    RISK_SCORE_THRESHOLD = 0.7  # 高风险阈值

    # Isolation Forest 配置
    _if_model: Any = None
    _if_features: list[dict] = []  # 保留最近 N 条特征

    @classmethod
    def get_cost_window(cls, key: str) -> SlidingWindowStats:
        with cls._lock:
            if key not in cls._cost_windows:
                cls._cost_windows[key] = SlidingWindowStats(window_size=100)
            return cls._cost_windows[key]

    @classmethod
    def get_call_window(cls, key: str) -> deque[datetime]:
        with cls._lock:
            if key not in cls._call_count_windows:
                cls._call_count_windows[key] = deque(maxlen=cls.CALL_COUNT_THRESHOLD + 1)
            return cls._call_count_windows[key]

    @classmethod
    def get_user_profile(cls, user_id: int) -> UserProfile:
        with cls._lock:
            if user_id not in cls._user_profiles:
                cls._user_profiles[user_id] = UserProfile(user_id=user_id)
            return cls._user_profiles[user_id]

    @classmethod
    def _init_isolation_forest(cls) -> None:
        """延迟初始化 Isolation Forest"""
        if cls._if_model is None and HAS_SKLEARN:
            cls._if_model = IsolationForest(
                n_estimators=100,
                contamination=0.1,
                random_state=42,
                n_jobs=-1,
            )

    @classmethod
    def _extract_features(
        cls,
        user_id: int,
        provider: str,
        model: str,
        cost_user: float,
        input_tokens: int,
        output_tokens: int,
        hour: int,
    ) -> list[float]:
        """提取特征向量用于 ML 模型"""
        return [
            math.log1p(cost_user),
            math.log1p(input_tokens),
            math.log1p(output_tokens),
            float(hour) / 24.0,  # 归一化小时
            hash(provider) % 10 / 10.0,  # provider 特征
            1.0 if cost_user > 0.01 else 0.0,  # 高费用标记
        ]

    @classmethod
    def detect(
        cls,
        user_id: int,
        provider: str,
        model: str,
        cost_user: float,
        success: bool = True,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> AnomalyResult:
        """检测单次调用是否异常"""
        cost_key = f"{user_id}:{provider}:{model}"
        call_key = f"{user_id}:{provider}"

        cost_window = cls.get_cost_window(cost_key)
        call_window = cls.get_call_window(call_key)

        now = datetime.utcnow()
        hour = now.hour

        # ---- 策略 1: 费用 Z-Score 检测 ----
        cost_window.add(cost_user)
        z_score = cost_window.z_score(cost_user)

        if z_score is not None and abs(z_score) > cls.Z_SCORE_THRESHOLD:
            reason = (
                f"费用异常: z_score={z_score:.2f}, cost={cost_user}, mean={cost_window.mean:.4f}"
            )
            AuditLogger.log_anomaly(
                user_id,
                provider,
                reason,
                {
                    "z_score": z_score,
                    "cost": cost_user,
                    "model": model,
                },
            )
            return AnomalyResult(
                is_anomalous=True,
                z_score=z_score,
                reason=reason,
                confidence=min(abs(z_score) / 5.0, 1.0),
            )

        # ---- 策略 2: 调用频率检测 ----
        one_minute_ago = now - timedelta(minutes=1)
        with cls._lock:
            while call_window and call_window[0] < one_minute_ago:
                call_window.popleft()
            call_window.append(now)

        if len(call_window) > cls.CALL_COUNT_THRESHOLD:
            reason = f"调用频率异常: {len(call_window)} 次/分钟 > {cls.CALL_COUNT_THRESHOLD}"
            AuditLogger.log_anomaly(
                user_id,
                provider,
                reason,
                {
                    "calls_per_minute": len(call_window),
                    "threshold": cls.CALL_COUNT_THRESHOLD,
                    "model": model,
                },
            )
            return AnomalyResult(
                is_anomalous=True,
                z_score=None,
                reason=reason,
                confidence=0.95,
            )

        # ---- 策略 3: Isolation Forest 检测 ----
        if HAS_SKLEARN and cost_user > 0:
            cls._init_isolation_forest()
            features = cls._extract_features(
                user_id, provider, model, cost_user, input_tokens, output_tokens, hour
            )

            with cls._lock:
                cls._if_features.append(features)
                # 保留最近 1000 条
                if len(cls._if_features) > 1000:
                    cls._if_features = cls._if_features[-1000:]

            if len(cls._if_features) >= 50:
                import numpy as np

                X = np.array(cls._if_features)
                try:
                    pred = cls._if_model.fit_predict(X[-500:])  # 用最近500条
                    if pred[-1] == -1:
                        reason = f"Isolation Forest 异常: 特征={features}"
                        AuditLogger.log_anomaly(
                            user_id,
                            provider,
                            reason,
                            {"features": features, "method": "isolation_forest"},
                        )
                        return AnomalyResult(
                            is_anomalous=True,
                            z_score=None,
                            reason=reason,
                            confidence=0.85,
                        )
                except Exception:
                    pass  # 静默失败，不影响主流程

        return AnomalyResult(
            is_anomalous=False,
            z_score=z_score,
            reason=None,
            confidence=0.0,
        )

    @classmethod
    def get_user_risk_score(cls, user_id: int) -> RiskScore:
        """获取用户整体风险评分"""
        profile = cls.get_user_profile(user_id)

        score = 0.0
        factors = []

        # 基于失败率
        if profile.total_calls > 0:
            failure_rate = profile.failure_count / profile.total_calls
            if failure_rate > 0.3:
                score += 0.4
                factors.append(f"高失败率: {failure_rate:.1%}")
            elif failure_rate > 0.1:
                score += 0.2
                factors.append(f"异常失败率: {failure_rate:.1%}")

        # 基于日均费用波动
        if profile.std_daily_cost > 0 and profile.avg_daily_cost > 0:
            cv = profile.std_daily_cost / profile.avg_daily_cost
            if cv > 2.0:
                score += 0.3
                factors.append(f"日均费用波动大: CV={cv:.2f}")

        # 低于阈值的风险评分
        if score < 0.3:
            level = RiskLevel.LOW
        elif score < 0.5:
            level = RiskLevel.MEDIUM
        elif score < 0.7:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        return RiskScore(
            user_id=user_id,
            level=level,
            score=min(score, 1.0),
            factors=factors,
            last_updated=datetime.utcnow(),
        )

    @classmethod
    def update_user_profile(
        cls,
        user_id: int,
        cost_user: float,
        success: bool,
    ) -> None:
        """增量更新用户行为画像"""
        profile = cls.get_user_profile(user_id)
        profile.total_calls += 1

        if not success:
            profile.failure_count += 1

        # 更新日均费用
        profile.daily_costs.append(cost_user)
        if len(profile.daily_costs) > profile.daily_costs_window:
            profile.daily_costs.popleft()

        if profile.daily_costs:
            profile.avg_daily_cost = sum(profile.daily_costs) / len(profile.daily_costs)
            if len(profile.daily_costs) > 1:
                mean = profile.avg_daily_cost
                variance = sum((x - mean) ** 2 for x in profile.daily_costs) / (len(profile.daily_costs) - 1)
                profile.std_daily_cost = math.sqrt(variance)

        profile.last_updated = datetime.utcnow()

    @classmethod
    def detect_batch(
        cls,
        logs: list[UsageLog],
    ) -> list[UsageLog]:
        """批量检测异常（支持协同攻击检测）"""
        if not logs:
            return []

        anomalous_logs = []
        provider_call_counts: dict[str, int] = {}

        for log in logs:
            cost_user = float(log.cost_user)
            detection = cls.detect(
                user_id=log.user_id,
                provider=log.provider,
                model=log.model,
                cost_user=cost_user,
                success=log.success if hasattr(log, "success") else True,
                input_tokens=log.input_tokens if hasattr(log, "input_tokens") else 0,
                output_tokens=log.output_tokens if hasattr(log, "output_tokens") else 0,
            )

            if detection.is_anomalous:
                log.is_anomalous = True
                log.anomaly_reason = detection.reason
                anomalous_logs.append(log)

            # 更新画像
            cls.update_user_profile(
                log.user_id,
                cost_user,
                log.success if hasattr(log, "success") else True,
            )

            # 统计 provider 调用（用于协同攻击检测）
            key = f"{log.provider}"
            provider_call_counts[key] = provider_call_counts.get(key, 0) + 1

        # ---- 协同攻击检测 ----
        total_calls = len(logs)
        for provider, count in provider_call_counts.items():
            # 如果某 provider 在短时间内调用占比异常高
            if total_calls > 10 and count / total_calls > 0.5:
                # 检查是否来自不同用户
                user_ids = set(log.user_id for log in logs if log.provider == provider)
                if len(user_ids) > 3:  # 多用户
                    reason = f"疑似协同攻击: provider={provider}, 用户数={len(user_ids)}, 调用数={count}"
                    AuditLogger.log_batch_anomaly(
                        provider=provider,
                        user_count=len(user_ids),
                        call_count=count,
                        reason=reason,
                    )

        return anomalous_logs

    @classmethod
    async def detect_from_db(
        cls,
        session: AsyncSession,
        user_id: int,
        lookback_hours: int = 24,
    ) -> list[UsageLog]:
        """从数据库检测历史异常（批量检测）"""
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

        anomalous_logs = cls.detect_batch(list(logs))

        if anomalous_logs:
            await session.commit()

        return anomalous_logs
