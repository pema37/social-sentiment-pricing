"""
Retrospective Loss Audit Schemas

The "Free Pricing Audit" that shows prospects how much money they
lost (or left on the table) over a configurable lookback window.

This is the sales weapon: instead of "you're 18% above competitors
right now", it becomes "over the last 90 days, you were overpriced
on your top 15 SKUs for an average of 47 days, costing you an
estimated $12,400 in lost margin."
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# REQUEST SCHEMAS
# ═══════════════════════════════════════════════════════════════

class AuditRequest(BaseModel):
    """Request to generate a retrospective loss audit."""
    lookback_days: int = Field(default=90, ge=7, le=365, description="Days to analyze")
    product_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        description="Specific products to audit. None = all products with competitor data."
    )
    estimated_daily_units: Optional[int] = Field(
        default=None, ge=1,
        description="Override daily unit estimate. If None, derived from order data or defaults to 5."
    )
    include_sentiment: bool = Field(
        default=True,
        description="Factor sentiment into optimal price calculation"
    )


# ═══════════════════════════════════════════════════════════════
# PER-SKU DETAIL SCHEMAS
# ═══════════════════════════════════════════════════════════════

class PricingGapDay(BaseModel):
    """A single day where a pricing gap existed."""
    date: datetime
    your_price: Decimal
    competitor_avg_price: Decimal
    optimal_price: Decimal
    gap_amount: Decimal = Field(description="your_price - optimal_price (positive = overpriced)")
    gap_percent: Decimal
    gap_type: str = Field(description="'overpriced' | 'underpriced' | 'aligned'")


class SKUAuditResult(BaseModel):
    """Retrospective audit for a single product/SKU."""
    product_id: uuid.UUID
    product_name: str
    sku: Optional[str] = None
    category: Optional[str] = None

    # Current snapshot
    current_price: Decimal
    current_competitor_avg: Optional[Decimal] = None
    current_gap_percent: Optional[Decimal] = None

    # Competitor coverage
    competitor_count: int
    competitor_names: List[str]

    # Overpriced analysis
    days_overpriced: int = Field(description="Days where your price > optimal by >2%")
    avg_overpriced_gap_percent: Optional[Decimal] = None
    estimated_lost_revenue: Decimal = Field(
        default=Decimal("0"),
        description="Revenue lost from being overpriced (lower sales volume)"
    )

    # Underpriced analysis
    days_underpriced: int = Field(description="Days where your price < optimal by >2%")
    avg_underpriced_gap_percent: Optional[Decimal] = None
    estimated_missed_margin: Decimal = Field(
        default=Decimal("0"),
        description="Margin left on the table from underpricing"
    )

    # Aligned days
    days_aligned: int = Field(description="Days within ±2% of optimal")

    # Combined impact
    total_estimated_impact: Decimal = Field(
        default=Decimal("0"),
        description="lost_revenue + missed_margin"
    )

    # Daily breakdown (for charts)
    daily_gaps: List[PricingGapDay] = Field(
        default_factory=list,
        description="Day-by-day gap timeline for charting"
    )


# ═══════════════════════════════════════════════════════════════
# AGGREGATE AUDIT RESPONSE
# ═══════════════════════════════════════════════════════════════

class AuditSummary(BaseModel):
    """Top-level headline numbers for the audit."""
    total_products_analyzed: int
    lookback_days: int
    analysis_period_start: datetime
    analysis_period_end: datetime

    # The headline number: "You left $X on the table"
    total_estimated_impact: Decimal
    total_lost_revenue: Decimal
    total_missed_margin: Decimal

    # Averages across all SKUs
    avg_days_overpriced: Decimal
    avg_days_underpriced: Decimal
    avg_overpriced_gap_percent: Optional[Decimal] = None

    # Worst offenders
    top_loss_products: List[str] = Field(
        description="Product names sorted by total_estimated_impact desc, top 5"
    )

    # Monthly projection
    monthly_projected_loss: Decimal = Field(
        description="total_estimated_impact / lookback_days * 30"
    )
    annual_projected_loss: Decimal = Field(
        description="total_estimated_impact / lookback_days * 365"
    )


class RetrospectiveAuditResponse(BaseModel):
    """Complete retrospective loss audit report."""
    id: uuid.UUID = Field(description="Audit ID for retrieval")
    user_id: uuid.UUID
    created_at: datetime

    # Summary (the sales pitch headline numbers)
    summary: AuditSummary

    # Per-SKU breakdown
    sku_results: List[SKUAuditResult]

    # Methodology note (transparency for the merchant)
    methodology: str = Field(
        default=(
            "This audit compares your historical prices against competitor average prices "
            "over the analysis period. 'Lost revenue' estimates sales volume reduction from "
            "overpricing using price elasticity modeling. 'Missed margin' calculates additional "
            "profit available from underpriced items. Estimates use conservative assumptions "
            "and actual results may vary."
        )
    )

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# LIST / HISTORY SCHEMAS
# ═══════════════════════════════════════════════════════════════

class AuditListItem(BaseModel):
    """Summary for listing past audits."""
    id: uuid.UUID
    created_at: datetime
    lookback_days: int
    total_products_analyzed: int
    total_estimated_impact: Decimal
    monthly_projected_loss: Decimal


class AuditListResponse(BaseModel):
    """Paginated list of past audits."""
    items: List[AuditListItem]
    total: int


    