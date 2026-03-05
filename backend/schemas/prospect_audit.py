"""
Prospect Audit Schemas (Public / Unauthenticated)

The "Free Pricing Audit" lead magnet. No login required.
Prospect provides a Shopify store URL or pastes a CSV of products+prices.
We scrape public competitor data and show a teaser.
Full PDF requires email capture.
"""

from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, EmailStr


# ═══════════════════════════════════════════════════════════════
# REQUEST
# ═══════════════════════════════════════════════════════════════

class ProspectProductRow(BaseModel):
    """A single product from CSV paste."""
    name: str = Field(max_length=500)
    price: Decimal = Field(ge=0)
    sku: Optional[str] = Field(default=None, max_length=100)


class ProspectAuditRequest(BaseModel):
    """
    Request for a public prospect audit.
    Provide EITHER store_url OR products — not both.
    """
    # Option A: Shopify store URL (we fetch /products.json)
    store_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Shopify store URL, e.g. https://mystore.myshopify.com"
    )
    # Option B: CSV-pasted products
    products: Optional[List[ProspectProductRow]] = Field(
        default=None,
        description="List of products with name + price"
    )


class ProspectPDFRequest(BaseModel):
    """Request for the full PDF — requires email."""
    email: EmailStr
    company_name: Optional[str] = Field(default=None, max_length=255)
    # Include the original audit request so we can regenerate
    store_url: Optional[str] = None
    products: Optional[List[ProspectProductRow]] = None


# ═══════════════════════════════════════════════════════════════
# PER-PRODUCT TEASER RESULT
# ═══════════════════════════════════════════════════════════════

class ProspectProductResult(BaseModel):
    """Lightweight audit result for one product."""
    name: str
    sku: Optional[str] = None
    your_price: Decimal
    market_avg_price: Optional[Decimal] = None
    gap_percent: Optional[Decimal] = None
    gap_type: Optional[Literal["overpriced", "underpriced", "aligned", "no_data"]] = "no_data"
    competitor_count: int = 0


# ═══════════════════════════════════════════════════════════════
# TEASER RESPONSE (shown free, no email required)
# ═══════════════════════════════════════════════════════════════

class ProspectAuditTeaser(BaseModel):
    """
    Public teaser results. Shows headline numbers + top 5 products.
    Full breakdown + PDF requires email.
    """
    # Source info
    store_name: Optional[str] = None
    total_products_found: int
    products_with_market_data: int

    # Headline numbers (the hook)
    estimated_monthly_impact: Decimal = Field(
        description="Projected monthly loss from pricing gaps"
    )
    products_overpriced: int
    products_underpriced: int
    avg_gap_percent: Optional[Decimal] = None

    # Top 5 worst offenders (teaser)
    top_products: List[ProspectProductResult] = Field(
        max_length=5,
        description="Top 5 products by estimated impact — the teaser"
    )

    # Total count withheld (drives email capture)
    remaining_products_count: int = Field(
        description="Number of additional products in the full report"
    )

    # CTA
    cta_message: str = Field(
        default="Enter your email to get the full report with all products and a downloadable PDF."
    )



    