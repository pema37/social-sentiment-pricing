"""
Payment Model

Tracks MNEE payment transactions for subscriptions and other purchases.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from enum import Enum

from sqlmodel import SQLModel, Field
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
    
    # Status - use str instead of Enum to avoid PostgreSQL enum issues
    status: str = Field(default="pending", max_length=20)
    payment_type: str = Field(default="subscription", max_length=20)
    
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
    
    # Primary key - use str for id to match how it's used in routes
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    
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
    
    # Alias for backward compatibility
    @property
    def transaction_hash(self) -> Optional[str]:
        """Alias for txid for backward compatibility."""
        return self.txid
    
    def get_metadata(self) -> Optional[dict]:
        """Parse metadata JSON."""
        if self.metadata_json:
            import json
            try:
                return json.loads(self.metadata_json)
            except:
                return None
        return None
    
    def set_metadata(self, value: Optional[dict]):
        """Set metadata as JSON string."""
        if value:
            import json
            self.metadata_json = json.dumps(value)
        else:
            self.metadata_json = None


# =============================================================================
# Pydantic Schemas for API
# =============================================================================

class PaymentCreate(SQLModel):
    """Schema for creating a payment."""
    amount: str
    payment_type: str = "subscription"
    description: Optional[str] = None
    memo: Optional[str] = None


class PaymentUpdate(SQLModel):
    """Schema for updating a payment."""
    status: Optional[str] = None
    txid: Optional[str] = None
    error_message: Optional[str] = None


class PaymentResponse(PaymentBase):
    """Schema for payment API response."""
    id: str
    user_id: UUID
    subscription_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        