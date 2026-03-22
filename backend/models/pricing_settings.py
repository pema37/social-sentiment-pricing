# backend/models/pricing_settings.py
"""
Pricing Settings Model - Per-user configuration for auto-approval and notifications.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class PricingSettings(SQLModel, table=True):
    __tablename__ = "pricing_settings"

    id: UUID = Field(default_factory=uuid4, sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))

    # One settings record per user
    user_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True))

    # Auto-approval thresholds
    auto_approve_enabled: bool = Field(default=True)
    auto_approve_max_increase: Decimal = Field(
        default=Decimal("5.0"), decimal_places=2, description="Auto-approve price increases up to this %"
    )
    auto_approve_max_decrease: Decimal = Field(
        default=Decimal("10.0"), decimal_places=2, description="Auto-approve price decreases up to this %"
    )
    auto_approve_min_confidence: Decimal = Field(
        default=Decimal("0.7"), decimal_places=2, description="Minimum confidence score for auto-approval (0.0-1.0)"
    )
    min_margin_percent: Decimal = Field(
        default=Decimal("10.0"),
        decimal_places=2,
        description="Minimum profit margin % - never price below cost + this margin",
    )

    # Rate limits
    max_auto_changes_per_day: int = Field(default=3)
    global_cooldown_hours: int = Field(default=24)

    # Blackout periods (no auto-changes)
    blackout_hours_start: int | None = Field(default=0, description="Hour (0-23) when blackout starts")
    blackout_hours_end: int | None = Field(default=6, description="Hour (0-23) when blackout ends")

    # Products requiring manual approval regardless of thresholds
    require_approval_above_price: Decimal | None = Field(
        default=None, decimal_places=2, description="Products priced above this always need approval"
    )

    # Recommendation expiry
    recommendation_valid_hours: int = Field(default=48, description="Hours before pending recommendations expire")

    # Notifications
    notify_on_auto_apply: bool = Field(default=True)
    notify_on_pending: bool = Field(default=True)
    notification_email: str | None = Field(default=None, max_length=255)
    notification_slack_webhook: str | None = Field(default=None, max_length=500)

    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )
    updated_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
