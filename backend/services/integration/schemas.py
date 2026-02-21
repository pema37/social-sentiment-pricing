# backend/services/integration/models.py

"""
Data models and enums for e-commerce integrations.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List


# ==================== Enums ====================

class PriceUpdateResult(str, Enum):
    """Result of a price update operation"""
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    PRODUCT_NOT_FOUND = "product_not_found"
    UNAUTHORIZED = "unauthorized"


class ConnectionStatus(str, Enum):
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
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ExternalProductVariant:
    """A product variant from external platform"""
    id: str
    title: str
    price: Optional[float] = None
    sku: Optional[str] = None
    inventory_quantity: Optional[int] = None
    compare_at_price: Optional[float] = None


@dataclass
class ExternalProduct:
    """Normalized product data from any e-commerce platform"""
    id: str
    title: str
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    inventory_quantity: Optional[int] = None
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None
    variants: Optional[List[ExternalProductVariant]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ProductSyncResult:
    """Result of fetching products from platform"""
    success: bool
    products: Optional[List[ExternalProduct]] = None
    has_more: bool = False
    next_cursor: Optional[str] = None
    error: Optional[str] = None
    retries_used: int = 0


@dataclass
class PriceUpdateRequest:
    """Request to update a product's price"""
    external_product_id: str
    external_variant_id: Optional[str] = None
    new_price: float = 0.0
    compare_at_price: Optional[float] = None


@dataclass
class PriceUpdateResponse:
    """Response from price update operation"""
    result: PriceUpdateResult
    external_product_id: str
    old_price: Optional[float] = None
    new_price: Optional[float] = None
    error: Optional[str] = None
    retries_used: int = 0


@dataclass
class WebhookRegistration:
    """Result of webhook registration"""
    success: bool
    webhook_id: Optional[str] = None
    topic: Optional[str] = None
    error: Optional[str] = None
    