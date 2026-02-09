# backend/tests/test_competitor_fallback.py
"""
Comprehensive tests for CompetitorFallbackService — generates recommendations
based on competitor price alone when no pricing rules match.

Tests cover:
- Module constants
- Initialization
- generate (full orchestration)
- _find_valid_competitor_price (filtering, validation)
- _is_valid_current_price
- _calculate_competitor_based_price (above/below/competitive)
- _apply_constraints (min/max, rounding)
- _calculate_change_percent
- _create_recommendation (persistence, approval check)
- _build_factors (dict structure)
- _try_auto_apply (auto-apply logic)

Total: ~55 tests
"""

import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# === Import isolation ===
for mod in [
    "db.session",
    "models.product",
    "models.price_recommendation",
    "models.pricing_settings",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from services.pricing.competitor_fallback import (
    CompetitorFallbackService,
    ABOVE_COMPETITOR_THRESHOLD,
    BELOW_COMPETITOR_THRESHOLD,
    MAX_VALID_COMPETITOR_PRICE,
    COMPETITOR_MATCH_FACTOR,
    INCREASE_FACTOR,
    MIN_CHANGE_THRESHOLD,
    COMPETITOR_CONFIDENCE,
)

SERVICE_PATH = "services.pricing.competitor_fallback"

# ============================================================
# Helpers
# ============================================================

PRODUCT_ID = uuid4()
USER_ID = uuid4()
COMP_ID = uuid4()


def make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def make_product(
    id=None,
    name="Test Product",
    current_price=Decimal("100.00"),
    min_price=None,
    max_price=None,
):
    p = MagicMock()
    p.id = id or PRODUCT_ID
    p.name = name
    p.current_price = current_price
    p.min_price = min_price
    p.max_price = max_price
    return p


def make_settings(
    auto_approve_enabled=True,
    recommendation_valid_hours=48,
):
    s = MagicMock()
    s.auto_approve_enabled = auto_approve_enabled
    s.recommendation_valid_hours = recommendation_valid_hours
    return s


def make_signals(competitor_prices=None):
    from services.pricing.rule_evaluator import MarketSignals
    return MarketSignals(competitor_prices=competitor_prices or {})


# ============================================================
# 1. Module Constants
# ============================================================

class TestModuleConstants:

    def test_above_competitor_threshold(self):
        assert ABOVE_COMPETITOR_THRESHOLD == Decimal("10")

    def test_below_competitor_threshold(self):
        assert BELOW_COMPETITOR_THRESHOLD == Decimal("-15")

    def test_max_valid_competitor_price(self):
        assert MAX_VALID_COMPETITOR_PRICE == Decimal("5000")

    def test_competitor_match_factor(self):
        assert COMPETITOR_MATCH_FACTOR == Decimal("0.98")

    def test_increase_factor(self):
        assert INCREASE_FACTOR == Decimal("1.05")

    def test_min_change_threshold(self):
        assert MIN_CHANGE_THRESHOLD == Decimal("1")

    def test_competitor_confidence(self):
        assert COMPETITOR_CONFIDENCE == Decimal("0.65")


# ============================================================
# 2. Initialization
# ============================================================

class TestCompetitorFallbackInit:

    def test_stores_db(self):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)
        assert svc.db is db

    def test_creates_settings_service(self):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)
        assert svc.settings_service is not None


# ============================================================
# 3. generate (orchestration)
# ============================================================

class TestGenerate:

    @pytest.mark.asyncio
    async def test_returns_none_when_no_competitor_prices(self):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)
        signals = make_signals(competitor_prices={})

        result = await svc.generate(make_product(), USER_ID, signals)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_invalid_current_price(self):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)
        signals = make_signals(competitor_prices={COMP_ID: Decimal("50")})
        product = make_product(current_price=Decimal("0"))

        result = await svc.generate(product, USER_ID, signals)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_price_is_competitive(self):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)
        # Current=100, competitor=100 → 0% diff → competitive, no change
        signals = make_signals(competitor_prices={COMP_ID: Decimal("100")})

        result = await svc.generate(make_product(current_price=Decimal("100")), USER_ID, signals)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_change_too_small(self):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)

        # Engineer a scenario where calculated price is very close to current
        # Current=100, competitor=89 → diff_pct=12.4% > 10 → suggests match at 98%
        # new_price = 89*0.98 = 87.22 → change = -12.78% → exceeds MIN_CHANGE_THRESHOLD
        # Instead, mock _calculate_competitor_based_price to return tiny change
        svc._find_valid_competitor_price = MagicMock(return_value=(Decimal("100"), COMP_ID))
        svc._is_valid_current_price = MagicMock(return_value=True)
        svc._calculate_competitor_based_price = MagicMock(return_value=(Decimal("100.50"), "test"))
        svc._apply_constraints = MagicMock(return_value=Decimal("100.50"))
        svc._calculate_change_percent = MagicMock(return_value=Decimal("0.50"))

        result = await svc.generate(make_product(), USER_ID, make_signals())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_recommendation_when_significant_change(self):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)

        svc._find_valid_competitor_price = MagicMock(return_value=(Decimal("80"), COMP_ID))
        svc._is_valid_current_price = MagicMock(return_value=True)
        svc._calculate_competitor_based_price = MagicMock(
            return_value=(Decimal("78.40"), "Price match at 98%")
        )
        svc._apply_constraints = MagicMock(return_value=Decimal("78.40"))
        svc._calculate_change_percent = MagicMock(return_value=Decimal("-21.60"))
        svc.settings_service.get_or_create = AsyncMock(return_value=make_settings())

        mock_rec = MagicMock()
        svc._create_recommendation = AsyncMock(return_value=mock_rec)

        result = await svc.generate(make_product(), USER_ID, make_signals())
        assert result is mock_rec


# ============================================================
# 4. _find_valid_competitor_price
# ============================================================

class TestFindValidCompetitorPrice:

    def setup_method(self):
        self.svc = CompetitorFallbackService(make_mock_db())

    def test_returns_first_valid_price(self):
        prices = {COMP_ID: Decimal("99.99")}
        price, comp_id = self.svc._find_valid_competitor_price(prices)
        assert price == Decimal("99.99")
        assert comp_id == COMP_ID

    def test_returns_none_for_empty_dict(self):
        price, comp_id = self.svc._find_valid_competitor_price({})
        assert price is None
        assert comp_id is None

    def test_skips_zero_price(self):
        prices = {COMP_ID: Decimal("0")}
        price, _ = self.svc._find_valid_competitor_price(prices)
        assert price is None

    def test_skips_negative_price(self):
        prices = {COMP_ID: Decimal("-10")}
        price, _ = self.svc._find_valid_competitor_price(prices)
        assert price is None

    def test_skips_price_above_max_valid(self):
        prices = {COMP_ID: Decimal("6000")}
        price, _ = self.svc._find_valid_competitor_price(prices)
        assert price is None

    def test_accepts_price_just_below_max(self):
        prices = {COMP_ID: Decimal("4999.99")}
        price, _ = self.svc._find_valid_competitor_price(prices)
        assert price == Decimal("4999.99")

    def test_skips_none_price(self):
        prices = {COMP_ID: None}
        price, _ = self.svc._find_valid_competitor_price(prices)
        assert price is None

    def test_finds_first_valid_among_invalid(self):
        id2 = uuid4()
        prices = {COMP_ID: Decimal("0"), id2: Decimal("50")}
        price, comp_id = self.svc._find_valid_competitor_price(prices)
        assert price == Decimal("50")
        assert comp_id == id2


# ============================================================
# 5. _is_valid_current_price
# ============================================================

class TestIsValidCurrentPrice:

    def setup_method(self):
        self.svc = CompetitorFallbackService(make_mock_db())

    def test_valid_price(self):
        assert self.svc._is_valid_current_price(make_product(current_price=Decimal("50"))) is True

    def test_zero_price(self):
        assert self.svc._is_valid_current_price(make_product(current_price=Decimal("0"))) is False

    def test_negative_price(self):
        assert self.svc._is_valid_current_price(make_product(current_price=Decimal("-10"))) is False

    def test_none_price(self):
        assert self.svc._is_valid_current_price(make_product(current_price=None)) is False


# ============================================================
# 6. _calculate_competitor_based_price
# ============================================================

class TestCalculateCompetitorBasedPrice:

    def setup_method(self):
        self.svc = CompetitorFallbackService(make_mock_db())

    def test_above_competitor_suggests_decrease(self):
        """Current=120, competitor=100 → 20% above → suggest 98% match."""
        product = make_product(current_price=Decimal("120"))
        new_price, reasoning = self.svc._calculate_competitor_based_price(
            product, Decimal("100")
        )
        assert new_price == Decimal("100") * COMPETITOR_MATCH_FACTOR  # 98.00
        assert "above competitor" in reasoning

    def test_below_competitor_suggests_increase(self):
        """Current=80, competitor=100 → -20% → suggest 5% increase."""
        product = make_product(current_price=Decimal("80"))
        new_price, reasoning = self.svc._calculate_competitor_based_price(
            product, Decimal("100")
        )
        assert new_price == Decimal("80") * INCREASE_FACTOR  # 84.00
        assert "below competitor" in reasoning

    def test_competitive_returns_none(self):
        """Current=100, competitor=100 → 0% diff → competitive."""
        product = make_product(current_price=Decimal("100"))
        new_price, reasoning = self.svc._calculate_competitor_based_price(
            product, Decimal("100")
        )
        assert new_price is None
        assert reasoning == ""

    def test_exactly_at_above_threshold_no_change(self):
        """10% above is exactly at threshold → not >10, so competitive."""
        product = make_product(current_price=Decimal("110"))
        new_price, _ = self.svc._calculate_competitor_based_price(
            product, Decimal("100")
        )
        assert new_price is None

    def test_just_above_threshold_triggers(self):
        """10.01% above → triggers decrease."""
        product = make_product(current_price=Decimal("110.01"))
        new_price, _ = self.svc._calculate_competitor_based_price(
            product, Decimal("100")
        )
        assert new_price is not None

    def test_exactly_at_below_threshold_no_change(self):
        """15% below = -15 → not < -15, so competitive."""
        product = make_product(current_price=Decimal("85"))
        new_price, _ = self.svc._calculate_competitor_based_price(
            product, Decimal("100")
        )
        assert new_price is None


# ============================================================
# 7. _apply_constraints
# ============================================================

class TestApplyConstraints:

    def setup_method(self):
        self.svc = CompetitorFallbackService(make_mock_db())

    def test_no_constraints(self):
        product = make_product(min_price=None, max_price=None)
        result = self.svc._apply_constraints(Decimal("99.999"), product)
        assert result == Decimal("100.00")

    def test_clamps_to_min(self):
        product = make_product(min_price=Decimal("50"), max_price=None)
        result = self.svc._apply_constraints(Decimal("30"), product)
        assert result == Decimal("50.00")

    def test_clamps_to_max(self):
        product = make_product(min_price=None, max_price=Decimal("150"))
        result = self.svc._apply_constraints(Decimal("200"), product)
        assert result == Decimal("150.00")

    def test_rounds_to_two_decimals(self):
        product = make_product(min_price=None, max_price=None)
        result = self.svc._apply_constraints(Decimal("99.995"), product)
        assert result == Decimal("100.00")  # ROUND_HALF_UP


# ============================================================
# 8. _calculate_change_percent
# ============================================================

class TestCalculateChangePercent:

    def setup_method(self):
        self.svc = CompetitorFallbackService(make_mock_db())

    def test_positive_change(self):
        result = self.svc._calculate_change_percent(Decimal("100"), Decimal("110"))
        assert result == Decimal("10.00")

    def test_negative_change(self):
        result = self.svc._calculate_change_percent(Decimal("100"), Decimal("90"))
        assert result == Decimal("-10.00")

    def test_no_change(self):
        result = self.svc._calculate_change_percent(Decimal("100"), Decimal("100"))
        assert result == Decimal("0.00")

    def test_rounds_to_two_decimals(self):
        result = self.svc._calculate_change_percent(Decimal("3"), Decimal("4"))
        assert result == Decimal("33.33")


# ============================================================
# 9. _build_factors
# ============================================================

class TestBuildFactors:

    def setup_method(self):
        self.svc = CompetitorFallbackService(make_mock_db())

    def test_has_required_keys(self):
        result = self.svc._build_factors(
            Decimal("100"), Decimal("90"), str(COMP_ID), Decimal("80")
        )
        assert "match_details" in result
        assert "price_impacts" in result
        assert "confidence_breakdown" in result
        assert "data_source" in result

    def test_data_source_is_competitor_only(self):
        result = self.svc._build_factors(
            Decimal("100"), Decimal("90"), str(COMP_ID), Decimal("80")
        )
        assert result["data_source"] == "competitor_only"

    def test_match_details_contains_competitor_info(self):
        result = self.svc._build_factors(
            Decimal("100"), Decimal("90"), str(COMP_ID), Decimal("80")
        )
        details = result["match_details"]
        assert details["rule_type"] == "competitor_fallback"
        assert details["competitor_id"] == str(COMP_ID)
        assert details["competitor_price"] == 80.0

    def test_confidence_is_065(self):
        result = self.svc._build_factors(
            Decimal("100"), Decimal("90"), str(COMP_ID), Decimal("80")
        )
        assert result["confidence_breakdown"]["base_confidence"] == 0.65

    def test_none_competitor_id(self):
        result = self.svc._build_factors(
            Decimal("100"), Decimal("90"), None, Decimal("80")
        )
        assert result["match_details"]["competitor_id"] is None


# ============================================================
# 10. _try_auto_apply
# ============================================================

class TestTryAutoApply:

    @pytest.mark.asyncio
    async def test_skips_when_requires_approval(self):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)

        rec = MagicMock(requires_approval=True, id=uuid4())
        settings = make_settings(auto_approve_enabled=True)

        with patch(f"{SERVICE_PATH}.ApprovalService", create=True) as MockAS:
            await svc._try_auto_apply(rec, USER_ID, settings)
            MockAS.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_auto_approve_disabled(self):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)

        rec = MagicMock(requires_approval=False, id=uuid4())
        settings = make_settings(auto_approve_enabled=False)

        with patch(f"{SERVICE_PATH}.ApprovalService", create=True) as MockAS:
            await svc._try_auto_apply(rec, USER_ID, settings)
            MockAS.assert_not_called()

    @pytest.mark.asyncio
    @patch("services.pricing.approval_service.ApprovalService")
    async def test_auto_applies_when_eligible(self, MockAS):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)

        mock_instance = AsyncMock()
        MockAS.return_value = mock_instance

        rec = MagicMock(requires_approval=False, id=uuid4())
        settings = make_settings(auto_approve_enabled=True)

        await svc._try_auto_apply(rec, USER_ID, settings)
        mock_instance.auto_approve_and_apply.assert_awaited_once_with(rec.id, USER_ID)

    @pytest.mark.asyncio
    @patch("services.pricing.approval_service.ApprovalService")
    async def test_handles_auto_apply_exception(self, MockAS):
        db = make_mock_db()
        svc = CompetitorFallbackService(db)

        mock_instance = AsyncMock()
        mock_instance.auto_approve_and_apply.side_effect = Exception("failed")
        MockAS.return_value = mock_instance

        rec = MagicMock(requires_approval=False, id=uuid4())
        settings = make_settings(auto_approve_enabled=True)

        # Should not raise
        await svc._try_auto_apply(rec, USER_ID, settings)


        