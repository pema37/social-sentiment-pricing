"""
Outcome Measurement Tasks - Celery tasks for multi-window impact tracking.

These tasks run on a schedule to measure pricing recommendation outcomes
at 7-day, 14-day, and 30-day windows after price application.

This is the engine that makes the feedback loop compound. Without these
tasks running, the multi-window columns stay null, the confidence
calibration has no data, and the intelligence environment doesn't learn.

Schedule:
- measure_outcomes_7d:  Runs daily at 2 AM
- measure_outcomes_14d: Runs daily at 3 AM
- measure_outcomes_30d: Runs daily at 4 AM

Each task:
1. Finds outcomes due for that measurement window
2. Fetches sales data from the merchant's Shopify store
3. Records the revenue/units for the window
4. Advances the measurement status state machine

IMPORTANT: Each task creates its own database session to avoid event loop
conflicts when running in Celery's forked worker processes.

Place at: backend/workers/tasks/outcome_measurement_tasks.py
Then register the beat schedule in celery_app.py
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

import asyncio
import re
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import select

from workers.celery_app import celery_app
from core.config import settings
from core.logging import get_logger
from core.encryption import decrypt_token
from models.integration import Integration, EcommercePlatform, IntegrationStatus
from models.integration import ProductIntegrationLink
from services.pricing.outcome_measurement import OutcomeMeasurementService
from services.integration.shopify_service import ShopifyService

logger = get_logger(__name__)


# ==============================================================================
# HELPERS (same pattern as pricing_tasks.py)
# ==============================================================================

def get_task_session_maker():
    """
    Create a fresh async session maker for Celery tasks.

    Uses NullPool to prevent connection reuse across forked processes.
    """
    db_url = settings.DATABASE_URL

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "sslmode=" in db_url:
        db_url = re.sub(r'[\?&]sslmode=[^&]*', '', db_url)
        db_url = db_url.replace('?&', '?').replace('&&', '&').rstrip('?&')

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

async def _measure_outcomes(window: str):
    """
    Measure outcomes for a specific time window.

    Flow:
    1. Get outcomes due for this window (batch of 50)
    2. For each outcome, fetch sales data from the merchant's platform
    3. Record the measurement
    4. Repeat until no more outcomes are due
    """
    session_maker = get_task_session_maker()
    total_measured = 0
    total_failed = 0
    total_skipped = 0

    async with session_maker() as db:
        measurement_service = OutcomeMeasurementService(db)

        while True:
            # Get next batch
            outcomes = await measurement_service.get_outcomes_due_for_measurement(
                window=window,
                batch_size=50,
            )

            if not outcomes:
                break

            logger.info(f"[{window}] Processing batch of {len(outcomes)} outcomes")

            for outcome in outcomes:
                try:
                    sales_data = await _fetch_sales_data(
                        db=db,
                        product_id=outcome.product_id,
                        user_id=outcome.user_id,
                        price_applied_at=outcome.price_applied_at,
                        window=window,
                    )

                    if sales_data is None:
                        # Can't fetch data — mark as failed so we don't retry forever
                        await measurement_service.mark_measurement_failed(outcome.id)
                        total_failed += 1
                        logger.warning(
                            f"[{window}] No sales data for product {outcome.product_id}, "
                            f"marking outcome {outcome.id} as failed"
                        )
                        continue

                    await measurement_service.record_window_measurement(
                        outcome_id=outcome.id,
                        window=window,
                        revenue=sales_data["revenue"],
                        units=sales_data["units"],
                        margin=sales_data.get("margin"),
                    )
                    total_measured += 1

                except Exception as e:
                    total_failed += 1
                    logger.error(
                        f"[{window}] Error measuring outcome {outcome.id}: {e}"
                    )
                    # Don't mark as failed on transient errors — retried next run
                    continue

    logger.info(
        f"[{window}] Measurement complete: {total_measured} measured, "
        f"{total_failed} failed, {total_skipped} skipped"
    )

    return {
        "window": window,
        "measured": total_measured,
        "failed": total_failed,
        "skipped": total_skipped,
    }


async def _fetch_sales_data(
    db: AsyncSession,
    product_id,
    user_id,
    price_applied_at: datetime,
    window: str,
) -> Optional[dict]:
    """
    Fetch sales data for a product over a specific time window.

    Wired to real Shopify GraphQL Orders API via ShopifyService.
    WooCommerce support: add elif branch when WooCommerce orders service exists.

    Flow:
    1. Look up merchant's active integration
    2. Find the ProductIntegrationLink for this product (get external_product_id)
    3. Decrypt access token
    4. Call ShopifyService.fetch_product_sales_data() for the window period
    5. Return {revenue, units} or None if any step fails
    """
    window_days = {"7d": 7, "14d": 14, "30d": 30}.get(window)
    if not window_days:
        return None

    window_start = price_applied_at
    window_end = price_applied_at + timedelta(days=window_days)

    # Step 1: Get active integration for this merchant
    stmt = select(Integration).where(
        Integration.user_id == user_id,
        Integration.status == IntegrationStatus.ACTIVE,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        logger.debug(f"No active integration for user {user_id}")
        return None

    # Step 2: Find the product link (maps our product_id to Shopify's external_product_id)
    link_stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.product_id == product_id,
        ProductIntegrationLink.integration_id == integration.id,
        ProductIntegrationLink.sync_enabled == True,
    )
    link_result = await db.execute(link_stmt)
    link = link_result.scalars().first()

    if not link:
        logger.debug(
            f"No product link for product {product_id} "
            f"in integration {integration.id}"
        )
        return None

    # Step 3: Decrypt access token
    try:
        access_token = decrypt_token(integration.access_token_encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt access token for integration {integration.id}: {e}")
        return None

    # Step 4: Call platform-specific orders API
    if integration.platform == EcommercePlatform.SHOPIFY:
        shopify = ShopifyService()
        sales_data = await shopify.fetch_product_sales_data(
            store_url=integration.store_url,
            access_token=access_token,
            external_product_id=link.external_product_id,
            created_at_min=window_start.isoformat(),
            created_at_max=window_end.isoformat(),
        )

        if sales_data is None:
            logger.warning(
                f"Shopify returned no sales data for product {link.external_product_id} "
                f"({window_start.date()} to {window_end.date()})"
            )
            return None

        logger.info(
            f"[{window}] Shopify sales for product {link.external_product_id}: "
            f"${sales_data['revenue']}, {sales_data['units']} units "
            f"({window_start.date()} to {window_end.date()})"
        )
        return sales_data

    elif integration.platform == EcommercePlatform.WOOCOMMERCE:
        # TODO: Wire WooCommerce orders API when service is ready
        # from services.integration.woocommerce_service import WooCommerceService
        # woo = WooCommerceService()
        # return await woo.fetch_product_sales_data(...)
        logger.debug(
            f"WooCommerce sales data fetch not yet implemented. "
            f"Product {product_id}, window {window}"
        )
        return None

    else:
        logger.warning(f"Unsupported platform: {integration.platform}")
        return None


async def _get_measurement_stats():
    """Get counts by measurement status for monitoring."""
    session_maker = get_task_session_maker()

    async with session_maker() as db:
        service = OutcomeMeasurementService(db)
        stats = await service.get_measurement_stats()

        logger.info(f"Measurement pipeline stats: {stats}")
        return stats


# ==============================================================================
# CELERY TASKS
# ==============================================================================

@celery_app.task(name="workers.tasks.outcome_measurement_tasks.measure_outcomes_7d")
def measure_outcomes_7d():
    """
    Measure 7-day impact for applied recommendations.

    Picks up outcomes in 'decision_recorded' or 'single_measured' status
    where price_applied_at is 7+ days ago. Fetches sales data from
    Shopify and records revenue + units.

    Scheduled: Daily at 2 AM
    """
    return run_async(_measure_outcomes("7d"))


@celery_app.task(name="workers.tasks.outcome_measurement_tasks.measure_outcomes_14d")
def measure_outcomes_14d():
    """
    Measure 14-day impact for applied recommendations.

    Picks up outcomes in 'measured_7d' status where price_applied_at
    is 14+ days ago.

    Scheduled: Daily at 3 AM
    """
    return run_async(_measure_outcomes("14d"))


@celery_app.task(name="workers.tasks.outcome_measurement_tasks.measure_outcomes_30d")
def measure_outcomes_30d():
    """
    Measure 30-day impact for applied recommendations.

    Picks up outcomes in 'measured_14d' status where price_applied_at
    is 30+ days ago.

    Scheduled: Daily at 4 AM
    """
    return run_async(_measure_outcomes("30d"))


@celery_app.task(name="workers.tasks.outcome_measurement_tasks.measurement_stats")
def measurement_stats():
    """
    Report measurement pipeline stats.

    Use: Manual trigger or daily monitoring task.
    Shows how many outcomes are in each measurement status.
    """
    return run_async(_get_measurement_stats())


    