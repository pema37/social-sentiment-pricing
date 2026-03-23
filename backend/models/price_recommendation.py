# backend/models/price_recommendation.py
"""
Price Recommendation Model - AI-generated price suggestions with approval workflow.

Status Flow: pending → approved/rejected/expired → applied
Auto-approve: Changes < threshold are auto-approved based on user settings.
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import JSON
from pydantic import field_validator
from sqlmodel import Field, SQLModel


class RecommendationStatus(StrEnum):
    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    EXPIRED = "expired"


class PriceRecommendation(SQLModel, table=True):
    __tablename__ = "price_recommendations"

    id: UUID = Field(default_factory=uuid4, sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))

    # Ownership
    user_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True))
    product_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True))

    # Which rule triggered this (null if manual or scheduled evaluation)
    triggered_rule_id: UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("pricing_rules.id"), nullable=True))

    # Price data
    current_price: Decimal = Field(decimal_places=2)
    recommended_price: Decimal = Field(decimal_places=2)
    change_percent: Decimal = Field(decimal_places=2)

    # AI reasoning
    confidence_score: Decimal = Field(
        decimal_places=2, description="0.0 to 1.0 based on data quality and signal agreement"
    )
    reasoning: str = Field(sa_column=Column(Text, nullable=False), description="Human-readable explanation")
    factors: dict = Field(
        default={},
        sa_column=Column(JSON),
        description="Breakdown: sentiment_impact, competitor_impact, trend_impact, etc.",
    )

    # Status workflow
    status: RecommendationStatus = Field(default=RecommendationStatus.PENDING)
    requires_approval: bool = Field(default=True)

    # Expiry
    valid_until: datetime = Field(
        description="Recommendation expires if not acted on", sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    @field_validator("valid_until")
    @classmethod
    def valid_until_must_be_future(cls, v: datetime) -> datetime:
        now = datetime.now(UTC)
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        if v <= now:
            raise ValueError("valid_until must be a future date")
        return v

    # Review tracking
    reviewed_by: UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), nullable=True))
    reviewed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    rejection_reason: str | None = Field(default=None, max_length=500)

    # Application tracking
    applied_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    applied_to_platform: str | None = Field(default=None, max_length=50)

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(UTC)),
    )

    class Config:
        use_enum_values = True
