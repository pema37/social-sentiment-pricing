# backend/models/competitor_product.py

import uuid as uuid_lib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class CompetitorProduct(SQLModel, table=True):
    """
    Links your product to a competitor's equivalent product.

    This allows tracking competitor prices for the same/similar items.
    One of your products can be linked to multiple competitor products
    (e.g., your iPhone 15 Pro linked to Amazon's listing, Best Buy's listing, etc.)
    """

    __tablename__ = "competitor_products"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    # Links to your product
    product_id: uuid_lib.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )

    # Links to competitor
    competitor_id: uuid_lib.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("competitors.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )

    # Competitor's product details
    competitor_product_name: str = Field(max_length=500)
    competitor_product_url: str = Field(max_length=1000)
    competitor_sku: str | None = Field(default=None, max_length=100)

    # Current tracked price (updated by scraper)
    current_price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    currency: str = Field(default="USD", max_length=3)

    # Price tracking metadata
    last_price_update: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    price_available: bool = Field(default=True)

    # Match confidence (how sure we are this is the same product)
    match_confidence: Decimal = Field(default=Decimal("1.0"), max_digits=3, decimal_places=2)

    # Notes about the mapping
    notes: str | None = Field(default=None, sa_column=Column(Text))

    # Tracking status
    is_active: bool = Field(default=True, index=True)

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=lambda: datetime.now(UTC)),
    )
