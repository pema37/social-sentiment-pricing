# backend/api/v1/routes/product_sync.py
"""
Product Sync API - Endpoints for bi-directional product synchronization.

Note: API returns snake_case, frontend API client transforms to camelCase.

Endpoints:
- POST /products/{id}/sync - Push single product to store(s)
- POST /products/sync/bulk - Push multiple products to store(s)
- POST /products/{id}/link - Manually link product to store product
- GET /products/{id}/sync-status - Check sync status for a product
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_db
from models.product import Product
from models.integration import ProductIntegrationLink, Integration, IntegrationStatus
from models.user import User
from services.integration.product_sync_service import ProductSyncService
from core.deps import get_current_user

router = APIRouter(prefix="/products", tags=["product-sync"])


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response Schemas (snake_case per backend conventions)
# API client transforms to camelCase for frontend
# ─────────────────────────────────────────────────────────────────────────────

class SyncProductRequest(BaseModel):
    """Request to sync a product to e-commerce store(s)."""
    integration_id: Optional[UUID] = Field(
        None, 
        description="Specific integration to sync to. If None, syncs to all active integrations."
    )


class LinkProductRequest(BaseModel):
    """Request to manually link a product to an existing e-commerce product."""
    integration_id: UUID = Field(..., description="Integration to link to")
    external_product_id: str = Field(..., description="Product ID in the e-commerce store")
    external_variant_id: Optional[str] = Field(None, description="Variant ID (for Shopify)")


class BulkSyncRequest(BaseModel):
    """Request to sync multiple products."""
    product_ids: Optional[List[UUID]] = Field(
        None,
        description="Specific product IDs to sync. If None, syncs all products without links."
    )
    integration_id: Optional[UUID] = Field(
        None,
        description="Specific integration to sync to. If None, syncs to all active integrations."
    )


class SyncLinkResponse(BaseModel):
    """Response for a single sync link."""
    link_id: str
    integration_id: str
    platform: str
    store_url: str
    external_product_id: str
    external_variant_id: Optional[str] = None
    sync_enabled: bool
    last_synced_at: Optional[str] = None
    external_price: Optional[float] = None


class AvailableIntegrationResponse(BaseModel):
    """Response for an available integration."""
    integration_id: str
    platform: str
    store_url: str


class SyncStatusResponse(BaseModel):
    """Response showing sync status for a product."""
    product_id: str
    product_name: str
    has_links: bool
    links: List[SyncLinkResponse]
    available_integrations: List[AvailableIntegrationResponse]


class SyncResultItemResponse(BaseModel):
    """Response for a single sync result."""
    integration_id: str
    platform: str
    store_url: str
    success: bool
    external_product_id: Optional[str] = None
    link_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{product_id}/sync", response_model=dict)
async def sync_product_to_store(
    product_id: UUID,
    request: Optional[SyncProductRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Push a product to e-commerce store(s).
    
    Creates the product in WooCommerce/Shopify and establishes
    the ProductIntegrationLink for future price syncing.
    """
    # Get the product
    stmt = select(Product).where(
        Product.id == product_id,
        Product.user_id == current_user.id
    )
    result = await db.execute(stmt)
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    sync_service = ProductSyncService(db)
    
    # If specific integration requested
    if request and request.integration_id:
        stmt = select(Integration).where(
            Integration.id == request.integration_id,
            Integration.user_id == current_user.id,
            Integration.status == IntegrationStatus.ACTIVE
        )
        result = await db.execute(stmt)
        integration = result.scalars().first()
        
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Integration not found or not active"
            )
        
        sync_result = await sync_service.push_product_to_store(product, integration)
        return {
            "product_id": str(product_id),
            "product_name": product.name,
            "results": [{
                "integration_id": str(integration.id),
                "platform": integration.platform.value,
                "store_url": integration.store_url,
                **sync_result
            }]
        }
    
    # Sync to all active integrations
    sync_result = await sync_service.sync_product_on_create(
        product=product,
        user_id=current_user.id,
        auto_push=True
    )
    
    return {
        "product_id": str(product_id),
        "product_name": product.name,
        **sync_result
    }


@router.post("/{product_id}/link", response_model=dict)
async def link_product_to_store(
    product_id: UUID,
    request: LinkProductRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually link an SSP product to an existing e-commerce product.
    
    Use this when:
    - The product already exists in both systems
    - Auto-sync failed and you want to manually specify the mapping
    - You imported products separately and need to connect them
    """
    # Verify product ownership
    stmt = select(Product).where(
        Product.id == product_id,
        Product.user_id == current_user.id
    )
    result = await db.execute(stmt)
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Verify integration ownership
    stmt = select(Integration).where(
        Integration.id == request.integration_id,
        Integration.user_id == current_user.id
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    sync_service = ProductSyncService(db)
    link_result = await sync_service.link_existing_product(
        product_id=product_id,
        integration_id=request.integration_id,
        external_product_id=request.external_product_id,
        external_variant_id=request.external_variant_id,
    )
    
    if not link_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=link_result.get("error", "Failed to create link")
        )
    
    return {
        "product_id": str(product_id),
        "product_name": product.name,
        "integration_id": str(request.integration_id),
        "platform": integration.platform.value,
        **link_result
    }


@router.get("/{product_id}/sync-status", response_model=SyncStatusResponse)
async def get_product_sync_status(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the sync status for a product.
    
    Shows:
    - Which stores the product is linked to
    - Which integrations are available for syncing
    - Last sync timestamps
    """
    # Get the product
    stmt = select(Product).where(
        Product.id == product_id,
        Product.user_id == current_user.id
    )
    result = await db.execute(stmt)
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Get existing links
    stmt = (
        select(ProductIntegrationLink, Integration)
        .join(Integration, ProductIntegrationLink.integration_id == Integration.id)
        .where(ProductIntegrationLink.product_id == product_id)
    )
    result = await db.execute(stmt)
    links_with_integrations = result.all()
    
    links = []
    linked_integration_ids = set()
    for link, integration in links_with_integrations:
        linked_integration_ids.add(integration.id)
        links.append(SyncLinkResponse(
            link_id=str(link.id),
            integration_id=str(integration.id),
            platform=integration.platform.value,
            store_url=integration.store_url,
            external_product_id=link.external_product_id,
            external_variant_id=link.external_variant_id,
            sync_enabled=link.sync_enabled,
            last_synced_at=link.last_synced_at.isoformat() if link.last_synced_at else None,
            external_price=float(link.external_price) if link.external_price else None,
        ))
    
    # Get available integrations (not yet linked)
    stmt = select(Integration).where(
        Integration.user_id == current_user.id,
        Integration.status == IntegrationStatus.ACTIVE
    )
    result = await db.execute(stmt)
    all_integrations = result.scalars().all()
    
    available_integrations = []
    for integration in all_integrations:
        if integration.id not in linked_integration_ids:
            available_integrations.append(AvailableIntegrationResponse(
                integration_id=str(integration.id),
                platform=integration.platform.value,
                store_url=integration.store_url,
            ))
    
    return SyncStatusResponse(
        product_id=str(product_id),
        product_name=product.name,
        has_links=len(links) > 0,
        links=links,
        available_integrations=available_integrations,
    )


@router.post("/sync/bulk", response_model=dict)
async def bulk_sync_products(
    request: Optional[BulkSyncRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Push multiple products to e-commerce store(s).
    
    If product_ids is not specified, syncs all products that don't have links.
    Useful for initial setup or recovering from sync issues.
    """
    sync_service = ProductSyncService(db)
    
    result = await sync_service.bulk_push_products(
        user_id=current_user.id,
        product_ids=request.product_ids if request else None,
    )
    
    return result


@router.delete("/{product_id}/link/{integration_id}", response_model=dict)
async def unlink_product_from_store(
    product_id: UUID,
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove the link between an SSP product and an e-commerce product.
    
    This does NOT delete the product from either system - it just
    removes the sync relationship. Price changes will no longer be pushed.
    """
    # Verify product ownership
    stmt = select(Product).where(
        Product.id == product_id,
        Product.user_id == current_user.id
    )
    result = await db.execute(stmt)
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Find and delete the link
    stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.product_id == product_id,
        ProductIntegrationLink.integration_id == integration_id
    )
    result = await db.execute(stmt)
    link = result.scalars().first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    await db.delete(link)
    await db.commit()
    
    return {
        "success": True,
        "message": "Product unlinked from store",
        "product_id": str(product_id),
        "integration_id": str(integration_id)
    }


