"""定价引擎：定义各 Provider/Model 的价格表 + 计算费用"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from ..config import settings


# ===== 价格表（单位：美元 / 1M tokens）=====
PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "chat": {
            "gpt-4o": {"input": 5.0, "output": 15.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4-turbo": {"input": 10.0, "output": 30.0},
            "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        },
        "images": {
            "dall-e-3": {"size_1024": 0.04, "size_1792": 0.08},
            "dall-e-2": {"size_256": 0.016, "size_512": 0.018, "size_1024": 0.02},
        },
    },
    "anthropic": {
        "chat": {
            "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-opus": {"input": 15.0, "output": 75.0},
            "claude-3-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
        },
    },
    "doubao": {
        "chat": {
            "doubao-pro-32k": {"input": 0.001, "output": 0.005},
            "doubao-pro-128k": {"input": 0.003, "output": 0.015},
            "doubao-lite-32k": {"input": 0.0005, "output": 0.002},
        },
    },
    "midjourney": {
        "images": {
            "midjourney-v6": {"standard": 0.04, "turbo": 0.08, "relax": 0.03},
        },
    },
    "deepseek": {
        "chat": {
            "deepseek-chat": {"input": 0.14, "output": 0.28},
            "deepseek-coder": {"input": 0.14, "output": 0.28},
        },
    },
}


@dataclass
class CostBreakdown:
    """费用明细"""
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_provider: Decimal  # 上游成本
    cost_user: Decimal      # 用户支付（含加价）
    markup_rate: float
    currency: str = "USD"


class PricingEngine:
    """定价计算引擎"""

    def __init__(self, markup_rate: float | None = None, tax_rate: float | None = None):
        self.markup_rate = markup_rate if markup_rate is not None else float(settings.markup_rate)
        self.tax_rate = tax_rate if tax_rate is not None else float(settings.tax_rate)

    def get_price(self, provider: str, model: str, token_type: Literal["input", "output"]) -> Decimal:
        """获取指定 provider/model 的单位价格（$/1M tokens）"""
        try:
            prices = PRICING[provider]["chat"][model]
            return Decimal(str(prices[token_type]))
        except KeyError:
            # 默认价格（未知模型）
            return Decimal("1.0")

    def calculate_provider_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Decimal:
        """计算上游成本（美元）"""
        input_price = self.get_price(provider, model, "input")
        output_price = self.get_price(provider, model, "output")

        cost = (
            Decimal(input_tokens) / 1_000_000 * input_price
            + Decimal(output_tokens) / 1_000_000 * output_price
        )
        return cost.quantize(Decimal("0.000001"))

    def calculate_user_cost(self, cost_provider: Decimal) -> Decimal:
        """应用加价倍率计算用户价格（含税）"""
        return (cost_provider * Decimal(str(self.markup_rate)) * Decimal(1 + self.tax_rate)).quantize(
            Decimal("0.0001")
        )

    def calculate(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> CostBreakdown:
        """完整费用计算"""
        cost_provider = self.calculate_provider_cost(provider, model, input_tokens, output_tokens)
        cost_user = self.calculate_user_cost(cost_provider)
        return CostBreakdown(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_provider=cost_provider,
            cost_user=cost_user,
            markup_rate=self.markup_rate,
        )
