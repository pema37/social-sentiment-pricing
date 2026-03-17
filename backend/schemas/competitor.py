# backend/schemas/competitor.py

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# Competitor Schemas
# ============================================================


class CompetitorBase(BaseModel):
    """Base fields for competitor."""

    name: str = Field(..., min_length=1, max_length=255)
    website: str | None = Field(None, max_length=500)
    description: str | None = None
    scraping_config: dict = Field(default_factory=dict)
    is_active: bool = True
    scrape_frequency_minutes: int = Field(default=60, ge=5, le=1440)


class CompetitorCreate(CompetitorBase):
    """Schema for creating a competitor."""

    pass


class CompetitorUpdate(BaseModel):
    """Schema for updating a competitor. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    website: str | None = Field(None, max_length=500)
    description: str | None = None
    scraping_config: dict | None = None
    is_active: bool | None = None
    scrape_frequency_minutes: int | None = Field(None, ge=5, le=1440)


class CompetitorResponse(CompetitorBase):
    """Schema for competitor response."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    last_scraped_at: datetime | None = None
    consecutive_failures: int = 0
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class CompetitorListResponse(BaseModel):
    """Paginated list of competitors."""

    items: list[CompetitorResponse]
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
    competitor_sku: str | None = Field(None, max_length=100)
    currency: str = Field(default="USD", max_length=3)
    match_confidence: Decimal = Field(default=Decimal("1.0"), ge=0, le=1)
    notes: str | None = None
    is_active: bool = True


class CompetitorProductCreate(CompetitorProductBase):
    """Schema for creating a competitor product mapping."""

    product_id: uuid.UUID  # Your product
    competitor_id: uuid.UUID  # Which competitor
    current_price: Decimal | None = Field(None, ge=0, description="Current competitor price")


class CompetitorProductUpdate(BaseModel):
    """Schema for updating a competitor product mapping."""

    competitor_product_name: str | None = Field(None, min_length=1, max_length=500)
    competitor_product_url: str | None = Field(None, max_length=1000)
    competitor_sku: str | None = Field(None, max_length=100)
    currency: str | None = Field(None, max_length=3)
    match_confidence: Decimal | None = Field(None, ge=0, le=1)
    notes: str | None = None
    is_active: bool | None = None
    current_price: Decimal | None = Field(None, ge=0, description="Current competitor price")


class CompetitorProductResponse(CompetitorProductBase):
    """Schema for competitor product response."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    product_id: uuid.UUID
    competitor_id: uuid.UUID
    current_price: Decimal | None = None
    last_price_update: datetime | None = None
    price_available: bool = True
    created_at: datetime
    updated_at: datetime


class CompetitorProductWithDetails(CompetitorProductResponse):
    """Extended response with competitor name."""

    competitor_name: str
    your_product_name: str
    your_current_price: Decimal
    price_difference: Decimal | None = None
    price_difference_percent: Decimal | None = None


class CompetitorProductListResponse(BaseModel):
    """Paginated list of competitor products."""

    items: list[CompetitorProductResponse]
    total: int
    page: int
    size: int


# ============================================================
# Competitor Price History Schemas
# ============================================================


class CompetitorPriceHistoryResponse(BaseModel):
    """Schema for price history response."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    competitor_product_id: uuid.UUID
    old_price: Decimal | None = None
    new_price: Decimal
    currency: str
    change_amount: Decimal | None = None
    change_percent: Decimal | None = None
    change_type: str
    detected_promotion: bool
    promotion_name: str | None = None
    was_available: bool
    is_available: bool
    observed_at: datetime


class CompetitorPriceHistoryListResponse(BaseModel):
    """Paginated list of price history."""

    items: list[CompetitorPriceHistoryResponse]
    total: int


# ============================================================
# Analysis & Comparison Schemas
# ============================================================


class CompetitorPriceComparison(BaseModel):
    """Price comparison between your product and competitors."""

    product_id: uuid.UUID
    product_name: str
    your_price: Decimal
    competitor_prices: list[dict]  # [{competitor_name, price, url, difference, last_updated}]
    lowest_competitor_price: Decimal | None = None
    highest_competitor_price: Decimal | None = None
    average_competitor_price: Decimal | None = None
    your_position: str  # "lowest", "highest", "middle", "no_data"
    recommendation: str


class CompetitorAlert(BaseModel):
    """Alert for significant competitor price changes."""

    alert_type: str  # "price_drop", "price_increase", "new_promotion", "back_in_stock"
    competitor_name: str
    competitor_product_name: str
    product_id: uuid.UUID
    your_product_name: str
    old_price: Decimal | None
    new_price: Decimal
    change_percent: Decimal | None
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
    current_price: Decimal | None
    trend_direction: str  # "increasing", "decreasing", "stable", "volatile"
    trend_strength: Decimal  # 0-1 confidence
    promotion_frequency: int
