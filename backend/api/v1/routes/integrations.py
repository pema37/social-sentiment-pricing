# backend/api/v1/routes/integrations.py

"""
Integration API Routes

Endpoints for connecting/disconnecting e-commerce platforms,
syncing products, and pushing price updates.
"""

import secrets
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlmodel import Session, select

from backend.core.deps import get_current_user, get_db
from backend.core.encryption import encrypt_token, decrypt_token
from backend.models.user import User
from backend.models.integration import (
    Integration,
    IntegrationSyncLog,
    ProductIntegrationLink,
    EcommercePlatform,
    IntegrationStatus,
)
from backend.models.product import Product
from backend.schemas.integration import (
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
)
from backend.services.integration.base import PriceUpdateRequest, EcommerceService
from backend.services.integration.shopify_service import ShopifyService
from backend.services.integration.woocommerce_service import WooCommerceService


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


# ==================== OAuth Flow ====================

@router.post("/oauth/init", response_model=OAuthInitResponse)
async def init_oauth(
    request: OAuthInitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start OAuth flow for connecting a store.
    Returns authorization URL to redirect user to.
    """
    # Check if integration already exists
    existing = db.exec(
        select(Integration).where(
            Integration.user_id == current_user.id,
            Integration.platform == request.platform,
            Integration.store_url == request.store_url,
        )
    ).first()
    
    if existing and existing.status == IntegrationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This store is already connected"
        )
    
    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    
    # Get service and generate OAuth URL
    service = get_ecommerce_service(request.platform)
    
    # TODO: Get redirect_uri from config
    redirect_uri = "http://localhost:8000/api/v1/integrations/oauth/callback"
    
    auth_url = service.generate_oauth_url(
        store_url=request.store_url,
        state=state,
        redirect_uri=redirect_uri,
    )
    
    # Store pending integration with state
    if existing:
        existing.oauth_state = state
        existing.status = IntegrationStatus.DISCONNECTED
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
    
    db.commit()
    
    return OAuthInitResponse(
        authorization_url=auth_url,
        state=state,
    )


@router.get("/oauth/callback")
async def oauth_callback(
    code: str,
    state: str,
    shop: str = None,  # Shopify includes this
    db: Session = Depends(get_db),
):
    """
    OAuth callback endpoint.
    Shopify redirects here after user approves.
    """
    # Find integration by state
    integration = db.exec(
        select(Integration).where(Integration.oauth_state == state)
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state - OAuth session expired or invalid"
        )
    
    # Get service and exchange code
    service = get_ecommerce_service(integration.platform)
    
    redirect_uri = "http://localhost:8000/api/v1/integrations/oauth/callback"
    
    result = await service.exchange_oauth_code(
        store_url=integration.store_url,
        code=code,
        redirect_uri=redirect_uri,
    )
    
    if not result.success:
        integration.status = IntegrationStatus.ERROR
        integration.error_message = result.error
        integration.oauth_state = None
        db.add(integration)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth failed: {result.error}"
        )
    
    # Store encrypted credentials
    integration.access_token_encrypted = encrypt_token(result.access_token)
    if result.refresh_token:
        integration.refresh_token_encrypted = encrypt_token(result.refresh_token)
    if result.scope:
        integration.scopes = result.scope.split(",")
    
    integration.status = IntegrationStatus.ACTIVE
    integration.oauth_state = None
    integration.error_message = None
    integration.updated_at = datetime.now(timezone.utc)
    
    db.add(integration)
    db.commit()
    
    # TODO: Redirect to frontend success page
    return {"message": "Successfully connected!", "integration_id": str(integration.id)}


# ==================== Integration CRUD ====================

@router.get("", response_model=IntegrationListResponse)
async def list_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all integrations for current user"""
    integrations = db.exec(
        select(Integration).where(Integration.user_id == current_user.id)
    ).all()
    
    return IntegrationListResponse(
        integrations=[IntegrationResponse.model_validate(i) for i in integrations],
        total=len(integrations),
    )


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific integration"""
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update integration settings"""
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
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
    
    integration.updated_at = datetime.now(timezone.utc)
    db.add(integration)
    db.commit()
    db.refresh(integration)
    
    return IntegrationResponse.model_validate(integration)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_integration(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect an integration"""
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Mark as disconnected (soft delete)
    integration.status = IntegrationStatus.DISCONNECTED
    integration.updated_at = datetime.now(timezone.utc)
    db.add(integration)
    db.commit()


# ==================== Sync Operations ====================

@router.post("/{integration_id}/sync", response_model=SyncStatusResponse)
async def trigger_sync(
    integration_id: UUID,
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a product sync from the e-commerce platform"""
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
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
    
    # Update sync status
    integration.sync_status = "syncing"
    db.add(integration)
    db.commit()
    
    # TODO: Add background task for actual sync
    # background_tasks.add_task(run_product_sync, integration_id, request.sync_type)
    
    return SyncStatusResponse(
        integration_id=integration.id,
        sync_status=integration.sync_status,
        last_sync_at=integration.last_sync_at,
        products_synced=integration.products_synced,
    )


@router.get("/{integration_id}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current sync status"""
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
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


@router.get("/{integration_id}/sync/logs", response_model=SyncLogsListResponse)
async def get_sync_logs(
    integration_id: UUID,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get sync history for an integration"""
    # First verify ownership
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    logs = db.exec(
        select(IntegrationSyncLog)
        .where(IntegrationSyncLog.integration_id == integration_id)
        .order_by(IntegrationSyncLog.started_at.desc())
        .limit(limit)
    ).all()
    
    return SyncLogsListResponse(
        logs=[SyncLogResponse.model_validate(log) for log in logs],
        total=len(logs),
    )


# ==================== Product Links ====================

@router.post("/{integration_id}/links", response_model=ProductLinkResponse)
async def create_product_link(
    integration_id: UUID,
    data: ProductLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link an SSP product to an external platform product"""
    # Verify integration ownership
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Verify product ownership
    product = db.exec(
        select(Product).where(
            Product.id == data.product_id,
            Product.user_id == current_user.id,
        )
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check for existing link
    existing = db.exec(
        select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.external_product_id == data.external_product_id,
        )
    ).first()
    
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
    db.commit()
    db.refresh(link)
    
    return ProductLinkResponse.model_validate(link)


@router.get("/{integration_id}/links", response_model=ProductLinkListResponse)
async def list_product_links(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all product links for an integration"""
    # Verify integration ownership
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    links = db.exec(
        select(ProductIntegrationLink)
        .where(ProductIntegrationLink.integration_id == integration_id)
    ).all()
    
    return ProductLinkListResponse(
        links=[ProductLinkResponse.model_validate(link) for link in links],
        total=len(links),
    )


@router.delete("/{integration_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_link(
    integration_id: UUID,
    link_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a product link"""
    # Verify integration ownership
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    link = db.exec(
        select(ProductIntegrationLink).where(
            ProductIntegrationLink.id == link_id,
            ProductIntegrationLink.integration_id == integration_id,
        )
    ).first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product link not found"
        )
    
    db.delete(link)
    db.commit()


# ==================== Price Push ====================

@router.post("/{integration_id}/push-price", response_model=PricePushResponse)
async def push_price(
    integration_id: UUID,
    request: PricePushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Push a price update to the e-commerce platform"""
    # Verify integration
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
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
    link = db.exec(
        select(ProductIntegrationLink).where(
            ProductIntegrationLink.id == request.product_link_id,
            ProductIntegrationLink.integration_id == integration_id,
        )
    ).first()
    
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
    
    result = await service.update_price(
        store_url=integration.store_url,
        access_token=access_token,
        request=update_request,
    )
    
    # Update link with new price info
    if result.result.value == "success":
        link.external_price = float(request.new_price)
        if request.compare_at_price:
            link.external_compare_at_price = float(request.compare_at_price)
        link.last_price_push_at = datetime.now(timezone.utc)
        link.updated_at = datetime.now(timezone.utc)
        db.add(link)
        db.commit()
    
    return PricePushResponse(
        success=result.result.value == "success",
        product_link_id=link.id,
        old_price=result.old_price,
        new_price=request.new_price,
        error=result.error,
    )


# ==================== Health Check ====================

@router.get("/{integration_id}/health", response_model=IntegrationHealthResponse)
async def check_integration_health(
    integration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if an integration connection is healthy"""
    integration = db.exec(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    ).first()
    
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
        checked_at=datetime.now(timezone.utc),
    )

