# backend/services/integration/sync_service.py

"""
Product Sync Service

Orchestrates syncing products between e-commerce platforms and SSP.
Handles full syncs, incremental syncs, and webhook-triggered updates.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.integration import (
    Integration,
    IntegrationSyncLog,
    ProductIntegrationLink,
    IntegrationStatus,
)
from models.product import Product
from core.encryption import decrypt_token
from services.integration.base import EcommerceService, ExternalProduct
from services.integration.shopify_service import ShopifyService
from services.integration.woocommerce_service import WooCommerceService

logger = logging.getLogger(__name__)


class SyncService:
    """
    Orchestrates product synchronization between e-commerce platforms and SSP.
    
    Supports:
    - Full sync: Fetches all products from platform
    - Incremental sync: Fetches only changed products (using cursor)
    - Webhook sync: Processes single product updates from webhooks
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def get_service(self, integration: Integration) -> EcommerceService:
        """Get the appropriate e-commerce service for the integration."""
        from models.integration import EcommercePlatform
        
        if integration.platform == EcommercePlatform.SHOPIFY:
            return ShopifyService()
        elif integration.platform == EcommercePlatform.WOOCOMMERCE:
            return WooCommerceService()
        else:
            raise ValueError(f"Unsupported platform: {integration.platform}")
    
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
        """
        # Get integration
        query = select(Integration).where(Integration.id == integration_id)
        if user_id:
            query = query.where(Integration.user_id == user_id)
        
        result = await self.db.execute(query)
        integration = result.scalars().first()
        
        if not integration:
            raise ValueError("Integration not found")
        
        if integration.status != IntegrationStatus.ACTIVE:
            raise ValueError("Integration is not active")
        
        # Create sync log
        sync_log = IntegrationSyncLog(
            integration_id=integration.id,
            sync_type=sync_type,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(sync_log)
        
        # Update integration status
        integration.sync_status = "syncing"
        self.db.add(integration)
        await self.db.commit()
        
        try:
            # Run the sync
            products_created, products_updated, products_deleted = await self._sync_products(
                integration=integration,
                sync_type=sync_type,
            )
            
            # Update sync log - success
            sync_log.success = True
            sync_log.products_created = products_created
            sync_log.products_updated = products_updated
            sync_log.products_deleted = products_deleted
            sync_log.completed_at = datetime.now(timezone.utc)
            # Handle potential timezone mismatch
            if sync_log.started_at.tzinfo is None:
                started = sync_log.started_at.replace(tzinfo=timezone.utc)
            else:
                started = sync_log.started_at
            sync_log.duration_seconds = (
                sync_log.completed_at - started
            ).total_seconds()
            
            # Update integration
            integration.sync_status = "idle"
            integration.last_sync_at = datetime.now(timezone.utc)
            integration.products_synced = await self._count_linked_products(integration.id)
            integration.error_message = None
            
        except Exception as e:
            logger.exception(f"Sync failed for integration {integration_id}")
            
            # Update sync log - failure
            sync_log.success = False
            sync_log.error_details = str(e)
            sync_log.completed_at = datetime.now(timezone.utc)
            # Handle potential timezone mismatch
            if sync_log.started_at.tzinfo is None:
                started = sync_log.started_at.replace(tzinfo=timezone.utc)
            else:
                started = sync_log.started_at
            sync_log.duration_seconds = (
                sync_log.completed_at - started
            ).total_seconds()
            
            # Update integration
            integration.sync_status = "error"
            integration.error_message = str(e)
        
        self.db.add(sync_log)
        self.db.add(integration)
        await self.db.commit()
        await self.db.refresh(sync_log)
        
        return sync_log
    
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
        service = self.get_service(integration)
        access_token = decrypt_token(integration.access_token_encrypted)
        
        products_created = 0
        products_updated = 0
        products_deleted = 0
        
        # Determine starting cursor
        cursor = None
        if sync_type == "incremental" and integration.sync_cursor:
            cursor = integration.sync_cursor
        
        # Track external IDs we've seen (for detecting deletions)
        seen_external_ids = set()
        
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
                raise Exception(f"Failed to fetch products: {result.error}")
            
            # Process each product
            for external_product in result.products:
                seen_external_ids.add(external_product.id)
                
                created, updated = await self._upsert_product(
                    integration=integration,
                    external_product=external_product,
                )
                
                products_created += created
                products_updated += updated
            
            # Update cursor and check for more
            cursor = result.next_cursor
            has_more = result.has_more
            
            # Save cursor progress
            integration.sync_cursor = cursor
            self.db.add(integration)
            await self.db.commit()
        
        # Handle deletions (only for full sync)
        if sync_type == "full":
            products_deleted = await self._handle_deletions(
                integration=integration,
                seen_external_ids=seen_external_ids,
            )
        
        return products_created, products_updated, products_deleted
    
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
        # Check if we already have a link for this external product
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id,
            ProductIntegrationLink.external_product_id == external_product.id,
        )
        result = await self.db.execute(stmt)
        existing_link = result.scalars().first()
        
        if existing_link:
            # Update existing product
            stmt = select(Product).where(Product.id == existing_link.product_id)
            result = await self.db.execute(stmt)
            product = result.scalars().first()
            
            if product:
                self._update_product_from_external(product, external_product)
                self.db.add(product)
                
                # Update link with latest price
                existing_link.external_price = external_product.price
                existing_link.external_compare_at_price = external_product.compare_at_price
                existing_link.last_price_pull_at = datetime.now(timezone.utc)
                existing_link.updated_at = datetime.now(timezone.utc)
                self.db.add(existing_link)
                
                await self.db.commit()
                return 0, 1
        
        # Create new product - generate SKU if not provided
        generated_sku = external_product.sku or f"{integration.platform.value.upper()}-{external_product.id}"
        
        product = Product(
            user_id=integration.user_id,
            name=external_product.title,
            sku=generated_sku,
            base_price=external_product.price or 0.0,
            current_price=external_product.price or 0.0,
            cost=None,  # External platforms don't expose cost
        )
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        
        # Create link
        link = ProductIntegrationLink(
            product_id=product.id,
            integration_id=integration.id,
            external_product_id=external_product.id,
            external_variant_id=self._get_default_variant_id(external_product),
            external_price=external_product.price,
            external_compare_at_price=external_product.compare_at_price,
            last_price_pull_at=datetime.now(timezone.utc),
        )
        self.db.add(link)
        await self.db.commit()
        
        return 1, 0
    
    def _update_product_from_external(
        self,
        product: Product,
        external_product: ExternalProduct,
    ) -> None:
        """Update a product with external data."""
        product.name = external_product.title
        # Keep existing SKU if external SKU is empty
        product.sku = external_product.sku or product.sku
        product.current_price = external_product.price or product.current_price
        product.updated_at = datetime.now(timezone.utc)
    
    def _get_default_variant_id(self, external_product: ExternalProduct) -> Optional[str]:
        """Get the default variant ID for a product."""
        if external_product.variants and len(external_product.variants) > 0:
            return external_product.variants[0].id
        return None
    
    async def _handle_deletions(
        self,
        integration: Integration,
        seen_external_ids: set,
    ) -> int:
        """
        Handle products that were deleted from the external platform.
        
        For now, we just disable sync on the link rather than deleting.
        """
        deleted_count = 0
        
        # Get all links for this integration
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id,
            ProductIntegrationLink.sync_enabled == True,
        )
        result = await self.db.execute(stmt)
        links = result.scalars().all()
        
        for link in links:
            if link.external_product_id not in seen_external_ids:
                # Product was deleted from external platform
                link.sync_enabled = False
                link.updated_at = datetime.now(timezone.utc)
                self.db.add(link)
                deleted_count += 1
        
        if deleted_count > 0:
            await self.db.commit()
        
        return deleted_count
    
    async def _count_linked_products(self, integration_id: UUID) -> int:
        """Count the number of linked products for an integration."""
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.sync_enabled == True,
        )
        result = await self.db.execute(stmt)
        links = result.scalars().all()
        return len(links)
    
    async def sync_single_product(
        self,
        integration_id: UUID,
        external_product_id: str,
        action: str = "update",  # "create", "update", "delete"
    ) -> Optional[ProductIntegrationLink]:
        """
        Sync a single product (typically called from webhook).
        
        Args:
            integration_id: The integration ID
            external_product_id: The external platform's product ID
            action: The action that triggered this sync
            
        Returns:
            The updated ProductIntegrationLink, or None if deleted
        """
        stmt = select(Integration).where(Integration.id == integration_id)
        result = await self.db.execute(stmt)
        integration = result.scalars().first()
        
        if not integration or integration.status != IntegrationStatus.ACTIVE:
            logger.warning(f"Integration {integration_id} not found or not active")
            return None
        
        service = self.get_service(integration)
        access_token = decrypt_token(integration.access_token_encrypted)
        
        if action == "delete":
            # Handle deletion
            stmt = select(ProductIntegrationLink).where(
                ProductIntegrationLink.integration_id == integration_id,
                ProductIntegrationLink.external_product_id == external_product_id,
            )
            result = await self.db.execute(stmt)
            link = result.scalars().first()
            
            if link:
                link.sync_enabled = False
                link.updated_at = datetime.now(timezone.utc)
                self.db.add(link)
                await self.db.commit()
                
                # Create a sync log for the deletion
                sync_log = IntegrationSyncLog(
                    integration_id=integration.id,
                    sync_type="webhook",
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=0,
                    success=True,
                    products_deleted=1,
                )
                self.db.add(sync_log)
                await self.db.commit()
            
            return None
        
        # Fetch the product from the platform
        external_product = await service.fetch_single_product(
            store_url=integration.store_url,
            access_token=access_token,
            external_product_id=external_product_id,
        )
        
        if not external_product:
            logger.warning(f"Product {external_product_id} not found on platform")
            return None
        
        # Upsert the product
        created, updated = await self._upsert_product(
            integration=integration,
            external_product=external_product,
        )
        
        # Create sync log
        sync_log = IntegrationSyncLog(
            integration_id=integration.id,
            sync_type="webhook",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=0,
            success=True,
            products_created=created,
            products_updated=updated,
        )
        self.db.add(sync_log)
        await self.db.commit()
        
        # Return the link
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.external_product_id == external_product_id,
        )
        result = await self.db.execute(stmt)
        link = result.scalars().first()
        
        return link


# ==================== Background Task Function ====================

async def run_product_sync(
    db: AsyncSession,
    integration_id: UUID,
    sync_type: str = "full",
) -> IntegrationSyncLog:
    """
    Background task function for running product sync.
    
    This can be called from FastAPI BackgroundTasks or Celery.
    """
    sync_service = SyncService(db)
    return await sync_service.run_sync(
        integration_id=integration_id,
        sync_type=sync_type,
    )
