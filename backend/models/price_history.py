# backend/models/price_history.py

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class PriceHistory(SQLModel, table=True):
    __tablename__ = "price_history"

    # Primary key (UUID)
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )

    # Foreign key to Product
    product_id: str = Field(foreign_key="products.id", index=True, max_length=36)

    # Price change details
    old_price: Decimal = Field(max_digits=10, decimal_places=2)
    new_price: Decimal = Field(max_digits=10, decimal_places=2)
    change_percent: Decimal = Field(max_digits=5, decimal_places=2)  # e.g., +5.25 or -3.50

    # Why the price changed
    change_reason: str = Field(max_length=50)  # sentiment_adjustment, manual, competitor_response

    # Sentiment context at time of change
    sentiment_score_at_change: Optional[Decimal] = Field(
        default=None, max_digits=4, decimal_places=3
    )
    sentiment_volume: Optional[int] = Field(default=None)  # Number of mentions analyzed

    # Who/what triggered the change
    triggered_by: str = Field(max_length=50)  # system, user, api

    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)


