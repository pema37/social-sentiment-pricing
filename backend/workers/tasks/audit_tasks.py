"""
Retrospective Audit Tasks - Celery tasks for pre-computing pricing audits.

Scheduled weekly so the dashboard teaser card and PDF export load
instantly instead of generating on every page load.

Tasks:
  - generate_weekly_audits: Runs for all users with competitor data (Sunday 5 AM)
  - generate_audit_for_user: On-demand for a specific user

IMPORTANT: Each task creates its own database session to avoid event loop
conflicts when running in Celery's forked worker processes.
"""

import asyncio
import re

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import select

from core.config import settings
from core.logging import get_logger
from models.competitor_product import CompetitorProduct
from schemas.retrospective_audit import AuditRequest
from services.retrospective_audit_service import RetrospectiveAuditService
from workers.celery_app import celery_app

logger = get_logger(__name__)


# ==============================================================================
# HELPERS (same pattern as pricing_tasks.py)
# ==============================================================================


def get_task_session_maker():
    """Create a fresh async session maker for Celery tasks."""
    db_url = settings.DATABASE_URL

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "sslmode=" in db_url:
        db_url = re.sub(r"[\?&]sslmode=[^&]*", "", db_url)
        db_url = db_url.replace("?&", "?").replace("&&", "&").rstrip("?&")

    use_ssl = "neon.tech" in db_url or "railway" in db_url

    engine = create_async_engine(
        db_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"ssl": True} if use_ssl else {},
    )

    return sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def run_async(coro):
    """Run async code in sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()


# ==============================================================================
# ASYNC IMPLEMENTATIONS
# ==============================================================================


async def _generate_weekly_audits():
    """
    Generate 90-day retrospective audits for all users who have
    at least one active competitor product link.

    This pre-computes the audit so the dashboard teaser card
    and PDF export load instantly during the week.
    """
    session_maker = get_task_session_maker()

    async with session_maker() as db:
        # Find all user IDs that have active competitor products
        stmt = select(CompetitorProduct.product_id).where(CompetitorProduct.is_active == True).distinct()
        result = await db.execute(stmt)
        product_ids_with_comps = [row[0] for row in result.all()]

        if not product_ids_with_comps:
            logger.info("No competitor products found — skipping audit generation")
            return {"users_processed": 0, "audits_generated": 0, "errors": 0}

        # Get distinct user IDs from those products
        from models.product import Product

        user_stmt = select(Product.user_id).where(Product.id.in_(product_ids_with_comps)).distinct()
        user_result = await db.execute(user_stmt)
        user_ids = [row[0] for row in user_result.all()]

        logger.info(f"Generating weekly audits for {len(user_ids)} users")

        audits_generated = 0
        errors = 0

        for user_id in user_ids:
            try:
                service = RetrospectiveAuditService(db, str(user_id))
                request = AuditRequest(lookback_days=90)
                audit = await service.generate_audit(request)

                if audit.summary.total_products_analyzed > 0:
                    audits_generated += 1
                    logger.info(
                        f"Audit for user {user_id}: "
                        f"{audit.summary.total_products_analyzed} products, "
                        f"${audit.summary.total_estimated_impact} impact"
                    )
                else:
                    logger.info(f"Audit for user {user_id}: no products with data")

            except Exception as e:
                errors += 1
                logger.error(f"Error generating audit for user {user_id}: {e}")

        logger.info(
            f"Weekly audit generation complete: {len(user_ids)} users, {audits_generated} audits, {errors} errors"
        )

        return {
            "users_processed": len(user_ids),
            "audits_generated": audits_generated,
            "errors": errors,
        }


async def _generate_audit_for_user(user_id: str, lookback_days: int = 90):
    """Generate a retrospective audit for a specific user on demand."""
    session_maker = get_task_session_maker()

    async with session_maker() as db:
        try:
            service = RetrospectiveAuditService(db, user_id)
            request = AuditRequest(lookback_days=lookback_days)
            audit = await service.generate_audit(request)

            return {
                "success": True,
                "user_id": user_id,
                "products_analyzed": audit.summary.total_products_analyzed,
                "total_impact": str(audit.summary.total_estimated_impact),
                "monthly_projection": str(audit.summary.monthly_projected_loss),
            }
        except Exception as e:
            logger.error(f"Error generating audit for user {user_id}: {e}")
            return {"success": False, "error": str(e)}


# ==============================================================================
# CELERY TASKS
# ==============================================================================


@celery_app.task(name="workers.tasks.audit_tasks.generate_weekly_audits")
def generate_weekly_audits():
    """
    Generate 90-day retrospective audits for all users with competitor data.

    Scheduled: Runs every Sunday at 5:00 AM UTC
    """
    return run_async(_generate_weekly_audits())


@celery_app.task(name="workers.tasks.audit_tasks.generate_audit_for_user")
def generate_audit_for_user(user_id: str, lookback_days: int = 90):
    """
    Generate a retrospective audit for a specific user.

    Triggered by: Manual request, new competitor data linked, etc.
    """
    return run_async(_generate_audit_for_user(user_id, lookback_days))
