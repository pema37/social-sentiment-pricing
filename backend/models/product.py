# backend/models/product.py

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlmodel import SQLModel, Field, Column, JSON


class Product(SQLModel, table=True):
    __tablename__ = "products"

    # Primary key (UUID)
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )

    # Foreign key to User
    user_id: str = Field(foreign_key="users.id", index=True, max_length=36)

    # Basic product info
    name: str = Field(max_length=255, index=True)
    sku: Optional[str] = Field(default=None, max_length=100, unique=True)
    description: Optional[str] = Field(default=None)

    # Pricing fields
    base_price: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    current_price: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    min_price: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    max_price: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)

    # Sentiment pricing config
    sentiment_multiplier: Decimal = Field(default=0.1, max_digits=3, decimal_places=2)
    auto_pricing_enabled: bool = Field(default=False)

    # Keywords to search on social media (stored as JSON array)
    keywords: List[str] = Field(default=[], sa_column=Column(JSON))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

