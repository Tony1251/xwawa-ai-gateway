"""核心功能单元测试"""
import pytest
from decimal import Decimal

from src.billing.pricing import PricingEngine, CostBreakdown
from src.routing.router import ModelRouter, get_router
from src.providers.base import get_provider
from src.audit.ml_detector import MLAnomalyDetector, SlidingWindowStats, AnomalyResult
from src.wallet.crud import generate_api_key, hash_api_key
from src.payment.providers import PaymentStatus, MockPaymentProvider, PaymentOrder


# ===== Pricing =====

def test_pricing_engine_basic():
    pricing = PricingEngine(markup_rate=1.30, tax_rate=0.06)
    cost = pricing.calculate_provider_cost("openai", "gpt-4o", input_tokens=1_000_000, output_tokens=1_000_000)
    # gpt-4o: input=5, output=15 per 1M → 20 total
    assert cost == Decimal("20.000000")

    user_cost = pricing.calculate_user_cost(cost)
    # 20 * 1.30 * 1.06 = 27.56
    assert user_cost == Decimal("27.5600")


def test_pricing_engine_doubao():
    pricing = PricingEngine(markup_rate=1.30, tax_rate=0.06)
    cost = pricing.calculate_provider_cost("doubao", "doubao-pro-32k", input_tokens=1_000_000, output_tokens=1_000_000)
    # doubao-pro-32k: input=0.001, output=0.005 → 0.006 total
    assert cost == Decimal("0.006000")


def test_pricing_engine_unknown_model():
    pricing = PricingEngine()
    cost = pricing.calculate_provider_cost("openai", "unknown-model-xyz", 1_000_000, 1_000_000)
    # Unknown model defaults to 1.0 per 1M → 2.0 total
    assert cost == Decimal("2.000000")


# ===== Routing =====

def test_router_exact_match():
    router = ModelRouter()
    decision = router.route("gpt-4o")
    assert decision.provider == "openai"
    assert decision.model == "gpt-4o"
    assert decision.reason == "exact_match"


def test_router_prefix_match():
    router = ModelRouter()
    decision = router.route("claude-3-5-sonnet-20241022")
    assert decision.provider == "anthropic"
    assert decision.reason.startswith("prefix_match")


def test_router_list_models():
    router = ModelRouter()
    models = router.list_models("openai")
    assert "gpt-4o" in models
    assert models["gpt-4o"] == "openai"


# ===== API Key =====

def test_generate_api_key():
    raw_key, key_hash, key_prefix = generate_api_key()
    assert len(raw_key) == 57  # 43 base64 chars
    assert len(key_hash) == 64  # sha256 hex
    assert len(key_prefix) == 8
    assert key_prefix == raw_key[:8]


def test_hash_api_key_consistency():
    raw = "test_api_key_12345"
    h1 = hash_api_key(raw)
    h2 = hash_api_key(raw)
    assert h1 == h2
    assert len(h1) == 64


# ===== Anomaly Detection =====

def test_sliding_window_stats():
    sw = SlidingWindowStats(window_size=5)
    sw.add(1.0)
    sw.add(2.0)
    sw.add(3.0)
    assert sw.mean == 2.0
    assert sw.std > 0

def test_anomaly_detector_normal():
    result = MLAnomalyDetector.detect(
        user_id=1,
        provider="openai",
        model="gpt-4o",
        cost_user=0.01,
    )
    assert isinstance(result, AnomalyResult)
    assert result.is_anomalous == False


# ===== Payment =====

@pytest.mark.asyncio
async def test_mock_payment_creates_order():
    provider = MockPaymentProvider()
    order = await provider.create_order(
        user_id=1,
        amount=Decimal("100"),
        subject="测试充值",
    )
    assert order.status == PaymentStatus.SUCCESS
    assert order.amount == Decimal("100")
    assert order.order_id.startswith("MOCK-")


@pytest.mark.asyncio
async def test_mock_payment_query():
    provider = MockPaymentProvider()
    order = await provider.create_order(user_id=1, amount=Decimal("50"), subject="测试")
    queried = await provider.query_order(order.order_id)
    assert queried.order_id == order.order_id


@pytest.mark.asyncio
async def test_mock_payment_refund():
    provider = MockPaymentProvider()
    order = await provider.create_order(user_id=1, amount=Decimal("50"), subject="测试")
    ok = await provider.refund(order.order_id)
    assert ok == True
    refunded = await provider.query_order(order.order_id)
    assert refunded.status == PaymentStatus.REFUNDED


# ===== Integration: Pricing + Routing =====

def test_pricing_and_routing_integration():
    pricing = PricingEngine(markup_rate=1.5, tax_rate=0.0)
    router = ModelRouter()

    for model, expected_provider in [
        ("gpt-4o", "openai"),
        ("claude-3-haiku", "anthropic"),
        ("doubao-pro-32k", "doubao"),
    ]:
        decision = router.route(model)
        assert decision.provider == expected_provider

        # 计算费用（1M input + 1M output）
        cost = pricing.calculate_provider_cost(decision.provider, model, 1_000_000, 1_000_000)
        user_cost = pricing.calculate_user_cost(cost)
        assert user_cost > cost  # 加价后更贵
