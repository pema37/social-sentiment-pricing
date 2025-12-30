# backend/services/integration/sync_service.py

"""
Product Sync Service

Orchestrates syncing products between e-commerce platforms and SSP.
Handles full syncs, incremental syncs, and webhook-triggered updates.
"""

import logging
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
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

# Use new modular imports
from .base import EcommerceService
from .models import ExternalProduct
from .circuit_breaker import CircuitOpenError, circuit_breaker_registry
from .shopify_service import ShopifyService
from .woocommerce_service import WooCommerceService

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time as naive datetime (for PostgreSQL TIMESTAMP WITHOUT TIME ZONE)."""
    return datetime.utcnow()


class SyncError(Exception):
    """Base exception for sync errors"""
    pass


class SyncTemporarilyUnavailable(SyncError):
    """Raised when external service is temporarily unavailable"""
    pass


class SyncService:
    """
    Orchestrates product synchronization between e-commerce platforms and SSP.
    
    Supports:
    - Full sync: Fetches all products from platform
    - Incremental sync: Fetches only changed products (using cursor)
    - Webhook sync: Processes single product updates from webhooks
    """
    
    # Service instances (cached)
    _services: dict[EcommercePlatform, EcommerceService] = {}
    
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
    
    async def run_sync(
        self,
        integration_id: UUID,
        sync_type: str = "full",
        user_id: Optional[UUID] = None,
    ) -> IntegrationSyncLog:
        """
        Run a product sync for an integration.
        
        Args:
            integration_id: The integration to sync
            sync_type: "full" or "incremental"
            user_id: Optional user ID for ownership verification
            
        Returns:
            IntegrationSyncLog with sync results
            
        Raises:
            SyncTemporarilyUnavailable: If external service is down
            ValueError: If integration not found or inactive
        """
        integration = await self._get_integration(integration_id, user_id)
        sync_log = await self._create_sync_log(integration, sync_type)
        
        try:
            counts = await self._sync_products(integration, sync_type)
            await self._finalize_success(integration, sync_log, counts)
            
        except CircuitOpenError as e:
            logger.warning(f"Sync blocked by circuit breaker: {integration.store_url}")
            await self._finalize_failure(integration, sync_log, "Service temporarily unavailable")
            raise SyncTemporarilyUnavailable(str(e))
            
        except Exception as e:
            logger.exception(f"Sync failed for integration {integration_id}")
            await self._finalize_failure(integration, sync_log, str(e))
        
        return sync_log
    
    async def _get_integration(
        self, 
        integration_id: UUID, 
        user_id: Optional[UUID]
    ) -> Integration:
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
    
    async def _create_sync_log(
        self, 
        integration: Integration, 
        sync_type: str
    ) -> IntegrationSyncLog:
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
        sync_log.duration_seconds = self._calc_duration(sync_log.started_at, now)
        
        integration.sync_status = "idle"
        integration.last_sync_at = now
        integration.products_synced = await self._count_linked_products(integration.id)
        integration.error_message = None
        
        self.db.add(sync_log)
        self.db.add(integration)
        await self.db.commit()
        await self.db.refresh(sync_log)
        
        logger.info(
            f"Sync completed for {integration.store_url}: "
            f"created={created}, updated={updated}, deleted={deleted}"
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
        sync_log.duration_seconds = self._calc_duration(sync_log.started_at, now)
        
        integration.sync_status = "error"
        integration.error_message = error
        
        self.db.add(sync_log)
        self.db.add(integration)
        await self.db.commit()
        await self.db.refresh(sync_log)
    
    def _calc_duration(self, start: datetime, end: datetime) -> float:
        """Calculate duration in seconds."""
        return (end - start).total_seconds()
    
    async def _sync_products(
        self,
        integration: Integration,
        sync_type: str,
    ) -> Tuple[int, int, int]:
        """
        Fetch products from platform and sync to database.
        
        Returns:
            Tuple of (created, updated, deleted) counts
        """
        service = self.get_service(integration.platform)
        access_token = decrypt_token(integration.access_token_encrypted)
        
        created, updated, deleted = 0, 0, 0
        seen_external_ids = set()
        
        # Determine starting cursor
        cursor = integration.sync_cursor if sync_type == "incremental" else None
        
        # Paginate through all products
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
            
            # Process each product
            for external_product in result.products:
                seen_external_ids.add(external_product.id)
                c, u = await self._upsert_product(integration, external_product)
                created += c
                updated += u
            
            # Update cursor and check for more
            cursor = result.next_cursor
            has_more = result.has_more
            
            # Save cursor progress
            integration.sync_cursor = cursor
            self.db.add(integration)
            await self.db.commit()
        
        # Handle deletions (only for full sync)
        if sync_type == "full":
            deleted = await self._handle_deletions(integration, seen_external_ids)
        
        return created, updated, deleted
    
    async def _upsert_product(
        self,
        integration: Integration,
        external_product: ExternalProduct,
    ) -> Tuple[int, int]:
        """
        Create or update a product from external data.
        
        Returns:
            Tuple of (created, updated) - one will be 1, other 0
        """
        # Check for existing link
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id,
            ProductIntegrationLink.external_product_id == external_product.id,
        )
        result = await self.db.execute(stmt)
        existing_link = result.scalars().first()
        
        if existing_link:
            return await self._update_existing(existing_link, external_product)
        return await self._create_new(integration, external_product)
    
    async def _update_existing(
        self,
        link: ProductIntegrationLink,
        external_product: ExternalProduct,
    ) -> Tuple[int, int]:
        """Update existing product and link."""
        stmt = select(Product).where(Product.id == link.product_id)
        result = await self.db.execute(stmt)
        product = result.scalars().first()
        
        if not product:
            return 0, 0
        
        now = utc_now()
        
        # Update product
        product.name = external_product.title
        product.sku = external_product.sku or product.sku
        product.current_price = external_product.price or product.current_price
        product.updated_at = now
        self.db.add(product)
        
        # Update link
        link.external_price = external_product.price
        link.external_compare_at_price = external_product.compare_at_price
        link.last_price_pull_at = now
        link.updated_at = now
        self.db.add(link)
        
        await self.db.commit()
        return 0, 1
    
    async def _create_new(
        self,
        integration: Integration,
        external_product: ExternalProduct,
    ) -> Tuple[int, int]:
        """Create new product and link, or link to existing product with same SKU."""
        sku = external_product.sku or f"{integration.platform.value.upper()}-{external_product.id}"
        
        # Check if product with this SKU already exists for this user
        existing_stmt = select(Product).where(
            Product.user_id == integration.user_id,
            Product.sku == sku,
        )
        result = await self.db.execute(existing_stmt)
        existing_product = result.scalars().first()
        
        if existing_product:
            # Product exists - just create the link
            logger.info(f"Product with SKU {sku} already exists, creating link only")
            
            variant_id = None
            if external_product.variants:
                variant_id = external_product.variants[0].id
            
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
            
            return 0, 1  # Count as update since product existed
        
        # Create new product
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
        
        # Create link
        variant_id = None
        if external_product.variants:
            variant_id = external_product.variants[0].id
        
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
    
    async def _handle_deletions(
        self,
        integration: Integration,
        seen_external_ids: set,
    ) -> int:
        """
        Handle products deleted from external platform.
        Disables sync on link rather than deleting.
        """
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
    
    # ==================== Webhook Sync ====================
    
    async def sync_single_product(
        self,
        integration_id: UUID,
        external_product_id: str,
        action: str = "update",
    ) -> Optional[ProductIntegrationLink]:
        """
        Sync a single product (typically from webhook).
        
        Args:
            integration_id: The integration ID
            external_product_id: The external platform's product ID
            action: "create", "update", or "delete"
            
        Returns:
            The updated ProductIntegrationLink, or None if deleted
        """
        stmt = select(Integration).where(Integration.id == integration_id)
        result = await self.db.execute(stmt)
        integration = result.scalars().first()
        
        if not integration or integration.status != IntegrationStatus.ACTIVE:
            logger.warning(f"Integration {integration_id} not found or inactive")
            return None
        
        if action == "delete":
            return await self._handle_webhook_delete(integration, external_product_id)
        
        return await self._handle_webhook_upsert(integration, external_product_id)
    
    async def _handle_webhook_delete(
        self,
        integration: Integration,
        external_product_id: str,
    ) -> None:
        """Handle webhook delete action."""
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id,
            ProductIntegrationLink.external_product_id == external_product_id,
        )
        result = await self.db.execute(stmt)
        link = result.scalars().first()
        
        now = utc_now()
        
        if link:
            link.sync_enabled = False
            link.updated_at = now
            self.db.add(link)
            
            sync_log = IntegrationSyncLog(
                integration_id=integration.id,
                sync_type="webhook",
                started_at=now,
                completed_at=now,
                duration_seconds=0,
                success=True,
                products_deleted=1,
            )
            self.db.add(sync_log)
            await self.db.commit()
        
        return None
    
    async def _handle_webhook_upsert(
        self,
        integration: Integration,
        external_product_id: str,
    ) -> Optional[ProductIntegrationLink]:
        """Handle webhook create/update action."""
        service = self.get_service(integration.platform)
        access_token = decrypt_token(integration.access_token_encrypted)
        
        try:
            external_product = await service.fetch_single_product(
                store_url=integration.store_url,
                access_token=access_token,
                external_product_id=external_product_id,
            )
        except CircuitOpenError:
            logger.warning(f"Webhook sync blocked by circuit breaker: {integration.store_url}")
            return None
        
        if not external_product:
            logger.warning(f"Product {external_product_id} not found on platform")
            return None
        
        created, updated = await self._upsert_product(integration, external_product)
        
        # Create sync log
        now = utc_now()
        sync_log = IntegrationSyncLog(
            integration_id=integration.id,
            sync_type="webhook",
            started_at=now,
            completed_at=now,
            duration_seconds=0,
            success=True,
            products_created=created,
            products_updated=updated,
        )
        self.db.add(sync_log)
        await self.db.commit()
        
        # Return link
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id,
            ProductIntegrationLink.external_product_id == external_product_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    # ==================== Circuit Breaker Status ====================
    
    async def get_circuit_status(self, store_url: str) -> dict:
        """Get circuit breaker status for a store."""
        breaker = await circuit_breaker_registry.get(store_url)
        return breaker.get_status()
    
    async def reset_circuit(self, store_url: str) -> None:
        """Reset circuit breaker for a store (admin action)."""
        await circuit_breaker_registry.reset(store_url)
        logger.info(f"Circuit breaker reset for {store_url}")


# ==================== Background Task Function ====================

async def run_product_sync(
    db: AsyncSession,
    integration_id: UUID,
    sync_type: str = "full",
) -> IntegrationSyncLog:
    """
    Background task function for running product sync.
    Can be called from FastAPI BackgroundTasks or Celery.
    """
    sync_service = SyncService(db)
    return await sync_service.run_sync(
        integration_id=integration_id,
        sync_type=sync_type,
    )

