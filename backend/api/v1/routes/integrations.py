# backend/api/v1/routes/integrations.py

"""
Integration API Routes

Endpoints for connecting/disconnecting e-commerce platforms,
syncing products, and pushing price updates.

Production-ready with:
- Full sync background task integration
- OAuth callback with frontend redirect
- WooCommerce API key connection endpoint
- Configurable URLs from settings
- Automatic webhook registration/unregistration
"""

import logging
import secrets
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from core.config import settings
from core.deps import get_current_user
from db.session import get_session, async_session
from core.encryption import encrypt_token, decrypt_token
from models.user import User
from models.integration import (
    Integration,
    IntegrationSyncLog,
    ProductIntegrationLink,
    EcommercePlatform,
    IntegrationStatus,
)
from models.product import Product
from schemas.integration import (
    OAuthInitRequest,
    OAuthInitResponse,
    OAuthCallbackRequest,
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationListResponse,
    SyncTriggerRequest,
    SyncStatusResponse,
    SyncLogResponse,
    SyncLogsListResponse,
    ProductLinkCreate,
    ProductLinkResponse,
    ProductLinkListResponse,
    PricePushRequest,
    PricePushResponse,
    BulkPricePushRequest,
    BulkPricePushResponse,
    IntegrationHealthResponse,
    WooCommerceConnectRequest,
)
from schemas.common import PaginatedResponse, PaginationParams
from services.integration import (
    EcommerceService,
    PriceUpdateRequest,
    PriceUpdateResult,
    ShopifyService,
    WooCommerceService,
    SyncService,
    WebhookRegistrationService,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ==================== Service Factory ====================

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


# ==================== Background Task Wrapper ====================

async def run_sync_background(
    integration_id: UUID,
    sync_type: str,
    user_id: UUID,
):
    """
    Background task wrapper for running product sync.
    
    Creates its own database session since background tasks
    run outside the request lifecycle.
    """
    async with async_session() as db:
        try:
            sync_service = SyncService(db)
            sync_log = await sync_service.run_sync(
                integration_id=integration_id,
                sync_type=sync_type,
                user_id=user_id,
            )
            logger.info(
                f"Sync completed for integration {integration_id}: "
                f"created={sync_log.products_created}, "
                f"updated={sync_log.products_updated}, "
                f"deleted={sync_log.products_deleted}"
            )
        except Exception as e:
            logger.exception(f"Background sync failed for integration {integration_id}: {e}")


# ==================== OAuth Flow ====================

@router.post("/oauth/init", response_model=OAuthInitResponse)
async def init_oauth(
    request: OAuthInitRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Start OAuth flow for connecting a store.
    Returns authorization URL to redirect user to.
    
    For Shopify: Returns Shopify OAuth URL
    For WooCommerce: Returns WooCommerce admin URL for API key generation
    """
    # Check if integration already exists
    stmt = select(Integration).where(
        Integration.user_id == current_user.id,
        Integration.platform == request.platform,
        Integration.store_url == request.store_url,
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    
    if existing and existing.status == IntegrationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This store is already connected"
        )
    
    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    
    # Get service and generate OAuth URL
    service = get_ecommerce_service(request.platform)
    
    # Use configured redirect URI
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/integrations/oauth/callback"
    
    auth_url = service.generate_oauth_url(
        store_url=request.store_url,
        state=state,
        redirect_uri=redirect_uri,
    )
    
    # Store pending integration with state
    if existing:
        existing.oauth_state = state
        existing.status = IntegrationStatus.DISCONNECTED
        existing.store_url = request.store_url  # Update in case URL changed
        db.add(existing)
    else:
        integration = Integration(
            user_id=current_user.id,
            platform=request.platform,
            store_url=request.store_url,
            status=IntegrationStatus.DISCONNECTED,
            oauth_state=state,
            access_token_encrypted=b"pending",  # Placeholder until OAuth completes
        )
        db.add(integration)
    
    await db.commit()
    
    return OAuthInitResponse(
        authorization_url=auth_url,
        state=state,
    )


@router.get("/oauth/callback")
async def oauth_callback(
    code: str,
    state: str,
    shop: str = None,  # Shopify includes this
    db: AsyncSession = Depends(get_session),
):
    """
    OAuth callback endpoint.
    Shopify redirects here after user approves.
    Redirects to frontend with success/error status.
    """
    # Find integration by state
    stmt = select(Integration).where(Integration.oauth_state == state)
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        # Redirect to frontend with error
        error_url = f"{settings.FRONTEND_URL}/integrations?error=invalid_state&message=OAuth+session+expired+or+invalid"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)
    
    # Get service and exchange code
    service = get_ecommerce_service(integration.platform)
    
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/integrations/oauth/callback"
    
    oauth_result = await service.exchange_oauth_code(
        store_url=integration.store_url,
        code=code,
        redirect_uri=redirect_uri,
    )
    
    if not oauth_result.success:
        integration.status = IntegrationStatus.ERROR
        integration.error_message = oauth_result.error
        integration.oauth_state = None
        db.add(integration)
        await db.commit()
        
        # Redirect to frontend with error
        error_url = (
            f"{settings.FRONTEND_URL}/integrations"
            f"?error=oauth_failed"
            f"&message={oauth_result.error}"
            f"&platform={integration.platform.value}"
        )
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)
    
    # Store encrypted credentials
    integration.access_token_encrypted = encrypt_token(oauth_result.access_token)
    if oauth_result.refresh_token:
        integration.refresh_token_encrypted = encrypt_token(oauth_result.refresh_token)
    if oauth_result.scope:
        integration.scopes = oauth_result.scope.split(",")
    
    integration.status = IntegrationStatus.ACTIVE
    integration.oauth_state = None
    integration.error_message = None
    integration.updated_at = datetime.utcnow()
    
    db.add(integration)
    await db.commit()
    
    logger.info(f"OAuth successful for integration {integration.id} ({integration.platform.value})")
    
    # Register webhooks automatically
    try:
        webhook_service = WebhookRegistrationService(db)
        results = await webhook_service.register_webhooks(integration.id)
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Registered {success_count} webhooks for integration {integration.id}")
    except Exception as e:
        logger.warning(f"Auto webhook registration failed: {e}")
    
    # Redirect to frontend with success
    success_url = (
        f"{settings.FRONTEND_URL}/integrations"
        f"?connected=true"
        f"&integration_id={integration.id}"
        f"&platform={integration.platform.value}"
    )
    return RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)


# ==================== WooCommerce API Key Connection ====================

@router.post("/woocommerce/connect", response_model=IntegrationResponse)
async def connect_woocommerce(
    request: WooCommerceConnectRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Connect a WooCommerce store using API keys.
    
    WooCommerce uses consumer key/secret instead of OAuth.
    Users generate these in WooCommerce Admin > Settings > Advanced > REST API.
    """
    # Check if integration already exists
    stmt = select(Integration).where(
        Integration.user_id == current_user.id,
        Integration.platform == EcommercePlatform.WOOCOMMERCE,
        Integration.store_url == request.store_url,
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    
    if existing and existing.status == IntegrationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This store is already connected"
        )
    
    # Verify credentials work
    service = WooCommerceService()
    credentials = f"{request.consumer_key}:{request.consumer_secret}"
    
    is_valid = await service.verify_credentials(
        store_url=request.store_url,
        access_token=credentials,
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API credentials. Please verify your consumer key and secret."
        )
    
    # Create or update integration
    if existing:
        existing.access_token_encrypted = encrypt_token(credentials)
        existing.status = IntegrationStatus.ACTIVE
        existing.error_message = None
        existing.store_name = request.store_name
        existing.updated_at = datetime.utcnow()
        db.add(existing)
        integration = existing
    else:
        integration = Integration(
            user_id=current_user.id,
            platform=EcommercePlatform.WOOCOMMERCE,
            store_url=request.store_url,
            store_name=request.store_name,
            status=IntegrationStatus.ACTIVE,
            access_token_encrypted=encrypt_token(credentials),
            scopes=["read_products", "write_products"],  # WooCommerce default
        )
        db.add(integration)
    
    await db.commit()
    await db.refresh(integration)
    
    logger.info(f"WooCommerce connected for user {current_user.id}: {request.store_url}")
    
    # Register webhooks automatically
    try:
        webhook_service = WebhookRegistrationService(db)
        results = await webhook_service.register_webhooks(integration.id)
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Registered {success_count} webhooks for integration {integration.id}")
    except Exception as e:
        logger.warning(f"Auto webhook registration failed: {e}")
    
    return IntegrationResponse.model_validate(integration)


# ==================== Integration CRUD ====================

@router.get("", response_model=IntegrationListResponse)
async def list_integrations(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all integrations for current user."""
    stmt = select(Integration).where(
        Integration.user_id == current_user.id
    ).order_by(Integration.created_at.desc())
    
    result = await db.execute(stmt)
    integrations = list(result.scalars().all())
    
    return IntegrationListResponse(
        integrations=[IntegrationResponse.model_validate(i) for i in integrations],
        total=len(integrations),
    )


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific integration."""
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
    
    return IntegrationResponse.model_validate(integration)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: UUID,
    data: IntegrationUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update integration settings."""
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
    
    # Update fields
    if data.store_name is not None:
        integration.store_name = data.store_name
    if data.status is not None:
        integration.status = data.status
    if data.settings is not None:
        integration.settings = data.settings
    
    integration.updated_at = datetime.utcnow()
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    
    return IntegrationResponse.model_validate(integration)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Disconnect an integration (soft delete with webhook cleanup)."""
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
    
    # Unregister webhooks first (best effort)
    if integration.status == IntegrationStatus.ACTIVE:
        try:
            webhook_service = WebhookRegistrationService(db)
            await webhook_service.unregister_webhooks(integration.id)
            logger.info(f"Webhooks unregistered for integration {integration_id}")
        except Exception as e:
            logger.warning(f"Failed to unregister webhooks: {e}")
    
    # Mark as disconnected (soft delete)
    integration.status = IntegrationStatus.DISCONNECTED
    integration.updated_at = datetime.utcnow()
    db.add(integration)
    await db.commit()
    
    logger.info(f"Integration {integration_id} disconnected by user {current_user.id}")


# ==================== Sync Operations ====================

@router.post("/{integration_id}/sync", response_model=SyncStatusResponse)
async def trigger_sync(
    integration_id: UUID,
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger a product sync from the e-commerce platform.
    
    The sync runs as a background task. Use GET /sync/status to check progress.
    """
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
    
    if integration.status != IntegrationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration is not active"
        )
    
    if integration.sync_status == "syncing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sync already in progress"
        )
    
    # Update sync status immediately
    integration.sync_status = "syncing"
    db.add(integration)
    await db.commit()
    
    # Add background task for actual sync
    background_tasks.add_task(
        run_sync_background,
        integration_id=integration_id,
        sync_type=request.sync_type,
        user_id=current_user.id,
    )
    
    logger.info(f"Sync triggered for integration {integration_id} by user {current_user.id}")
    
    return SyncStatusResponse(
        integration_id=integration.id,
        sync_status=integration.sync_status,
        last_sync_at=integration.last_sync_at,
        products_synced=integration.products_synced,
    )


@router.get("/{integration_id}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get current sync status."""
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
    
    return SyncStatusResponse(
        integration_id=integration.id,
        sync_status=integration.sync_status,
        last_sync_at=integration.last_sync_at,
        products_synced=integration.products_synced,
    )


@router.get("/{integration_id}/sync/logs", response_model=PaginatedResponse[SyncLogResponse])
async def get_sync_logs(
    integration_id: UUID,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get sync history for an integration."""
    # First verify ownership
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
    
    # Build base query
    query = select(IntegrationSyncLog).where(
        IntegrationSyncLog.integration_id == integration_id
    )
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    
    # Paginate
    query = query.order_by(IntegrationSyncLog.started_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    logs = list(result.scalars().all())
    
    items = [SyncLogResponse.model_validate(log) for log in logs]
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


# ==================== Product Links ====================

@router.post("/{integration_id}/links", response_model=ProductLinkResponse)
async def create_product_link(
    integration_id: UUID,
    data: ProductLinkCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Link an SSP product to an external platform product."""
    # Verify integration ownership
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
    
    # Verify product ownership
    stmt = select(Product).where(
        Product.id == data.product_id,
        Product.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check for existing link
    stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.integration_id == integration_id,
        ProductIntegrationLink.external_product_id == data.external_product_id,
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This external product is already linked"
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
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all product links for an integration."""
    # Verify integration ownership
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
    
    stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.integration_id == integration_id
    )
    result = await db.execute(stmt)
    links = list(result.scalars().all())
    
    return ProductLinkListResponse(
        links=[ProductLinkResponse.model_validate(link) for link in links],
        total=len(links),
    )


@router.delete("/{integration_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_link(
    integration_id: UUID,
    link_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Remove a product link."""
    # Verify integration ownership
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
    
    stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.id == link_id,
        ProductIntegrationLink.integration_id == integration_id,
    )
    result = await db.execute(stmt)
    link = result.scalars().first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product link not found"
        )
    
    await db.delete(link)
    await db.commit()


# ==================== Price Push ====================

@router.post("/{integration_id}/push-price", response_model=PricePushResponse)
async def push_price(
    integration_id: UUID,
    request: PricePushRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Push a price update to the e-commerce platform."""
    # Verify integration
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
    
    # Get product link
    stmt = select(ProductIntegrationLink).where(
        ProductIntegrationLink.id == request.product_link_id,
        ProductIntegrationLink.integration_id == integration_id,
    )
    link_result = await db.execute(stmt)
    link = link_result.scalars().first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product link not found"
        )
    
    # Decrypt token and call service
    access_token = decrypt_token(integration.access_token_encrypted)
    service = get_ecommerce_service(integration.platform)
    
    update_request = PriceUpdateRequest(
        external_product_id=link.external_product_id,
        external_variant_id=link.external_variant_id,
        new_price=request.new_price,
        compare_at_price=request.compare_at_price,
    )
    
    price_response = await service.update_price(
        store_url=integration.store_url,
        access_token=access_token,
        request=update_request,
    )
    
    # Check result with defensive coding
    is_success = False
    if price_response and price_response.result is not None:
        is_success = price_response.result == PriceUpdateResult.SUCCESS
    
    # Update link with new price info on success
    if is_success:
        link.external_price = float(request.new_price)
        if request.compare_at_price:
            link.external_compare_at_price = float(request.compare_at_price)
        link.last_price_push_at = datetime.utcnow()
        link.updated_at = datetime.utcnow()
        db.add(link)
        await db.commit()
        
        logger.info(
            f"Price pushed for product link {link.id}: "
            f"${price_response.old_price} -> ${request.new_price}"
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
        new_price=request.new_price,
        error=price_response.error if price_response else "No response from service",
    )


# ==================== Health Check ====================

@router.get("/{integration_id}/health", response_model=IntegrationHealthResponse)
async def check_integration_health(
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
    
    # Decrypt token and check health
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
        checked_at=datetime.utcnow(),
    )
