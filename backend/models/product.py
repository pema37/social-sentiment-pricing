# backend/models/product.py

import uuid as uuid_lib
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.integration import ProductIntegrationLink


class Product(SQLModel, table=True):
    __tablename__ = "products"

    # SKU uniqueness is now per-user, not global.
    # Enforced by composite unique constraint (user_id, sku) via Alembic migration
    # sku_per_user_001. This allows different merchants to have the same SKU.
    __table_args__ = (UniqueConstraint("user_id", "sku", name="uq_products_user_id_sku"),)

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    user_id: uuid_lib.UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    )

    name: str = Field(max_length=255, index=True)
    # FIX: Removed unique=True — now enforced as (user_id, sku) via __table_args__
    sku: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None)

    category: str | None = Field(default=None, max_length=100)
    image_url: str | None = Field(default=None)
    is_active: bool = Field(default=True)

    base_price: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    current_price: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    min_price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    max_price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    cost: Decimal | None = Field(default=None, max_digits=10, decimal_places=2, description="Cost to acquire/produce")

    # FIXED: Changed default from 0.1 to 0.2 (20% sentiment impact)
    sentiment_multiplier: Decimal = Field(default=Decimal("0.2"), max_digits=3, decimal_places=2)

    # NOTE: Keeping auto_pricing_enabled default as False for safety
    # Users should explicitly opt-in to automatic price changes
    auto_pricing_enabled: bool = Field(default=False)

    keywords: list[str] = Field(default=[], sa_column=Column(JSONB))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=lambda: datetime.now(UTC)),
    )

    # Relationships
    integration_links: list["ProductIntegrationLink"] = Relationship(back_populates="product")
