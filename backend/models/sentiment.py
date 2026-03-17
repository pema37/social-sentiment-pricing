# backend/models/sentiment.py

import uuid as uuid_lib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class Sentiment(SQLModel, table=True):
    __tablename__ = "sentiments"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    product_id: uuid_lib.UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True),
    )

    source: str = Field(max_length=50)
    raw_text: str

    compound_score: Decimal = Field(max_digits=4, decimal_places=3)
    positive_score: Decimal = Field(max_digits=4, decimal_places=3)
    negative_score: Decimal = Field(max_digits=4, decimal_places=3)
    neutral_score: Decimal = Field(max_digits=4, decimal_places=3)

    author: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None)

    analyzed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
