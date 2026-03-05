"""
Audit Persistence Service

Saves and retrieves RetrospectiveAudit records from the database.
Used by the Celery weekly task (save) and the API endpoints (load cached).
"""

import uuid as uuid_lib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, desc
from sqlmodel import select

from models.retrospective_audit import RetrospectiveAudit
from schemas.retrospective_audit import (
    RetrospectiveAuditResponse,
    AuditSummary,
    SKUAuditResult,
    AuditListItem,
)


class AuditPersistenceService:
    """Save and retrieve persisted audits."""

    def __init__(self, session: AsyncSession, user_id: str):
        self.session = session
        self.user_id = user_id

    async def save_audit(self, audit: RetrospectiveAuditResponse) -> RetrospectiveAudit:
        """Persist an audit response to the database."""
        record = RetrospectiveAudit(
            id=audit.id,
            user_id=uuid_lib.UUID(self.user_id),
            lookback_days=audit.summary.lookback_days,
            total_products_analyzed=audit.summary.total_products_analyzed,
            total_estimated_impact=audit.summary.total_estimated_impact,
            total_lost_revenue=audit.summary.total_lost_revenue,
            total_missed_margin=audit.summary.total_missed_margin,
            monthly_projected_loss=audit.summary.monthly_projected_loss,
            annual_projected_loss=audit.summary.annual_projected_loss,
            summary_json=audit.summary.model_dump(mode="json"),
            sku_results_json=[s.model_dump(mode="json") for s in audit.sku_results],
            analysis_period_start=audit.summary.analysis_period_start,
            analysis_period_end=audit.summary.analysis_period_end,
            methodology=audit.methodology,
            created_at=audit.created_at,
        )

        self.session.add(record)
        await self.session.flush()
        return record

    async def get_latest(
        self, lookback_days: Optional[int] = None
    ) -> Optional[RetrospectiveAuditResponse]:
        """
        Get the most recent persisted audit for this user.
        Optionally filter by lookback_days.
        """
        query = (
            select(RetrospectiveAudit)
            .where(RetrospectiveAudit.user_id == self.user_id)
        )
        if lookback_days:
            query = query.where(RetrospectiveAudit.lookback_days == lookback_days)

        query = query.order_by(desc(RetrospectiveAudit.created_at)).limit(1)

        result = await self.session.execute(query)
        record = result.scalars().first()

        if not record:
            return None

        return self._record_to_response(record)

    async def get_by_id(self, audit_id: uuid_lib.UUID) -> Optional[RetrospectiveAuditResponse]:
        """Retrieve a specific audit by ID."""
        query = (
            select(RetrospectiveAudit)
            .where(
                and_(
                    RetrospectiveAudit.id == audit_id,
                    RetrospectiveAudit.user_id == self.user_id,
                )
            )
        )
        result = await self.session.execute(query)
        record = result.scalars().first()

        if not record:
            return None

        return self._record_to_response(record)

    async def list_audits(
        self, limit: int = 20, offset: int = 0
    ) -> tuple[list[AuditListItem], int]:
        """List past audits for this user."""
        # Count
        from sqlalchemy import func
        count_query = (
            select(func.count(RetrospectiveAudit.id))
            .where(RetrospectiveAudit.user_id == self.user_id)
        )
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Fetch
        query = (
            select(RetrospectiveAudit)
            .where(RetrospectiveAudit.user_id == self.user_id)
            .order_by(desc(RetrospectiveAudit.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        records = result.scalars().all()

        items = [
            AuditListItem(
                id=r.id,
                created_at=r.created_at,
                lookback_days=r.lookback_days,
                total_products_analyzed=r.total_products_analyzed,
                total_estimated_impact=r.total_estimated_impact,
                monthly_projected_loss=r.monthly_projected_loss,
            )
            for r in records
        ]

        return items, total

    @staticmethod
    def _record_to_response(record: RetrospectiveAudit) -> RetrospectiveAuditResponse:
        """Convert a DB record back to the API response schema."""
        summary = AuditSummary(**record.summary_json)
        sku_results = [SKUAuditResult(**s) for s in record.sku_results_json]

        return RetrospectiveAuditResponse(
            id=record.id,
            user_id=record.user_id,
            created_at=record.created_at,
            summary=summary,
            sku_results=sku_results,
            methodology=record.methodology or "",
        )



        