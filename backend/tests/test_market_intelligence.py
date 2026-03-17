"""
Tests for Market Intelligence Pipeline (You.com + Gemini).

DeveloperWeek 2026 Hackathon - You.com Challenge Track

Coverage:
- YouComClient: API calls, caching, retries, specialized searches
- Data models: WebResult, NewsResult, SearchResponse
- TTLCache: set/get, expiry, key isolation
- AgentEvent: SSE formatting
- MarketIntelligencePipeline: full pipeline streaming
- Intelligence Router: health, validation, serialization

Run: pytest tests/test_market_intelligence.py -v
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.market_intelligence import (
    AgentEvent,
    AgentRole,
    IntelligenceRequest,
    MarketIntelligencePipeline,
    PriceRecommendation,
    ThoughtType,
)
from services.youcom_client import (
    Freshness,
    NewsResult,
    SearchResponse,
    WebResult,
    YouComClient,
    _TTLCache,
)

# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES & HELPERS
# ═══════════════════════════════════════════════════════════════════════════

SAMPLE_SEARCH_RESPONSE = {
    "results": {
        "web": [
            {
                "url": "https://store.example.com/nike-air-max",
                "title": "Nike Air Max 90 - $129.99",
                "description": "Classic Nike Air Max 90 at great prices",
                "snippets": ["Nike Air Max 90 for $129.99", "Free shipping available"],
                "page_age": "2 days ago",
                "authors": [],
            },
            {
                "url": "https://shoes.example.com/deals",
                "title": "Running Shoes Deals",
                "description": "Compare prices on top running shoes",
                "snippets": ["Air Max 90 starting at $119.95"],
                "page_age": "1 week ago",
                "authors": ["Shoe Expert"],
            },
        ],
        "news": [
            {
                "url": "https://news.example.com/nike-pricing",
                "title": "Nike Adjusts Pricing Strategy for 2026",
                "description": "Nike announces new pricing tiers for their classic lineup",
                "page_age": "3 days ago",
            },
        ],
    },
    "metadata": {"request_uuid": "test-uuid-123"},
}


def make_mock_response(data: dict, status_code: int = 200):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx

        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"{status_code}", request=MagicMock(), response=resp
        )
    return resp


# ═══════════════════════════════════════════════════════════════════════════
# TEST: TTLCache
# ═══════════════════════════════════════════════════════════════════════════


class TestTTLCache:
    """Tests for the in-memory TTL cache."""

    def test_set_and_get(self):
        cache = _TTLCache(ttl=60)
        cache.set("test query", "result_value")
        assert cache.get("test query") == "result_value"

    def test_returns_none_for_missing(self):
        cache = _TTLCache(ttl=60)
        assert cache.get("nonexistent") is None

    def test_expires_after_ttl(self):
        cache = _TTLCache(ttl=0.1)
        cache.set("query", "value")
        assert cache.get("query") == "value"
        time.sleep(0.15)
        assert cache.get("query") is None

    def test_different_params_different_keys(self):
        cache = _TTLCache(ttl=60)
        cache.set("query", "value_a", count=5)
        cache.set("query", "value_b", count=10)
        assert cache.get("query", count=5) == "value_a"
        assert cache.get("query", count=10) == "value_b"

    def test_clear(self):
        cache = _TTLCache(ttl=60)
        cache.set("q1", "v1")
        cache.set("q2", "v2")
        cache.clear()
        assert cache.get("q1") is None
        assert cache.get("q2") is None


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Data Models
# ═══════════════════════════════════════════════════════════════════════════


class TestDataModels:
    """Tests for WebResult, NewsResult, SearchResponse."""

    def test_web_result_from_api(self):
        data = SAMPLE_SEARCH_RESPONSE["results"]["web"][0]
        result = WebResult.from_api(data)
        assert result.url == "https://store.example.com/nike-air-max"
        assert result.title == "Nike Air Max 90 - $129.99"
        assert len(result.snippets) == 2
        assert result.page_age == "2 days ago"

    def test_web_result_handles_missing_fields(self):
        result = WebResult.from_api({})
        assert result.url == ""
        assert result.title == ""
        assert result.snippets == []
        assert result.page_age is None

    def test_news_result_from_api(self):
        data = SAMPLE_SEARCH_RESPONSE["results"]["news"][0]
        result = NewsResult.from_api(data)
        assert result.url == "https://news.example.com/nike-pricing"
        assert "Nike" in result.title
        assert result.page_age == "3 days ago"

    def test_search_response_total_results(self):
        resp = SearchResponse(
            query="test",
            web_results=[WebResult.from_api(r) for r in SAMPLE_SEARCH_RESPONSE["results"]["web"]],
            news_results=[NewsResult.from_api(r) for r in SAMPLE_SEARCH_RESPONSE["results"]["news"]],
        )
        assert resp.total_results == 3

    def test_search_response_to_context_block(self):
        resp = SearchResponse(
            query="Nike Air Max",
            web_results=[WebResult.from_api(SAMPLE_SEARCH_RESPONSE["results"]["web"][0])],
            news_results=[NewsResult.from_api(SAMPLE_SEARCH_RESPONSE["results"]["news"][0])],
            latency_ms=150.0,
        )
        block = resp.to_context_block()
        assert "Nike Air Max" in block
        assert "Web Sources" in block
        assert "Recent News" in block
        assert "$129.99" in block
        assert "150ms" in block
        assert "2 sources retrieved" in block


# ═══════════════════════════════════════════════════════════════════════════
# TEST: YouComClient
# ═══════════════════════════════════════════════════════════════════════════


class TestYouComClient:
    """Tests for the You.com API client."""

    def test_raises_without_api_key(self):
        with pytest.raises(ValueError, match="API key is required"):
            YouComClient(api_key="")

    def test_raises_with_none_api_key(self):
        with pytest.raises(ValueError, match="API key is required"):
            YouComClient(api_key=None)  # type: ignore

    @pytest.mark.asyncio
    async def test_search_returns_parsed_response(self):
        client = YouComClient(api_key="test-key")
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        client._client = mock_client

        result = await client.search("Nike Air Max 90")

        assert result.query == "Nike Air Max 90"
        assert len(result.web_results) == 2
        assert len(result.news_results) == 1
        assert result.request_id == "test-uuid-123"
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_search_uses_cache(self):
        client = YouComClient(api_key="test-key", cache_ttl=60)
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        client._client = mock_client

        # First call hits API
        result1 = await client.search("test query")
        assert not result1.cached

        # Second call uses cache
        result2 = await client.search("test query")
        assert result2.cached

        # API only called once
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_search_competitor_prices(self):
        client = YouComClient(api_key="test-key")
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        client._client = mock_client

        result = await client.search_competitor_prices(product_name="Air Max 90", brand="Nike", category="Shoes")

        # Verify query was constructed correctly
        call_args = mock_client.get.call_args
        params = call_args[1]["params"] if "params" in call_args[1] else call_args[0][1]
        assert "Nike" in params["query"]
        assert "price" in params["query"]
        assert params["count"] == 8

    @pytest.mark.asyncio
    async def test_search_market_sentiment(self):
        client = YouComClient(api_key="test-key")
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        client._client = mock_client

        result = await client.search_market_sentiment(product_name="Air Max 90", brand="Nike")

        call_args = mock_client.get.call_args
        params = call_args[1]["params"] if "params" in call_args[1] else call_args[0][1]
        assert "reviews" in params["query"]
        assert "sentiment" in params["query"]

    @pytest.mark.asyncio
    async def test_search_market_trends(self):
        client = YouComClient(api_key="test-key")
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        client._client = mock_client

        result = await client.search_market_trends(category="Running Shoes")

        call_args = mock_client.get.call_args
        params = call_args[1]["params"] if "params" in call_args[1] else call_args[0][1]
        assert "Running Shoes" in params["query"]
        assert "trends" in params["query"]

    @pytest.mark.asyncio
    async def test_request_count_tracks(self):
        client = YouComClient(api_key="test-key")
        assert client.request_count == 0

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        client._client = mock_client

        await client.search("test 1")
        assert client.request_count == 1

        # Clear cache so second request actually hits API
        client._cache.clear()
        await client.search("test 2")
        assert client.request_count == 2

    @pytest.mark.asyncio
    async def test_close_client(self):
        client = YouComClient(api_key="test-key")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        client._client = mock_client

        await client.close()
        mock_client.aclose.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Freshness Enum
# ═══════════════════════════════════════════════════════════════════════════


class TestFreshness:
    """Tests for Freshness enum values."""

    def test_enum_values(self):
        assert Freshness.DAY.value == "day"
        assert Freshness.WEEK.value == "week"
        assert Freshness.MONTH.value == "month"
        assert Freshness.YEAR.value == "year"


# ═══════════════════════════════════════════════════════════════════════════
# TEST: AgentEvent
# ═══════════════════════════════════════════════════════════════════════════


class TestAgentEvent:
    """Tests for AgentEvent data model and SSE formatting."""

    def test_to_dict(self):
        event = AgentEvent(
            agent=AgentRole.SCOUT,
            thought_type=ThoughtType.OBSERVATION,
            content="Found 5 results",
            is_final=False,
        )
        d = event.to_dict()
        assert d["agent"] == "scout"
        assert d["thought_type"] == "observation"
        assert d["content"] == "Found 5 results"
        assert d["is_final"] is False
        assert d["metadata"] is None

    def test_to_sse(self):
        event = AgentEvent(
            agent=AgentRole.ANALYST,
            thought_type=ThoughtType.ANALYSIS,
            content="Analyzing prices",
        )
        sse = event.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        parsed = json.loads(sse[6:].strip())
        assert parsed["agent"] == "analyst"

    def test_to_sse_special_characters(self):
        event = AgentEvent(
            agent=AgentRole.STRATEGIST,
            thought_type=ThoughtType.RECOMMENDATION,
            content='Price: $129.99 — "best value" for <consumers>',
        )
        sse = event.to_sse()
        parsed = json.loads(sse[6:].strip())
        assert "$129.99" in parsed["content"]
        assert '"best value"' in parsed["content"]

    def test_to_dict_with_metadata(self):
        event = AgentEvent(
            agent=AgentRole.STRATEGIST,
            thought_type=ThoughtType.RECOMMENDATION,
            content="Done",
            is_final=True,
            metadata={"recommendation": {"price": 99.99}},
        )
        d = event.to_dict()
        assert d["is_final"] is True
        assert d["metadata"]["recommendation"]["price"] == 99.99


# ═══════════════════════════════════════════════════════════════════════════
# TEST: PriceRecommendation
# ═══════════════════════════════════════════════════════════════════════════


class TestPriceRecommendation:
    """Tests for the PriceRecommendation dataclass."""

    def test_creation(self):
        rec = PriceRecommendation(
            recommended_price=119.99,
            confidence=0.82,
            price_range_low=99.99,
            price_range_high=139.99,
            risk_level="low",
            strategy="Competitive undercut",
            reasoning="Based on 5 competitor prices",
            key_factors=["competitor avg $130", "positive sentiment"],
            price_change_percent=-7.7,
            sources_used=8,
        )
        assert rec.recommended_price == 119.99
        assert rec.confidence == 0.82
        assert rec.risk_level == "low"
        assert len(rec.key_factors) == 2
        assert rec.sources_used == 8


# ═══════════════════════════════════════════════════════════════════════════
# TEST: MarketIntelligencePipeline
# ═══════════════════════════════════════════════════════════════════════════


class TestMarketIntelligencePipeline:
    """Tests for the full Scout → Analyst → Strategist pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_raises_without_api_key(self):
        with patch("services.market_intelligence.settings") as mock_settings:
            mock_settings.YOUCOM_API_KEY = None
            with pytest.raises(ValueError, match="API key required"):
                MarketIntelligencePipeline()

    @pytest.mark.asyncio
    async def test_full_pipeline_streams_events(self):
        """Test that the pipeline produces events from all three agents."""
        with patch("services.market_intelligence.settings") as mock_settings:
            mock_settings.YOUCOM_API_KEY = "test-key"
            mock_settings.GEMINI_API_KEY = None  # Use fallback

            pipeline = MarketIntelligencePipeline(youcom_api_key="test-key")

            # Mock the YouComClient's search methods
            mock_response = SearchResponse(
                query="test",
                web_results=[
                    WebResult(
                        url="https://example.com/product",
                        title="Test Product - $99.99",
                        description="A test product",
                        snippets=["Available for $99.99"],
                    )
                ],
                news_results=[],
                latency_ms=100.0,
            )

            pipeline._client.search_competitor_prices = AsyncMock(return_value=mock_response)
            pipeline._client.search_market_sentiment = AsyncMock(return_value=mock_response)
            pipeline._client.search_market_trends = AsyncMock(return_value=mock_response)

            request = IntelligenceRequest(
                product_name="Test Product",
                current_price=99.99,
                brand="TestBrand",
                category="TestCategory",
            )

            events = []
            async for event in pipeline.run(request):
                events.append(event)

            # Should have events from all three agents
            agents_seen = {e.agent for e in events}
            assert AgentRole.SCOUT in agents_seen
            assert AgentRole.ANALYST in agents_seen
            assert AgentRole.STRATEGIST in agents_seen

            # Should have at least one final event per agent
            final_events = [e for e in events if e.is_final]
            final_agents = {e.agent for e in final_events}
            assert AgentRole.SCOUT in final_agents
            assert AgentRole.ANALYST in final_agents
            assert AgentRole.STRATEGIST in final_agents

            # Strategist final should have recommendation
            strat_final = [e for e in final_events if e.agent == AgentRole.STRATEGIST]
            assert len(strat_final) == 1
            assert strat_final[0].metadata is not None
            assert "recommendation" in strat_final[0].metadata

            await pipeline.close()

    @pytest.mark.asyncio
    async def test_pipeline_handles_empty_results(self):
        """Pipeline should complete gracefully when searches return nothing."""
        with patch("services.market_intelligence.settings") as mock_settings:
            mock_settings.YOUCOM_API_KEY = "test-key"
            mock_settings.GEMINI_API_KEY = None

            pipeline = MarketIntelligencePipeline(youcom_api_key="test-key")

            empty_response = SearchResponse(
                query="obscure product",
                web_results=[],
                news_results=[],
                latency_ms=50.0,
            )

            pipeline._client.search_competitor_prices = AsyncMock(return_value=empty_response)
            pipeline._client.search_market_sentiment = AsyncMock(return_value=empty_response)

            request = IntelligenceRequest(
                product_name="Obscure Product XYZ",
                current_price=50.0,
            )

            events = []
            async for event in pipeline.run(request):
                events.append(event)

            # Should still complete with all agents
            agents_seen = {e.agent for e in events}
            assert AgentRole.SCOUT in agents_seen
            assert AgentRole.ANALYST in agents_seen
            assert AgentRole.STRATEGIST in agents_seen

            # Should have fallback recommendation
            strat_final = [e for e in events if e.agent == AgentRole.STRATEGIST and e.is_final]
            assert len(strat_final) == 1
            rec = strat_final[0].metadata.get("recommendation")
            assert rec is not None
            assert rec["confidence"] < 0.5  # Low confidence for heuristic

            await pipeline.close()


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Intelligence Router
# ═══════════════════════════════════════════════════════════════════════════


class TestIntelligenceRouter:
    """Tests for the Market Intelligence API router."""

    def test_health_response_schema(self):
        """IntelligenceHealthResponse should serialize correctly."""
        from api.v1.routes.market_intelligence import IntelligenceHealthResponse

        resp = IntelligenceHealthResponse(
            status="healthy",
            youcom_configured=True,
            gemini_configured=True,
            demo_ready=True,
            message="Ready!",
        )
        data = resp.model_dump()
        assert data["status"] == "healthy"
        assert data["youcom_configured"] is True
        assert data["demo_ready"] is True

    def test_query_request_validation(self):
        """IntelligenceQueryRequest should validate inputs."""
        from api.v1.routes.market_intelligence import IntelligenceQueryRequest

        # Valid
        req = IntelligenceQueryRequest(
            product_name="Nike Air Max",
            current_price=129.99,
            brand="Nike",
            category="Shoes",
        )
        assert req.product_name == "Nike Air Max"
        assert req.current_price == 129.99

        # Minimal (only required field)
        req2 = IntelligenceQueryRequest(product_name="Test")
        assert req2.brand is None
        assert req2.category is None
        assert req2.features is None

    def test_query_request_rejects_empty_name(self):
        """Product name must be non-empty."""
        from api.v1.routes.market_intelligence import IntelligenceQueryRequest

        with pytest.raises(Exception):  # ValidationError
            IntelligenceQueryRequest(product_name="")

    def test_query_request_rejects_negative_price(self):
        """Price must be positive if provided."""
        from api.v1.routes.market_intelligence import IntelligenceQueryRequest

        with pytest.raises(Exception):  # ValidationError
            IntelligenceQueryRequest(product_name="Test", current_price=-10)
