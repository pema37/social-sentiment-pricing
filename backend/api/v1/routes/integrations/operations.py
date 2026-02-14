# backend/api/v1/routes/integrations/operations.py
"""Price push and health check endpoints."""

import logging
from datetime import datetime, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT
from db.session import get_session
from core.encryption import decrypt_token
from models.user import User
from models.integration import Integration, ProductIntegrationLink, IntegrationStatus, EcommercePlatform
from schemas.integration import (
    PricePushRequest,
    PricePushResponse,
    IntegrationHealthResponse,
)
from services.integration import (
    EcommerceService,
    PriceUpdateRequest,
    PriceUpdateResult,
    ShopifyService,
    WooCommerceService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_ecommerce_service(platform: EcommercePlatform) -> EcommerceService:
    """Factory to get the right service for the platform."""
    if platform == EcommercePlatform.SHOPIFY:
        return ShopifyService()
    elif platform == EcommercePlatform.WOOCOMMERCE:
        return WooCommerceService()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {platform}"
        )


@router.post("/{integration_id}/push-price", response_model=PricePushResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def push_price(
    request: Request,
    integration_id: UUID,
    price_request: PricePushRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Push a price update to the e-commerce platform."""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    db_result = await db.execute(stmt)
    integration = db_result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    if integration.status != IntegrationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration is not active"
        )
    
    stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.id == price_request.product_link_id,
        ProductIntegrationLink.integration_id == integration_id,
    )
    link_result = await db.execute(stmt)
    link = link_result.scalars().first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product link not found"
        )
    
    access_token = decrypt_token(integration.access_token_encrypted)
    service = get_ecommerce_service(integration.platform)
    
    update_request = PriceUpdateRequest(
        external_product_id=link.external_product_id,
        external_variant_id=link.external_variant_id,
        new_price=price_request.new_price,
        compare_at_price=price_request.compare_at_price,
    )
    
    price_response = await service.update_price(
        store_url=integration.store_url,
        access_token=access_token,
        request=update_request,
    )
    
    is_success = False
    if price_response and price_response.result is not None:
        is_success = price_response.result == PriceUpdateResult.SUCCESS
    
    if is_success:
        link.external_price = float(price_request.new_price)
        if price_request.compare_at_price:
            link.external_compare_at_price = float(price_request.compare_at_price)
        link.last_price_push_at = datetime.now(UTC)
        link.updated_at = datetime.now(UTC)
        db.add(link)
        await db.commit()
        
        logger.info(
            f"Price pushed for product link {link.id}: "
            f"${price_response.old_price} -> ${price_request.new_price}"
        )
    else:
        logger.warning(
            f"Price push failed for product link {link.id}: "
            f"{price_response.error if price_response else 'No response'}"
        )
    
    return PricePushResponse(
        success=is_success,
        product_link_id=link.id,
        old_price=price_response.old_price if price_response else None,
        new_price=price_request.new_price,
        error=price_response.error if price_response else "No response from service",
    )


@router.get("/{integration_id}/health", response_model=IntegrationHealthResponse)
async def check_integration_health(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Check if an integration connection is healthy."""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    access_token = decrypt_token(integration.access_token_encrypted)
    service = get_ecommerce_service(integration.platform)
    
    status_result = await service.health_check(
        store_url=integration.store_url,
        access_token=access_token,
    )
    
    return IntegrationHealthResponse(
        integration_id=integration.id,
        platform=integration.platform,
        store_url=integration.store_url,
        status=status_result.value,
        checked_at=datetime.now(UTC),
    )
