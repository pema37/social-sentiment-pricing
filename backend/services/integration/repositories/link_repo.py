# backend/services/integration/repositories/link_repo.py

"""
Product Integration Link Repository

Handles all database operations for ProductIntegrationLink model.
Single Responsibility: Only link CRUD operations.
"""

import logging
from datetime import datetime, UTC
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.integration import ProductIntegrationLink

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time as naive datetime."""
    return datetime.now(UTC)


class LinkRepository:
    """
    Repository for ProductIntegrationLink database operations.
    
    Methods:
    - find_by_external_id: Find link by integration + external product ID
    - find_active_by_integration: Get all active links for an integration
    - count_active: Count active links for an integration
    - create: Create new link
    - update_from_external: Update link with external product data
    - disable_sync: Disable sync for a link (soft delete)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def find_by_external_id(
        self,
        integration_id: UUID,
        external_product_id: str,
    ) -> Optional[ProductIntegrationLink]:
        """Find a link by integration and external product ID."""
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.external_product_id == external_product_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def find_active_by_integration(
        self,
        integration_id: UUID,
    ) -> List[ProductIntegrationLink]:
        """Find all active (sync_enabled=True) links for an integration."""
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.sync_enabled == True,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def count_active(self, integration_id: UUID) -> int:
        """Count active links for an integration."""
        links = await self.find_active_by_integration(integration_id)
        return len(links)
    
    async def create(
        self,
        product_id: UUID,
        integration_id: UUID,
        external_product_id: str,
        external_variant_id: Optional[str],
        external_price: Optional[float],
        external_compare_at_price: Optional[float],
        sync_enabled: bool = True,
    ) -> ProductIntegrationLink:
        """Create a new integration link."""
        link = ProductIntegrationLink(
            product_id=product_id,
            integration_id=integration_id,
            external_product_id=external_product_id,
            external_variant_id=external_variant_id,
            external_price=external_price,
            external_compare_at_price=external_compare_at_price,
            sync_enabled=sync_enabled,
            last_price_pull_at=utc_now(),
        )
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link
    
    async def update_prices(
        self,
        link: ProductIntegrationLink,
        external_price: Optional[float],
        external_compare_at_price: Optional[float],
    ) -> ProductIntegrationLink:
        """Update link with price data from external product."""
        now = utc_now()
        
        link.external_price = external_price
        link.external_compare_at_price = external_compare_at_price
        link.last_price_pull_at = now
        link.updated_at = now
        
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link
    
    async def disable_sync(self, link: ProductIntegrationLink) -> ProductIntegrationLink:
        """Disable sync for a link (soft delete)."""
        link.sync_enabled = False
        link.updated_at = utc_now()
        self.db.add(link)
        await self.db.commit()
        return link
    
    async def disable_missing(
        self,
        integration_id: UUID,
        seen_external_ids: set,
    ) -> int:
        """
        Disable sync for links whose external products are no longer present.
        
        Returns:
            Number of links disabled.
        """
        links = await self.find_active_by_integration(integration_id)
        
        disabled_count = 0
        for link in links:
            if link.external_product_id not in seen_external_ids:
                link.sync_enabled = False
                link.updated_at = utc_now()
                self.db.add(link)
                disabled_count += 1
        
        if disabled_count > 0:
            await self.db.commit()
            logger.info(f"Disabled sync for {disabled_count} deleted products")
        
        return disabled_count
    
