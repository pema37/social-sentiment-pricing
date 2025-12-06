# backend/models/pricing_rule.py
"""
Pricing Rule Model - Configurable rules that trigger price recommendations.

Rule Types: sentiment_threshold, competitor_relative, time_based, volume_surge, viral_detection
Actions: increase_percent, decrease_percent, set_absolute, match_competitor, undercut_competitor
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


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
    product_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True)
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
    last_triggered_at: Optional[datetime] = Field(default=None)
    
    # Timestamps - use naive UTC datetimes for asyncpg compatibility
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False
    )
    updated_at: Optional[datetime] = Field(default=None)

    class Config:
        use_enum_values = True
