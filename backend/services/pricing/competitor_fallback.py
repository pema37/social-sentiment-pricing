# backend/services/pricing/competitor_fallback.py
"""
Competitor Fallback Service - Generates recommendations based on competitor price alone.

Used when no pricing rules match (e.g., insufficient sentiment data).
Provides basic price recommendations based on competitive positioning.

FIX (2026-01-24): Now respects user's auto-approval settings.
FIX (2026-02-18): Wired PipelineAdapter to produce typed ScoutOutput,
AnalystOutput, StrategistOutput evidence chains — same pattern as
recommendation_service.py, with rule=None. Evidence is stored in
factors dict → extracted by record_merchant_decision() → stored as
JSONB on RecommendationOutcome for calibration & backward learning.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.pricing_settings import PricingSettings
from models.product import Product

from .pipeline_adapter import PipelineAdapter
from .rule_evaluator import MarketSignals
from .settings_service import SettingsService

logger = logging.getLogger(__name__)


# Thresholds for competitor-based pricing decisions
ABOVE_COMPETITOR_THRESHOLD = Decimal("10")  # We're >10% above = suggest decrease
BELOW_COMPETITOR_THRESHOLD = Decimal("-15")  # We're >15% below = suggest increase
MAX_VALID_COMPETITOR_PRICE = Decimal("5000")  # Filter out scraping errors
COMPETITOR_MATCH_FACTOR = Decimal("0.98")  # Match at 98% of competitor
INCREASE_FACTOR = Decimal("1.05")  # 5% increase when below competitor
MIN_CHANGE_THRESHOLD = Decimal("1")  # Skip changes <1%
COMPETITOR_CONFIDENCE = Decimal("0.65")  # Lower confidence for competitor-only


class CompetitorFallbackService:
    """Generates recommendations based on competitor pricing."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings_service = SettingsService(db)

    async def generate(self, product: Product, user_id: UUID, signals: MarketSignals) -> PriceRecommendation | None:
        """
        Generate a recommendation based on competitor price alone.

        Returns:
            PriceRecommendation with data_source='competitor_only', or None
        """
        # Find valid competitor price
        competitor_price, competitor_id = self._find_valid_competitor_price(signals.competitor_prices)

        if not competitor_price:
            logger.debug(f"No valid competitor prices for product {product.id}")
            return None

        # Validate current price
        if not self._is_valid_current_price(product):
            return None

        # Calculate recommendation
        new_price, reasoning = self._calculate_competitor_based_price(product, competitor_price)

        if new_price is None:
            return None

        # Apply constraints and validate
        raw_price_before_constraints = new_price
        new_price = self._apply_constraints(new_price, product)
        change_percent = self._calculate_change_percent(product.current_price, new_price)

        if abs(change_percent) < MIN_CHANGE_THRESHOLD:
            logger.debug(f"Change too small ({change_percent}%), skipping")
            return None

        # Get settings and create recommendation
        settings = await self.settings_service.get_or_create(user_id)

        return await self._create_recommendation(
            product=product,
            user_id=user_id,
            new_price=new_price,
            change_percent=change_percent,
            reasoning=reasoning,
            competitor_id=competitor_id,
            competitor_price=competitor_price,
            settings=settings,
            signals=signals,
            raw_price_before_constraints=raw_price_before_constraints,
        )

    def _find_valid_competitor_price(self, competitor_prices: dict) -> tuple[Decimal | None, str | None]:
        """Find first valid competitor price."""
        for comp_id, price in competitor_prices.items():
            if price and price > 0 and price < MAX_VALID_COMPETITOR_PRICE:
                logger.debug(f"Using competitor {comp_id} price: ${price}")
                return Decimal(str(price)), comp_id
        return None, None

    def _is_valid_current_price(self, product: Product) -> bool:
        """Check if product has valid current price."""
        if not product.current_price or product.current_price <= 0:
            logger.warning(f"Product {product.id} has invalid current_price: {product.current_price}")
            return False
        return True

    def _calculate_competitor_based_price(
        self, product: Product, competitor_price: Decimal
    ) -> tuple[Decimal | None, str]:
        """
        Calculate new price based on competitive position.

        Returns:
            (new_price, reasoning) or (None, "") if no change needed
        """
        current = product.current_price
        diff_pct = ((current - competitor_price) / competitor_price) * Decimal("100")

        if diff_pct > ABOVE_COMPETITOR_THRESHOLD:
            # We're significantly above competitor - suggest matching
            new_price = competitor_price * COMPETITOR_MATCH_FACTOR
            reasoning = (
                f"Your price (${current:.2f}) is {diff_pct:.1f}% above competitor "
                f"(${competitor_price:.2f}). Recommending price match at 98% of competitor."
            )
            logger.info(f"Product {product.id}: {diff_pct:.1f}% above competitor, suggesting decrease")
            return new_price, reasoning

        elif diff_pct < BELOW_COMPETITOR_THRESHOLD:
            # We're significantly below competitor - opportunity for increase
            new_price = current * INCREASE_FACTOR
            reasoning = (
                f"Your price (${current:.2f}) is {abs(diff_pct):.1f}% below competitor "
                f"(${competitor_price:.2f}). Room for a 5% price increase."
            )
            logger.info(f"Product {product.id}: {abs(diff_pct):.1f}% below competitor, suggesting increase")
            return new_price, reasoning

        else:
            # Price is competitive, no change needed
            logger.info(f"Product {product.id} price is competitive ({diff_pct:.1f}% vs competitor)")
            return None, ""

    def _apply_constraints(self, price: Decimal, product: Product) -> Decimal:
        """Apply min/max product constraints."""
        if product.min_price and price < product.min_price:
            price = product.min_price
            logger.debug(f"Adjusted to min_price: ${product.min_price}")

        if product.max_price and price > product.max_price:
            price = product.max_price
            logger.debug(f"Adjusted to max_price: ${product.max_price}")

        return price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _calculate_change_percent(self, current: Decimal, new: Decimal) -> Decimal:
        """Calculate percentage change."""
        return (((new - current) / current) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    async def _create_recommendation(
        self,
        product: Product,
        user_id: UUID,
        new_price: Decimal,
        change_percent: Decimal,
        reasoning: str,
        competitor_id: str | None,
        competitor_price: Decimal,
        settings: PricingSettings,
        signals: MarketSignals,
        raw_price_before_constraints: Decimal | None = None,
    ) -> PriceRecommendation:
        """Create and persist the recommendation."""
        valid_until = datetime.now(UTC) + timedelta(hours=settings.recommendation_valid_hours)

        factors = self._build_factors(product.current_price, new_price, competitor_id, competitor_price)

        # ══════════════════════════════════════════════════════════════
        # INTELLIGENCE ENVIRONMENT: Build typed agent evidence chains
        # Same pattern as recommendation_service.py, with rule=None
        # ══════════════════════════════════════════════════════════════

        try:
            scout_output = PipelineAdapter.build_scout_output(product, signals)

            # Competitor fallback has no confidence_breakdown from
            # ConfidenceCalculator, so build a minimal one that
            # PipelineAdapter.build_analyst_output() can consume.
            confidence_breakdown = {
                "components": {
                    "signal_agreement": {"score": 0.5},
                    "market_stability": {"score": 0.5},
                    "rule_confidence": {"score": 0.3},  # Lower: no rule matched
                    "data_quality": {"score": round(scout_output.data_completeness, 4)},
                    "historical_accuracy": {"score": 0.5},
                },
            }

            analyst_output = PipelineAdapter.build_analyst_output(
                scout_output, confidence_breakdown, signals, rule=None
            )
            strategist_output = PipelineAdapter.build_strategist_output(
                analyst_output,
                product,
                new_price,
                change_percent,
                COMPETITOR_CONFIDENCE,
                reasoning,
                factors,
                rule=None,
                raw_price_before_boundaries=raw_price_before_constraints,
            )

            # Store typed evidence in factors for record_merchant_decision()
            factors["scout_evidence"] = scout_output.to_evidence()
            factors["analyst_evidence"] = analyst_output.to_evidence()
            factors["strategist_evidence"] = strategist_output.to_evidence()

            logger.debug(f"Built typed evidence chain for competitor fallback product {product.id}")
        except Exception as e:
            logger.warning(f"Failed to build typed evidence for competitor fallback product {product.id}: {e}")
            # Graceful degradation: recommendation still works,
            # just without typed evidence. record_merchant_decision()
            # falls back to old-style extraction from match_details/price_impacts.

        # ══════════════════════════════════════════════════════════════
        # END INTELLIGENCE ENVIRONMENT
        # ══════════════════════════════════════════════════════════════

        requires_approval = self.settings_service.check_requires_approval(
            product, change_percent, COMPETITOR_CONFIDENCE, settings
        )

        recommendation = PriceRecommendation(
            user_id=user_id,
            product_id=product.id,
            triggered_rule_id=None,  # No rule - this is a fallback
            current_price=product.current_price,
            recommended_price=new_price,
            change_percent=change_percent,
            confidence_score=COMPETITOR_CONFIDENCE,
            reasoning=reasoning,
            factors=factors,
            status=RecommendationStatus.PENDING,
            requires_approval=requires_approval,
            valid_until=valid_until,
        )

        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)

        logger.info(
            f"Generated competitor fallback for product {product.id}: "
            f"${product.current_price} → ${new_price} ({change_percent:+.1f}%), "
            f"requires_approval={requires_approval}, "
            f"evidence_chain={'complete' if 'scout_evidence' in factors else 'partial'}"
        )

        # Auto-apply if eligible
        await self._try_auto_apply(recommendation, user_id, settings)

        return recommendation

    def _build_factors(
        self, current_price: Decimal, new_price: Decimal, competitor_id: str | None, competitor_price: Decimal
    ) -> dict:
        """Build the factors dict for the recommendation."""
        price_diff_pct = ((current_price - competitor_price) / competitor_price) * Decimal("100")

        return {
            "match_details": {
                "rule_type": "competitor_fallback",
                "competitor_id": str(competitor_id) if competitor_id else None,
                "competitor_price": float(competitor_price),
                "price_diff_pct": float(price_diff_pct),
            },
            "price_impacts": {
                "competitor": float(new_price - current_price),
            },
            "confidence_breakdown": {
                "base_confidence": 0.65,
                "reason": "competitor_only",
                "note": "Lower confidence - based on competitor price only, no sentiment data",
            },
            "data_source": "competitor_only",
        }

    async def _try_auto_apply(
        self, recommendation: PriceRecommendation, user_id: UUID, settings: PricingSettings
    ) -> None:
        """Attempt to auto-apply if settings allow."""
        if recommendation.requires_approval or not settings.auto_approve_enabled:
            return

        try:
            from services.pricing.approval_service import ApprovalService

            approval_service = ApprovalService(self.db)
            await approval_service.auto_approve_and_apply(recommendation.id, user_id)
            logger.info(f"Auto-applied competitor fallback {recommendation.id}")
        except Exception as e:
            logger.warning(f"Auto-apply failed for competitor fallback {recommendation.id}: {e}")
