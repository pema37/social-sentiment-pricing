# backend/schemas/integration.py

"""
Integration Schemas

Request/Response DTOs for e-commerce integration endpoints.

FIX (2026-01-24): Added proper Dict[str, Any] type annotations to fix Pylance warnings.
FIX (2026-01-27): Added consumer_key/consumer_secret to IntegrationUpdate for credential updates.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ==================== Enums ====================

class EcommercePlatform(str, Enum):
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    ERROR = "error"
    PAUSED = "paused"
    DISCONNECTED = "disconnected"


# ==================== OAuth Schemas ====================

class OAuthInitRequest(BaseModel):
    """Request to start OAuth flow"""
    platform: EcommercePlatform
    store_url: str = Field(..., min_length=3, max_length=255)
    
    @field_validator("store_url")
    @classmethod
    def validate_store_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        # Preserve the protocol, just lowercase the domain
        if v.startswith("http://"):
            return "http://" + v[7:].lower()
        elif v.startswith("https://"):
            return "https://" + v[8:].lower()
        # No protocol provided - just lowercase
        return v.lower()


class OAuthInitResponse(BaseModel):
    """Response with OAuth authorization URL"""
    authorization_url: str
    state: str  # For CSRF verification on callback


class OAuthCallbackRequest(BaseModel):
    """OAuth callback data"""
    code: str
    state: str
    shop: Optional[str] = None  # Shopify includes this


class WooCommerceConnectRequest(BaseModel):
    """Connect WooCommerce store with API keys"""
    store_url: str = Field(..., min_length=3, max_length=255)
    store_name: Optional[str] = Field(None, max_length=255)
    consumer_key: str = Field(..., min_length=10)
    consumer_secret: str = Field(..., min_length=10)
    
    @field_validator("store_url")
    @classmethod
    def validate_store_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        # Preserve the protocol, just lowercase the domain
        if v.startswith("http://"):
            return "http://" + v[7:].lower()
        elif v.startswith("https://"):
            return "https://" + v[8:].lower()
        # No protocol provided - just lowercase
        return v.lower()
    
    @field_validator("consumer_key")
    @classmethod
    def validate_consumer_key(cls, v: str) -> str:
        if not v.startswith("ck_"):
            raise ValueError("Consumer key must start with 'ck_'")
        return v
    
    @field_validator("consumer_secret")
    @classmethod
    def validate_consumer_secret(cls, v: str) -> str:
        if not v.startswith("cs_"):
            raise ValueError("Consumer secret must start with 'cs_'")
        return v
    

# ==================== Integration CRUD Schemas ====================

class IntegrationCreate(BaseModel):
    """Manual integration creation (for WooCommerce API keys)"""
    platform: EcommercePlatform
    store_url: str = Field(..., min_length=3, max_length=255)
    store_name: Optional[str] = Field(None, max_length=255)
    # For WooCommerce manual setup
    consumer_key: Optional[str] = None
    consumer_secret: Optional[str] = None


class IntegrationUpdate(BaseModel):
    """
    Update integration settings.
    
    FIX (2026-01-27): Added consumer_key and consumer_secret fields to allow
    updating WooCommerce credentials without deleting/reconnecting the integration.
    """
    store_name: Optional[str] = Field(None, max_length=255)
    status: Optional[IntegrationStatus] = None
    settings: Optional[Dict[str, Any]] = None
    # NEW (2026-01-27): Allow credential updates for WooCommerce reconnection
    consumer_key: Optional[str] = Field(None, min_length=10)
    consumer_secret: Optional[str] = Field(None, min_length=10)
    
    @field_validator("consumer_key")
    @classmethod
    def validate_consumer_key(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith("ck_"):
            raise ValueError("Consumer key must start with 'ck_'")
        return v
    
    @field_validator("consumer_secret")
    @classmethod
    def validate_consumer_secret(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith("cs_"):
            raise ValueError("Consumer secret must start with 'cs_'")
        return v


class IntegrationResponse(BaseModel):
    """Integration response (public fields only - no secrets)"""
    id: UUID
    platform: EcommercePlatform
    store_url: str
    store_name: Optional[str]
    status: IntegrationStatus
    error_message: Optional[str]
    scopes: List[str]
    last_sync_at: Optional[datetime]
    sync_status: str
    products_synced: int
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class IntegrationListResponse(BaseModel):
    """List of integrations"""
    integrations: List[IntegrationResponse]
    total: int


# ==================== Sync Schemas ====================

class SyncTriggerRequest(BaseModel):
    """Request to trigger a product sync"""
    sync_type: str = Field(default="full", pattern="^(full|incremental)$")


class SyncStatusResponse(BaseModel):
    """Current sync status"""
    integration_id: UUID
    sync_status: str  # idle, syncing, error
    last_sync_at: Optional[datetime]
    products_synced: int
    current_progress: Optional[int] = None  # For ongoing syncs


class SyncLogResponse(BaseModel):
    """Sync log entry"""
    id: UUID
    sync_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    success: bool
    products_created: int
    products_updated: int
    products_deleted: int
    error_details: Optional[str]
    
    class Config:
        from_attributes = True


class SyncLogsListResponse(BaseModel):
    """List of sync logs"""
    logs: List[SyncLogResponse]
    total: int


# ==================== Product Link Schemas ====================

class ProductLinkCreate(BaseModel):
    """Link an SSP product to an external platform product"""
    product_id: UUID
    external_product_id: str = Field(..., max_length=100)
    external_variant_id: Optional[str] = Field(None, max_length=100)


class ProductLinkResponse(BaseModel):
    """Product link response"""
    id: UUID
    product_id: UUID
    integration_id: UUID
    external_product_id: str
    external_variant_id: Optional[str]
    external_price: Optional[float]
    external_compare_at_price: Optional[float]
    last_price_push_at: Optional[datetime]
    last_price_pull_at: Optional[datetime]
    sync_enabled: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProductLinkListResponse(BaseModel):
    """List of product links"""
    links: List[ProductLinkResponse]
    total: int


# ==================== Price Push Schemas ====================

class PricePushRequest(BaseModel):
    """Request to push a price update to the platform"""
    product_link_id: UUID
    new_price: Decimal = Field(..., gt=0, decimal_places=2)
    compare_at_price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)


class PricePushResponse(BaseModel):
    """Result of price push operation"""
    success: bool
    product_link_id: UUID
    old_price: Optional[Decimal]
    new_price: Decimal
    error: Optional[str] = None


class BulkPricePushRequest(BaseModel):
    """Push multiple price updates"""
    updates: List[PricePushRequest] = Field(..., min_length=1, max_length=100)


class BulkPricePushResponse(BaseModel):
    """Results of bulk price push"""
    results: List[PricePushResponse]
    success_count: int
    failure_count: int


# ==================== Webhook Schemas ====================

class WebhookPayload(BaseModel):
    """Generic webhook payload wrapper"""
    topic: str
    shop: str
    payload: Dict[str, Any]


# ==================== Health Check ====================

class IntegrationHealthResponse(BaseModel):
    """Health check response for an integration"""
    integration_id: UUID
    platform: EcommercePlatform
    store_url: str
    status: str  # healthy, unhealthy, rate_limited, unauthorized
    checked_at: datetime



    