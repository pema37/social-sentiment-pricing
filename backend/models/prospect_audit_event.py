"""
Prospect Audit Event Model — Tracks prospect audit funnel events.

Events: page_view → audit_started → audit_completed → email_submitted → pdf_downloaded
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class ProspectAuditEvent(SQLModel, table=True):
    """Tracks prospect audit funnel events."""

    __tablename__ = "prospect_audit_events"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    event_type: str = Field(
        sa_column=Column(String(50), nullable=False, index=True),
    )
    store_url: str | None = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )
    email: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    input_mode: str | None = Field(
        default=None,
        sa_column=Column(String(10), nullable=True),
    )
    products_found: int | None = Field(default=None)
    estimated_impact: str | None = Field(
        default=None,
        sa_column=Column(String(50), nullable=True),
    )
    ip_hash: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    user_agent: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
