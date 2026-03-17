"""
Test Suite: health.py + payment.py + market_trends.py schemas
Place at: backend/tests/test_health_payment_market_schemas.py
Run: pytest backend/tests/test_health_payment_market_schemas.py -v
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.health import HealthResponse
from schemas.market_trends import (
    CategorySchema,
    MarketTrendsRequest,
    MarketTrendsResponse,
    TrendCategoriesResponse,
    TrendingProductSchema,
    TrendSourcesResponse,
)
from schemas.payment import (
    ConfirmPaymentRequest,
    ConfirmPaymentResponse,
    PaymentError,
    PaymentHistoryResponse,
    PaymentInfo,
    PaymentRequest,
    PlanInfo,
    PlanListResponse,
    SubscribeRequest,
    SubscriptionInfo,
    TransactionVerification,
)

NOW = datetime.now(UTC)


# =====================================================================
# HealthResponse
# =====================================================================


class TestHealthResponse:
    def test_valid(self):
        h = HealthResponse(
            status="ok",
            api="SSP",
            version="1.0.0",
            database="connected",
            uptime_seconds=12345.67,
            timestamp_utc="2026-02-08T12:00:00Z",
        )
        assert h.status == "ok"

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            HealthResponse(status="ok", api="SSP")


# =====================================================================
# Payment – Plans
# =====================================================================


class TestPlanInfo:
    def test_valid(self):
        p = PlanInfo(
            tier="starter",
            name="Starter Plan",
            price_monthly=149.0,
            price_yearly=1490.0,
            product_limit=50,
            features=["Sentiment Analysis", "Competitor Tracking"],
        )
        assert p.tier == "starter"
        assert len(p.features) == 2

    def test_plan_list_response(self):
        r = PlanListResponse(
            plans=[
                PlanInfo(
                    tier="starter",
                    name="Starter",
                    price_monthly=149,
                    price_yearly=1490,
                    product_limit=50,
                    features=[],
                )
            ]
        )
        assert r.plans[0].tier == "starter"


# =====================================================================
# Payment – Subscription
# =====================================================================


class TestSubscription:
    def test_subscription_info(self):
        s = SubscriptionInfo(
            tier="professional",
            status="active",
            current_period_start=NOW,
            current_period_end=NOW,
            product_limit=200,
            products_used=45,
        )
        assert s.products_used == 45

    def test_subscription_info_defaults(self):
        s = SubscriptionInfo(
            tier="starter",
            status="active",
            product_limit=50,
        )
        assert s.products_used == 0
        assert s.current_period_start is None

    def test_subscribe_request_defaults(self):
        r = SubscribeRequest(tier="starter")
        assert r.billing_cycle == "monthly"
        assert r.network == "bsv"

    def test_subscribe_request_ethereum(self):
        r = SubscribeRequest(tier="enterprise", billing_cycle="yearly", network="ethereum")
        assert r.network == "ethereum"

    def test_subscribe_request_invalid_network(self):
        with pytest.raises(ValidationError):
            SubscribeRequest(tier="starter", network="bitcoin")


# =====================================================================
# Payment – PaymentRequest / PaymentInfo
# =====================================================================


class TestPaymentSchemas:
    def test_payment_request(self):
        p = PaymentRequest(
            payment_id="pay_123",
            amount="149.00",
            amount_raw=14900,
            recipient_address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            memo="SSP-starter-monthly",
            expires_at=NOW,
        )
        assert p.currency == "MNEE"
        assert p.network == "bsv"
        assert "bsv" in p.network_options

    def test_payment_info_minimal(self):
        p = PaymentInfo(
            id="pay_123",
            amount="149.00",
            status="pending",
            payment_type="subscription",
            created_at=NOW,
        )
        assert p.transaction_hash is None
        assert p.network is None

    def test_payment_info_full(self):
        p = PaymentInfo(
            id="pay_456",
            amount="299.00",
            status="confirmed",
            payment_type="subscription",
            created_at=NOW,
            transaction_hash="0xabc123",
            network="ethereum",
        )
        assert p.network == "ethereum"

    def test_payment_history(self):
        r = PaymentHistoryResponse(
            payments=[],
            total=0,
            limit=20,
            offset=0,
        )
        assert r.total == 0


# =====================================================================
# Payment – Confirmation
# =====================================================================


class TestPaymentConfirmation:
    def test_confirm_request_minimal(self):
        r = ConfirmPaymentRequest(transaction_hash="0xabc123")
        assert r.network == "bsv"
        assert r.from_address is None

    def test_confirm_request_full(self):
        r = ConfirmPaymentRequest(
            transaction_hash="0xabc123",
            network="ethereum",
            from_address="0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
        )
        assert r.network == "ethereum"

    def test_confirm_response_defaults(self):
        r = ConfirmPaymentResponse(success=True, message="Payment confirmed")
        assert r.verified_on_chain is False
        assert r.payment_id is None

    def test_confirm_response_full(self):
        r = ConfirmPaymentResponse(
            success=True,
            message="Verified on chain",
            payment_id="pay_123",
            payment_status="confirmed",
            subscription_tier="professional",
            subscription_status="active",
            verified_on_chain=True,
        )
        assert r.verified_on_chain is True


# =====================================================================
# Payment – Transaction Verification
# =====================================================================


class TestTransactionVerification:
    def test_minimal(self):
        t = TransactionVerification(
            verified=True,
            transaction_hash="0xabc",
            network="bsv",
        )
        assert t.confirmations == 0
        assert t.amount is None

    def test_full(self):
        t = TransactionVerification(
            verified=True,
            transaction_hash="0xabc",
            network="ethereum",
            amount="149.00",
            amount_raw=14900,
            from_address="0x123",
            to_address="0x456",
            memo="SSP-pay",
            confirmations=12,
            block_height=19000000,
            timestamp=NOW,
        )
        assert t.confirmations == 12

    def test_failed_verification(self):
        t = TransactionVerification(
            verified=False,
            transaction_hash="0xbad",
            network="bsv",
            error="Transaction not found",
        )
        assert t.error == "Transaction not found"


# =====================================================================
# Payment – Error
# =====================================================================


class TestPaymentError:
    def test_valid(self):
        e = PaymentError(
            error="Insufficient funds",
            code="INSUFFICIENT_FUNDS",
        )
        assert e.details is None

    def test_with_details(self):
        e = PaymentError(
            error="Rate limited",
            code="RATE_LIMIT",
            details={"retry_after": 60},
        )
        assert e.details["retry_after"] == 60


# =====================================================================
# Market Trends – TrendingProductSchema
# =====================================================================


class TestTrendingProductSchema:
    def test_valid(self):
        t = TrendingProductSchema(
            rank=1,
            name="Smart Watch X",
            category="Wearables",
            price_range="$200-$350",
            trend_score=85.5,
            sentiment="positive",
            source="Amazon",
            reason="Viral TikTok review",
        )
        assert t.rank == 1
        assert t.image_url is None

    def test_trend_score_range(self):
        with pytest.raises(ValidationError):
            TrendingProductSchema(
                rank=1,
                name="X",
                category="Y",
                price_range="$10",
                trend_score=101,
                sentiment="positive",
                source="Amazon",
                reason="test",
            )

    def test_trend_score_below_zero(self):
        with pytest.raises(ValidationError):
            TrendingProductSchema(
                rank=1,
                name="X",
                category="Y",
                price_range="$10",
                trend_score=-1,
                sentiment="positive",
                source="Amazon",
                reason="test",
            )


# =====================================================================
# Market Trends – Request / Response
# =====================================================================


class TestMarketTrendsRequest:
    def test_defaults(self):
        r = MarketTrendsRequest()
        assert r.category is None
        assert r.source is None
        assert r.limit == 10

    def test_custom(self):
        r = MarketTrendsRequest(category="Electronics", source="tiktok", limit=25)
        assert r.limit == 25

    def test_limit_max(self):
        with pytest.raises(ValidationError):
            MarketTrendsRequest(limit=51)

    def test_limit_min(self):
        with pytest.raises(ValidationError):
            MarketTrendsRequest(limit=0)


class TestMarketTrendsResponse:
    def test_valid(self):
        r = MarketTrendsResponse(
            trends=[],
            ai_summary="Market is trending upward",
            generated_at="2026-02-08T12:00:00Z",
        )
        assert r.category is None

    def test_with_filters(self):
        r = MarketTrendsResponse(
            trends=[],
            ai_summary="Summary",
            generated_at="2026-02-08T12:00:00Z",
            category="Electronics",
            source="amazon",
        )
        assert r.source == "amazon"


class TestTrendCategoriesAndSources:
    def test_categories_response(self):
        r = TrendCategoriesResponse(
            categories=[
                CategorySchema(id="electronics", name="Electronics", icon="📱"),
                CategorySchema(id="fashion", name="Fashion", icon="👗"),
            ]
        )
        assert len(r.categories) == 2

    def test_sources_response(self):
        r = TrendSourcesResponse(sources=["amazon", "walmart", "tiktok"])
        assert len(r.sources) == 3
