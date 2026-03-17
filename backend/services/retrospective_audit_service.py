"""
Retrospective Loss Audit Service

Core engine that:
1. Queries CompetitorPriceHistory over a lookback window
2. Reconstructs daily price positioning per SKU
3. Calculates estimated revenue lost (overpriced) and margin missed (underpriced)
4. Produces the audit report used as the sales weapon / Free Pricing Audit

The math per SKU per day:
  - gap = your_price - optimal_price
  - If overpriced (gap > 2%):
      lost_units = estimated_daily_units × elasticity_factor × gap_percent
      lost_revenue = lost_units × your_price
  - If underpriced (gap < -2%):
      missed_margin = estimated_daily_units × abs(gap)

Conservative defaults:
  - elasticity_factor = 0.015 (1.5% unit loss per 1% overpricing)
  - estimated_daily_units = 5 (if no order data)
  - alignment_threshold = 2% (within ±2% = "aligned")
"""

import uuid as uuid_lib
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Date, and_, cast, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.competitor import Competitor
from models.competitor_price_history import CompetitorPriceHistory
from models.competitor_product import CompetitorProduct
from models.price_history import PriceHistory
from models.product import Product
from schemas.retrospective_audit import (
    AuditRequest,
    AuditSummary,
    PricingGapDay,
    RetrospectiveAuditResponse,
    SKUAuditResult,
)

# ── Constants ─────────────────────────────────────────────────
ALIGNMENT_THRESHOLD = Decimal("0.02")  # ±2% = aligned
DEFAULT_DAILY_UNITS = 5
ELASTICITY_FACTOR = Decimal("0.015")  # 1.5% unit loss per 1% overpricing
TWO = Decimal("2")
ZERO = Decimal("0")
HUNDRED = Decimal("100")


class RetrospectiveAuditService:
    """
    Generates retrospective pricing loss audits.

    Usage:
        service = RetrospectiveAuditService(session, user_id)
        report = await service.generate_audit(AuditRequest(lookback_days=90))
    """

    def __init__(self, session: AsyncSession, user_id: str):
        self.session = session
        self.user_id = user_id

    # ══════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════

    async def generate_audit(self, request: AuditRequest) -> RetrospectiveAuditResponse:
        """Generate a complete retrospective loss audit."""
        now = datetime.now(UTC)
        period_start = now - timedelta(days=request.lookback_days)

        # 1. Get products to analyze
        products = await self._get_auditable_products(request.product_ids)
        if not products:
            return self._empty_audit(now, period_start, request.lookback_days)

        # 2. For each product, compute the SKU-level audit
        sku_results: list[SKUAuditResult] = []
        for product in products:
            result = await self._audit_single_product(
                product=product,
                period_start=period_start,
                period_end=now,
                estimated_daily_units=request.estimated_daily_units or DEFAULT_DAILY_UNITS,
            )
            if result is not None:
                sku_results.append(result)

        # 3. Build summary from SKU results
        summary = self._build_summary(
            sku_results=sku_results,
            lookback_days=request.lookback_days,
            period_start=period_start,
            period_end=now,
        )

        audit_id = uuid_lib.uuid4()

        return RetrospectiveAuditResponse(
            id=audit_id,
            user_id=uuid_lib.UUID(self.user_id),
            created_at=now,
            summary=summary,
            sku_results=sku_results,
        )

    # ══════════════════════════════════════════════════════════
    # PRODUCT RETRIEVAL
    # ══════════════════════════════════════════════════════════

    async def _get_auditable_products(self, product_ids: list[uuid_lib.UUID] | None = None) -> list[Product]:
        """
        Get products that have at least one active competitor product link.
        Optionally filter to specific product IDs.
        """
        # Subquery: product IDs that have at least one competitor product
        competitor_product_ids = (
            select(CompetitorProduct.product_id).where(CompetitorProduct.is_active == True).distinct()
        )

        query = (
            select(Product)
            .where(
                and_(
                    Product.user_id == self.user_id,
                    Product.is_active == True,
                    Product.id.in_(competitor_product_ids),
                )
            )
            .order_by(Product.name)
        )

        if product_ids:
            query = query.where(Product.id.in_(product_ids))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ══════════════════════════════════════════════════════════
    # SINGLE PRODUCT AUDIT
    # ══════════════════════════════════════════════════════════

    async def _audit_single_product(
        self,
        product: Product,
        period_start: datetime,
        period_end: datetime,
        estimated_daily_units: int,
    ) -> SKUAuditResult | None:
        """Compute the retrospective audit for one product."""

        # Get competitor product links for this product
        cp_result = await self.session.execute(
            select(CompetitorProduct).where(
                and_(
                    CompetitorProduct.product_id == product.id,
                    CompetitorProduct.is_active == True,
                )
            )
        )
        comp_products = list(cp_result.scalars().all())

        if not comp_products:
            return None

        cp_ids = [cp.id for cp in comp_products]

        # Get competitor names
        competitor_ids = list({cp.competitor_id for cp in comp_products})
        comp_result = await self.session.execute(
            select(Competitor.id, Competitor.name).where(Competitor.id.in_(competitor_ids))
        )
        competitor_name_map: dict[uuid_lib.UUID, str] = {row.id: row.name for row in comp_result.all()}
        competitor_names = list(competitor_name_map.values())

        # Get competitor price history grouped by day
        daily_competitor_prices = await self._get_daily_competitor_prices(
            competitor_product_ids=cp_ids,
            period_start=period_start,
            period_end=period_end,
        )

        if not daily_competitor_prices:
            return None

        # Get the merchant's own price history to reconstruct daily prices
        merchant_daily_prices = await self._get_merchant_daily_prices(
            product=product,
            period_start=period_start,
            period_end=period_end,
        )

        # Walk through each day and compute gaps
        daily_gaps: list[PricingGapDay] = []
        days_overpriced = 0
        days_underpriced = 0
        days_aligned = 0
        total_lost_revenue = ZERO
        total_missed_margin = ZERO
        overpriced_gap_percents: list[Decimal] = []
        underpriced_gap_percents: list[Decimal] = []

        for day_str, comp_avg in sorted(daily_competitor_prices.items()):
            merchant_price = merchant_daily_prices.get(day_str, product.current_price)

            if merchant_price is None or merchant_price <= 0 or comp_avg <= 0:
                continue

            # Optimal price: target competitor average (conservative)
            optimal_price = comp_avg

            gap_amount = merchant_price - optimal_price
            gap_percent = (gap_amount / optimal_price * HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # Classify the gap
            abs_gap_ratio = abs(gap_amount) / optimal_price
            if abs_gap_ratio <= ALIGNMENT_THRESHOLD:
                gap_type = "aligned"
                days_aligned += 1
            elif gap_amount > 0:
                gap_type = "overpriced"
                days_overpriced += 1
                overpriced_gap_percents.append(gap_percent)

                # Lost revenue: overpricing drives away customers
                # lost_units = daily_units × elasticity × gap%
                lost_units = Decimal(str(estimated_daily_units)) * ELASTICITY_FACTOR * abs(gap_percent)
                day_lost_revenue = (lost_units * merchant_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total_lost_revenue += day_lost_revenue
            else:
                gap_type = "underpriced"
                days_underpriced += 1
                underpriced_gap_percents.append(abs(gap_percent))

                # Missed margin: you could have charged more
                missed_per_unit = abs(gap_amount)
                day_missed_margin = (Decimal(str(estimated_daily_units)) * missed_per_unit).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                total_missed_margin += day_missed_margin

            # Parse date string back to datetime for the response
            try:
                day_dt = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                day_dt = datetime.now(UTC)

            daily_gaps.append(
                PricingGapDay(
                    date=day_dt,
                    your_price=merchant_price.quantize(Decimal("0.01")),
                    competitor_avg_price=comp_avg.quantize(Decimal("0.01")),
                    optimal_price=optimal_price.quantize(Decimal("0.01")),
                    gap_amount=gap_amount.quantize(Decimal("0.01")),
                    gap_percent=gap_percent,
                    gap_type=gap_type,
                )
            )

        total_impact = total_lost_revenue + total_missed_margin

        # Current snapshot
        current_comp_avg = None
        current_gap_pct = None
        latest_comp_prices = [
            cp.current_price for cp in comp_products if cp.current_price is not None and cp.current_price > 0
        ]
        if latest_comp_prices:
            current_comp_avg = (sum(latest_comp_prices) / Decimal(str(len(latest_comp_prices)))).quantize(
                Decimal("0.01")
            )
            if current_comp_avg > 0:
                current_gap_pct = ((product.current_price - current_comp_avg) / current_comp_avg * HUNDRED).quantize(
                    Decimal("0.01")
                )

        avg_overpriced = None
        if overpriced_gap_percents:
            avg_overpriced = (sum(overpriced_gap_percents) / Decimal(str(len(overpriced_gap_percents)))).quantize(
                Decimal("0.01")
            )

        avg_underpriced = None
        if underpriced_gap_percents:
            avg_underpriced = (sum(underpriced_gap_percents) / Decimal(str(len(underpriced_gap_percents)))).quantize(
                Decimal("0.01")
            )

        return SKUAuditResult(
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            category=product.category,
            current_price=product.current_price,
            current_competitor_avg=current_comp_avg,
            current_gap_percent=current_gap_pct,
            competitor_count=len(comp_products),
            competitor_names=competitor_names,
            days_overpriced=days_overpriced,
            avg_overpriced_gap_percent=avg_overpriced,
            estimated_lost_revenue=total_lost_revenue.quantize(Decimal("0.01")),
            days_underpriced=days_underpriced,
            avg_underpriced_gap_percent=avg_underpriced,
            estimated_missed_margin=total_missed_margin.quantize(Decimal("0.01")),
            days_aligned=days_aligned,
            total_estimated_impact=total_impact.quantize(Decimal("0.01")),
            daily_gaps=daily_gaps,
        )

    # ══════════════════════════════════════════════════════════
    # DATA RETRIEVAL HELPERS
    # ══════════════════════════════════════════════════════════

    async def _get_daily_competitor_prices(
        self,
        competitor_product_ids: list[uuid_lib.UUID],
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Decimal]:
        """
        Get average competitor price per day across all competitor product links.
        Returns {date_string: avg_price}.
        """
        query = (
            select(
                cast(CompetitorPriceHistory.observed_at, Date).label("obs_date"),
                func.avg(CompetitorPriceHistory.new_price).label("avg_price"),
            )
            .where(
                and_(
                    CompetitorPriceHistory.competitor_product_id.in_(competitor_product_ids),
                    CompetitorPriceHistory.observed_at >= period_start,
                    CompetitorPriceHistory.observed_at <= period_end,
                    CompetitorPriceHistory.is_available == True,
                )
            )
            .group_by("obs_date")
            .order_by("obs_date")
        )

        result = await self.session.execute(query)
        rows = result.all()

        daily_prices: dict[str, Decimal] = {}
        for row in rows:
            date_key = row.obs_date.strftime("%Y-%m-%d") if hasattr(row.obs_date, "strftime") else str(row.obs_date)
            daily_prices[date_key] = Decimal(str(row.avg_price))

        # Fill gaps: if we don't have data for a day, use last known price
        if daily_prices:
            filled = self._forward_fill_prices(daily_prices, period_start, period_end)
            return filled

        return daily_prices

    async def _get_merchant_daily_prices(
        self,
        product: Product,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Decimal]:
        """
        Reconstruct the merchant's price for each day from PriceHistory.
        Falls back to current_price if no history exists.
        """
        query = (
            select(PriceHistory)
            .where(
                and_(
                    PriceHistory.product_id == product.id,
                    PriceHistory.user_id == self.user_id,
                    PriceHistory.created_at >= period_start,
                    PriceHistory.created_at <= period_end,
                )
            )
            .order_by(PriceHistory.created_at.asc())
        )

        result = await self.session.execute(query)
        history = list(result.scalars().all())

        if not history:
            # No price changes in the period — price was constant
            # Fill every day with current_price
            daily: dict[str, Decimal] = {}
            current = period_start
            while current <= period_end:
                daily[current.strftime("%Y-%m-%d")] = product.current_price
                current += timedelta(days=1)
            return daily

        # Build daily map: walk through changes, carry forward
        daily: dict[str, Decimal] = {}
        # Start with the price before the first change in the window
        running_price = history[0].old_price if history[0].old_price else product.base_price
        change_idx = 0

        current = period_start
        while current <= period_end:
            day_str = current.strftime("%Y-%m-%d")

            # Apply any price changes that happened on this day
            while change_idx < len(history) and history[change_idx].created_at.strftime("%Y-%m-%d") <= day_str:
                running_price = history[change_idx].new_price
                change_idx += 1

            daily[day_str] = running_price
            current += timedelta(days=1)

        return daily

    # ══════════════════════════════════════════════════════════
    # UTILITY
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _forward_fill_prices(
        daily_prices: dict[str, Decimal],
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Decimal]:
        """Forward-fill missing days with last known price."""
        filled: dict[str, Decimal] = {}
        last_known: Decimal | None = None

        # Find the earliest known price to seed
        sorted_keys = sorted(daily_prices.keys())
        if sorted_keys:
            last_known = daily_prices[sorted_keys[0]]

        current = period_start
        while current <= period_end:
            day_str = current.strftime("%Y-%m-%d")
            if day_str in daily_prices:
                last_known = daily_prices[day_str]
            if last_known is not None:
                filled[day_str] = last_known
            current += timedelta(days=1)

        return filled

    def _build_summary(
        self,
        sku_results: list[SKUAuditResult],
        lookback_days: int,
        period_start: datetime,
        period_end: datetime,
    ) -> AuditSummary:
        """Aggregate SKU results into headline numbers."""
        if not sku_results:
            return AuditSummary(
                total_products_analyzed=0,
                lookback_days=lookback_days,
                analysis_period_start=period_start,
                analysis_period_end=period_end,
                total_estimated_impact=ZERO,
                total_lost_revenue=ZERO,
                total_missed_margin=ZERO,
                avg_days_overpriced=ZERO,
                avg_days_underpriced=ZERO,
                avg_overpriced_gap_percent=None,
                top_loss_products=[],
                monthly_projected_loss=ZERO,
                annual_projected_loss=ZERO,
            )

        n = Decimal(str(len(sku_results)))
        total_lost = sum(s.estimated_lost_revenue for s in sku_results)
        total_missed = sum(s.estimated_missed_margin for s in sku_results)
        total_impact = total_lost + total_missed

        avg_days_over = (sum(Decimal(str(s.days_overpriced)) for s in sku_results) / n).quantize(Decimal("0.1"))
        avg_days_under = (sum(Decimal(str(s.days_underpriced)) for s in sku_results) / n).quantize(Decimal("0.1"))

        # Average overpriced gap across SKUs that were overpriced
        overpriced_skus = [s for s in sku_results if s.avg_overpriced_gap_percent is not None]
        avg_gap = None
        if overpriced_skus:
            avg_gap = (
                sum(s.avg_overpriced_gap_percent for s in overpriced_skus) / Decimal(str(len(overpriced_skus)))
            ).quantize(Decimal("0.01"))

        # Top loss products (sorted by total impact, top 5)
        sorted_by_impact = sorted(sku_results, key=lambda s: s.total_estimated_impact, reverse=True)
        top_loss = [s.product_name for s in sorted_by_impact[:5]]

        # Monthly & annual projections
        if lookback_days > 0:
            daily_rate = total_impact / Decimal(str(lookback_days))
            monthly = (daily_rate * Decimal("30")).quantize(Decimal("0.01"))
            annual = (daily_rate * Decimal("365")).quantize(Decimal("0.01"))
        else:
            monthly = ZERO
            annual = ZERO

        return AuditSummary(
            total_products_analyzed=len(sku_results),
            lookback_days=lookback_days,
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            total_estimated_impact=total_impact.quantize(Decimal("0.01")),
            total_lost_revenue=total_lost.quantize(Decimal("0.01")),
            total_missed_margin=total_missed.quantize(Decimal("0.01")),
            avg_days_overpriced=avg_days_over,
            avg_days_underpriced=avg_days_under,
            avg_overpriced_gap_percent=avg_gap,
            top_loss_products=top_loss,
            monthly_projected_loss=monthly,
            annual_projected_loss=annual,
        )

    def _empty_audit(
        self,
        now: datetime,
        period_start: datetime,
        lookback_days: int,
    ) -> RetrospectiveAuditResponse:
        """Return an empty audit when no products have competitor data."""
        return RetrospectiveAuditResponse(
            id=uuid_lib.uuid4(),
            user_id=uuid_lib.UUID(self.user_id),
            created_at=now,
            summary=AuditSummary(
                total_products_analyzed=0,
                lookback_days=lookback_days,
                analysis_period_start=period_start,
                analysis_period_end=now,
                total_estimated_impact=ZERO,
                total_lost_revenue=ZERO,
                total_missed_margin=ZERO,
                avg_days_overpriced=ZERO,
                avg_days_underpriced=ZERO,
                top_loss_products=[],
                monthly_projected_loss=ZERO,
                annual_projected_loss=ZERO,
            ),
            sku_results=[],
        )
