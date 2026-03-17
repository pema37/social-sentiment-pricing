"""
Test Suite: backend/schemas/competitor.py
Covers: CompetitorBase/Create/Update/Response, CompetitorProduct*,
        CompetitorPriceHistory*, CompetitorPriceComparison,
        CompetitorAlert, CompetitorTrendAnalysis.

Place this file at: backend/tests/test_competitor_schemas.py
Run with: pytest backend/tests/test_competitor_schemas.py -v
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas.competitor import (
    CompetitorAlert,
    CompetitorCreate,
    CompetitorListResponse,
    CompetitorPriceComparison,
    CompetitorPriceHistoryResponse,
    CompetitorProductCreate,
    CompetitorProductResponse,
    CompetitorProductUpdate,
    CompetitorProductWithDetails,
    CompetitorResponse,
    CompetitorTrendAnalysis,
    CompetitorUpdate,
)

# =====================================================================
# CompetitorBase / CompetitorCreate
# =====================================================================


class TestCompetitorCreate:
    def test_valid_minimal(self):
        c = CompetitorCreate(name="Amazon")
        assert c.name == "Amazon"
        assert c.website is None
        assert c.description is None
        assert c.scraping_config == {}
        assert c.is_active is True
        assert c.scrape_frequency_minutes == 60

    def test_valid_full(self):
        c = CompetitorCreate(
            name="Best Buy",
            website="https://bestbuy.com",
            description="Electronics retailer",
            scraping_config={"selector": ".price"},
            is_active=True,
            scrape_frequency_minutes=120,
        )
        assert c.website == "https://bestbuy.com"
        assert c.scraping_config == {"selector": ".price"}

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            CompetitorCreate()

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            CompetitorCreate(name="")

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            CompetitorCreate(name="x" * 256)

    def test_name_at_max_length(self):
        c = CompetitorCreate(name="x" * 255)
        assert len(c.name) == 255

    def test_website_max_length(self):
        with pytest.raises(ValidationError):
            CompetitorCreate(name="Test", website="x" * 501)

    def test_scrape_frequency_min(self):
        """Must be >= 5 minutes."""
        with pytest.raises(ValidationError):
            CompetitorCreate(name="Test", scrape_frequency_minutes=4)

    def test_scrape_frequency_max(self):
        """Must be <= 1440 minutes (24h)."""
        with pytest.raises(ValidationError):
            CompetitorCreate(name="Test", scrape_frequency_minutes=1441)

    def test_scrape_frequency_boundaries(self):
        c5 = CompetitorCreate(name="T", scrape_frequency_minutes=5)
        c1440 = CompetitorCreate(name="T", scrape_frequency_minutes=1440)
        assert c5.scrape_frequency_minutes == 5
        assert c1440.scrape_frequency_minutes == 1440

    def test_scraping_config_default_empty_dict(self):
        c = CompetitorCreate(name="Test")
        assert c.scraping_config == {}


# =====================================================================
# CompetitorUpdate
# =====================================================================


class TestCompetitorUpdate:
    def test_empty_update(self):
        u = CompetitorUpdate()
        assert u.name is None
        assert u.website is None
        assert u.scrape_frequency_minutes is None

    def test_partial_update_name(self):
        u = CompetitorUpdate(name="New Name")
        assert u.name == "New Name"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            CompetitorUpdate(name="")

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            CompetitorUpdate(name="x" * 256)

    def test_scrape_frequency_range(self):
        with pytest.raises(ValidationError):
            CompetitorUpdate(scrape_frequency_minutes=3)
        with pytest.raises(ValidationError):
            CompetitorUpdate(scrape_frequency_minutes=1500)

    def test_partial_update_config(self):
        u = CompetitorUpdate(scraping_config={"new": "config"})
        assert u.scraping_config == {"new": "config"}


# =====================================================================
# CompetitorResponse
# =====================================================================


class TestCompetitorResponse:
    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "name": "Amazon",
            "website": "https://amazon.com",
            "description": None,
            "scraping_config": {},
            "is_active": True,
            "scrape_frequency_minutes": 60,
            "last_scraped_at": None,
            "consecutive_failures": 0,
            "last_error": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

    def test_valid(self, valid_data):
        r = CompetitorResponse(**valid_data)
        assert r.name == "Amazon"
        assert r.consecutive_failures == 0

    def test_with_failure_tracking(self, valid_data):
        valid_data["consecutive_failures"] = 5
        valid_data["last_error"] = "Timeout"
        r = CompetitorResponse(**valid_data)
        assert r.consecutive_failures == 5
        assert r.last_error == "Timeout"

    def test_missing_id_raises(self, valid_data):
        del valid_data["id"]
        with pytest.raises(ValidationError):
            CompetitorResponse(**valid_data)

    def test_missing_user_id_raises(self, valid_data):
        del valid_data["user_id"]
        with pytest.raises(ValidationError):
            CompetitorResponse(**valid_data)


class TestCompetitorListResponse:
    def test_valid(self):
        r = CompetitorListResponse(items=[], total=0, page=1, size=20)
        assert r.items == []
        assert r.total == 0


# =====================================================================
# CompetitorProductCreate
# =====================================================================


class TestCompetitorProductCreate:
    def test_valid_minimal(self):
        p = CompetitorProductCreate(
            competitor_product_name="BT Headphones",
            competitor_product_url="https://amazon.com/bt-hp",
            product_id=uuid.uuid4(),
            competitor_id=uuid.uuid4(),
        )
        assert p.competitor_product_name == "BT Headphones"
        assert p.currency == "USD"
        assert p.match_confidence == Decimal("1.0")
        assert p.is_active is True
        assert p.current_price is None

    def test_valid_with_price(self):
        p = CompetitorProductCreate(
            competitor_product_name="BT Headphones",
            competitor_product_url="https://amazon.com/bt-hp",
            product_id=uuid.uuid4(),
            competitor_id=uuid.uuid4(),
            current_price=Decimal("74.99"),
        )
        assert p.current_price == Decimal("74.99")

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_url="https://test.com",
                product_id=uuid.uuid4(),
                competitor_id=uuid.uuid4(),
            )

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_name="Test",
                product_id=uuid.uuid4(),
                competitor_id=uuid.uuid4(),
            )

    def test_missing_product_id_raises(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_name="Test",
                competitor_product_url="https://test.com",
                competitor_id=uuid.uuid4(),
            )

    def test_missing_competitor_id_raises(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_name="Test",
                competitor_product_url="https://test.com",
                product_id=uuid.uuid4(),
            )

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_name="",
                competitor_product_url="https://test.com",
                product_id=uuid.uuid4(),
                competitor_id=uuid.uuid4(),
            )

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_name="x" * 501,
                competitor_product_url="https://test.com",
                product_id=uuid.uuid4(),
                competitor_id=uuid.uuid4(),
            )

    def test_url_max_length(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_name="Test",
                competitor_product_url="x" * 1001,
                product_id=uuid.uuid4(),
                competitor_id=uuid.uuid4(),
            )

    def test_match_confidence_range(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_name="Test",
                competitor_product_url="https://test.com",
                product_id=uuid.uuid4(),
                competitor_id=uuid.uuid4(),
                match_confidence=Decimal("1.5"),
            )

    def test_match_confidence_negative_raises(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_name="Test",
                competitor_product_url="https://test.com",
                product_id=uuid.uuid4(),
                competitor_id=uuid.uuid4(),
                match_confidence=Decimal("-0.1"),
            )

    def test_current_price_negative_raises(self):
        with pytest.raises(ValidationError):
            CompetitorProductCreate(
                competitor_product_name="Test",
                competitor_product_url="https://test.com",
                product_id=uuid.uuid4(),
                competitor_id=uuid.uuid4(),
                current_price=Decimal("-10"),
            )

    def test_current_price_zero_accepted(self):
        """ge=0 allows zero (free product)."""
        p = CompetitorProductCreate(
            competitor_product_name="Test",
            competitor_product_url="https://test.com",
            product_id=uuid.uuid4(),
            competitor_id=uuid.uuid4(),
            current_price=Decimal("0"),
        )
        assert p.current_price == Decimal("0")


# =====================================================================
# CompetitorProductUpdate
# =====================================================================


class TestCompetitorProductUpdate:
    def test_empty_update(self):
        u = CompetitorProductUpdate()
        assert u.competitor_product_name is None
        assert u.current_price is None

    def test_partial_update(self):
        u = CompetitorProductUpdate(current_price=Decimal("59.99"))
        assert u.current_price == Decimal("59.99")
        assert u.competitor_product_name is None

    def test_match_confidence_range(self):
        with pytest.raises(ValidationError):
            CompetitorProductUpdate(match_confidence=Decimal("2.0"))

    def test_current_price_negative_raises(self):
        with pytest.raises(ValidationError):
            CompetitorProductUpdate(current_price=Decimal("-5"))


# =====================================================================
# CompetitorProductResponse
# =====================================================================


class TestCompetitorProductResponse:
    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "product_id": uuid.uuid4(),
            "competitor_id": uuid.uuid4(),
            "competitor_product_name": "BT Headphones Pro",
            "competitor_product_url": "https://amazon.com/product",
            "competitor_sku": None,
            "currency": "USD",
            "match_confidence": Decimal("0.9"),
            "notes": None,
            "is_active": True,
            "current_price": Decimal("74.99"),
            "last_price_update": datetime.now(UTC),
            "price_available": True,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

    def test_valid(self, valid_data):
        r = CompetitorProductResponse(**valid_data)
        assert r.competitor_product_name == "BT Headphones Pro"
        assert r.current_price == Decimal("74.99")

    def test_nullable_fields(self, valid_data):
        valid_data["current_price"] = None
        valid_data["last_price_update"] = None
        valid_data["competitor_sku"] = None
        r = CompetitorProductResponse(**valid_data)
        assert r.current_price is None


# =====================================================================
# CompetitorProductWithDetails
# =====================================================================


class TestCompetitorProductWithDetails:
    def test_valid(self):
        d = CompetitorProductWithDetails(
            id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            competitor_id=uuid.uuid4(),
            competitor_product_name="BT HP",
            competitor_product_url="https://test.com",
            currency="USD",
            match_confidence=Decimal("0.9"),
            is_active=True,
            price_available=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            competitor_name="Amazon",
            your_product_name="Wireless Headphones",
            your_current_price=Decimal("99.99"),
            price_difference=Decimal("-25.00"),
            price_difference_percent=Decimal("-25.03"),
        )
        assert d.competitor_name == "Amazon"
        assert d.price_difference == Decimal("-25.00")


# =====================================================================
# CompetitorPriceHistoryResponse
# =====================================================================


class TestCompetitorPriceHistoryResponse:
    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "competitor_product_id": uuid.uuid4(),
            "old_price": Decimal("89.99"),
            "new_price": Decimal("74.99"),
            "currency": "USD",
            "change_amount": Decimal("-15.00"),
            "change_percent": Decimal("-16.67"),
            "change_type": "decrease",
            "detected_promotion": False,
            "promotion_name": None,
            "was_available": True,
            "is_available": True,
            "observed_at": datetime.now(UTC),
        }

    def test_valid(self, valid_data):
        r = CompetitorPriceHistoryResponse(**valid_data)
        assert r.new_price == Decimal("74.99")
        assert r.change_type == "decrease"

    def test_with_promotion(self, valid_data):
        valid_data["detected_promotion"] = True
        valid_data["promotion_name"] = "Summer Sale"
        r = CompetitorPriceHistoryResponse(**valid_data)
        assert r.detected_promotion is True
        assert r.promotion_name == "Summer Sale"

    def test_nullable_old_price(self, valid_data):
        valid_data["old_price"] = None
        valid_data["change_amount"] = None
        valid_data["change_percent"] = None
        r = CompetitorPriceHistoryResponse(**valid_data)
        assert r.old_price is None

    def test_missing_new_price_raises(self, valid_data):
        del valid_data["new_price"]
        with pytest.raises(ValidationError):
            CompetitorPriceHistoryResponse(**valid_data)


# =====================================================================
# CompetitorPriceComparison
# =====================================================================


class TestCompetitorPriceComparison:
    def test_valid(self):
        c = CompetitorPriceComparison(
            product_id=uuid.uuid4(),
            product_name="Headphones",
            your_price=Decimal("99.99"),
            competitor_prices=[
                {"competitor_name": "Amazon", "price": 74.99},
            ],
            lowest_competitor_price=Decimal("74.99"),
            highest_competitor_price=Decimal("74.99"),
            average_competitor_price=Decimal("74.99"),
            your_position="highest",
            recommendation="Consider lowering price",
        )
        assert c.your_position == "highest"
        assert len(c.competitor_prices) == 1

    def test_no_competitor_data(self):
        c = CompetitorPriceComparison(
            product_id=uuid.uuid4(),
            product_name="Test",
            your_price=Decimal("50"),
            competitor_prices=[],
            your_position="no_data",
            recommendation="Add competitors",
        )
        assert c.competitor_prices == []
        assert c.lowest_competitor_price is None


# =====================================================================
# CompetitorAlert
# =====================================================================


class TestCompetitorAlert:
    def test_valid(self):
        a = CompetitorAlert(
            alert_type="price_drop",
            competitor_name="Amazon",
            competitor_product_name="BT HP",
            product_id=uuid.uuid4(),
            your_product_name="Headphones",
            old_price=Decimal("89.99"),
            new_price=Decimal("74.99"),
            change_percent=Decimal("-16.67"),
            your_current_price=Decimal("99.99"),
            suggested_action="Lower price to match",
            observed_at=datetime.now(UTC),
        )
        assert a.alert_type == "price_drop"

    def test_nullable_old_price(self):
        """First observation — no old price."""
        a = CompetitorAlert(
            alert_type="new_promotion",
            competitor_name="Best Buy",
            competitor_product_name="HP Pro",
            product_id=uuid.uuid4(),
            your_product_name="Headphones",
            old_price=None,
            new_price=Decimal("69.99"),
            change_percent=None,
            your_current_price=Decimal("99.99"),
            suggested_action="Monitor",
            observed_at=datetime.now(UTC),
        )
        assert a.old_price is None
        assert a.change_percent is None


# =====================================================================
# CompetitorTrendAnalysis
# =====================================================================


class TestCompetitorTrendAnalysis:
    def test_valid(self):
        t = CompetitorTrendAnalysis(
            competitor_product_id=uuid.uuid4(),
            competitor_name="Amazon",
            product_name="BT Headphones",
            period_days=30,
            price_changes_count=5,
            average_price=Decimal("82.50"),
            min_price=Decimal("74.99"),
            max_price=Decimal("89.99"),
            current_price=Decimal("74.99"),
            trend_direction="decreasing",
            trend_strength=Decimal("0.75"),
            promotion_frequency=2,
        )
        assert t.trend_direction == "decreasing"
        assert t.trend_strength == Decimal("0.75")
        assert t.promotion_frequency == 2

    def test_nullable_current_price(self):
        t = CompetitorTrendAnalysis(
            competitor_product_id=uuid.uuid4(),
            competitor_name="Amazon",
            product_name="Test",
            period_days=7,
            price_changes_count=0,
            average_price=Decimal("50"),
            min_price=Decimal("50"),
            max_price=Decimal("50"),
            current_price=None,
            trend_direction="stable",
            trend_strength=Decimal("0.5"),
            promotion_frequency=0,
        )
        assert t.current_price is None

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            CompetitorTrendAnalysis(
                competitor_product_id=uuid.uuid4(),
                competitor_name="Amazon",
                # missing product_name and other required fields
            )
