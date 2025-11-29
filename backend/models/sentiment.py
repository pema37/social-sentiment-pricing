# backend/models/sentiment.py

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class Sentiment(SQLModel, table=True):
    __tablename__ = "sentiments"

    # Primary key (UUID)
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )

    # Foreign key to Product
    product_id: str = Field(foreign_key="products.id", index=True, max_length=36)

    # Source of the sentiment data
    source: str = Field(max_length=50)  # twitter, reddit, tiktok, manual

    # The actual text that was analyzed
    raw_text: str

    # VADER sentiment scores (-1.0 to 1.0)
    compound_score: Decimal = Field(max_digits=4, decimal_places=3)  # -1.000 to 1.000
    positive_score: Decimal = Field(max_digits=4, decimal_places=3)  # 0.000 to 1.000
    negative_score: Decimal = Field(max_digits=4, decimal_places=3)  # 0.000 to 1.000
    neutral_score: Decimal = Field(max_digits=4, decimal_places=3)   # 0.000 to 1.000

    # Optional metadata
    author: Optional[str] = Field(default=None, max_length=255)
    url: Optional[str] = Field(default=None)

    # Timestamp
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

