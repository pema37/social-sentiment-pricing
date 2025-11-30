# backend/schemas/competitor.py

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, HttpUrl


# ============================================================
# Competitor Schemas
# ============================================================

class CompetitorBase(BaseModel):
    """Base fields for competitor."""
    name: str = Field(..., min_length=1, max_length=255)
    website: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    scraping_config: dict = Field(default_factory=dict)
    is_active: bool = True
    scrape_frequency_minutes: int = Field(default=60, ge=5, le=1440)


class CompetitorCreate(CompetitorBase):
    """Schema for creating a competitor."""
    pass


class CompetitorUpdate(BaseModel):
    """Schema for updating a competitor. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    website: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    scraping_config: Optional[dict] = None
    is_active: Optional[bool] = None
    scrape_frequency_minutes: Optional[int] = Field(None, ge=5, le=1440)


class CompetitorResponse(CompetitorBase):
    """Schema for competitor response."""
    id: uuid.UUID
    user_id: uuid.UUID
    last_scraped_at: Optional[datetime] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CompetitorListResponse(BaseModel):
    """Paginated list of competitors."""
    items: List[CompetitorResponse]
    total: int
    page: int
    size: int


# ============================================================
# Competitor Product Schemas
# ============================================================

class CompetitorProductBase(BaseModel):
    """Base fields for competitor product mapping."""
    competitor_product_name: str = Field(..., min_length=1, max_length=500)
    competitor_product_url: str = Field(..., max_length=1000)
    competitor_sku: Optional[str] = Field(None, max_length=100)
    currency: str = Field(default="USD", max_length=3)
    match_confidence: Decimal = Field(default=Decimal("1.0"), ge=0, le=1)
    notes: Optional[str] = None
    is_active: bool = True


class CompetitorProductCreate(CompetitorProductBase):
    """Schema for creating a competitor product mapping."""
    product_id: uuid.UUID  # Your product
    competitor_id: uuid.UUID  # Which competitor


class CompetitorProductUpdate(BaseModel):
    """Schema for updating a competitor product mapping."""
    competitor_product_name: Optional[str] = Field(None, min_length=1, max_length=500)
    competitor_product_url: Optional[str] = Field(None, max_length=1000)
    competitor_sku: Optional[str] = Field(None, max_length=100)
    currency: Optional[str] = Field(None, max_length=3)
    match_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class CompetitorProductResponse(CompetitorProductBase):
    """Schema for competitor product response."""
    id: uuid.UUID
    product_id: uuid.UUID
    competitor_id: uuid.UUID
    current_price: Optional[Decimal] = None
    last_price_update: Optional[datetime] = None
    price_available: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CompetitorProductWithDetails(CompetitorProductResponse):
    """Extended response with competitor name."""
    competitor_name: str
    your_product_name: str
    your_current_price: Decimal
    price_difference: Optional[Decimal] = None
    price_difference_percent: Optional[Decimal] = None


class CompetitorProductListResponse(BaseModel):
    """Paginated list of competitor products."""
    items: List[CompetitorProductResponse]
    total: int
    page: int
    size: int


# ============================================================
# Competitor Price History Schemas
# ============================================================

class CompetitorPriceHistoryResponse(BaseModel):
    """Schema for price history response."""
    id: uuid.UUID
    competitor_product_id: uuid.UUID
    old_price: Optional[Decimal] = None
    new_price: Decimal
    currency: str
    change_amount: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    change_type: str
    detected_promotion: bool
    promotion_name: Optional[str] = None
    was_available: bool
    is_available: bool
    observed_at: datetime

    class Config:
        from_attributes = True


class CompetitorPriceHistoryListResponse(BaseModel):
    """Paginated list of price history."""
    items: List[CompetitorPriceHistoryResponse]
    total: int


# ============================================================
# Analysis & Comparison Schemas
# ============================================================

class CompetitorPriceComparison(BaseModel):
    """Price comparison between your product and competitors."""
    product_id: uuid.UUID
    product_name: str
    your_price: Decimal
    competitor_prices: List[dict]  # [{competitor_name, price, url, difference, last_updated}]
    lowest_competitor_price: Optional[Decimal] = None
    highest_competitor_price: Optional[Decimal] = None
    average_competitor_price: Optional[Decimal] = None
    your_position: str  # "lowest", "highest", "middle", "no_data"
    recommendation: str


class CompetitorAlert(BaseModel):
    """Alert for significant competitor price changes."""
    alert_type: str  # "price_drop", "price_increase", "new_promotion", "back_in_stock"
    competitor_name: str
    competitor_product_name: str
    product_id: uuid.UUID
    your_product_name: str
    old_price: Optional[Decimal]
    new_price: Decimal
    change_percent: Optional[Decimal]
    your_current_price: Decimal
    suggested_action: str
    observed_at: datetime


class CompetitorTrendAnalysis(BaseModel):
    """Trend analysis for a competitor product."""
    competitor_product_id: uuid.UUID
    competitor_name: str
    product_name: str
    period_days: int
    price_changes_count: int
    average_price: Decimal
    min_price: Decimal
    max_price: Decimal
    current_price: Optional[Decimal]
    trend_direction: str  # "increasing", "decreasing", "stable", "volatile"
    trend_strength: Decimal  # 0-1 confidence
    promotion_frequency: int

