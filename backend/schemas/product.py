# backend/schemas/product.py

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field


# ============== Request Schemas ==============

class ProductCreate(BaseModel):
    name: str = Field(..., max_length=255)
    sku: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    base_price: Decimal = Field(..., gt=0)
    min_price: Optional[Decimal] = Field(default=None, gt=0)
    max_price: Optional[Decimal] = Field(default=None, gt=0)
    sentiment_multiplier: Decimal = Field(default=0.1, ge=0, le=1)
    auto_pricing_enabled: bool = False
    keywords: List[str] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    sku: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    base_price: Optional[Decimal] = Field(default=None, gt=0)
    current_price: Optional[Decimal] = Field(default=None, gt=0)
    min_price: Optional[Decimal] = Field(default=None, gt=0)
    max_price: Optional[Decimal] = Field(default=None, gt=0)
    sentiment_multiplier: Optional[Decimal] = Field(default=None, ge=0, le=1)
    auto_pricing_enabled: Optional[bool] = None
    keywords: Optional[List[str]] = None


# ============== Response Schemas ==============

class ProductRead(BaseModel):
    id: str
    user_id: str
    name: str
    sku: Optional[str]
    description: Optional[str]
    base_price: Decimal
    current_price: Decimal
    min_price: Optional[Decimal]
    max_price: Optional[Decimal]
    sentiment_multiplier: Decimal
    auto_pricing_enabled: bool
    keywords: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Price Suggestion Schema ==============

class PriceSuggestion(BaseModel):
    product_id: str
    current_price: Decimal
    suggested_price: Decimal
    change_percent: Decimal
    reasoning: str
    confidence: Decimal = Field(ge=0, le=1)
    factors: dict

