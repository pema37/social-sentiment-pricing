# backend/models/price_history.py

import uuid as uuid_lib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class PriceHistory(SQLModel, table=True):
    __tablename__ = "price_history"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    product_id: uuid_lib.UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True),
    )

    old_price: Decimal = Field(max_digits=10, decimal_places=2)
    new_price: Decimal = Field(max_digits=10, decimal_places=2)
    change_percent: Decimal = Field(max_digits=5, decimal_places=2)

    change_reason: str = Field(max_length=50)

    sentiment_score_at_change: Optional[Decimal] = Field(
        default=None, max_digits=4, decimal_places=3
    )
    sentiment_volume: Optional[int] = Field(default=None)

    triggered_by: str = Field(max_length=50)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

