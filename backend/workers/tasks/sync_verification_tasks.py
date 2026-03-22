# backend/workers/tasks/sync_verification_tasks.py

"""
Sync Verification Tasks - Periodic checks for price drift between ActualPrice and e-commerce platforms.

These tasks detect when prices become out of sync due to:
- Manual edits in WooCommerce/Shopify
- Failed price pushes that weren't detected
- Third-party apps modifying prices
- Webhook failures

IMPORTANT: Each task creates its own database session to avoid event loop
conflicts when running in Celery's forked worker processes.

PATCHED (2026-01-28): Bug #6 fix - Added recover_stuck_syncs task to handle
integrations stuck in 'syncing' status. See SSP_AUDIT_REPORT.md.

ADDED (2026-03-13): check_all_integration_health task.
Polls health of every ACTIVE and ERROR integration every 30 minutes.
Writes status back to DB so the frontend diagnostic panel and init_oauth
always see the real connection state without waiting for a manual check.

Wire into Celery Beat schedule (celery_app.py or equivalent):
    "check-integration-health": {
        "task": "workers.tasks.sync_verification_tasks.check_all_integration_health",
        "schedule": crontab(minute="*/30"),
    },
"""

import asyncio
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import select

from core.config import settings
from core.encryption import decrypt_token
from core.logging import get_logger
from models.integration import Integration, IntegrationStatus, IntegrationSyncLog, ProductIntegrationLink
from models.product import Product
from services.integration.schemas import ConnectionStatus
from services.integration.shopify_service import ShopifyService
from services.integration.woocommerce_service import WooCommerceService
from workers.celery_app import celery_app

logger = get_logger(__name__)


# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Price difference threshold to consider as mismatch (in dollars)
PRICE_MISMATCH_THRESHOLD = Decimal("0.05")

# Maximum links to check per run (None = check all eligible links)
MAX_PRODUCTS_PER_RUN: int | None = None

# How old a sync can be before we force a re-check (hours)
STALE_SYNC_HOURS = 24

# Stuck sync recovery config (Bug #6)
STUCK_SYNC_TIMEOUT_MINUTES = 15

# Grace period after a fresh OAuth before the health check is allowed to run.
# Prevents the health check from immediately setting status=ERROR on a
# newly-connected integration before the first sync has had time to complete.
# Once last_sync_at is set (first sync done), the grace period is lifted.
HEALTH_CHECK_GRACE_PERIOD_SECONDS = 10 * 60  # 10 minutes

# Health poll: statuses that should be checked every cycle.
# ACTIVE — verify the token is still valid.
# ERROR  — re-check so we can auto-recover if the merchant reconnected
#          via a different path (e.g., direct OAuth from Partner Dashboard).
# PAUSED / DISCONNECTED are skipped — merchant intentionally offline.
_HEALTH_POLL_STATUSES = {IntegrationStatus.ACTIVE, IntegrationStatus.ERROR}


# ==============================================================================
# HELPERS
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


async def _verify_all_price_syncs() -> dict:
    """
    Verify prices are in sync between ActualPrice and e-commerce platforms.

    Checks all products with active integrations and reports mismatches.

    Returns:
        Dict with verification results and any mismatches found
    """
    session_maker = get_task_session_maker()

    results = {
        "checked": 0,
        "matched": 0,
        "mismatched": 0,
        "errors": 0,
        "mismatches": [],
        "error_details": [],
    }

    async with session_maker() as db:
        integrations_stmt = select(Integration).where(Integration.status == IntegrationStatus.ACTIVE)
        integrations_result = await db.execute(integrations_stmt)
        integrations = {i.id: i for i in integrations_result.scalars().all()}

        if not integrations:
            logger.info("No active integrations found")
            return results

        links_stmt = (
            select(ProductIntegrationLink)
            .where(ProductIntegrationLink.sync_enabled)
            .where(ProductIntegrationLink.integration_id.in_(integrations.keys()))
            .order_by(ProductIntegrationLink.id)
        )
        if MAX_PRODUCTS_PER_RUN is not None:
            links_stmt = links_stmt.limit(MAX_PRODUCTS_PER_RUN)
        links_result = await db.execute(links_stmt)
        links = list(links_result.scalars().all())

        logger.info(f"Checking {len(links)} product-integration links")

        product_ids = [link.product_id for link in links]
        products_stmt = select(Product).where(Product.id.in_(product_ids))
        products_result = await db.execute(products_stmt)
        products = {p.id: p for p in products_result.scalars().all()}

        woo_service = WooCommerceService()
        shopify_service = ShopifyService()

        for link in links:
            product = products.get(link.product_id)
            integration = integrations.get(link.integration_id)

            if not product or not integration:
                continue

            results["checked"] += 1

            try:
                try:
                    access_token = decrypt_token(integration.access_token_encrypted)
                except Exception as e:
                    results["errors"] += 1
                    results["error_details"].append(
                        {
                            "product_id": str(product.id),
                            "product_name": product.name,
                            "error": f"Failed to decrypt credentials: {e!s}",
                        }
                    )
                    continue

                platform_price = None

                if integration.platform.lower() == "woocommerce":
                    external_product = await woo_service.fetch_single_product(
                        store_url=integration.store_url,
                        access_token=access_token,
                        external_product_id=link.external_product_id,
                    )
                    if external_product:
                        platform_price = _resolve_link_price(
                            external_product=external_product,
                            external_variant_id=link.external_variant_id,
                        )

                elif integration.platform.lower() == "shopify":
                    external_product = await shopify_service.fetch_single_product(
                        store_url=integration.store_url,
                        access_token=access_token,
                        external_product_id=link.external_product_id,
                    )
                    if external_product:
                        platform_price = _resolve_link_price(
                            external_product=external_product,
                            external_variant_id=link.external_variant_id,
                        )

                if platform_price is None:
                    results["errors"] += 1
                    results["error_details"].append(
                        {
                            "product_id": str(product.id),
                            "product_name": product.name,
                            "error": "Could not fetch price from platform",
                        }
                    )
                    continue

                our_price = Decimal(str(product.current_price)) if product.current_price else Decimal("0")
                their_price = Decimal(str(platform_price))
                price_diff = abs(our_price - their_price)

                if price_diff <= PRICE_MISMATCH_THRESHOLD:
                    results["matched"] += 1
                    link.external_price = their_price
                    link.last_sync_verified_at = datetime.now(UTC)
                    db.add(link)
                else:
                    results["mismatched"] += 1
                    mismatch_info = {
                        "product_id": str(product.id),
                        "product_name": product.name,
                        "our_price": float(our_price),
                        "platform_price": float(their_price),
                        "difference": float(price_diff),
                        "platform": integration.platform,
                        "store_url": integration.store_url,
                        "external_product_id": link.external_product_id,
                        "last_push_at": link.last_price_push_at.isoformat() if link.last_price_push_at else None,
                    }
                    results["mismatches"].append(mismatch_info)
                    logger.warning(
                        f"Price mismatch detected: {product.name} - "
                        f"ActualPrice: ${our_price}, {integration.platform}: ${their_price} "
                        f"(diff: ${price_diff})"
                    )

            except Exception as e:
                results["errors"] += 1
                results["error_details"].append(
                    {"product_id": str(product.id), "product_name": product.name, "error": str(e)}
                )
                logger.error(f"Error checking product {product.id}: {e}")

        await db.commit()

    logger.info(
        f"Sync verification complete: "
        f"{results['checked']} checked, {results['matched']} matched, "
        f"{results['mismatched']} mismatched, {results['errors']} errors"
    )

    return results


def _resolve_link_price(external_product, external_variant_id: str | None) -> float | None:
    """Resolve the effective external price for a specific product-integration link."""
    if not external_product:
        return None

    if external_variant_id and getattr(external_product, "variants", None):
        for variant in external_product.variants:
            if str(getattr(variant, "id", "")) == str(external_variant_id):
                return variant.price

    return external_product.price


async def _auto_fix_price_mismatches(dry_run: bool = True) -> dict:
    """
    Automatically fix price mismatches by pushing ActualPrice to platform.

    Args:
        dry_run: If True, only report what would be fixed without making changes

    Returns:
        Dict with fix results
    """
    session_maker = get_task_session_maker()

    results = {
        "dry_run": dry_run,
        "found": 0,
        "fixed": 0,
        "failed": 0,
        "details": [],
    }

    verification = await _verify_all_price_syncs()
    mismatches = verification.get("mismatches", [])
    results["found"] = len(mismatches)

    if dry_run or not mismatches:
        results["details"] = mismatches
        return results

    async with session_maker() as db:
        woo_service = WooCommerceService()
        shopify_service = ShopifyService()

        for mismatch in mismatches:
            product_id = UUID(mismatch["product_id"])

            product_stmt = select(Product).where(Product.id == product_id)
            product_result = await db.execute(product_stmt)
            product = product_result.scalars().first()

            if not product:
                results["failed"] += 1
                continue

            link_stmt = (
                select(ProductIntegrationLink)
                .where(ProductIntegrationLink.product_id == product_id)
                .where(ProductIntegrationLink.sync_enabled)
            )
            link_result = await db.execute(link_stmt)
            link = link_result.scalars().first()

            if not link:
                results["failed"] += 1
                continue

            integration_stmt = select(Integration).where(Integration.id == link.integration_id)
            integration_result = await db.execute(integration_stmt)
            integration = integration_result.scalars().first()

            if not integration:
                results["failed"] += 1
                continue

            try:
                access_token = decrypt_token(integration.access_token_encrypted)

                from services.integration.schemas import PriceUpdateRequest

                request = PriceUpdateRequest(
                    external_product_id=link.external_product_id,
                    new_price=product.current_price,
                )

                if integration.platform.lower() == "woocommerce":
                    response = await woo_service.update_price(
                        store_url=integration.store_url, access_token=access_token, request=request
                    )
                elif integration.platform.lower() == "shopify":
                    response = await shopify_service.update_price(
                        store_url=integration.store_url, access_token=access_token, request=request
                    )
                else:
                    results["failed"] += 1
                    continue

                if response.result.value == "success":
                    results["fixed"] += 1
                    link.last_price_push_at = datetime.now(UTC)
                    link.external_price = product.current_price
                    db.add(link)
                    logger.info(
                        f"Auto-fixed price for {product.name}: ${mismatch['platform_price']} -> ${product.current_price}"
                    )
                else:
                    results["failed"] += 1
                    logger.error(f"Failed to auto-fix {product.name}: {response.error}")

            except Exception as e:
                results["failed"] += 1
                logger.error(f"Error fixing {product.name}: {e}")

        await db.commit()

    return results


async def _get_sync_status_report() -> dict:
    """
    Generate a comprehensive sync status report.

    Returns:
        Dict with sync health metrics
    """
    session_maker = get_task_session_maker()

    async with session_maker() as db:
        total_stmt = select(ProductIntegrationLink).where(ProductIntegrationLink.sync_enabled)
        total_result = await db.execute(total_stmt)
        total_links = list(total_result.scalars().all())

        recent_threshold = datetime.now(UTC) - timedelta(hours=STALE_SYNC_HOURS)
        recent_count = sum(
            1 for link in total_links if link.last_price_push_at and link.last_price_push_at > recent_threshold
        )

        product_ids = [link.product_id for link in total_links]
        products_stmt = select(Product).where(Product.id.in_(product_ids))
        products_result = await db.execute(products_stmt)
        products = {p.id: p for p in products_result.scalars().all()}

        mismatch_count = 0
        for link in total_links:
            product = products.get(link.product_id)
            if product and link.external_price:
                our_price = Decimal(str(product.current_price)) if product.current_price else Decimal("0")
                their_price = Decimal(str(link.external_price))
                if abs(our_price - their_price) > PRICE_MISMATCH_THRESHOLD:
                    mismatch_count += 1

        return {
            "total_synced_products": len(total_links),
            "recently_synced": recent_count,
            "stale_syncs": len(total_links) - recent_count,
            "known_mismatches": mismatch_count,
            "sync_health_percent": round((len(total_links) - mismatch_count) / len(total_links) * 100, 1)
            if total_links
            else 100.0,
            "checked_at": datetime.now(UTC).isoformat(),
        }


async def _recover_stuck_syncs() -> dict:
    """
    Recover integrations stuck in 'syncing' status.

    Note (2026-01-28): Added to fix Bug #6 where syncs would get stuck
    in 'syncing' status forever if the worker crashed.
    """
    session_maker = get_task_session_maker()

    results = {
        "checked": 0,
        "recovered": 0,
        "still_running": 0,
        "details": [],
    }

    cutoff = datetime.now(UTC) - timedelta(minutes=STUCK_SYNC_TIMEOUT_MINUTES)

    async with session_maker() as db:
        stmt = select(Integration).where(Integration.sync_status == "syncing")
        result = await db.execute(stmt)
        integrations = result.scalars().all()

        results["checked"] = len(integrations)

        for integration in integrations:
            log_stmt = (
                select(IntegrationSyncLog)
                .where(IntegrationSyncLog.integration_id == integration.id)
                .where(IntegrationSyncLog.completed_at.is_(None))
                .order_by(IntegrationSyncLog.started_at.desc())
                .limit(1)
            )
            log_result = await db.execute(log_stmt)
            stuck_log = log_result.scalars().first()

            if stuck_log and stuck_log.started_at < cutoff:
                now = datetime.now(UTC)
                stuck_duration_minutes = (now - stuck_log.started_at).total_seconds() / 60

                stuck_log.success = False
                stuck_log.error_details = (
                    f"Sync timed out after {stuck_duration_minutes:.1f} minutes "
                    f"(recovered by cleanup task at {now.isoformat()})"
                )
                stuck_log.completed_at = now
                stuck_log.duration_seconds = (now - stuck_log.started_at).total_seconds()
                db.add(stuck_log)

                integration.sync_status = "error"
                integration.error_message = "Sync was interrupted. Please try again."
                db.add(integration)

                results["recovered"] += 1
                results["details"].append(
                    {
                        "integration_id": str(integration.id),
                        "store_url": integration.store_url,
                        "stuck_for_minutes": stuck_duration_minutes,
                        "action": "recovered",
                    }
                )

                logger.warning(
                    f"Recovered stuck sync for integration {integration.id} "
                    f"({integration.store_url}) - was syncing for "
                    f"{stuck_duration_minutes:.1f} minutes"
                )

            elif stuck_log:
                results["still_running"] += 1

            else:
                recent_log_stmt = (
                    select(IntegrationSyncLog)
                    .where(IntegrationSyncLog.integration_id == integration.id)
                    .order_by(IntegrationSyncLog.started_at.desc())
                    .limit(1)
                )
                recent_result = await db.execute(recent_log_stmt)
                recent_log = recent_result.scalars().first()

                if not recent_log or (recent_log.completed_at is not None):
                    integration.sync_status = "error"
                    integration.error_message = "Sync status was inconsistent. Please try again."
                    db.add(integration)

                    results["recovered"] += 1
                    results["details"].append(
                        {
                            "integration_id": str(integration.id),
                            "store_url": integration.store_url,
                            "stuck_for_minutes": None,
                            "action": "fixed_inconsistent_state",
                        }
                    )

                    logger.warning(
                        f"Fixed inconsistent sync status for integration {integration.id} ({integration.store_url})"
                    )

        if results["recovered"] > 0:
            await db.commit()

    logger.info(
        f"Stuck sync recovery complete: "
        f"{results['checked']} checked, {results['recovered']} recovered, "
        f"{results['still_running']} still running"
    )

    return results


# ==============================================================================
# ADDED (2026-03-13): Integration health polling
# ==============================================================================


async def _check_all_integration_health() -> dict:
    """
    Poll health of every ACTIVE and ERROR integration and persist results to DB.

    Why both statuses:
    - ACTIVE  → detect newly revoked tokens before a price push fails
    - ERROR   → auto-recover if the merchant reconnected via a different path

    Each integration gets one GraphQL `{ shop { name } }` call.
    On failure the integration status is set to ERROR with a descriptive
    error_message. On success it is set back to ACTIVE and error_message
    is cleared.

    This is the background complement to the fix in operations.py:
    - operations.py  → writes status on manual health check
    - this task      → writes status automatically every 30 minutes

    Returns:
        Dict with counts: checked, healthy, unhealthy, errors, recovered
    """
    session_maker = get_task_session_maker()

    results: dict = {
        "checked": 0,
        "healthy": 0,
        "unhealthy": 0,
        "recovered": 0,  # ERROR → ACTIVE transitions
        "errors": 0,  # decrypt failures or unexpected exceptions
        "details": [],
    }

    async with session_maker() as db:
        stmt = select(Integration).where(Integration.status.in_(_HEALTH_POLL_STATUSES))
        result = await db.execute(stmt)
        integrations = result.scalars().all()

        if not integrations:
            logger.info("Health poll: no ACTIVE or ERROR integrations to check")
            return results

        logger.info(f"Health poll: checking {len(integrations)} integrations")

        shopify_service = ShopifyService()
        woo_service = WooCommerceService()
        now = datetime.now(UTC)

        for integration in integrations:
            results["checked"] += 1
            previous_status = integration.status

            # ── Grace period ───────────────────────────────────────────────
            # Skip freshly connected integrations that haven't completed their
            # first sync yet. Running a decrypt-based health check immediately
            # after OAuth can fail due to token encoding transitions and sets
            # status=ERROR, triggering a DISCONNECTED→ACTIVE→ERROR loop.
            # Once last_sync_at is populated the grace period is lifted.
            if integration.last_sync_at is None:
                age_seconds = (now - integration.updated_at).total_seconds()
                if age_seconds < HEALTH_CHECK_GRACE_PERIOD_SECONDS:
                    logger.info(
                        f"Health poll: skipping {integration.id} "
                        f"({integration.store_url}) — no first sync yet, "
                        f"within {HEALTH_CHECK_GRACE_PERIOD_SECONDS // 60}min grace period"
                    )
                    results["healthy"] += 1
                    continue

            # ── Decrypt ────────────────────────────────────────────────────
            try:
                access_token = decrypt_token(integration.access_token_encrypted)
            except Exception as exc:
                logger.warning(
                    f"Health poll: failed to decrypt token for "
                    f"integration {integration.id} ({integration.store_url}): {exc}"
                )
                integration.status = IntegrationStatus.ERROR
                integration.error_message = "Stored credentials are invalid. Please reconnect."
                integration.updated_at = now
                db.add(integration)
                results["errors"] += 1
                results["details"].append(
                    {
                        "integration_id": str(integration.id),
                        "store_url": integration.store_url,
                        "platform": integration.platform.value,
                        "result": "decrypt_failed",
                    }
                )
                continue

            # ── Health check ───────────────────────────────────────────────
            try:
                if integration.platform == "shopify":
                    connection_status = await shopify_service.health_check(
                        store_url=integration.store_url,
                        access_token=access_token,
                    )
                else:
                    connection_status = await woo_service.health_check(
                        store_url=integration.store_url,
                        access_token=access_token,
                    )
            except Exception as exc:
                logger.error(f"Health poll: unexpected error for integration {integration.id}: {exc}")
                results["errors"] += 1
                results["details"].append(
                    {
                        "integration_id": str(integration.id),
                        "store_url": integration.store_url,
                        "platform": integration.platform.value,
                        "result": "exception",
                        "error": str(exc),
                    }
                )
                continue

            # ── Persist result ─────────────────────────────────────────────
            if connection_status == ConnectionStatus.HEALTHY:
                integration.status = IntegrationStatus.ACTIVE
                integration.error_message = None
                integration.updated_at = now

                if previous_status == IntegrationStatus.ERROR:
                    # Token was revoked but is now valid again
                    # (e.g., merchant reconnected via Partner Dashboard)
                    results["recovered"] += 1
                    logger.info(
                        f"Health poll: integration {integration.id} ({integration.store_url}) auto-recovered → ACTIVE"
                    )
                else:
                    results["healthy"] += 1

            else:
                error_map = {
                    ConnectionStatus.UNAUTHORIZED: ("Shopify access token was revoked. Reconnect your store."),
                    ConnectionStatus.RATE_LIMITED: ("Shopify API rate limit hit. Will retry automatically."),
                    ConnectionStatus.UNHEALTHY: ("Could not reach the store. Check the store URL."),
                }
                error_message = error_map.get(
                    connection_status,
                    f"Integration check failed: {connection_status.value}",
                )

                integration.status = IntegrationStatus.ERROR
                integration.error_message = error_message
                integration.updated_at = now
                results["unhealthy"] += 1

                if previous_status == IntegrationStatus.ACTIVE:
                    logger.warning(
                        f"Health poll: integration {integration.id} "
                        f"({integration.store_url}) went ACTIVE → ERROR: "
                        f"{connection_status.value}"
                    )

            db.add(integration)
            results["details"].append(
                {
                    "integration_id": str(integration.id),
                    "store_url": integration.store_url,
                    "platform": integration.platform.value,
                    "previous_status": previous_status.value,
                    "new_status": integration.status.value,
                    "connection_status": connection_status.value,
                }
            )

        await db.commit()

    logger.info(
        f"Health poll complete: {results['checked']} checked, "
        f"{results['healthy']} healthy, {results['unhealthy']} unhealthy, "
        f"{results['recovered']} recovered, {results['errors']} errors"
    )

    return results


# ==============================================================================
# CELERY TASKS
# ==============================================================================


@celery_app.task(name="workers.tasks.sync_verification_tasks.verify_price_syncs")
def verify_price_syncs():
    """
    Verify all product prices are in sync with e-commerce platforms.

    Scheduled: Runs every 6 hours
    """
    return run_async(_verify_all_price_syncs())


@celery_app.task(name="workers.tasks.sync_verification_tasks.auto_fix_mismatches")
def auto_fix_mismatches(dry_run: bool = True):
    """
    Automatically fix price mismatches by pushing ActualPrice to platform.

    Use: Manual trigger, set dry_run=False to actually fix
    """
    return run_async(_auto_fix_price_mismatches(dry_run=dry_run))


@celery_app.task(name="workers.tasks.sync_verification_tasks.get_sync_status")
def get_sync_status():
    """
    Get current sync health status.

    Use: Manual trigger or dashboard polling
    """
    return run_async(_get_sync_status_report())


@celery_app.task(name="workers.tasks.sync_verification_tasks.recover_stuck_syncs")
def recover_stuck_syncs():
    """
    Recover integrations stuck in 'syncing' status.

    Scheduled: Runs every 5 minutes via Celery Beat

    Note (2026-01-28): Added to fix Bug #6 - never-ending sync spinner.
    """
    return run_async(_recover_stuck_syncs())


# ADDED (2026-03-13)
@celery_app.task(name="workers.tasks.sync_verification_tasks.check_all_integration_health")
def check_all_integration_health():
    """
    Poll health of every ACTIVE and ERROR integration and write status to DB.

    Scheduled: Every 30 minutes via Celery Beat.

    Wire into celery_app.py beat_schedule:
        "check-integration-health": {
            "task": "workers.tasks.sync_verification_tasks.check_all_integration_health",
            "schedule": crontab(minute="*/30"),
        },

    What this does:
    - Calls health_check() on each integration (one GraphQL ping per store)
    - Writes ACTIVE or ERROR + error_message back to the integrations table
    - Logs ACTIVE→ERROR transitions as warnings for Sentry pickup
    - Logs ERROR→ACTIVE transitions as auto-recoveries

    This ensures the frontend diagnostic panel always reflects the real
    connection state without waiting for a merchant to manually trigger
    a health check.
    """
    return run_async(_check_all_integration_health())
