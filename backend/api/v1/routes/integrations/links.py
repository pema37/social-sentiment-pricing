# backend/api/v1/routes/integrations/links.py
"""Product link endpoints.

PATCHED (2026-02-21):
- create_product_link: Variant-aware duplicate check — no longer rejects
  variant B's link because variant A already exists for the same product
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT
from db.session import get_session
from models.user import User
from models.product import Product
from models.integration import Integration, ProductIntegrationLink
from schemas.integration import (
    ProductLinkCreate,
    ProductLinkResponse,
    ProductLinkListResponse,
)

router = APIRouter()


@router.post("/{integration_id}/links", response_model=ProductLinkResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_product_link(
    request: Request,
    integration_id: UUID,
    data: ProductLinkCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Link an SSP product to an external platform product/variant."""
    # Validate integration belongs to user
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    # Validate product belongs to user
    stmt = select(Product).where(
        Product.id == data.product_id,
        Product.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    
    # FIX: Variant-aware duplicate check.
    # Old code only checked external_product_id, so creating variant B's
    # link was rejected because variant A's link already existed.
    stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.integration_id == integration_id,
        ProductIntegrationLink.external_product_id == data.external_product_id,
    )
    if data.external_variant_id:
        stmt = stmt.where(
            ProductIntegrationLink.external_variant_id == data.external_variant_id
        )
    else:
        stmt = stmt.where(
            ProductIntegrationLink.external_variant_id.is_(None)
        )
    
    result = await db.execute(stmt)
    existing = result.scalars().first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This external product variant is already linked",
        )
    
    link = ProductIntegrationLink(
        product_id=data.product_id,
        integration_id=integration_id,
        external_product_id=data.external_product_id,
        external_variant_id=data.external_variant_id,
    )
    
    db.add(link)
    await db.commit()
    await db.refresh(link)
    
    return ProductLinkResponse.model_validate(link)


@router.get("/{integration_id}/links", response_model=ProductLinkListResponse)
async def list_product_links(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all product links for an integration."""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.integration_id == integration_id,
    )
    result = await db.execute(stmt)
    links = list(result.scalars().all())
    
    return ProductLinkListResponse(
        links=[ProductLinkResponse.model_validate(link) for link in links],
        total=len(links),
    )


@router.delete("/{integration_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_product_link(
    request: Request,
    integration_id: UUID,
    link_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Remove a product link."""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.id == link_id,
        ProductIntegrationLink.integration_id == integration_id,
    )
    result = await db.execute(stmt)
    link = result.scalars().first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product link not found",
        )
    
    await db.delete(link)
    await db.commit()


    