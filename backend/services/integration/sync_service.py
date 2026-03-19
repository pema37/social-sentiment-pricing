# backend/services/integration/sync_service.py

"""
Product Sync Service - PULL operations

Orchestrates syncing products FROM e-commerce platforms TO SSP.
Handles full syncs, incremental syncs, and webhook-triggered updates.

PATCHED (2026-01-28): Bug #6 fix - Added recover_stuck_syncs() method to
handle integrations stuck in 'syncing' status due to worker crashes or
unexpected failures. See SSP_AUDIT_REPORT.md.

PATCHED (2026-02-21): Performance + correctness fixes:
- Batched commits per page instead of per product
- Generic exceptions re-raised from run_sync for caller visibility
- recover_stuck_syncs filters by cutoff in initial query
- _count_linked_products uses COUNT() instead of loading all rows
- Token decryption validated before setting status to 'syncing'
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.encryption import decrypt_token
from models.integration import (
    EcommercePlatform,
    Integration,
    IntegrationStatus,
    IntegrationSyncLog,
    ProductIntegrationLink,
)
from models.product import Product

from .base import EcommerceService
from .circuit_breaker import CircuitOpenError
from .schemas import ExternalProduct
from .shopify_service import ShopifyService
from .woocommerce_service import WooCommerceService

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time as naive datetime."""
    return datetime.now(UTC)


class SyncError(Exception):
    """Base exception for sync errors"""

    pass


class SyncTemporarilyUnavailable(SyncError):
    """Raised when external service is temporarily unavailable"""

    pass


class SyncTimeoutError(SyncError):
    """Raised when sync operation times out"""

    pass


class SyncService:
    """
    Orchestrates product synchronization FROM e-commerce platforms.

    For pushing prices TO platforms, see PricePushService.
    """

    _services: dict[EcommercePlatform, EcommerceService] = {}
    SYNC_TIMEOUT_SECONDS = 300
    STUCK_SYNC_TIMEOUT_MINUTES = 15  # If syncing for longer than this, it's stuck

    def __init__(self, db: AsyncSession):
        self.db = db

    @classmethod
    def get_service(cls, platform: EcommercePlatform) -> EcommerceService:
        """Get the appropriate e-commerce service (cached)."""
        if platform not in cls._services:
            if platform == EcommercePlatform.SHOPIFY:
                cls._services[platform] = ShopifyService()
            elif platform == EcommercePlatform.WOOCOMMERCE:
                cls._services[platform] = WooCommerceService()
            else:
                raise ValueError(f"Unsupported platform: {platform}")
        return cls._services[platform]

    # ─── Stuck sync recovery (Bug #6 fix) ────────────────────────

    async def recover_stuck_syncs(self, user_id: UUID | None = None) -> int:
        """
        Recover integrations stuck in 'syncing' status.

        This handles cases where:
        - Celery worker crashed mid-sync
        - Database commit failed after sync completed
        - Process was killed unexpectedly
        - Network timeout wasn't properly caught

        Args:
            user_id: Optional - only recover syncs for specific user

        Returns:
            Number of integrations recovered
        """
        cutoff = utc_now() - timedelta(minutes=self.STUCK_SYNC_TIMEOUT_MINUTES)

        # FIX: Filter by cutoff in initial query to avoid loading integrations
        # that just started syncing moments ago
        stmt = select(Integration).where(
            Integration.sync_status == "syncing",
            Integration.updated_at < cutoff,
        )
        if user_id:
            stmt = stmt.where(Integration.user_id == user_id)

        result = await self.db.execute(stmt)
        integrations = result.scalars().all()

        recovered = 0
        for integration in integrations:
            # Check if there's a sync log that's been "in progress" too long
            log_stmt = (
                select(IntegrationSyncLog)
                .where(IntegrationSyncLog.integration_id == integration.id)
                .where(IntegrationSyncLog.completed_at.is_(None))
                .where(IntegrationSyncLog.started_at < cutoff)
                .order_by(IntegrationSyncLog.started_at.desc())
                .limit(1)
            )
            log_result = await self.db.execute(log_stmt)
            stuck_log = log_result.scalars().first()

            if stuck_log:
                now = utc_now()

                stuck_log.success = False
                stuck_log.error_details = (
                    f"Sync timed out after {self.STUCK_SYNC_TIMEOUT_MINUTES} minutes "
                    f"(recovered by cleanup task at {now.isoformat()})"
                )
                stuck_log.completed_at = now
                stuck_log.duration_seconds = (now - stuck_log.started_at).total_seconds()
                self.db.add(stuck_log)

                integration.sync_status = "error"
                integration.error_message = "Sync was interrupted. Please try again."
                self.db.add(integration)

                recovered += 1
                logger.warning(
                    f"Recovered stuck sync for integration {integration.id} "
                    f"({integration.store_url}) - was syncing for "
                    f"{(now - stuck_log.started_at).total_seconds():.0f} seconds"
                )
            else:
                # No stuck log found, but integration is still 'syncing' past cutoff.
                # Could be a race condition or a log that was never created.
                recent_log_stmt = (
                    select(IntegrationSyncLog)
                    .where(IntegrationSyncLog.integration_id == integration.id)
                    .order_by(IntegrationSyncLog.started_at.desc())
                    .limit(1)
                )
                recent_result = await self.db.execute(recent_log_stmt)
                recent_log = recent_result.scalars().first()

                if not recent_log or (recent_log.completed_at is not None):
                    integration.sync_status = "error"
                    integration.error_message = "Sync status was inconsistent. Please try again."
                    self.db.add(integration)
                    recovered += 1
                    logger.warning(
                        f"Recovered inconsistent sync status for integration {integration.id} ({integration.store_url})"
                    )

        if recovered > 0:
            await self.db.commit()
            logger.info(f"Recovered {recovered} stuck sync(s)")

        return recovered

    async def get_stuck_syncs(self, user_id: UUID | None = None) -> list[dict]:
        """
        Get list of integrations currently stuck in 'syncing' status.

        Useful for diagnostics and admin dashboards.
        """
        cutoff = utc_now() - timedelta(minutes=self.STUCK_SYNC_TIMEOUT_MINUTES)

        # FIX: Filter by cutoff in initial query
        stmt = select(Integration).where(
            Integration.sync_status == "syncing",
            Integration.updated_at < cutoff,
        )
        if user_id:
            stmt = stmt.where(Integration.user_id == user_id)

        result = await self.db.execute(stmt)
        integrations = result.scalars().all()

        stuck = []
        for integration in integrations:
            log_stmt = (
                select(IntegrationSyncLog)
                .where(IntegrationSyncLog.integration_id == integration.id)
                .where(IntegrationSyncLog.completed_at.is_(None))
                .order_by(IntegrationSyncLog.started_at.desc())
                .limit(1)
            )
            log_result = await self.db.execute(log_stmt)
            sync_log = log_result.scalars().first()

            if sync_log and sync_log.started_at < cutoff:
                stuck.append(
                    {
                        "integration_id": str(integration.id),
                        "store_url": integration.store_url,
                        "platform": integration.platform.value
                        if hasattr(integration.platform, "value")
                        else str(integration.platform),
                        "started_at": sync_log.started_at.isoformat(),
                        "stuck_for_minutes": (utc_now() - sync_log.started_at).total_seconds() / 60,
                        "sync_log_id": str(sync_log.id),
                    }
                )

        return stuck

    # ─── Main sync orchestration ─────────────────────────────────

    async def run_sync(
        self,
        integration_id: UUID,
        sync_type: str = "full",
        user_id: UUID | None = None,
    ) -> IntegrationSyncLog:
        """Run a product sync with timeout protection."""
        integration = await self._get_integration(integration_id, user_id)

        # FIX: Validate token BEFORE setting status to 'syncing'.
        # If decryption fails, we don't want the integration stuck in 'syncing'.
        try:
            decrypt_token(integration.access_token_encrypted)
        except Exception as e:
            logger.error(f"Token decryption failed for integration {integration_id}: {e}")
            raise SyncError(f"Failed to decrypt store credentials: {e}")

        sync_log = await self._create_sync_log(integration, sync_type)

        try:
            counts = await asyncio.wait_for(
                self._sync_products(integration, sync_type), timeout=self.SYNC_TIMEOUT_SECONDS
            )
            await self._finalize_success(integration, sync_log, counts)

        except TimeoutError:
            error_msg = f"Sync timed out after {self.SYNC_TIMEOUT_SECONDS} seconds"
            logger.error(f"{error_msg} for integration {integration_id}")
            await self._finalize_failure(integration, sync_log, error_msg)
            raise SyncTimeoutError(error_msg)

        except CircuitOpenError as e:
            logger.warning(f"Sync blocked by circuit breaker: {integration.store_url}")
            await self._finalize_failure(integration, sync_log, "Service temporarily unavailable")
            raise SyncTemporarilyUnavailable(str(e))

        except Exception as e:
            # FIX: Re-raise after finalizing so callers know the sync failed.
            # Previously this was swallowed — callers got a sync_log with
            # success=False but no exception, unlike timeout/circuit breaker.
            logger.exception(f"Sync failed for integration {integration_id}")
            await self._finalize_failure(integration, sync_log, str(e))
            raise SyncError(str(e)) from e

        return sync_log

    async def _get_integration(self, integration_id: UUID, user_id: UUID | None) -> Integration:
        """Fetch and validate integration."""
        query = select(Integration).where(Integration.id == integration_id)
        if user_id:
            query = query.where(Integration.user_id == user_id)

        result = await self.db.execute(query)
        integration = result.scalars().first()

        if not integration:
            raise ValueError("Integration not found")
        if integration.status not in (IntegrationStatus.ACTIVE, IntegrationStatus.ERROR):
            raise ValueError("Integration is not active")
        # Reset error status so sync can proceed
        if integration.status == IntegrationStatus.ERROR:
            integration.status = IntegrationStatus.ACTIVE
            self.db.add(integration)
            await self.db.commit()

        return integration

    async def _create_sync_log(self, integration: Integration, sync_type: str) -> IntegrationSyncLog:
        """Create initial sync log and update integration status."""
        sync_log = IntegrationSyncLog(
            integration_id=integration.id,
            sync_type=sync_type,
            started_at=utc_now(),
        )
        self.db.add(sync_log)

        integration.sync_status = "syncing"
        self.db.add(integration)
        await self.db.commit()

        return sync_log

    async def _finalize_success(
        self,
        integration: Integration,
        sync_log: IntegrationSyncLog,
        counts: tuple[int, int, int],
    ) -> None:
        """Finalize a successful sync."""
        created, updated, deleted = counts
        now = utc_now()

        sync_log.success = True
        sync_log.products_created = created
        sync_log.products_updated = updated
        sync_log.products_deleted = deleted
        sync_log.completed_at = now
        sync_log.duration_seconds = (now - sync_log.started_at).total_seconds()

        integration.sync_status = "idle"
        integration.last_sync_at = now
        integration.products_synced = await self._count_linked_products(integration.id)
        integration.error_message = None

        self.db.add(sync_log)
        self.db.add(integration)
        await self.db.commit()
        await self.db.refresh(sync_log)

        logger.info(
            f"Sync completed for {integration.store_url}: created={created}, updated={updated}, deleted={deleted}"
        )

    async def _finalize_failure(
        self,
        integration: Integration,
        sync_log: IntegrationSyncLog,
        error: str,
    ) -> None:
        """Finalize a failed sync."""
        now = utc_now()

        sync_log.success = False
        sync_log.error_details = error
        sync_log.completed_at = now
        sync_log.duration_seconds = (now - sync_log.started_at).total_seconds()

        integration.sync_status = "error"
        integration.error_message = error

        self.db.add(sync_log)
        self.db.add(integration)
        await self.db.commit()
        await self.db.refresh(sync_log)

    # ─── Product sync logic ──────────────────────────────────────

    async def _sync_products(self, integration: Integration, sync_type: str) -> tuple[int, int, int]:
        """Fetch products from platform and sync to database.

        Commits are batched per page (100 products) for performance,
        not per individual product/variant.
        """
        service = self.get_service(integration.platform)
        # Token already validated in run_sync, safe to decrypt again
        access_token = decrypt_token(integration.access_token_encrypted)

        created, updated, deleted = 0, 0, 0
        seen_link_keys: set = set()  # (external_product_id, external_variant_id) tuples
        cursor = integration.sync_cursor if sync_type == "incremental" else None

        has_more = True
        while has_more:
            result = await service.fetch_products(
                store_url=integration.store_url,
                access_token=access_token,
                cursor=cursor,
                limit=100,
            )

            if not result.success:
                raise SyncError(f"Failed to fetch products: {result.error}")

            for external_product in result.products:
                # Track all variant keys for deletion detection
                if external_product.variants:
                    for variant in external_product.variants:
                        seen_link_keys.add((external_product.id, variant.id))
                else:
                    seen_link_keys.add((external_product.id, None))

                c, u = await self._upsert_product(integration, external_product)
                created += c
                updated += u

            # FIX: Single commit per page — covers all upserts in this batch
            # plus the cursor update. Previously committed per product.
            cursor = result.next_cursor
            has_more = result.has_more
            integration.sync_cursor = cursor
            self.db.add(integration)
            await self.db.commit()

        if sync_type == "full":
            deleted = await self._handle_deletions(integration, seen_link_keys)

        return created, updated, deleted

    async def _upsert_product(self, integration: Integration, external_product: ExternalProduct) -> tuple[int, int]:
        """Create or update product + variant links from external data.

        One link per variant. Does NOT commit — caller batches commits.
        """
        created, updated = 0, 0

        variants = external_product.variants or []
        if not variants:
            c, u = await self._upsert_single_link(
                integration,
                external_product,
                variant_id=None,
                variant_sku=external_product.sku,
                variant_price=external_product.price,
                variant_compare_at_price=external_product.compare_at_price,
            )
            return c, u

        for variant in variants:
            c, u = await self._upsert_single_link(
                integration,
                external_product,
                variant_id=variant.id,
                variant_sku=variant.sku,
                variant_price=variant.price,
                variant_compare_at_price=getattr(variant, "compare_at_price", None),
            )
            created += c
            updated += u

        return created, updated

    async def _upsert_single_link(
        self,
        integration: Integration,
        external_product: ExternalProduct,
        variant_id: str | None,
        variant_sku: str | None,
        variant_price: float | None,
        variant_compare_at_price: float | None,
    ) -> tuple[int, int]:
        """Upsert a single product-variant link.

        Lookup key: integration_id + external_product_id + external_variant_id
        No SKU fallback. No name fallback.
        Does NOT commit — caller batches commits per page.
        """
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id,
            ProductIntegrationLink.external_product_id == external_product.id,
        )
        if variant_id:
            stmt = stmt.where(ProductIntegrationLink.external_variant_id == variant_id)
        else:
            stmt = stmt.where(ProductIntegrationLink.external_variant_id.is_(None))

        result = await self.db.execute(stmt)
        existing_link = result.scalars().first()

        if existing_link:
            return await self._update_existing(existing_link, external_product)

        return await self._create_new(
            integration,
            external_product,
            variant_id=variant_id,
            variant_sku=variant_sku,
            variant_price=variant_price,
            variant_compare_at_price=variant_compare_at_price,
        )

    async def _update_existing(
        self, link: ProductIntegrationLink, external_product: ExternalProduct
    ) -> tuple[int, int]:
        """Update existing product link with latest platform data.

        RULES (per Iqbal's Layer 2):
        - Only update platform-owned fields (name, sku)
        - NEVER overwrite current_price (owned by pricing engine)
        - Only write Product if something actually changed

        Does NOT commit — caller batches commits per page.
        """
        stmt = select(Product).where(Product.id == link.product_id)
        result = await self.db.execute(stmt)
        product = result.scalars().first()

        if not product:
            return 0, 0

        now = utc_now()
        changed = False

        # Platform-owned fields on Product (safe to update)
        if external_product.title and external_product.title != product.name:
            product.name = external_product.title
            changed = True

        if external_product.sku and external_product.sku != product.sku:
            product.sku = external_product.sku
            changed = True

        # NEVER overwrite current_price — owned by pricing engine.
        # Platform's price lives on link.external_price.

        if changed:
            product.updated_at = now
            self.db.add(product)

        # Platform-owned fields on the Link (always update)
        link.external_price = external_product.price
        link.external_compare_at_price = external_product.compare_at_price
        link.last_price_pull_at = now
        link.updated_at = now
        self.db.add(link)

        # FIX: Removed per-product commit. Caller commits per page.
        return 0, 1

    async def _create_new(
        self,
        integration: Integration,
        external_product: ExternalProduct,
        variant_id: str | None,
        variant_sku: str | None,
        variant_price: float | None,
        variant_compare_at_price: float | None,
    ) -> tuple[int, int]:
        """Create new product and link. No fallback matching.

        Uses flush() instead of commit() for the Product insert so we can
        get the generated ID without ending the transaction. The page-level
        commit in _sync_products will persist everything.
        """
        sku = variant_sku or f"{integration.platform.value.upper()}-{external_product.id}"
        if variant_id and not variant_sku:
            sku = f"{integration.platform.value.upper()}-{variant_id}"

        # Check if another variant of the same product already created a Product
        sibling_stmt = (
            select(ProductIntegrationLink)
            .where(
                ProductIntegrationLink.integration_id == integration.id,
                ProductIntegrationLink.external_product_id == external_product.id,
            )
            .limit(1)
        )
        result = await self.db.execute(sibling_stmt)
        sibling_link = result.scalars().first()

        if sibling_link:
            # Product exists — just add the variant link
            link = ProductIntegrationLink(
                product_id=sibling_link.product_id,
                integration_id=integration.id,
                external_product_id=external_product.id,
                external_variant_id=variant_id,
                external_price=variant_price,
                external_compare_at_price=variant_compare_at_price,
                last_price_pull_at=utc_now(),
            )
            self.db.add(link)
            # FIX: Removed per-product commit. Caller commits per page.
            return 0, 1

        # No product exists — create Product + first variant link
        product = Product(
            user_id=integration.user_id,
            name=external_product.title,
            sku=sku,
            base_price=variant_price or 0.0,
            current_price=variant_price or 0.0,
            cost=None,
        )
        self.db.add(product)
        # FIX: flush() to get the generated ID without committing the transaction.
        # The page-level commit in _sync_products persists everything.
        await self.db.flush()

        link = ProductIntegrationLink(
            product_id=product.id,
            integration_id=integration.id,
            external_product_id=external_product.id,
            external_variant_id=variant_id,
            external_price=variant_price,
            external_compare_at_price=variant_compare_at_price,
            last_price_pull_at=utc_now(),
        )
        self.db.add(link)
        # FIX: Removed per-product commit. Caller commits per page.

        return 1, 0

    async def _handle_deletions(self, integration: Integration, seen_link_keys: set) -> int:
        """Handle products/variants deleted from external platform.

        Disables sync for links whose (external_product_id, external_variant_id)
        tuple was not seen during this full sync.
        """
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id,
            ProductIntegrationLink.sync_enabled,
        )
        result = await self.db.execute(stmt)
        links = result.scalars().all()

        deleted = 0
        for link in links:
            key = (link.external_product_id, link.external_variant_id)
            if key not in seen_link_keys:
                link.sync_enabled = False
                link.updated_at = utc_now()
                self.db.add(link)
                deleted += 1

        if deleted > 0:
            await self.db.commit()
            logger.info(f"Disabled sync for {deleted} deleted products/variants")

        return deleted

    async def _count_linked_products(self, integration_id: UUID) -> int:
        """Count active linked products for an integration.

        FIX: Uses COUNT() query instead of loading all rows into memory.
        """
        stmt = select(func.count(ProductIntegrationLink.id)).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.sync_enabled,
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0


# ─── Background task functions ───────────────────────────────


async def run_product_sync(db: AsyncSession, integration_id: UUID, sync_type: str = "full") -> IntegrationSyncLog:
    """Background task function for running product sync."""
    sync_service = SyncService(db)
    return await sync_service.run_sync(integration_id=integration_id, sync_type=sync_type)


async def recover_stuck_syncs_async(db: AsyncSession) -> int:
    """
    Background task function for recovering stuck syncs.

    Should be called by Celery beat every 5 minutes.

    Returns:
        Number of syncs recovered
    """
    sync_service = SyncService(db)
    return await sync_service.recover_stuck_syncs()
