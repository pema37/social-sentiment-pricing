# backend/models/pricing_rule.py
"""
Pricing Rule Model - Configurable rules that trigger price recommendations.

Rule Types: sentiment_threshold, competitor_relative, time_based, volume_surge, viral_detection
Actions: increase_percent, decrease_percent, set_absolute, match_competitor, undercut_competitor

Scoping: Rules can apply to:
- A single product (product_id)
- All products (applies_to_all_products = True)
- Specific products (applies_to_products = [uuid1, uuid2, ...])
- Products by category (applies_to_categories = ["Electronics", ...])
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class RuleType(StrEnum):
    SENTIMENT_THRESHOLD = "sentiment_threshold"
    COMPETITOR_RELATIVE = "competitor_relative"
    TIME_BASED = "time_based"
    VOLUME_SURGE = "volume_surge"
    VIRAL_DETECTION = "viral_detection"


class RuleAction(StrEnum):
    INCREASE_PERCENT = "increase_percent"
    DECREASE_PERCENT = "decrease_percent"
    SET_ABSOLUTE = "set_absolute"
    MATCH_COMPETITOR = "match_competitor"
    UNDERCUT_COMPETITOR = "undercut_competitor"


class PricingRule(SQLModel, table=True):
    __tablename__ = "pricing_rules"

    id: UUID = Field(default_factory=uuid4, sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))

    # Ownership
    user_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True))

    # Legacy single product targeting (nullable for backward compatibility)
    product_id: UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=True, index=True))

    # NEW: Scoping - which products this rule applies to
    applies_to_all_products: bool = Field(default=False)
    applies_to_products: list[str] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    applies_to_categories: list[str] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))

    # Rule definition
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    rule_type: RuleType
    is_active: bool = Field(default=True)
    priority: int = Field(default=0)

    # Sentiment threshold conditions
    sentiment_threshold: Decimal | None = Field(default=None, decimal_places=2)
    sentiment_direction: str | None = Field(default=None, max_length=10)

    # Competitor relative conditions
    competitor_id: UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), nullable=True))
    competitor_margin_percent: Decimal | None = Field(default=None, decimal_places=2)
    price_position: str | None = Field(default=None, max_length=20)

    # Time-based conditions
    time_days: str | None = Field(default=None, max_length=50)
    time_start: str | None = Field(default=None, max_length=5)
    time_end: str | None = Field(default=None, max_length=5)

    # Volume surge conditions
    volume_threshold: int | None = Field(default=None)
    volume_window_hours: int | None = Field(default=24)

    # Viral detection conditions
    viral_threshold_reach: int | None = Field(default=None)
    viral_threshold_engagement: int | None = Field(default=None)
    viral_sentiment_min: Decimal | None = Field(default=None, decimal_places=2)

    # Action
    action: RuleAction
    action_value: Decimal = Field(decimal_places=2)

    # Boundaries
    min_price: Decimal | None = Field(default=None, decimal_places=2)
    max_price: Decimal | None = Field(default=None, decimal_places=2)
    max_change_percent: Decimal = Field(default=Decimal("15.0"), decimal_places=2)

    # Cooldown
    cooldown_hours: int = Field(default=24)
    last_triggered_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    # Timestamps - use naive UTC datetimes for asyncpg compatibility
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True, default=lambda: datetime.now(UTC))
    )

    class Config:
        use_enum_values = True

    def applies_to_product(self, product_id: UUID, product_category: str | None = None) -> bool:
        """
        Check if this rule applies to a given product.

        A rule applies if ANY of these conditions are true:
        1. applies_to_all_products is True
        2. product_id matches the rule's product_id (legacy)
        3. product_id is in applies_to_products list
        4. product_category is in applies_to_categories list
        """
        # Check all products flag
        if self.applies_to_all_products:
            return True

        # Check legacy single product
        if self.product_id and self.product_id == product_id:
            return True

        # Check products list
        if self.applies_to_products and str(product_id) in self.applies_to_products:
            return True

        # Check categories list
        return bool(self.applies_to_categories and product_category and product_category in self.applies_to_categories)
