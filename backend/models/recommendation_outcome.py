# backend/models/recommendation_outcome.py
"""
Recommendation Outcome - Tracks actual performance after price changes.
Used to measure rule accuracy and improve confidence scoring.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class OutcomeLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    INCONCLUSIVE = "inconclusive"


class RecommendationOutcome(SQLModel, table=True):
    __tablename__ = "recommendation_outcomes"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )
    
    user_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    )
    recommendation_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), nullable=False, unique=True, index=True)
    )
    product_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    )
    rule_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    )
    rule_type: Optional[str] = Field(default=None, max_length=50)
    
    price_before: Decimal = Field(decimal_places=2)
    price_after: Decimal = Field(decimal_places=2)
    price_change_percent: Decimal = Field(decimal_places=2)
    
    sales_count_before: int = Field(default=0)
    units_sold_before: int = Field(default=0)
    revenue_before: Decimal = Field(default=Decimal("0"), decimal_places=2)
    avg_daily_sales_before: Decimal = Field(default=Decimal("0"), decimal_places=2)
    
    sales_count_after: int = Field(default=0)
    units_sold_after: int = Field(default=0)
    revenue_after: Decimal = Field(default=Decimal("0"), decimal_places=2)
    avg_daily_sales_after: Decimal = Field(default=Decimal("0"), decimal_places=2)
    
    revenue_change: Decimal = Field(default=Decimal("0"), decimal_places=2)
    revenue_change_percent: Optional[Decimal] = Field(default=None, decimal_places=2)
    units_change: int = Field(default=0)
    units_change_percent: Optional[Decimal] = Field(default=None, decimal_places=2)
    
    outcome_score: Decimal = Field(default=Decimal("0"), decimal_places=2)
    outcome_label: OutcomeLabel = Field(default=OutcomeLabel.INCONCLUSIVE)
    
    original_confidence: Decimal = Field(decimal_places=2)
    
    price_applied_at: datetime = Field(index=True)
    measurement_window_hours: int = Field(default=48)
    measured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        use_enum_values = True

