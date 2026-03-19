# backend/schemas/integration.py

"""
Integration Schemas

Request/Response DTOs for e-commerce integration endpoints.

FIX (2026-01-24): Added proper Dict[str, Any] type annotations to fix Pylance warnings.
FIX (2026-01-27): Added consumer_key/consumer_secret to IntegrationUpdate for credential updates.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ==================== Enums ====================


class EcommercePlatform(StrEnum):
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


class IntegrationStatus(StrEnum):
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
    shop: str | None = None  # Shopify includes this


class WooCommerceConnectRequest(BaseModel):
    """Connect WooCommerce store with API keys"""

    store_url: str = Field(..., min_length=3, max_length=255)
    store_name: str | None = Field(None, max_length=255)
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
    store_name: str | None = Field(None, max_length=255)
    # For WooCommerce manual setup
    consumer_key: str | None = None
    consumer_secret: str | None = None


class IntegrationUpdate(BaseModel):
    """
    Update integration settings.

    FIX (2026-01-27): Added consumer_key and consumer_secret fields to allow
    updating WooCommerce credentials without deleting/reconnecting the integration.
    """

    store_name: str | None = Field(None, max_length=255)
    status: IntegrationStatus | None = None
    settings: dict[str, Any] | None = None
    # NEW (2026-01-27): Allow credential updates for WooCommerce reconnection
    consumer_key: str | None = Field(None, min_length=10)
    consumer_secret: str | None = Field(None, min_length=10)

    @field_validator("consumer_key")
    @classmethod
    def validate_consumer_key(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("ck_"):
            raise ValueError("Consumer key must start with 'ck_'")
        return v

    @field_validator("consumer_secret")
    @classmethod
    def validate_consumer_secret(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("cs_"):
            raise ValueError("Consumer secret must start with 'cs_'")
        return v


class IntegrationResponse(BaseModel):
    """Integration response (public fields only - no secrets)"""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    platform: EcommercePlatform
    store_url: str
    store_name: str | None
    status: IntegrationStatus
    error_message: str | None
    scopes: list[str]
    last_sync_at: datetime | None
    sync_status: str
    products_synced: int
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class IntegrationListResponse(BaseModel):
    """List of integrations"""

    integrations: list[IntegrationResponse]
    total: int


# ==================== Sync Schemas ====================


class SyncTriggerRequest(BaseModel):
    """Request to trigger a product sync"""

    sync_type: str = Field(default="full", pattern="^(full|incremental)$")


class SyncStatusResponse(BaseModel):
    """Current sync status"""

    integration_id: UUID
    sync_status: str  # idle, syncing, error
    last_sync_at: datetime | None
    products_synced: int
    current_progress: int | None = None  # For ongoing syncs


class SyncLogResponse(BaseModel):
    """Sync log entry"""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sync_type: str
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    success: bool
    products_created: int
    products_updated: int
    products_deleted: int
    error_details: str | None


class SyncLogsListResponse(BaseModel):
    """List of sync logs"""

    logs: list[SyncLogResponse]
    total: int


# ==================== Product Link Schemas ====================


class ProductLinkCreate(BaseModel):
    """Link an SSP product to an external platform product"""

    product_id: UUID
    external_product_id: str = Field(..., max_length=100)
    external_variant_id: str | None = Field(None, max_length=100)


class ProductLinkResponse(BaseModel):
    """Product link response"""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    integration_id: UUID
    external_product_id: str
    external_variant_id: str | None
    external_price: float | None
    external_compare_at_price: float | None
    last_price_push_at: datetime | None
    last_price_pull_at: datetime | None
    sync_enabled: bool
    created_at: datetime


class ProductLinkListResponse(BaseModel):
    """List of product links"""

    links: list[ProductLinkResponse]
    total: int


# ==================== Price Push Schemas ====================


class PricePushRequest(BaseModel):
    """Request to push a price update to the platform"""

    product_link_id: UUID
    new_price: Decimal = Field(..., gt=0, decimal_places=2)
    compare_at_price: Decimal | None = Field(None, gt=0, decimal_places=2)


class PricePushResponse(BaseModel):
    """Result of price push operation"""

    success: bool
    product_link_id: UUID
    old_price: Decimal | None
    new_price: Decimal
    error: str | None = None


class BulkPricePushRequest(BaseModel):
    """Push multiple price updates"""

    updates: list[PricePushRequest] = Field(..., min_length=1, max_length=100)


class BulkPricePushResponse(BaseModel):
    """Results of bulk price push"""

    results: list[PricePushResponse]
    success_count: int
    failure_count: int


# ==================== Webhook Schemas ====================


class WebhookPayload(BaseModel):
    """Generic webhook payload wrapper"""

    topic: str
    shop: str
    payload: dict[str, Any]


# ==================== Health Check ====================


class IntegrationHealthResponse(BaseModel):
    """Health check response for an integration"""

    integration_id: UUID
    platform: EcommercePlatform
    store_url: str
    status: str  # healthy, unhealthy, rate_limited, unauthorized
    checked_at: datetime
