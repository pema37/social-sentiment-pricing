# backend/models/social_mention.py

import uuid as uuid_lib
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class SocialMention(SQLModel, table=True):
    __tablename__ = "social_mentions"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    user_id: uuid_lib.UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    product_id: uuid_lib.UUID | None = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True),
    )

    # Source info
    source: str = Field(max_length=50, index=True)  # twitter, reddit, tiktok, aggregator
    source_id: str = Field(max_length=255, index=True)  # Platform's unique ID

    # Content
    content: str = Field(sa_column=Column(Text, nullable=False))
    author: str = Field(max_length=255)
    author_followers: int | None = Field(default=None)
    engagement_count: int = Field(default=0)  # likes + shares + comments
    url: str | None = Field(default=None, max_length=500)

    # Metadata
    language: str | None = Field(default=None, max_length=10)
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    raw_data: dict | None = Field(default=None, sa_column=Column(JSON))

    # Processing status
    processed: bool = Field(default=False, index=True)

    # Timestamps
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
