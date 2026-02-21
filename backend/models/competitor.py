# backend/models/competitor.py

import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class Competitor(SQLModel, table=True):
    """
    Represents a competitor company whose prices we track.
    
    Each competitor can have multiple products that map to your products.
    The scraping_config stores selectors and patterns for price extraction.
    """
    __tablename__ = "competitors"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    # Foreign key to User (tenant isolation)
    user_id: uuid_lib.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )

    # Competitor info
    name: str = Field(max_length=255, index=True)
    website: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Scraping configuration (CSS selectors, XPath, API endpoints, etc.)
    scraping_config: dict = Field(default={}, sa_column=Column(JSON))

    # Tracking status
    is_active: bool = Field(default=True, index=True)
    last_scraped_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    scrape_frequency_minutes: int = Field(default=60)

    # Error tracking
    consecutive_failures: int = Field(default=0)
    last_error: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

