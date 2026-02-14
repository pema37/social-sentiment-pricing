# backend/services/integration/sync_service.py

"""
Product Sync Service - PULL operations

Orchestrates syncing products FROM e-commerce platforms TO SSP.
Handles full syncs, incremental syncs, and webhook-triggered updates.

PATCHED (2026-01-28): Bug #6 fix - Added recover_stuck_syncs() method to
handle integrations stuck in 'syncing' status due to worker crashes or
unexpected failures. See SSP_AUDIT_REPORT.md.
"""

import asyncio
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, Tuple, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from models.integration import (
    Integration,
    IntegrationSyncLog,
    ProductIntegrationLink,
    IntegrationStatus,
    EcommercePlatform,
)
from models.product import Product
from core.encryption import decrypt_token

from .base import EcommerceService
from .schemas import ExternalProduct
from .circuit_breaker import CircuitOpenError, circuit_breaker_registry
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
    
    # ========== NEW: Stuck sync recovery constants ==========
    STUCK_SYNC_TIMEOUT_MINUTES = 15  # If syncing for longer than this, it's stuck
    # ========== END NEW ==========
    
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
    
    # ========== NEW: Stuck sync recovery method (Bug #6 fix) ==========
    async def recover_stuck_syncs(self, user_id: Optional[UUID] = None) -> int:
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
        
        Note (2026-01-28): Added to fix Bug #6 where syncs would get stuck
        in 'syncing' status forever if the worker crashed. This method should
        be called periodically by a Celery beat task (every 5 minutes).
        """
        cutoff = utc_now() - timedelta(minutes=self.STUCK_SYNC_TIMEOUT_MINUTES)
        
        # Find integrations stuck in 'syncing' status
        stmt = select(Integration).where(
            Integration.sync_status == "syncing",
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
                .where(IntegrationSyncLog.completed_at.is_(None))  # Not completed
                .where(IntegrationSyncLog.started_at < cutoff)     # Started too long ago
                .order_by(IntegrationSyncLog.started_at.desc())
                .limit(1)
            )
            log_result = await self.db.execute(log_stmt)
            stuck_log = log_result.scalars().first()
            
            if stuck_log:
                # This sync has been running too long - mark as failed
                now = utc_now()
                
                stuck_log.success = False
                stuck_log.error_details = (
                    f"Sync timed out after {self.STUCK_SYNC_TIMEOUT_MINUTES} minutes "
                    f"(recovered by cleanup task at {now.isoformat()})"
                )
                stuck_log.completed_at = now
                stuck_log.duration_seconds = (now - stuck_log.started_at).total_seconds()
                self.db.add(stuck_log)
                
                # Reset integration status so user can retry
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
                # No stuck log found, but integration is still 'syncing'
                # This could be a race condition or a log that was never created
                # Check if the integration has been 'syncing' without any recent log
                recent_log_stmt = (
                    select(IntegrationSyncLog)
                    .where(IntegrationSyncLog.integration_id == integration.id)
                    .order_by(IntegrationSyncLog.started_at.desc())
                    .limit(1)
                )
                recent_result = await self.db.execute(recent_log_stmt)
                recent_log = recent_result.scalars().first()
                
                # If no recent log, or the most recent log is completed but status is still 'syncing'
                if not recent_log or (recent_log.completed_at is not None):
                    integration.sync_status = "error"
                    integration.error_message = "Sync status was inconsistent. Please try again."
                    self.db.add(integration)
                    recovered += 1
                    logger.warning(
                        f"Recovered inconsistent sync status for integration {integration.id} "
                        f"({integration.store_url})"
                    )
        
        if recovered > 0:
            await self.db.commit()
            logger.info(f"Recovered {recovered} stuck sync(s)")
        
        return recovered
    
    async def get_stuck_syncs(self, user_id: Optional[UUID] = None) -> List[dict]:
        """
        Get list of integrations currently stuck in 'syncing' status.
        
        Useful for diagnostics and admin dashboards.
        
        Returns:
            List of dicts with integration info and how long they've been stuck
        """
        cutoff = utc_now() - timedelta(minutes=self.STUCK_SYNC_TIMEOUT_MINUTES)
        
        stmt = select(Integration).where(Integration.sync_status == "syncing")
        if user_id:
            stmt = stmt.where(Integration.user_id == user_id)
        
        result = await self.db.execute(stmt)
        integrations = result.scalars().all()
        
        stuck = []
        for integration in integrations:
            # Get the in-progress sync log
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
                stuck.append({
                    "integration_id": str(integration.id),
                    "store_url": integration.store_url,
                    "platform": integration.platform.value if hasattr(integration.platform, 'value') else str(integration.platform),
                    "started_at": sync_log.started_at.isoformat(),
                    "stuck_for_minutes": (utc_now() - sync_log.started_at).total_seconds() / 60,
                    "sync_log_id": str(sync_log.id),
                })
        
        return stuck
    # ========== END NEW ==========
    
    async def run_sync(
        self,
        integration_id: UUID,
        sync_type: str = "full",
        user_id: Optional[UUID] = None,
    ) -> IntegrationSyncLog:
        """Run a product sync with timeout protection."""
        integration = await self._get_integration(integration_id, user_id)
        sync_log = await self._create_sync_log(integration, sync_type)
        
        try:
            counts = await asyncio.wait_for(
                self._sync_products(integration, sync_type),
                timeout=self.SYNC_TIMEOUT_SECONDS
            )
            await self._finalize_success(integration, sync_log, counts)
            
        except asyncio.TimeoutError:
            error_msg = f"Sync timed out after {self.SYNC_TIMEOUT_SECONDS} seconds"
            logger.error(f"{error_msg} for integration {integration_id}")
            await self._finalize_failure(integration, sync_log, error_msg)
            raise SyncTimeoutError(error_msg)
            
        except CircuitOpenError as e:
            logger.warning(f"Sync blocked by circuit breaker: {integration.store_url}")
            await self._finalize_failure(integration, sync_log, "Service temporarily unavailable")
            raise SyncTemporarilyUnavailable(str(e))
            
        except Exception as e:
            logger.exception(f"Sync failed for integration {integration_id}")
            await self._finalize_failure(integration, sync_log, str(e))
        
        return sync_log
    
    async def _get_integration(self, integration_id: UUID, user_id: Optional[UUID]) -> Integration:
        """Fetch and validate integration."""
        query = select(Integration).where(Integration.id == integration_id)
        if user_id:
            query = query.where(Integration.user_id == user_id)
        
        result = await self.db.execute(query)
        integration = result.scalars().first()
        
        if not integration:
            raise ValueError("Integration not found")
        if integration.status != IntegrationStatus.ACTIVE:
            raise ValueError("Integration is not active")
        
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
        counts: Tuple[int, int, int],
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
        
        logger.info(f"Sync completed for {integration.store_url}: created={created}, updated={updated}, deleted={deleted}")
    
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
    
    async def _sync_products(self, integration: Integration, sync_type: str) -> Tuple[int, int, int]:
        """Fetch products from platform and sync to database."""
        service = self.get_service(integration.platform)
        access_token = decrypt_token(integration.access_token_encrypted)
        
        created, updated, deleted = 0, 0, 0
        seen_external_ids = set()
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
                seen_external_ids.add(external_product.id)
                c, u = await self._upsert_product(integration, external_product)
                created += c
                updated += u
            
            cursor = result.next_cursor
            has_more = result.has_more
            
            integration.sync_cursor = cursor
            self.db.add(integration)
            await self.db.commit()
        
        if sync_type == "full":
            deleted = await self._handle_deletions(integration, seen_external_ids)
        
        return created, updated, deleted
    
    async def _upsert_product(self, integration: Integration, external_product: ExternalProduct) -> Tuple[int, int]:
        """Create or update a product from external data."""
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id,
            ProductIntegrationLink.external_product_id == external_product.id,
        )
        result = await self.db.execute(stmt)
        existing_link = result.scalars().first()
        
        if existing_link:
            return await self._update_existing(existing_link, external_product)
        return await self._create_new(integration, external_product)
    
    async def _update_existing(self, link: ProductIntegrationLink, external_product: ExternalProduct) -> Tuple[int, int]:
        """Update existing product and link."""
        stmt = select(Product).where(Product.id == link.product_id)
        result = await self.db.execute(stmt)
        product = result.scalars().first()
        
        if not product:
            return 0, 0
        
        now = utc_now()
        product.name = external_product.title
        product.sku = external_product.sku or product.sku
        product.current_price = external_product.price or product.current_price
        product.updated_at = now
        self.db.add(product)
        
        link.external_price = external_product.price
        link.external_compare_at_price = external_product.compare_at_price
        link.last_price_pull_at = now
        link.updated_at = now
        self.db.add(link)
        
        await self.db.commit()
        return 0, 1
    
    async def _create_new(self, integration: Integration, external_product: ExternalProduct) -> Tuple[int, int]:
        """Create new product and link."""
        sku = external_product.sku or f"{integration.platform.value.upper()}-{external_product.id}"
        
        existing_stmt = select(Product).where(
            Product.user_id == integration.user_id,
            Product.sku == sku,
        )
        result = await self.db.execute(existing_stmt)
        existing_product = result.scalars().first()
        
        if existing_product:
            logger.info(f"Product with SKU {sku} already exists, creating link only")
            variant_id = external_product.variants[0].id if external_product.variants else None
            
            link = ProductIntegrationLink(
                product_id=existing_product.id,
                integration_id=integration.id,
                external_product_id=external_product.id,
                external_variant_id=variant_id,
                external_price=external_product.price,
                external_compare_at_price=external_product.compare_at_price,
                last_price_pull_at=utc_now(),
            )
            self.db.add(link)
            await self.db.commit()
            return 0, 1
        
        product = Product(
            user_id=integration.user_id,
            name=external_product.title,
            sku=sku,
            base_price=external_product.price or 0.0,
            current_price=external_product.price or 0.0,
            cost=None,
        )
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        
        variant_id = external_product.variants[0].id if external_product.variants else None
        link = ProductIntegrationLink(
            product_id=product.id,
            integration_id=integration.id,
            external_product_id=external_product.id,
            external_variant_id=variant_id,
            external_price=external_product.price,
            external_compare_at_price=external_product.compare_at_price,
            last_price_pull_at=utc_now(),
        )
        self.db.add(link)
        await self.db.commit()
        
        return 1, 0
    
    async def _handle_deletions(self, integration: Integration, seen_external_ids: set) -> int:
        """Handle products deleted from external platform."""
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id,
            ProductIntegrationLink.sync_enabled == True,
        )
        result = await self.db.execute(stmt)
        links = result.scalars().all()
        
        deleted = 0
        for link in links:
            if link.external_product_id not in seen_external_ids:
                link.sync_enabled = False
                link.updated_at = utc_now()
                self.db.add(link)
                deleted += 1
        
        if deleted > 0:
            await self.db.commit()
            logger.info(f"Disabled sync for {deleted} deleted products")
        
        return deleted
    
    async def _count_linked_products(self, integration_id: UUID) -> int:
        """Count linked products for an integration."""
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.sync_enabled == True,
        )
        result = await self.db.execute(stmt)
        return len(result.scalars().all())


# Background task function
async def run_product_sync(db: AsyncSession, integration_id: UUID, sync_type: str = "full") -> IntegrationSyncLog:
    """Background task function for running product sync."""
    sync_service = SyncService(db)
    return await sync_service.run_sync(integration_id=integration_id, sync_type=sync_type)


# ========== NEW: Background task function for stuck sync recovery ==========
async def recover_stuck_syncs_async(db: AsyncSession) -> int:
    """
    Background task function for recovering stuck syncs.
    
    Should be called by Celery beat every 5 minutes.
    
    Returns:
        Number of syncs recovered
    """
    sync_service = SyncService(db)
    return await sync_service.recover_stuck_syncs()
# ========== END NEW ==========



