# backend/schemas/alert.py
"""Alert schemas for API request/response validation."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from models.alert import AlertType, AlertSeverity, AlertChannel, AlertStatus


# ============== AlertConfiguration Schemas ==============

class AlertConfigurationCreate(BaseModel):
    """Create a new alert configuration."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    alert_type: AlertType
    is_active: bool = True
    product_ids: Optional[List[UUID]] = None
    conditions: Dict[str, Any] = Field(default_factory=dict)
    channels: List[AlertChannel] = Field(default=[AlertChannel.IN_APP])
    channel_settings: Dict[str, Any] = Field(default_factory=dict)
    cooldown_minutes: int = Field(default=60, ge=1)
    max_per_day: int = Field(default=10, ge=1)


class AlertConfigurationUpdate(BaseModel):
    """Update an existing alert configuration."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    product_ids: Optional[List[UUID]] = None
    conditions: Optional[Dict[str, Any]] = None
    channels: Optional[List[AlertChannel]] = None
    channel_settings: Optional[Dict[str, Any]] = None
    cooldown_minutes: Optional[int] = Field(None, ge=1)
    max_per_day: Optional[int] = Field(None, ge=1)


class AlertConfigurationRead(BaseModel):
    """Alert configuration response."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    alert_type: AlertType
    is_active: bool
    product_ids: Optional[List[UUID]]
    conditions: Dict[str, Any]
    channels: List[AlertChannel]
    channel_settings: Dict[str, Any]
    cooldown_minutes: int
    max_per_day: int
    created_at: datetime
    updated_at: datetime
    last_triggered_at: Optional[datetime]


# ============== Alert Schemas ==============

class AlertCreate(BaseModel):
    """Create a new alert (usually system-generated)."""
    alert_type: AlertType
    severity: AlertSeverity = AlertSeverity.MEDIUM
    title: str = Field(..., max_length=255)
    message: str
    product_id: Optional[UUID] = None
    competitor_id: Optional[UUID] = None
    recommendation_id: Optional[UUID] = None
    configuration_id: Optional[UUID] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class AlertRead(BaseModel):
    """Alert response."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    configuration_id: Optional[UUID]
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    product_id: Optional[UUID]
    competitor_id: Optional[UUID]
    recommendation_id: Optional[UUID]
    data: Dict[str, Any]
    status: AlertStatus
    channels_sent: List[str]
    channels_failed: List[str]
    created_at: datetime
    sent_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[UUID]
    resolved_at: Optional[datetime]


class AlertAcknowledge(BaseModel):
    """Acknowledge an alert."""
    pass  # No body needed, user comes from auth


class AlertResolve(BaseModel):
    """Resolve an alert."""
    resolution_note: Optional[str] = None


# ============== Stats/Summary Schemas ==============

class AlertStats(BaseModel):
    """Alert statistics for dashboard."""
    total_unread: int
    by_severity: Dict[str, int]  # {"critical": 2, "high": 5, ...}
    by_type: Dict[str, int]  # {"sentiment_drop": 3, ...}
    recent_24h: int


class AlertListResponse(BaseModel):
    """Paginated alert list response."""
    alerts: List[AlertRead]
    total: int
    page: int
    per_page: int
    has_more: bool

