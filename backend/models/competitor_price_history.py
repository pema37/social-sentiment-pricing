# backend/models/competitor_price_history.py

import uuid as uuid_lib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class CompetitorPriceHistory(SQLModel, table=True):
    """
    Tracks historical price changes for competitor products.

    Every time we scrape a competitor's price and it's different from
    the previous value, we log it here. This enables:
    - Trend analysis (are they raising or lowering prices?)
    - Promotion detection (sudden drops)
    - Competitive positioning over time
    """

    __tablename__ = "competitor_price_history"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    # Link to the competitor product mapping
    competitor_product_id: uuid_lib.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("competitor_products.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )

    # Price data
    old_price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    new_price: Decimal = Field(max_digits=10, decimal_places=2)
    currency: str = Field(default="USD", max_length=3)

    # Calculated change
    change_amount: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    change_percent: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)

    # Change classification
    change_type: str = Field(default="unknown", max_length=50)

    # Detection metadata
    detected_promotion: bool = Field(default=False)
    promotion_name: str | None = Field(default=None, max_length=255)

    # Availability tracking
    was_available: bool = Field(default=True)
    is_available: bool = Field(default=True)

    # Source info
    scraped_url: str | None = Field(default=None, max_length=1000)
    scrape_method: str = Field(default="http", max_length=50)

    # Timestamp of when this price was observed
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
