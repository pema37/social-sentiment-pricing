# backend/schemas/product.py
"""
Product schemas for API request/response validation.

FIX (2026-02-21): Added PlatformLink and platforms_linked to ProductRead
to support multi-platform badges in the product list UI. See BUG-005.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# ============== Request Schemas ==============

class ProductCreate(BaseModel):
    name: str = Field(..., max_length=255)
    sku: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    base_price: Decimal = Field(..., gt=0)
    category: Optional[str] = Field(default=None, max_length=100) 
    image_url: Optional[str] = None                                
    is_active: bool = True                                         
    cost: Optional[Decimal] = Field(default=None, ge=0, description="Cost to acquire/produce")  
    min_price: Optional[Decimal] = Field(default=None, gt=0)
    max_price: Optional[Decimal] = Field(default=None, gt=0)
    sentiment_multiplier: Decimal = Field(default=Decimal("0.1"), ge=0, le=1)
    auto_pricing_enabled: bool = False
    keywords: List[str] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=100)  
    image_url: Optional[str] = None                                 
    is_active: Optional[bool] = None 
    sku: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    base_price: Optional[Decimal] = Field(default=None, gt=0)
    current_price: Optional[Decimal] = Field(default=None, gt=0)
    cost: Optional[Decimal] = Field(default=None, ge=0) 
    min_price: Optional[Decimal] = Field(default=None, gt=0)
    max_price: Optional[Decimal] = Field(default=None, gt=0)
    sentiment_multiplier: Optional[Decimal] = Field(default=None, ge=0, le=1)
    auto_pricing_enabled: Optional[bool] = None
    keywords: Optional[List[str]] = None


# ============== Response Schemas ==============

class PlatformLink(BaseModel):
    """Platform connection info for a product."""
    platform: str              # "shopify" or "woocommerce"
    store_url: Optional[str] = None
    external_price: Optional[float] = None
    sync_enabled: bool = False


class ProductRead(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    sku: Optional[str]
    description: Optional[str]
    category: Optional[str]  
    image_url: Optional[str]  
    is_active: bool          
    base_price: Decimal
    current_price: Decimal
    cost: Optional[Decimal]
    min_price: Optional[Decimal]
    max_price: Optional[Decimal]
    sentiment_multiplier: Decimal
    auto_pricing_enabled: bool
    keywords: List[str]
    created_at: datetime
    updated_at: datetime
    # FIX BUG-005: Platform connection info
    platforms_linked: List[PlatformLink] = []

    class Config:
        from_attributes = True


# ============== Price Suggestion Schema ==============

class PriceSuggestion(BaseModel):
    product_id: UUID
    current_price: Decimal
    suggested_price: Decimal
    change_percent: Decimal
    reasoning: str
    confidence: Decimal = Field(ge=0, le=1)
    factors: dict



    