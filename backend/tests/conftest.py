"""
Shared test fixtures for ActualPrice backend test suite.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session, SQLModel, create_engine


# ---------------------------------------------------------------------------
# Mock DB session (for services that require db: AsyncSession)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Mock AsyncSession for services that require a database."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Mock user
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Mock product
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Mock sentiment data
# ---------------------------------------------------------------------------

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


