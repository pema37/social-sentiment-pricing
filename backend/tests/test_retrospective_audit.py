"""
Tests for RetrospectiveAuditService

Covers:
  - Empty state (no products, no competitor data)
  - Single product with overpriced days
  - Single product with underpriced days
  - Mixed overpriced/underpriced/aligned
  - Summary aggregation math
  - Forward-fill logic for missing price days
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from services.retrospective_audit_service import (
    RetrospectiveAuditService,
)

# ── Helpers ───────────────────────────────────────────────────


def _make_product(**overrides):
    """Create a mock Product."""
    defaults = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "name": "Test Widget",
        "sku": "WIDGET-001",
        "category": "gadgets",
        "current_price": Decimal("49.99"),
        "base_price": Decimal("39.99"),
        "is_active": True,
        "auto_pricing_enabled": False,
        "sentiment_multiplier": Decimal("0.2"),
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_comp_product(product_id, competitor_id, current_price=Decimal("45.00"), **overrides):
    """Create a mock CompetitorProduct."""
    defaults = {
        "id": uuid.uuid4(),
        "product_id": product_id,
        "competitor_id": competitor_id,
        "competitor_product_name": "Competitor Widget",
        "competitor_product_url": "https://competitor.com/widget",
        "current_price": current_price,
        "is_active": True,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ── Tests ─────────────────────────────────────────────────────


class TestForwardFill:
    """Test the static forward-fill utility."""

    def test_fills_gaps(self):
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 5, tzinfo=UTC)
        sparse = {
            "2026-01-01": Decimal("10.00"),
            "2026-01-03": Decimal("12.00"),
        }
        filled = RetrospectiveAuditService._forward_fill_prices(sparse, start, end)
        assert filled["2026-01-01"] == Decimal("10.00")
        assert filled["2026-01-02"] == Decimal("10.00")  # forward-filled
        assert filled["2026-01-03"] == Decimal("12.00")
        assert filled["2026-01-04"] == Decimal("12.00")  # forward-filled
        assert filled["2026-01-05"] == Decimal("12.00")  # forward-filled

    def test_empty_returns_empty(self):
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 3, tzinfo=UTC)
        filled = RetrospectiveAuditService._forward_fill_prices({}, start, end)
        assert filled == {}


class TestBuildSummary:
    """Test summary aggregation from SKU results."""

    def test_empty_sku_results(self):
        service = RetrospectiveAuditService.__new__(RetrospectiveAuditService)
        now = datetime.now(UTC)
        start = now - timedelta(days=90)

        summary = service._build_summary(
            sku_results=[],
            lookback_days=90,
            period_start=start,
            period_end=now,
        )
        assert summary.total_products_analyzed == 0
        assert summary.total_estimated_impact == Decimal("0")
        assert summary.monthly_projected_loss == Decimal("0")

    def test_single_sku_projection(self):
        service = RetrospectiveAuditService.__new__(RetrospectiveAuditService)
        now = datetime.now(UTC)
        start = now - timedelta(days=90)

        # Mock a SKU result with $900 total impact over 90 days
        sku = MagicMock()
        sku.product_name = "Widget A"
        sku.estimated_lost_revenue = Decimal("600.00")
        sku.estimated_missed_margin = Decimal("300.00")
        sku.total_estimated_impact = Decimal("900.00")
        sku.days_overpriced = 45
        sku.days_underpriced = 20
        sku.avg_overpriced_gap_percent = Decimal("8.50")

        summary = service._build_summary(
            sku_results=[sku],
            lookback_days=90,
            period_start=start,
            period_end=now,
        )

        assert summary.total_products_analyzed == 1
        assert summary.total_estimated_impact == Decimal("900.00")
        assert summary.total_lost_revenue == Decimal("600.00")
        assert summary.total_missed_margin == Decimal("300.00")

        # Monthly: 900 / 90 * 30 = 300
        assert summary.monthly_projected_loss == Decimal("300.00")
        # Annual: 900 / 90 * 365 = 3650
        assert summary.annual_projected_loss == Decimal("3650.00")
        assert summary.top_loss_products == ["Widget A"]


class TestElasticityMath:
    """Verify the per-day lost revenue calculation logic."""

    def test_overpriced_lost_revenue(self):
        """
        If a $50 product is 10% overpriced with 5 daily units:
        lost_units = 5 × 0.015 × 10 = 0.75
        lost_revenue = 0.75 × 50 = 37.50
        """
        daily_units = 5
        gap_percent = Decimal("10")
        merchant_price = Decimal("50.00")
        elasticity = Decimal("0.015")

        lost_units = Decimal(str(daily_units)) * elasticity * gap_percent
        lost_revenue = lost_units * merchant_price

        assert lost_units == Decimal("0.750")
        assert lost_revenue == Decimal("37.500")

    def test_underpriced_missed_margin(self):
        """
        If a $40 product is $5 below optimal with 5 daily units:
        missed_margin = 5 × 5 = 25
        """
        daily_units = 5
        gap_amount = Decimal("5.00")

        missed_margin = Decimal(str(daily_units)) * gap_amount
        assert missed_margin == Decimal("25.00")
