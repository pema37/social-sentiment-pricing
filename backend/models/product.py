# backend/models/product.py

import uuid as uuid_lib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

if TYPE_CHECKING:
    from models.integration import ProductIntegrationLink


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    user_id: uuid_lib.UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    )

    name: str = Field(max_length=255, index=True)
    sku: Optional[str] = Field(default=None, max_length=100, unique=True)
    description: Optional[str] = Field(default=None)

    base_price: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    current_price: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    min_price: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    max_price: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    cost: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2, description="Cost to acquire/produce")

    sentiment_multiplier: Decimal = Field(default=Decimal("0.1"), max_digits=3, decimal_places=2)
    auto_pricing_enabled: bool = Field(default=False)

    keywords: List[str] = Field(default=[], sa_column=Column(JSON))

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    integration_links: List["ProductIntegrationLink"] = Relationship(back_populates="product")

