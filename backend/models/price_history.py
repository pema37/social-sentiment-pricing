# backend/models/price_history.py
"""
Price History Model - Tracks all price changes with audit trail.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class ChangeReason(str, Enum):
    MANUAL = "manual"                           # User manually changed price
    RECOMMENDATION_APPLIED = "recommendation_applied"  # Auto or approved recommendation
    COMPETITOR_RESPONSE = "competitor_response"  # Reacting to competitor
    SCHEDULED = "scheduled"                     # Scheduled price change
    ROLLBACK = "rollback"                       # Reverted a previous change
    SYNC = "sync"                               # Synced from e-commerce platform
    INITIAL = "initial"                         # Initial price when product created


class PriceHistory(SQLModel, table=True):
    __tablename__ = "price_history"

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
    
    # Price data
    old_price: Decimal = Field(decimal_places=2)
    new_price: Decimal = Field(decimal_places=2)
    change_percent: Decimal = Field(decimal_places=2)
    
    # Audit trail
    change_reason: ChangeReason = Field(default=ChangeReason.MANUAL)
    recommendation_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), nullable=True),
        description="Links to the recommendation that triggered this change"
    )
    
    # Revenue tracking
    revenue_before: Optional[Decimal] = Field(default=None, decimal_places=2)
    revenue_after: Optional[Decimal] = Field(default=None, decimal_places=2)
    revenue_impact: Optional[Decimal] = Field(default=None, decimal_places=2)
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    class Config:
        use_enum_values = True

