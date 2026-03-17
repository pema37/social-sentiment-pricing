# backend/schemas/alert.py
"""Alert schemas for API request/response validation."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from models.alert import AlertChannel, AlertSeverity, AlertStatus, AlertType

# ============== AlertConfiguration Schemas ==============


class AlertConfigurationCreate(BaseModel):
    """Create a new alert configuration."""

    name: str = Field(..., max_length=255)
    description: str | None = None
    alert_type: AlertType
    is_active: bool = True
    product_ids: list[UUID] | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    channels: list[AlertChannel] = Field(default=[AlertChannel.IN_APP])
    channel_settings: dict[str, Any] = Field(default_factory=dict)
    cooldown_minutes: int = Field(default=60, ge=1)
    max_per_day: int = Field(default=10, ge=1)


class AlertConfigurationUpdate(BaseModel):
    """Update an existing alert configuration."""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    product_ids: list[UUID] | None = None
    conditions: dict[str, Any] | None = None
    channels: list[AlertChannel] | None = None
    channel_settings: dict[str, Any] | None = None
    cooldown_minutes: int | None = Field(None, ge=1)
    max_per_day: int | None = Field(None, ge=1)


class AlertConfigurationRead(BaseModel):
    """Alert configuration response."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    name: str
    description: str | None
    alert_type: AlertType
    is_active: bool
    product_ids: list[UUID] | None
    conditions: dict[str, Any]
    channels: list[AlertChannel]
    channel_settings: dict[str, Any]
    cooldown_minutes: int
    max_per_day: int
    created_at: datetime
    updated_at: datetime
    last_triggered_at: datetime | None


# ============== Alert Schemas ==============


class AlertCreate(BaseModel):
    """Create a new alert (usually system-generated)."""

    alert_type: AlertType
    severity: AlertSeverity = AlertSeverity.MEDIUM
    title: str = Field(..., max_length=255)
    message: str
    product_id: UUID | None = None
    competitor_id: UUID | None = None
    recommendation_id: UUID | None = None
    configuration_id: UUID | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class AlertRead(BaseModel):
    """Alert response."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    configuration_id: UUID | None
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    product_id: UUID | None
    competitor_id: UUID | None
    recommendation_id: UUID | None
    data: dict[str, Any]
    status: AlertStatus
    channels_sent: list[str]
    channels_failed: list[str]
    created_at: datetime
    sent_at: datetime | None
    acknowledged_at: datetime | None
    acknowledged_by: UUID | None
    resolved_at: datetime | None


class AlertAcknowledge(BaseModel):
    """Acknowledge an alert."""

    pass  # No body needed, user comes from auth


class AlertResolve(BaseModel):
    """Resolve an alert."""

    resolution_note: str | None = None


# ============== Stats/Summary Schemas ==============


class AlertStats(BaseModel):
    """Alert statistics for dashboard."""

    total_unread: int
    by_severity: dict[str, int]  # {"critical": 2, "high": 5, ...}
    by_type: dict[str, int]  # {"sentiment_drop": 3, ...}
    recent_24h: int


class AlertListResponse(BaseModel):
    """Paginated alert list response."""

    alerts: list[AlertRead]
    total: int
    page: int
    per_page: int
    has_more: bool
