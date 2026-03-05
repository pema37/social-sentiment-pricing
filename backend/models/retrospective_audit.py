"""
Retrospective Audit Model — Persists generated audits for retrieval.

Stores the audit summary and full SKU results as JSON so we don't
regenerate on every page load. The Celery weekly task populates this,
and the API can retrieve cached results.
"""

import uuid as uuid_lib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class RetrospectiveAudit(SQLModel, table=True):
    """Persisted retrospective pricing audit."""
    __tablename__ = "retrospective_audits"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    # Owner
    user_id: uuid_lib.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )

    # Audit parameters
    lookback_days: int = Field(default=90)

    # Summary metrics (denormalized for fast queries)
    total_products_analyzed: int = Field(default=0)
    total_estimated_impact: Decimal = Field(
        default=Decimal("0"), max_digits=12, decimal_places=2
    )
    total_lost_revenue: Decimal = Field(
        default=Decimal("0"), max_digits=12, decimal_places=2
    )
    total_missed_margin: Decimal = Field(
        default=Decimal("0"), max_digits=12, decimal_places=2
    )
    monthly_projected_loss: Decimal = Field(
        default=Decimal("0"), max_digits=12, decimal_places=2
    )
    annual_projected_loss: Decimal = Field(
        default=Decimal("0"), max_digits=12, decimal_places=2
    )

    # Full audit data (JSON blob for the complete response)
    summary_json: dict = Field(default={}, sa_column=Column(JSON))
    sku_results_json: list = Field(default=[], sa_column=Column(JSON))

    # Analysis window
    analysis_period_start: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    analysis_period_end: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    # Metadata
    methodology: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )



    