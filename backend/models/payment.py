"""
Payment Model

Tracks MNEE payment transactions for subscriptions and other purchases.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from enum import Enum

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Text


class PaymentStatus(str, Enum):
    """Payment transaction status."""
    PENDING = "pending"          # Awaiting payment
    PROCESSING = "processing"    # Payment detected, confirming
    CONFIRMED = "confirmed"      # Payment confirmed on blockchain
    FAILED = "failed"            # Payment failed
    EXPIRED = "expired"          # Payment request expired
    REFUNDED = "refunded"        # Payment refunded


class PaymentType(str, Enum):
    """Type of payment."""
    SUBSCRIPTION = "subscription"
    ONE_TIME = "one_time"
    REFUND = "refund"


# =============================================================================
# Payment Model
# =============================================================================

class PaymentBase(SQLModel):
    """Base payment fields."""
    
    # Amount
    amount: str = Field(max_length=20)  # MNEE amount (e.g., "29.00")
    amount_raw: int = Field(default=0)  # Raw amount (5 decimals)
    currency: str = Field(default="MNEE", max_length=10)
    
    # Status
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    payment_type: PaymentType = Field(default=PaymentType.SUBSCRIPTION)
    
    # Transaction details
    txid: Optional[str] = Field(default=None, max_length=100, index=True)
    from_address: Optional[str] = Field(default=None, max_length=50)
    to_address: Optional[str] = Field(default=None, max_length=50)
    memo: Optional[str] = Field(default=None, max_length=200)
    
    # Description
    description: Optional[str] = Field(default=None, max_length=500)
    
    # Error tracking
    error_message: Optional[str] = Field(default=None, max_length=500)


class Payment(PaymentBase, table=True):
    """Payment transaction record."""
    
    __tablename__ = "payments"
    
    # Primary key
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # Foreign keys
    user_id: UUID = Field(foreign_key="users.id", index=True)
    subscription_id: Optional[UUID] = Field(
        default=None, 
        foreign_key="subscriptions.id",
        index=True
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None)
    confirmed_at: Optional[datetime] = Field(default=None)
    
    # Metadata (JSON string for flexibility)
    metadata_json: Optional[str] = Field(default=None, sa_column=Column(Text))


# =============================================================================
# Pydantic Schemas for API
# =============================================================================

class PaymentCreate(SQLModel):
    """Schema for creating a payment."""
    amount: str
    payment_type: PaymentType = PaymentType.SUBSCRIPTION
    description: Optional[str] = None
    memo: Optional[str] = None


class PaymentUpdate(SQLModel):
    """Schema for updating a payment."""
    status: Optional[PaymentStatus] = None
    txid: Optional[str] = None
    error_message: Optional[str] = None


class PaymentResponse(PaymentBase):
    """Schema for payment API response."""
    id: UUID
    user_id: UUID
    subscription_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

