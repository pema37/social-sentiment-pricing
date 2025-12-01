# backend/models/social_mention.py


import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class SocialMention(SQLModel, table=True):
    __tablename__ = "social_mentions"
    
    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    user_id: uuid_lib.UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    )
    product_id: Optional[uuid_lib.UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=True, index=True),
    )
    
    # Source info
    source: str = Field(max_length=50, index=True)  # twitter, reddit, tiktok, aggregator
    source_id: str = Field(max_length=255, index=True)  # Platform's unique ID
    
    # Content
    content: str = Field(sa_column=Column(Text, nullable=False))
    author: str = Field(max_length=255)
    author_followers: Optional[int] = Field(default=None)
    engagement_count: int = Field(default=0)  # likes + shares + comments
    url: Optional[str] = Field(default=None, max_length=500)
    
    # Metadata
    language: Optional[str] = Field(default=None, max_length=10)
    published_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    raw_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Processing status
    processed: bool = Field(default=False, index=True)
    
    # Timestamps
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

