"""
Payment Model

Tracks MNEE payment transactions for subscriptions and other purchases.
"""

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel


class PaymentStatus(str, Enum):
    """Payment transaction status."""

    PENDING = "pending"  # Awaiting payment
    PROCESSING = "processing"  # Payment detected, confirming
    CONFIRMED = "confirmed"  # Payment confirmed on blockchain
    FAILED = "failed"  # Payment failed
    EXPIRED = "expired"  # Payment request expired
    REFUNDED = "refunded"  # Payment refunded


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
    txid: str | None = Field(default=None, max_length=100, index=True)
    from_address: str | None = Field(default=None, max_length=50)
    to_address: str | None = Field(default=None, max_length=50)
    memo: str | None = Field(default=None, max_length=200)

    # Description
    description: str | None = Field(default=None, max_length=500)

    # Error tracking
    error_message: str | None = Field(default=None, max_length=500)


class Payment(PaymentBase, table=True):
    """Payment transaction record."""

    __tablename__ = "payments"

    # Primary key - UUID type to match database column
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Foreign keys
    user_id: UUID = Field(foreign_key="users.id", index=True)
    subscription_id: UUID | None = Field(default=None, foreign_key="subscriptions.id", index=True)

    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    confirmed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    # Metadata (JSON string for flexibility)
    # NOTE: Cannot use 'metadata' as property name - conflicts with SQLAlchemy
    metadata_json: str | None = Field(default=None, sa_column=Column(Text))

    # Alias for backward compatibility
    @property
    def transaction_hash(self) -> str | None:
        """Alias for txid for backward compatibility."""
        return self.txid

    def get_metadata(self) -> dict | None:
        """Parse metadata JSON."""
        if self.metadata_json:
            import json

            try:
                return json.loads(self.metadata_json)
            except:
                return None
        return None

    def set_metadata(self, value: dict | None):
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
    description: str | None = None
    memo: str | None = None


class PaymentUpdate(SQLModel):
    """Schema for updating a payment."""

    status: str | None = None
    txid: str | None = None
    error_message: str | None = None


class PaymentResponse(PaymentBase):
    """Schema for payment API response."""

    id: UUID
    user_id: UUID
    subscription_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    confirmed_at: datetime | None = None

    class Config:
        from_attributes = True
