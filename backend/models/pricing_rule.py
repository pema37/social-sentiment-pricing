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

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB


class RuleType(str, Enum):
    SENTIMENT_THRESHOLD = "sentiment_threshold"
    COMPETITOR_RELATIVE = "competitor_relative"
    TIME_BASED = "time_based"
    VOLUME_SURGE = "volume_surge"
    VIRAL_DETECTION = "viral_detection"


class RuleAction(str, Enum):
    INCREASE_PERCENT = "increase_percent"
    DECREASE_PERCENT = "decrease_percent"
    SET_ABSOLUTE = "set_absolute"
    MATCH_COMPETITOR = "match_competitor"
    UNDERCUT_COMPETITOR = "undercut_competitor"


class PricingRule(SQLModel, table=True):
    __tablename__ = "pricing_rules"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )
    
    # Ownership
    user_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    )
    
    # Legacy single product targeting (nullable for backward compatibility)
    product_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    )
    
    # NEW: Scoping - which products this rule applies to
    applies_to_all_products: bool = Field(default=False)
    applies_to_products: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True)
    )
    applies_to_categories: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True)
    )
    
    # Rule definition
    name: str = Field(max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    rule_type: RuleType
    is_active: bool = Field(default=True)
    priority: int = Field(default=0)
    
    # Sentiment threshold conditions
    sentiment_threshold: Optional[Decimal] = Field(default=None, decimal_places=2)
    sentiment_direction: Optional[str] = Field(default=None, max_length=10)
    
    # Competitor relative conditions
    competitor_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), nullable=True)
    )
    competitor_margin_percent: Optional[Decimal] = Field(default=None, decimal_places=2)
    price_position: Optional[str] = Field(default=None, max_length=20)
    
    # Time-based conditions
    time_days: Optional[str] = Field(default=None, max_length=50)
    time_start: Optional[str] = Field(default=None, max_length=5)
    time_end: Optional[str] = Field(default=None, max_length=5)
    
    # Volume surge conditions
    volume_threshold: Optional[int] = Field(default=None)
    volume_window_hours: Optional[int] = Field(default=24)
    
    # Viral detection conditions
    viral_threshold_reach: Optional[int] = Field(default=None)
    viral_threshold_engagement: Optional[int] = Field(default=None)
    viral_sentiment_min: Optional[Decimal] = Field(default=None, decimal_places=2)
    
    # Action
    action: RuleAction
    action_value: Decimal = Field(decimal_places=2)
    
    # Boundaries
    min_price: Optional[Decimal] = Field(default=None, decimal_places=2)
    max_price: Optional[Decimal] = Field(default=None, decimal_places=2)
    max_change_percent: Decimal = Field(default=Decimal("15.0"), decimal_places=2)
    
    # Cooldown
    cooldown_hours: int = Field(default=24)
    last_triggered_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    
    # Timestamps - use naive UTC datetimes for asyncpg compatibility
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    )
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    class Config:
        use_enum_values = True
    
    def applies_to_product(self, product_id: UUID, product_category: Optional[str] = None) -> bool:
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
        if self.applies_to_products:
            if str(product_id) in self.applies_to_products:
                return True
        
        # Check categories list
        if self.applies_to_categories and product_category:
            if product_category in self.applies_to_categories:
                return True
        
        return False
    
    