# backend/models/price_recommendation.py
"""
Price Recommendation Model - AI-generated price suggestions with approval workflow.

Status Flow: pending → approved/rejected/expired → applied
Auto-approve: Changes < threshold are auto-approved based on user settings.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Text
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class RecommendationStatus(str, Enum):
    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    EXPIRED = "expired"


class PriceRecommendation(SQLModel, table=True):
    __tablename__ = "price_recommendations"

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
    
    # Which rule triggered this (null if manual or scheduled evaluation)
    triggered_rule_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), nullable=True)
    )
    
    # Price data
    current_price: Decimal = Field(decimal_places=2)
    recommended_price: Decimal = Field(decimal_places=2)
    change_percent: Decimal = Field(decimal_places=2)
    
    # AI reasoning
    confidence_score: Decimal = Field(
        decimal_places=2,
        description="0.0 to 1.0 based on data quality and signal agreement"
    )
    reasoning: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Human-readable explanation"
    )
    factors: dict = Field(
        default={},
        sa_column=Column(JSON),
        description="Breakdown: sentiment_impact, competitor_impact, trend_impact, etc."
    )
    
    # Status workflow
    status: RecommendationStatus = Field(default=RecommendationStatus.PENDING)
    requires_approval: bool = Field(default=True)
    
    # Expiry
    valid_until: datetime = Field(
        description="Recommendation expires if not acted on"
    )
    
    # Review tracking
    reviewed_by: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), nullable=True)
    )
    reviewed_at: Optional[datetime] = Field(default=None)
    rejection_reason: Optional[str] = Field(default=None, max_length=500)
    
    # Application tracking
    applied_at: Optional[datetime] = Field(default=None)
    applied_to_platform: Optional[str] = Field(default=None, max_length=50)
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    class Config:
        use_enum_values = True

