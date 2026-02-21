"""
Test Suite: integration.py + trend_analysis.py + competitor_matching.py schemas
Place at: backend/tests/test_integration_trend_matching_schemas.py
Run: pytest backend/tests/test_integration_trend_matching_schemas.py -v
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from schemas.integration import (
    EcommercePlatform,
    IntegrationStatus,
    OAuthInitRequest,
    OAuthInitResponse,
    OAuthCallbackRequest,
    WooCommerceConnectRequest,
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationListResponse,
    SyncTriggerRequest,
    SyncStatusResponse,
    SyncLogResponse,
    SyncLogsListResponse,
    ProductLinkCreate,
    ProductLinkResponse,
    ProductLinkListResponse,
    PricePushRequest,
    PricePushResponse,
    BulkPricePushRequest,
    BulkPricePushResponse,
    WebhookPayload,
    IntegrationHealthResponse,
)
from schemas.trend_analysis import (
    TrendDirection,
    TrendCategory,
    OpportunityType,
    RiskLevel,
    ConfidenceLevel,
    TrendAnalysisRequest,
    ProductOpportunityRequest,
    RiskDetectionRequest,
    InsightGenerationRequest,
    TrendSignalResponse,
    TrendPredictionResponse,
    PricingOpportunityResponse,
    RiskAlertResponse,
    AIInsightResponse,
    TrendAnalysisResponse,
    RiskDetectionResponse,
    QuickStatsResponse,
)
from schemas.competitor_matching import (
    CompetitorSearchRequest,
    ProductMatchRequest,
    BulkMatchRequest,
    MatchedProductSchema,
    CompetitorSearchResponse,
    ProviderInfoSchema,
    ProvidersListResponse,
    BulkMatchResultSchema,
    BulkMatchResponse,
    AutoLinkResultSchema,
    CacheClearResponse,
    MatchingErrorResponse,
)

NOW = datetime.now(timezone.utc)
UID = uuid4()


# =====================================================================
# Integration Enums
# =====================================================================

class TestIntegrationEnums:

    def test_platforms(self):
        assert {p.value for p in EcommercePlatform} == {"shopify", "woocommerce"}

    def test_statuses(self):
        assert {s.value for s in IntegrationStatus} == {
            "active", "error", "paused", "disconnected"
        }


# =====================================================================
# OAuth
# =====================================================================

class TestOAuth:

    def test_init_request(self):
        r = OAuthInitRequest(platform=EcommercePlatform.SHOPIFY, store_url="https://mystore.myshopify.com")
        assert r.store_url == "https://mystore.myshopify.com"

    def test_init_request_url_normalization(self):
        r = OAuthInitRequest(platform=EcommercePlatform.SHOPIFY, store_url="https://MyStore.COM/")
        assert r.store_url == "https://mystore.com"

    def test_init_request_short_url_raises(self):
        with pytest.raises(ValidationError):
            OAuthInitRequest(platform=EcommercePlatform.SHOPIFY, store_url="ab")

    def test_init_response(self):
        r = OAuthInitResponse(authorization_url="https://auth.shopify.com/...", state="abc123")
        assert r.state == "abc123"

    def test_callback_request(self):
        r = OAuthCallbackRequest(code="auth_code", state="csrf_token", shop="mystore.myshopify.com")
        assert r.shop == "mystore.myshopify.com"

    def test_callback_request_no_shop(self):
        r = OAuthCallbackRequest(code="auth_code", state="csrf_token")
        assert r.shop is None


# =====================================================================
# WooCommerce Connect
# =====================================================================

class TestWooCommerceConnect:

    def test_valid(self):
        r = WooCommerceConnectRequest(
            store_url="https://mystore.com",
            store_name="My Store",
            consumer_key="ck_abcdefghij",
            consumer_secret="cs_abcdefghij",
        )
        assert r.store_name == "My Store"

    def test_invalid_consumer_key_prefix(self):
        with pytest.raises(ValidationError):
            WooCommerceConnectRequest(
                store_url="https://mystore.com",
                consumer_key="bad_key_here",
                consumer_secret="cs_abcdefghij",
            )

    def test_invalid_consumer_secret_prefix(self):
        with pytest.raises(ValidationError):
            WooCommerceConnectRequest(
                store_url="https://mystore.com",
                consumer_key="ck_abcdefghij",
                consumer_secret="bad_secret_here",
            )

    def test_short_consumer_key_raises(self):
        with pytest.raises(ValidationError):
            WooCommerceConnectRequest(
                store_url="https://mystore.com",
                consumer_key="ck_short",
                consumer_secret="cs_abcdefghij",
            )


# =====================================================================
# Integration CRUD
# =====================================================================

class TestIntegrationCRUD:

    def test_create(self):
        r = IntegrationCreate(
            platform=EcommercePlatform.WOOCOMMERCE,
            store_url="https://shop.example.com",
        )
        assert r.consumer_key is None

    def test_update_empty(self):
        r = IntegrationUpdate()
        assert r.store_name is None
        assert r.status is None

    def test_update_with_credentials(self):
        r = IntegrationUpdate(
            consumer_key="ck_1234567890",
            consumer_secret="cs_1234567890",
        )
        assert r.consumer_key == "ck_1234567890"

    def test_update_invalid_key_prefix(self):
        with pytest.raises(ValidationError):
            IntegrationUpdate(consumer_key="bad_1234567890")

    def test_response(self):
        r = IntegrationResponse(
            id=UID,
            platform=EcommercePlatform.SHOPIFY,
            store_url="https://test.myshopify.com",
            store_name="Test Store",
            status=IntegrationStatus.ACTIVE,
            error_message=None,
            scopes=["read_products", "write_products"],
            last_sync_at=NOW,
            sync_status="idle",
            products_synced=150,
            settings={},
            created_at=NOW,
            updated_at=NOW,
        )
        assert r.products_synced == 150

    def test_list_response(self):
        r = IntegrationListResponse(integrations=[], total=0)
        assert r.total == 0


# =====================================================================
# Sync
# =====================================================================

class TestSync:

    def test_trigger_request_default(self):
        r = SyncTriggerRequest()
        assert r.sync_type == "full"

    def test_trigger_request_incremental(self):
        r = SyncTriggerRequest(sync_type="incremental")
        assert r.sync_type == "incremental"

    def test_trigger_request_invalid(self):
        with pytest.raises(ValidationError):
            SyncTriggerRequest(sync_type="partial")

    def test_sync_status(self):
        r = SyncStatusResponse(
            integration_id=UID,
            sync_status="idle",
            last_sync_at=NOW,
            products_synced=50,
        )
        assert r.current_progress is None

    def test_sync_log(self):
        r = SyncLogResponse(
            id=UID,
            sync_type="full",
            started_at=NOW,
            completed_at=NOW,
            duration_seconds=12.5,
            success=True,
            products_created=10,
            products_updated=5,
            products_deleted=0,
            error_details=None,
        )
        assert r.success is True

    def test_sync_logs_list(self):
        r = SyncLogsListResponse(logs=[], total=0)
        assert r.total == 0


# =====================================================================
# Product Links
# =====================================================================

class TestProductLinks:

    def test_link_create(self):
        r = ProductLinkCreate(
            product_id=UID,
            external_product_id="ext_123",
        )
        assert r.external_variant_id is None

    def test_link_response(self):
        r = ProductLinkResponse(
            id=UID,
            product_id=UID,
            integration_id=UID,
            external_product_id="ext_123",
            external_variant_id=None,
            external_price=29.99,
            external_compare_at_price=None,
            last_price_push_at=None,
            last_price_pull_at=None,
            sync_enabled=True,
            created_at=NOW,
        )
        assert r.sync_enabled is True

    def test_link_list(self):
        r = ProductLinkListResponse(links=[], total=0)
        assert r.total == 0


# =====================================================================
# Price Push
# =====================================================================

class TestPricePush:

    def test_push_request(self):
        r = PricePushRequest(
            product_link_id=UID,
            new_price=Decimal("29.99"),
        )
        assert r.compare_at_price is None

    def test_push_request_zero_price_raises(self):
        with pytest.raises(ValidationError):
            PricePushRequest(product_link_id=UID, new_price=Decimal("0"))

    def test_push_response(self):
        r = PricePushResponse(
            success=True,
            product_link_id=UID,
            old_price=Decimal("24.99"),
            new_price=Decimal("29.99"),
        )
        assert r.error is None

    def test_bulk_push_request(self):
        r = BulkPricePushRequest(
            updates=[
                PricePushRequest(product_link_id=UID, new_price=Decimal("10.00")),
            ]
        )
        assert len(r.updates) == 1

    def test_bulk_push_empty_raises(self):
        with pytest.raises(ValidationError):
            BulkPricePushRequest(updates=[])

    def test_bulk_push_response(self):
        r = BulkPricePushResponse(results=[], success_count=0, failure_count=0)
        assert r.success_count == 0


# =====================================================================
# Webhook + Health
# =====================================================================

class TestWebhookAndHealth:

    def test_webhook_payload(self):
        r = WebhookPayload(
            topic="products/update",
            shop="mystore.myshopify.com",
            payload={"id": 123, "title": "Updated Product"},
        )
        assert r.topic == "products/update"

    def test_integration_health(self):
        r = IntegrationHealthResponse(
            integration_id=UID,
            platform=EcommercePlatform.SHOPIFY,
            store_url="https://test.myshopify.com",
            status="healthy",
            checked_at=NOW,
        )
        assert r.status == "healthy"


# =====================================================================
# Trend Analysis – Enums
# =====================================================================

class TestTrendEnums:

    def test_trend_directions(self):
        assert {d.value for d in TrendDirection} == {"rising", "falling", "stable", "volatile"}

    def test_trend_categories(self):
        assert len(TrendCategory) == 8

    def test_opportunity_types(self):
        assert len(OpportunityType) == 5

    def test_risk_levels(self):
        assert {r.value for r in RiskLevel} == {"low", "medium", "high", "critical"}

    def test_confidence_levels(self):
        assert len(ConfidenceLevel) == 4


# =====================================================================
# Trend Analysis – Requests
# =====================================================================

class TestTrendRequests:

    def test_analysis_request_defaults(self):
        r = TrendAnalysisRequest()
        assert r.days == 30
        assert r.use_model == "openai"
        assert r.product_ids is None

    def test_analysis_request_custom(self):
        r = TrendAnalysisRequest(days=7, use_model="gemini", product_ids=["p1", "p2"])
        assert r.days == 7

    def test_analysis_request_days_min(self):
        with pytest.raises(ValidationError):
            TrendAnalysisRequest(days=6)

    def test_analysis_request_days_max(self):
        with pytest.raises(ValidationError):
            TrendAnalysisRequest(days=91)

    def test_analysis_request_invalid_model(self):
        with pytest.raises(ValidationError):
            TrendAnalysisRequest(use_model="claude")

    def test_product_opportunity_request(self):
        r = ProductOpportunityRequest(product_id="prod_123")
        assert r.use_model == "openai"

    def test_risk_detection_request(self):
        r = RiskDetectionRequest()
        assert r.use_model == "openai"

    def test_insight_request(self):
        r = InsightGenerationRequest(days=14, use_model="gemini")
        assert r.days == 14


# =====================================================================
# Trend Analysis – Responses
# =====================================================================

class TestTrendResponses:

    def test_trend_signal(self):
        r = TrendSignalResponse(
            signal_type="volume_spike",
            value=2.5,
            timestamp=NOW,
            source="twitter",
            description="Volume increased 2.5x",
        )
        assert r.value == 2.5

    def test_trend_prediction(self):
        r = TrendPredictionResponse(
            direction=TrendDirection.RISING,
            category=TrendCategory.VIRAL_POSITIVE,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=85.0,
            predicted_change=15.0,
            timeframe_days=7,
            reasoning="Strong viral signal detected",
        )
        assert r.direction == TrendDirection.RISING

    def test_prediction_confidence_range(self):
        with pytest.raises(ValidationError):
            TrendPredictionResponse(
                direction=TrendDirection.RISING,
                category=TrendCategory.VIRAL_POSITIVE,
                confidence=ConfidenceLevel.HIGH,
                confidence_score=101,
                predicted_change=10,
                timeframe_days=7,
                reasoning="test",
            )

    def test_pricing_opportunity(self):
        r = PricingOpportunityResponse(
            opportunity_type=OpportunityType.PRICE_INCREASE,
            product_id="prod_123",
            product_name="Widget X",
            current_price="29.99",
            suggested_price="34.99",
            expected_impact="+15% revenue",
            confidence=ConfidenceLevel.HIGH,
            confidence_score=80,
            reasoning="Strong demand signal",
            valid_until=NOW,
        )
        assert r.triggers == []

    def test_risk_alert(self):
        r = RiskAlertResponse(
            risk_level=RiskLevel.HIGH,
            risk_type="competitor_undercut",
            title="Major Competitor Price Drop",
            description="Amazon dropped price by 20%",
            affected_products=["prod_123"],
            recommended_actions=["Review pricing", "Monitor sales"],
            detected_at=NOW,
        )
        assert len(r.recommended_actions) == 2

    def test_ai_insight(self):
        r = AIInsightResponse(
            title="Market Shift Detected",
            summary="Demand increasing in wearables category",
            detailed_analysis="Analysis details...",
            key_factors=["TikTok viral", "Holiday season"],
            data_points_analyzed=1500,
            generated_at=NOW,
            model_used="gemini",
        )
        assert r.data_points_analyzed == 1500

    def test_full_analysis_response(self):
        r = TrendAnalysisResponse(
            analysis_id="analysis_123",
            generated_at=NOW,
            market_sentiment=TrendDirection.RISING,
            market_sentiment_score=45.5,
            predictions=[],
            opportunities=[],
            risks=[],
            insights=[],
            executive_summary="Market is healthy",
            recommended_actions=["Continue monitoring"],
            products_analyzed=25,
            mentions_analyzed=5000,
            time_range_days=30,
        )
        assert r.products_analyzed == 25

    def test_sentiment_score_range(self):
        with pytest.raises(ValidationError):
            TrendAnalysisResponse(
                analysis_id="x",
                generated_at=NOW,
                market_sentiment=TrendDirection.RISING,
                market_sentiment_score=101,
                executive_summary="x",
                products_analyzed=0,
                mentions_analyzed=0,
                time_range_days=30,
            )

    def test_risk_detection_response(self):
        r = RiskDetectionResponse(
            risks=[],
            overall_risk_level=RiskLevel.LOW,
            summary="No significant risks",
            generated_at=NOW,
        )
        assert r.overall_risk_level == RiskLevel.LOW

    def test_quick_stats(self):
        r = QuickStatsResponse(
            current_sentiment=0.65,
            sentiment_trend=TrendDirection.RISING,
            sentiment_change_7d=0.12,
            mentions_today=45,
            mentions_7d=312,
            volume_change_percent=15.5,
            active_opportunities=3,
            potential_revenue_impact="$5,000",
            active_risks=1,
            highest_risk_level=RiskLevel.MEDIUM,
            trending_up=["Widget X", "Widget Y"],
            trending_down=["Widget Z"],
            last_updated=NOW,
        )
        assert r.active_opportunities == 3


# =====================================================================
# Competitor Matching – Requests
# =====================================================================

class TestCompetitorSearchRequest:

    def test_valid_minimal(self):
        r = CompetitorSearchRequest(product_name="iPhone 15 Pro")
        assert r.max_results == 10
        assert r.min_confidence == 0.3
        assert r.use_cache is True

    def test_valid_full(self):
        r = CompetitorSearchRequest(
            product_name="iPhone 15 Pro 256GB",
            keywords=["apple", "smartphone"],
            our_price=Decimal("999.99"),
            max_results=20,
            exclude_domains=["mystore.com"],
            preferred_merchants=["Amazon", "Best Buy"],
            min_confidence=0.5,
            use_cache=False,
        )
        assert len(r.keywords) == 2

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            CompetitorSearchRequest(product_name="X")

    def test_max_results_range(self):
        with pytest.raises(ValidationError):
            CompetitorSearchRequest(product_name="Test", max_results=51)

    def test_min_confidence_range(self):
        with pytest.raises(ValidationError):
            CompetitorSearchRequest(product_name="Test", min_confidence=1.5)


class TestProductMatchRequest:

    def test_valid(self):
        r = ProductMatchRequest(product_id=UID)
        assert r.max_results == 10
        assert r.auto_link is False
        assert r.auto_link_threshold == 0.8

    def test_auto_link_threshold_min(self):
        with pytest.raises(ValidationError):
            ProductMatchRequest(product_id=UID, auto_link_threshold=0.4)


class TestBulkMatchRequest:

    def test_valid(self):
        r = BulkMatchRequest(product_ids=[uuid4(), uuid4()])
        assert r.max_results_per_product == 5

    def test_empty_list_raises(self):
        with pytest.raises(ValidationError):
            BulkMatchRequest(product_ids=[])


# =====================================================================
# Competitor Matching – Responses
# =====================================================================

class TestMatchedProductSchema:

    def test_valid(self):
        m = MatchedProductSchema(
            title="iPhone 15 Pro",
            url="https://amazon.com/dp/123",
            price="999.00",
            merchant="Amazon",
            merchant_domain="amazon.com",
            image_url=None,
            rating=4.5,
            reviews_count=1234,
            confidence_score=0.92,
            confidence_percent=92,
            source="serpapi_google_shopping",
        )
        assert m.in_stock is True
        assert m.currency == "USD"


class TestCompetitorSearchResponse:

    def test_valid(self):
        r = CompetitorSearchResponse(
            success=True,
            status="success",
            query_used="iPhone 15 Pro",
            total_found=10,
            products=[],
            providers_used=["serpapi"],
            providers_failed=[],
            search_time_ms=1234,
            cached=False,
        )
        assert r.total_found == 10


class TestProviderSchemas:

    def test_provider_info(self):
        p = ProviderInfoSchema(
            name="serpapi_google_shopping",
            available=True,
            requires_api_key=True,
            cost_per_request=0.01,
        )
        assert p.available is True

    def test_providers_list(self):
        r = ProvidersListResponse(
            providers=[], available_count=0, total_count=3,
        )
        assert r.total_count == 3


class TestBulkMatchSchemas:

    def test_bulk_match_result(self):
        r = BulkMatchResultSchema(
            product_name="Widget",
            success=True,
            total_found=5,
        )
        assert r.error is None

    def test_bulk_match_response(self):
        r = BulkMatchResponse(
            total_products=3,
            results={"prod_1": {"success": True}},
        )
        assert r.total_products == 3


class TestAutoLinkAndCache:

    def test_auto_link_result(self):
        r = AutoLinkResultSchema(
            product_id="prod_123",
            linked_count=3,
            links_created=[{"competitor_id": "c1"}],
        )
        assert r.linked_count == 3

    def test_cache_clear(self):
        r = CacheClearResponse(success=True, entries_cleared=42)
        assert r.entries_cleared == 42


class TestMatchingError:

    def test_minimal(self):
        r = MatchingErrorResponse(detail="Search failed")
        assert r.error_code is None

    def test_full(self):
        r = MatchingErrorResponse(
            detail="All providers unavailable",
            error_code="NO_PROVIDERS",
            provider_errors=["serpapi: Invalid API key"],
        )
        assert len(r.provider_errors) == 1


        