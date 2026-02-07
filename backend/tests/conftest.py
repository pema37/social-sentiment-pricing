"""
Shared test fixtures for ActualPrice backend test suite.
Covers both core services and the Autonomous Pipeline.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Environment setup — must run before any app imports
# ---------------------------------------------------------------------------

os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("GEMINI_MODEL", "gemini-3-flash-preview")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("BNB_RPC_URL", "https://bsc-testnet-dataseed.bnbchain.org")
os.environ.setdefault("BNB_CONTRACT_ADDRESS", "0xTEST_CONTRACT")


# ===========================================================================
# CORE SERVICE FIXTURES
# ===========================================================================

@pytest.fixture
def mock_db():
    """Mock AsyncSession for services that require a database."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    return MagicMock(
        id=uuid.uuid4(),
        email="merchant@example.com",
        full_name="Test Merchant",
        is_active=True,
        is_admin=False,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_product():
    return MagicMock(
        id=uuid.uuid4(),
        name="Wireless Bluetooth Headphones",
        sku="WBH-001",
        current_price=Decimal("79.99"),
        cost=Decimal("35.00"),
        margin_floor=Decimal("0.20"),
        category="Electronics",
        keywords=["headphones", "bluetooth", "wireless", "audio"],
        is_active=True,
        auto_pricing_enabled=False,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_competitor_product(mock_product):
    return MagicMock(
        id=uuid.uuid4(),
        product_id=mock_product.id,
        name="BT Headphones Pro",
        price=Decimal("74.99"),
        url="https://competitor.example.com/bt-headphones",
        last_scraped=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_sentiment_positive():
    return {
        "score": 0.85, "label": "positive", "confidence": 0.92,
        "source": "reddit", "mentions_count": 47,
    }


@pytest.fixture
def mock_sentiment_negative():
    return {
        "score": -0.65, "label": "negative", "confidence": 0.88,
        "source": "reddit", "mentions_count": 23,
    }


# ===========================================================================
# AUTONOMOUS PIPELINE FIXTURES
# ===========================================================================

# ---------------------------------------------------------------------------
# Sample Data Factories
# ---------------------------------------------------------------------------

class SampleData:
    """Factory for consistent test data across the test suite."""

    @staticmethod
    def market_signal(overrides: dict | None = None) -> dict:
        base = {
            "competitor_name": "TestCompetitor",
            "competitor_price": 84.99,
            "price_change_pct": -15.1,
            "signal_type": "price_drop",
            "product_category": "electronics",
            "source": "google_search",
            "confidence": 0.85,
            "raw_data": {"url": "https://competitor.com/product"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if overrides:
            base.update(overrides)
        return base

    @staticmethod
    def market_assessment(overrides: dict | None = None) -> dict:
        base = {
            "sentiment_score": -0.42,
            "sentiment_label": "bearish",
            "demand_elasticity": -1.8,
            "risk_level": "medium",
            "risk_factors": [
                "Competitor price 15% below current",
                "Bearish consumer sentiment trending",
                "High demand elasticity increases churn risk",
            ],
            "opportunity_score": 0.65,
            "market_context": "Competitor dropped price. Market bearish. High elasticity.",
            "recommended_direction": "decrease",
            "max_safe_change_pct": 15.0,
        }
        if overrides:
            base.update(overrides)
        return base

    @staticmethod
    def pricing_decision(overrides: dict | None = None) -> dict:
        base = {
            "recommended_price": 87.99,
            "current_price": 99.99,
            "change_pct": -12.0,
            "confidence_score": 0.87,
            "reasoning": "Competitor dropped 15%. Sentiment bearish. Reducing price 12%.",
            "action": "execute",
            "risk_acknowledgment": "Competitor price 15% below current",
            "expected_revenue_impact": "9.6% volume increase projected",
            "tx_hash": "0xa1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
        if overrides:
            base.update(overrides)
        return base

    @staticmethod
    def pipeline_trigger_request(overrides: dict | None = None) -> dict:
        base = {
            "product_id": "test-product-001",
            "current_price": 99.99,
            "product_category": "electronics",
            "cost_basis": 45.00,
            "margin_floor_pct": 20.0,
        }
        if overrides:
            base.update(overrides)
        return base


@pytest.fixture
def sample_data() -> SampleData:
    """Provide the SampleData factory to tests."""
    return SampleData()


# ---------------------------------------------------------------------------
# Gemini API Mocks
# ---------------------------------------------------------------------------

class MockGeminiResponse:
    """Mock for genai.models.generate_content response."""

    def __init__(self, text: str, function_calls: list | None = None):
        self._text = text
        self._function_calls = function_calls or []

    @property
    def text(self) -> str:
        return self._text

    @property
    def candidates(self) -> list:
        parts = []
        text_part = MagicMock()
        text_part.function_call = None
        text_part.text = self._text
        parts.append(text_part)

        for fc in self._function_calls:
            fc_part = MagicMock()
            fc_part.function_call = MagicMock()
            fc_part.function_call.name = fc["name"]
            fc_part.function_call.args = fc.get("args", {})
            parts.append(fc_part)

        candidate = MagicMock()
        candidate.content.parts = parts
        return [candidate]


class MockGeminiAsyncModels:
    """Mock for client.aio.models with configurable responses."""

    def __init__(self):
        self._responses: dict[str, str] = {}

    def set_response(self, content_contains: str, response_json: dict):
        self._responses[content_contains] = json.dumps(response_json)

    async def generate_content(self, model: str, contents: str, config=None) -> MockGeminiResponse:
        for key, response_text in self._responses.items():
            if key.lower() in contents.lower():
                return MockGeminiResponse(text=response_text)
        if self._responses:
            first_response = next(iter(self._responses.values()))
            return MockGeminiResponse(text=first_response)
        return MockGeminiResponse(text="{}")


class MockGeminiAio:
    """Mock for client.aio namespace."""

    def __init__(self):
        self.models = MockGeminiAsyncModels()


class MockGeminiClient:
    """Complete mock for genai.Client."""

    def __init__(self, api_key: str = "test"):
        self.aio = MockGeminiAio()
        self.models = MagicMock()

    def configure_scout_response(self, signal_data: dict):
        self.aio.models.set_response("scan the market", signal_data)

    def configure_analyst_response(self, assessment_data: dict):
        self.aio.models.set_response("analyze this market signal", assessment_data)

    def configure_strategist_response(self, decision_text: str = "Recommending 12% decrease."):
        self.aio.models.set_response("make a pricing decision", decision_text)


@pytest.fixture
def mock_gemini_client(sample_data: SampleData) -> MockGeminiClient:
    """Fully configured mock Gemini client with realistic agent responses."""
    client = MockGeminiClient()
    client.configure_scout_response(sample_data.market_signal())
    client.configure_analyst_response(sample_data.market_assessment())
    client.configure_strategist_response("Reducing price 12% to maintain position.")
    return client


@pytest.fixture
def patched_gemini_client(mock_gemini_client: MockGeminiClient):
    """Patch the global Gemini client in the orchestrator module."""
    with patch(
        "backend.services.ai_trend_analysis.autonomous_orchestrator.client",
        mock_gemini_client,
    ) as mock:
        yield mock


# ---------------------------------------------------------------------------
# FastAPI Test Client
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app():
    """Isolated FastAPI app with autonomous pipeline router."""
    from fastapi import FastAPI
    from backend.api.v1.routes.autonomous_pipeline import router

    app = FastAPI(title="Test App")
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def client(test_app, patched_gemini_client) -> TestClient:
    """Synchronous test client with mocked Gemini."""
    return TestClient(test_app)


@pytest.fixture
async def async_client(test_app, patched_gemini_client) -> AsyncGenerator:
    """Async test client for testing SSE streaming endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Utility Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def frozen_time():
    """Consistent timestamp for deterministic tests."""
    return datetime(2026, 2, 7, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def env_vars():
    """Temporarily set environment variables for a test."""
    original = {}

    def _set(**kwargs):
        for key, value in kwargs.items():
            original[key] = os.environ.get(key)
            os.environ[key] = value

    yield _set

    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


            