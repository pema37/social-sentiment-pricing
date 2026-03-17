# backend/schemas/product.py
"""
Product schemas for API request/response validation.

FIX (2026-02-21): Added PlatformLink and platforms_linked to ProductRead
to support multi-platform badges in the product list UI. See BUG-005.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ============== Request Schemas ==============


class ProductCreate(BaseModel):
    name: str = Field(..., max_length=255)
    sku: str | None = Field(default=None, max_length=100)
    description: str | None = None
    base_price: Decimal = Field(..., gt=0)
    category: str | None = Field(default=None, max_length=100)
    image_url: str | None = None
    is_active: bool = True
    cost: Decimal | None = Field(default=None, ge=0, description="Cost to acquire/produce")
    min_price: Decimal | None = Field(default=None, gt=0)
    max_price: Decimal | None = Field(default=None, gt=0)
    sentiment_multiplier: Decimal = Field(default=Decimal("0.1"), ge=0, le=1)
    auto_pricing_enabled: bool = False
    keywords: list[str] = []


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    image_url: str | None = None
    is_active: bool | None = None
    sku: str | None = Field(default=None, max_length=100)
    description: str | None = None
    base_price: Decimal | None = Field(default=None, gt=0)
    current_price: Decimal | None = Field(default=None, gt=0)
    cost: Decimal | None = Field(default=None, ge=0)
    min_price: Decimal | None = Field(default=None, gt=0)
    max_price: Decimal | None = Field(default=None, gt=0)
    sentiment_multiplier: Decimal | None = Field(default=None, ge=0, le=1)
    auto_pricing_enabled: bool | None = None
    keywords: list[str] | None = None


# ============== Response Schemas ==============


class PlatformLink(BaseModel):
    """Platform connection info for a product."""

    platform: str  # "shopify" or "woocommerce"
    store_url: str | None = None
    external_price: float | None = None
    sync_enabled: bool = False


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    name: str
    sku: str | None
    description: str | None
    category: str | None
    image_url: str | None
    is_active: bool
    base_price: Decimal
    current_price: Decimal
    cost: Decimal | None
    min_price: Decimal | None
    max_price: Decimal | None
    sentiment_multiplier: Decimal
    auto_pricing_enabled: bool
    keywords: list[str]
    created_at: datetime
    updated_at: datetime
    # FIX BUG-005: Platform connection info
    platforms_linked: list[PlatformLink] = []


# ============== Price Suggestion Schema ==============


class PriceSuggestion(BaseModel):
    product_id: UUID
    current_price: Decimal
    suggested_price: Decimal
    change_percent: Decimal
    reasoning: str
    confidence: Decimal = Field(ge=0, le=1)
    factors: dict
