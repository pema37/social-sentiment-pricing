# backend/services/integration/models.py

"""
Data models and enums for e-commerce integrations.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# ==================== Enums ====================


class PriceUpdateResult(StrEnum):
    """Result of a price update operation"""

    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    PRODUCT_NOT_FOUND = "product_not_found"
    UNAUTHORIZED = "unauthorized"


class ConnectionStatus(StrEnum):
    """Health check status for platform connection"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"


# ==================== Data Classes ====================


@dataclass
class OAuthResult:
    """Result of OAuth token exchange"""

    success: bool
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scope: str | None = None
    error: str | None = None


@dataclass
class ExternalProductVariant:
    """A product variant from external platform"""

    id: str
    title: str
    price: float | None = None
    sku: str | None = None
    inventory_quantity: int | None = None
    compare_at_price: float | None = None


@dataclass
class ExternalProduct:
    """Normalized product data from any e-commerce platform"""

    id: str
    title: str
    price: float | None = None
    compare_at_price: float | None = None
    sku: str | None = None
    description: str | None = None
    inventory_quantity: int | None = None
    product_type: str | None = None
    vendor: str | None = None
    tags: list[str] | None = None
    images: list[str] | None = None
    variants: list[ExternalProductVariant] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ProductSyncResult:
    """Result of fetching products from platform"""

    success: bool
    products: list[ExternalProduct] | None = None
    has_more: bool = False
    next_cursor: str | None = None
    error: str | None = None
    retries_used: int = 0


@dataclass
class PriceUpdateRequest:
    """Request to update a product's price"""

    external_product_id: str
    external_variant_id: str | None = None
    new_price: float = 0.0
    compare_at_price: float | None = None


@dataclass
class PriceUpdateResponse:
    """Response from price update operation"""

    result: PriceUpdateResult
    external_product_id: str
    old_price: float | None = None
    new_price: float | None = None
    error: str | None = None
    retries_used: int = 0


@dataclass
class WebhookRegistration:
    """Result of webhook registration"""

    success: bool
    webhook_id: str | None = None
    topic: str | None = None
    error: str | None = None
