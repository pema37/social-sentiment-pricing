# backend/models/alert.py

"""
Alert models for notification system.

AlertConfiguration: User-defined rules for when to trigger alerts
Alert: Individual alert instances that get dispatched
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import Text
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import String


class AlertType(str, Enum):
    """Types of alerts the system can generate."""
    SENTIMENT_DROP = "sentiment_drop"
    SENTIMENT_SPIKE = "sentiment_spike"
    VOLUME_SURGE = "volume_surge"
    VIRAL_MENTION = "viral_mention"
    COMPETITOR_PRICE_CHANGE = "competitor_price_change"
    PRICE_RECOMMENDATION = "price_recommendation"
    PRICE_APPLIED = "price_applied"
    TREND_DETECTED = "trend_detected"
    ANOMALY_DETECTED = "anomaly_detected"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """Notification delivery channels."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class AlertStatus(str, Enum):
    """Alert lifecycle status."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertConfiguration(SQLModel, table=True):
    """
    User-configurable alert rules.
    
    Defines when alerts should trigger and how they should be delivered.
    """
    __tablename__ = "alert_configurations"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    
    # Configuration
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    alert_type: AlertType
    is_active: bool = Field(default=True)
    
    # Scope - which products this applies to (null = all products)
    product_ids: Optional[List[UUID]] = Field(
        default=None, 
        sa_column=Column(ARRAY(String))
    )
    
    # Conditions (JSONB for flexibility)
    # Example: {"threshold": -0.3, "direction": "below", "window_hours": 24}
    conditions: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    
    # Delivery settings
    channels: List[AlertChannel] = Field(
        default=[AlertChannel.IN_APP],
        sa_column=Column(ARRAY(String))
    )
    
    # Channel-specific settings
    # Example: {"email": "user@example.com", "slack_webhook": "https://..."}
    channel_settings: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    
    # Rate limiting
    cooldown_minutes: int = Field(default=60)  # Min time between alerts of same type
    max_per_day: int = Field(default=10)  # Max alerts per day for this config
    
    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    )
    last_triggered_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    
    # Relationships
    alerts: List["Alert"] = Relationship(back_populates="configuration")


class Alert(SQLModel, table=True):
    """
    Individual alert instance.
    
    Created when an AlertConfiguration's conditions are met.
    Tracks delivery status across channels.
    """
    __tablename__ = "alerts"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    configuration_id: Optional[UUID] = Field(
        default=None, 
        foreign_key="alert_configurations.id"
    )
    
    # Alert details
    alert_type: AlertType
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM)
    title: str = Field(max_length=255)
    message: str = Field(sa_column=Column(Text))
    
    # Context
    product_id: Optional[UUID] = Field(default=None, foreign_key="products.id")
    competitor_id: Optional[UUID] = Field(default=None, foreign_key="competitors.id")
    recommendation_id: Optional[UUID] = Field(
        default=None, 
        foreign_key="price_recommendations.id"
    )
    
    # Rich data payload
    # Example: {"sentiment_score": -0.45, "previous_score": 0.2, "change": -0.65}
    data: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    
    # Delivery tracking
    status: AlertStatus = Field(default=AlertStatus.PENDING)
    channels_sent: List[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String))
    )
    channels_failed: List[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String))
    )
    
    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True, default=lambda: datetime.now(timezone.utc))
    )
    sent_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    acknowledged_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    acknowledged_by: Optional[UUID] = Field(default=None)
    resolved_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    
    # Relationships
    configuration: Optional[AlertConfiguration] = Relationship(
        back_populates="alerts"
    )
