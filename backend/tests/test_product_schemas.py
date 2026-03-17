"""
Test Suite: backend/schemas/product.py
Covers: ProductCreate, ProductUpdate, ProductRead, PriceSuggestion.

Place this file at: backend/tests/test_product_schemas.py
Run with: pytest backend/tests/test_product_schemas.py -v
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas.product import (
    PriceSuggestion,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)

# =====================================================================
# ProductCreate
# =====================================================================


class TestProductCreate:
    def test_valid_minimal(self):
        """Only name + base_price required."""
        p = ProductCreate(name="Headphones", base_price=Decimal("49.99"))
        assert p.name == "Headphones"
        assert p.base_price == Decimal("49.99")
        assert p.sku is None
        assert p.description is None
        assert p.category is None
        assert p.image_url is None
        assert p.is_active is True
        assert p.cost is None
        assert p.min_price is None
        assert p.max_price is None
        assert p.sentiment_multiplier == Decimal("0.1")
        assert p.auto_pricing_enabled is False
        assert p.keywords == []

    def test_valid_full(self):
        p = ProductCreate(
            name="Wireless Headphones",
            sku="WH-001",
            description="Premium bluetooth headphones",
            base_price=Decimal("99.99"),
            category="Electronics",
            image_url="https://example.com/img.png",
            is_active=True,
            cost=Decimal("35.00"),
            min_price=Decimal("79.99"),
            max_price=Decimal("129.99"),
            sentiment_multiplier=Decimal("0.3"),
            auto_pricing_enabled=True,
            keywords=["headphones", "bluetooth", "wireless"],
        )
        assert p.sku == "WH-001"
        assert p.cost == Decimal("35.00")
        assert len(p.keywords) == 3

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError) as exc:
            ProductCreate(base_price=Decimal("10.00"))
        assert "name" in str(exc.value).lower()

    def test_missing_base_price_raises(self):
        with pytest.raises(ValidationError) as exc:
            ProductCreate(name="Test")
        assert "base_price" in str(exc.value).lower()

    def test_base_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            ProductCreate(name="Test", base_price=Decimal("0"))

    def test_base_price_negative_raises(self):
        with pytest.raises(ValidationError):
            ProductCreate(name="Test", base_price=Decimal("-10"))

    def test_base_price_accepts_decimal_string(self):
        """Pydantic coerces numeric strings to Decimal."""
        p = ProductCreate(name="Test", base_price="29.99")
        assert p.base_price == Decimal("29.99")

    def test_name_max_length(self):
        """Name over 255 chars should fail."""
        with pytest.raises(ValidationError):
            ProductCreate(name="x" * 256, base_price=Decimal("10"))

    def test_name_at_max_length(self):
        p = ProductCreate(name="x" * 255, base_price=Decimal("10"))
        assert len(p.name) == 255

    def test_sku_max_length(self):
        with pytest.raises(ValidationError):
            ProductCreate(name="Test", base_price=Decimal("10"), sku="x" * 101)

    def test_category_max_length(self):
        with pytest.raises(ValidationError):
            ProductCreate(name="Test", base_price=Decimal("10"), category="x" * 101)

    def test_cost_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            ProductCreate(name="Test", base_price=Decimal("10"), cost=Decimal("-1"))

    def test_cost_zero_accepted(self):
        p = ProductCreate(name="Test", base_price=Decimal("10"), cost=Decimal("0"))
        assert p.cost == Decimal("0")

    def test_min_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            ProductCreate(name="Test", base_price=Decimal("10"), min_price=Decimal("0"))

    def test_max_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            ProductCreate(name="Test", base_price=Decimal("10"), max_price=Decimal("0"))

    def test_sentiment_multiplier_range_low(self):
        """Must be >= 0."""
        with pytest.raises(ValidationError):
            ProductCreate(name="Test", base_price=Decimal("10"), sentiment_multiplier=Decimal("-0.1"))

    def test_sentiment_multiplier_range_high(self):
        """Must be <= 1."""
        with pytest.raises(ValidationError):
            ProductCreate(name="Test", base_price=Decimal("10"), sentiment_multiplier=Decimal("1.1"))

    def test_sentiment_multiplier_boundaries(self):
        p0 = ProductCreate(name="T", base_price=Decimal("10"), sentiment_multiplier=Decimal("0"))
        p1 = ProductCreate(name="T", base_price=Decimal("10"), sentiment_multiplier=Decimal("1"))
        assert p0.sentiment_multiplier == Decimal("0")
        assert p1.sentiment_multiplier == Decimal("1")

    def test_keywords_default_empty_list(self):
        p = ProductCreate(name="Test", base_price=Decimal("10"))
        assert p.keywords == []

    def test_keywords_with_values(self):
        p = ProductCreate(name="Test", base_price=Decimal("10"), keywords=["a", "b"])
        assert p.keywords == ["a", "b"]


# =====================================================================
# ProductUpdate
# =====================================================================


class TestProductUpdate:
    def test_empty_update(self):
        """All fields optional — empty update is valid."""
        u = ProductUpdate()
        assert u.name is None
        assert u.base_price is None
        assert u.keywords is None

    def test_partial_update_name(self):
        u = ProductUpdate(name="New Name")
        assert u.name == "New Name"
        assert u.base_price is None

    def test_partial_update_price(self):
        u = ProductUpdate(base_price=Decimal("59.99"))
        assert u.base_price == Decimal("59.99")

    def test_base_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            ProductUpdate(base_price=Decimal("0"))

    def test_current_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            ProductUpdate(current_price=Decimal("0"))

    def test_cost_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            ProductUpdate(cost=Decimal("-5"))

    def test_cost_zero_accepted(self):
        u = ProductUpdate(cost=Decimal("0"))
        assert u.cost == Decimal("0")

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            ProductUpdate(name="x" * 256)

    def test_sentiment_multiplier_range(self):
        with pytest.raises(ValidationError):
            ProductUpdate(sentiment_multiplier=Decimal("1.5"))

    def test_keywords_nullable(self):
        """Keywords can be None (meaning 'don't update') or a list."""
        u1 = ProductUpdate(keywords=None)
        u2 = ProductUpdate(keywords=["new", "tags"])
        assert u1.keywords is None
        assert u2.keywords == ["new", "tags"]


# =====================================================================
# ProductRead
# =====================================================================


class TestProductRead:
    @pytest.fixture
    def valid_product_data(self):
        return {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "name": "Test Product",
            "sku": "TP-001",
            "description": "A test product",
            "category": "Test",
            "image_url": "https://example.com/img.png",
            "is_active": True,
            "base_price": Decimal("99.99"),
            "current_price": Decimal("89.99"),
            "cost": Decimal("40.00"),
            "min_price": Decimal("69.99"),
            "max_price": Decimal("129.99"),
            "sentiment_multiplier": Decimal("0.1"),
            "auto_pricing_enabled": False,
            "keywords": ["test"],
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

    def test_valid_full(self, valid_product_data):
        p = ProductRead(**valid_product_data)
        assert p.name == "Test Product"
        assert p.current_price == Decimal("89.99")

    def test_optional_fields_null(self, valid_product_data):
        valid_product_data["sku"] = None
        valid_product_data["description"] = None
        valid_product_data["category"] = None
        valid_product_data["image_url"] = None
        valid_product_data["cost"] = None
        valid_product_data["min_price"] = None
        valid_product_data["max_price"] = None
        p = ProductRead(**valid_product_data)
        assert p.sku is None
        assert p.cost is None

    def test_missing_id_raises(self, valid_product_data):
        del valid_product_data["id"]
        with pytest.raises(ValidationError):
            ProductRead(**valid_product_data)

    def test_missing_user_id_raises(self, valid_product_data):
        del valid_product_data["user_id"]
        with pytest.raises(ValidationError):
            ProductRead(**valid_product_data)

    def test_missing_name_raises(self, valid_product_data):
        del valid_product_data["name"]
        with pytest.raises(ValidationError):
            ProductRead(**valid_product_data)

    def test_missing_base_price_raises(self, valid_product_data):
        del valid_product_data["base_price"]
        with pytest.raises(ValidationError):
            ProductRead(**valid_product_data)

    def test_missing_current_price_raises(self, valid_product_data):
        del valid_product_data["current_price"]
        with pytest.raises(ValidationError):
            ProductRead(**valid_product_data)

    def test_uuid_coercion(self, valid_product_data):
        valid_product_data["id"] = "12345678-1234-5678-1234-567812345678"
        p = ProductRead(**valid_product_data)
        assert isinstance(p.id, uuid.UUID)


# =====================================================================
# PriceSuggestion
# =====================================================================


class TestPriceSuggestion:
    @pytest.fixture
    def valid_suggestion(self):
        return {
            "product_id": uuid.uuid4(),
            "current_price": Decimal("99.99"),
            "suggested_price": Decimal("89.99"),
            "change_percent": Decimal("-10.01"),
            "reasoning": "Competitor price drop detected",
            "confidence": Decimal("0.85"),
            "factors": {"sentiment": 0.6, "competitor": -0.15},
        }

    def test_valid(self, valid_suggestion):
        s = PriceSuggestion(**valid_suggestion)
        assert s.suggested_price == Decimal("89.99")
        assert s.confidence == Decimal("0.85")

    def test_confidence_must_be_0_to_1(self):
        with pytest.raises(ValidationError):
            PriceSuggestion(
                product_id=uuid.uuid4(),
                current_price=Decimal("100"),
                suggested_price=Decimal("90"),
                change_percent=Decimal("-10"),
                reasoning="test",
                confidence=Decimal("1.5"),
                factors={},
            )

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValidationError):
            PriceSuggestion(
                product_id=uuid.uuid4(),
                current_price=Decimal("100"),
                suggested_price=Decimal("90"),
                change_percent=Decimal("-10"),
                reasoning="test",
                confidence=Decimal("-0.1"),
                factors={},
            )

    def test_confidence_boundary_zero(self, valid_suggestion):
        valid_suggestion["confidence"] = Decimal("0")
        s = PriceSuggestion(**valid_suggestion)
        assert s.confidence == Decimal("0")

    def test_confidence_boundary_one(self, valid_suggestion):
        valid_suggestion["confidence"] = Decimal("1")
        s = PriceSuggestion(**valid_suggestion)
        assert s.confidence == Decimal("1")

    def test_missing_reasoning_raises(self, valid_suggestion):
        del valid_suggestion["reasoning"]
        with pytest.raises(ValidationError):
            PriceSuggestion(**valid_suggestion)

    def test_missing_factors_raises(self, valid_suggestion):
        del valid_suggestion["factors"]
        with pytest.raises(ValidationError):
            PriceSuggestion(**valid_suggestion)

    def test_negative_change_percent(self, valid_suggestion):
        """Price decreases should have negative change_percent."""
        valid_suggestion["change_percent"] = Decimal("-15.5")
        s = PriceSuggestion(**valid_suggestion)
        assert s.change_percent < 0

    def test_positive_change_percent(self, valid_suggestion):
        """Price increases should have positive change_percent."""
        valid_suggestion["change_percent"] = Decimal("8.2")
        valid_suggestion["suggested_price"] = Decimal("108.19")
        s = PriceSuggestion(**valid_suggestion)
        assert s.change_percent > 0
