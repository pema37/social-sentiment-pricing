"""
Prospect Audit API Routes (PUBLIC — No Authentication)

These endpoints are unauthenticated. They power the
"Free Pricing Audit" lead magnet on the marketing site.

Rate limited to prevent abuse of the Shopify scraper.

Endpoints:
  POST /api/v1/prospect/audit           — Teaser results (free, no email)
  POST /api/v1/prospect/audit/pdf       — Full PDF (requires email capture)
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from core.logging import get_logger
from core.rate_limit import limiter
from schemas.prospect_audit import (
    ProspectAuditRequest,
    ProspectAuditTeaser,
    ProspectPDFRequest,
)
from schemas.retrospective_audit import (
    AuditSummary,
    RetrospectiveAuditResponse,
    SKUAuditResult,
)
from services.audit_pdf_generator import generate_audit_pdf
from services.prospect_audit_service import ProspectAuditService
from services.prospect_lead_capture import capture_lead

logger = get_logger(__name__)

router = APIRouter(prefix="/prospect", tags=["Prospect Audit (Public)"])


@router.post("/audit", response_model=ProspectAuditTeaser)
@limiter.limit("10/minute")
async def generate_prospect_audit(request: ProspectAuditRequest, req: Request):
    """
    Generate a free pricing audit teaser.

    No authentication required. Rate limited to 10 requests/minute per IP.

    Prospect provides either:
    - A Shopify store URL (we fetch /products.json)
    - A list of products with names and prices

    Returns headline impact numbers + top 5 worst offenders.
    Full report + PDF requires email (see /prospect/audit/pdf).
    """
    if not request.store_url and not request.products:
        raise HTTPException(status_code=422, detail="Provide either a store_url or a list of products.")

    service = ProspectAuditService()
    teaser = await service.generate_teaser(request)
    return teaser


@router.post("/audit/pdf")
@limiter.limit("5/minute")
async def generate_prospect_pdf(request: ProspectPDFRequest, req: Request):
    """
    Generate the full pricing audit PDF.

    Requires email capture. Rate limited to 5 requests/minute per IP.
    The email gets pushed to HubSpot CRM for follow-up outreach.
    """
    if not request.store_url and not request.products:
        raise HTTPException(status_code=422, detail="Provide either a store_url or a list of products.")

    # Capture the lead (logs + pushes to CRM)
    await capture_lead(
        email=request.email,
        company_name=request.company_name,
        store_url=request.store_url,
        source="free_pricing_audit_pdf",
    )

    # Rebuild the full audit
    service = ProspectAuditService()

    products = request.products or []
    store_name = None

    if request.store_url:
        store_name, products = await service._fetch_shopify_products(request.store_url)

    if not products:
        raise HTTPException(status_code=422, detail="Could not fetch products from the provided store URL.")

    # Get full results (ungated)
    all_results = service.get_all_results(products)

    # Convert to RetrospectiveAuditResponse format for PDF generator
    now = datetime.now(UTC)
    overpriced = [r for r in all_results if r.gap_type == "overpriced"]
    underpriced = [r for r in all_results if r.gap_type == "underpriced"]

    total_impact = service._estimate_monthly_impact(all_results)

    sku_results = []
    for r in all_results:
        gap_pct = float(r.gap_percent or 0)
        lost_rev = (
            Decimal(str(abs(gap_pct) * 0.015 * 3 * float(r.your_price) * 30)).quantize(Decimal("0.01"))
            if r.gap_type == "overpriced"
            else Decimal("0")
        )
        missed_margin = (
            Decimal(str(abs(float(r.your_price) - float(r.market_avg_price or 0)) * 3 * 30)).quantize(Decimal("0.01"))
            if r.gap_type == "underpriced" and r.market_avg_price
            else Decimal("0")
        )

        sku_results.append(
            SKUAuditResult(
                product_id=uuid.uuid4(),
                product_name=r.name,
                sku=r.sku,
                category=None,
                current_price=r.your_price,
                current_competitor_avg=r.market_avg_price,
                current_gap_percent=r.gap_percent,
                competitor_count=r.competitor_count,
                competitor_names=[],
                days_overpriced=30 if r.gap_type == "overpriced" else 0,
                avg_overpriced_gap_percent=r.gap_percent if r.gap_type == "overpriced" else None,
                estimated_lost_revenue=lost_rev,
                days_underpriced=30 if r.gap_type == "underpriced" else 0,
                avg_underpriced_gap_percent=r.gap_percent if r.gap_type == "underpriced" else None,
                estimated_missed_margin=missed_margin,
                days_aligned=30 if r.gap_type == "aligned" else 0,
                total_estimated_impact=lost_rev + missed_margin,
                daily_gaps=[],
            )
        )

    sku_results.sort(key=lambda s: s.total_estimated_impact, reverse=True)
    top_names = [s.product_name for s in sku_results[:5] if s.total_estimated_impact > 0]

    audit = RetrospectiveAuditResponse(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        created_at=now,
        summary=AuditSummary(
            total_products_analyzed=len(all_results),
            lookback_days=30,
            analysis_period_start=now,
            analysis_period_end=now,
            total_estimated_impact=total_impact.quantize(Decimal("0.01")),
            total_lost_revenue=sum(s.estimated_lost_revenue for s in sku_results).quantize(Decimal("0.01")),
            total_missed_margin=sum(s.estimated_missed_margin for s in sku_results).quantize(Decimal("0.01")),
            avg_days_overpriced=Decimal("30") if overpriced else Decimal("0"),
            avg_days_underpriced=Decimal("30") if underpriced else Decimal("0"),
            avg_overpriced_gap_percent=None,
            top_loss_products=top_names,
            monthly_projected_loss=total_impact.quantize(Decimal("0.01")),
            annual_projected_loss=(total_impact * Decimal("12")).quantize(Decimal("0.01")),
        ),
        sku_results=sku_results,
        methodology=(
            "This audit compares your product prices against catalog-wide averages "
            "by product category. Estimates use conservative price elasticity assumptions "
            "(1.5% unit loss per 1% overpricing, 3 units/day baseline). "
            "For a more detailed analysis using real competitor data, sign up for ActualPrice."
        ),
    )

    pdf_bytes = generate_audit_pdf(audit)

    company_slug = (request.company_name or "store").lower().replace(" ", "-")[:30]
    filename = f"pricing-audit-{company_slug}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
