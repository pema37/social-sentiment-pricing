"""
Recommendation Service - Generates price recommendations based on rules and signals.

Refactored: Orchestration layer that delegates to focused sub-services.

Dependencies:
- PriceSyncService: Fetches live prices from stores (Priority 1)
- SettingsService: Manages user settings with defaults (Priority 2)
- CompetitorFallbackService: Generates competitor-only recommendations
- PriceCalculator, BoundaryEnforcer, ReasoningGenerator: Calculation helpers
- PipelineAdapter: Converts service outputs to typed agent contracts

FIX (2026-01-28) Bug #1: Always refresh product from DB before generating
recommendations to ensure current_price reflects actual database state.
FIX (2026-02-17): Wired PipelineAdapter to produce typed ScoutOutput,
AnalystOutput, StrategistOutput evidence chains on every recommendation.
Evidence is stored in factors dict → extracted by record_merchant_decision()
→ stored as JSONB on RecommendationOutcome for calibration & backward learning.
FIX (2026-02-18): Phase 5 — Wired IE orchestrator (ExperimentManager →
ScoringEngine → ContextInjector → Calibrator) as enhancement layer.
If IE is enabled and succeeds, uses its suggested price + calibrated confidence.
If IE fails or is disabled, falls back to existing PipelineAdapter flow unchanged.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.pricing_rule import PricingRule
from models.product import Product

# --- Phase 5: Intelligence Environment ---
from services.scoring.ie_orchestrator import (
    IERecommendation,
    IEStatus,
    create_ie_orchestrator,
)

from .competitor_fallback import CompetitorFallbackService
from .confidence_calculator import ConfidenceCalculator
from .pipeline_adapter import PipelineAdapter
from .price_sync_service import PriceSyncService
from .recommendation_helpers import (
    BoundaryEnforcer,
    PriceCalculator,
    ReasoningGenerator,
)
from .rule_evaluator import RuleEvaluator
from .settings_service import SettingsService
from .signal_processor import SignalProcessor

logger = logging.getLogger(__name__)


class RecommendationService:
    """Generates and manages price recommendations."""

    def __init__(self, db: AsyncSession):
        self.db = db

        # Core evaluation services
        self.rule_evaluator = RuleEvaluator(db)
        self.signal_processor = SignalProcessor(db)
        self.confidence_calculator = ConfidenceCalculator()

        # Specialized sub-services
        self.price_sync = PriceSyncService(db)
        self.settings_service = SettingsService(db)
        self.competitor_fallback = CompetitorFallbackService(db)

    async def generate_recommendation(self, product: Product, user_id: UUID) -> PriceRecommendation | None:
        """
        Generate a price recommendation for a product.

        Flow:
        1. Refresh product from DB to ensure fresh data
        2. Sync live price from store (if connected)
        3. Check for existing pending recommendations
        4. Gather market signals
        5. Find matching pricing rule
        6. If no rule matches, try competitor fallback
        7. Calculate price and create recommendation
        8. Auto-apply if settings allow
        """
        # =============================================================
        # BUGFIX (2026-01-28): Always refresh product from DB first
        # =============================================================
        await self.db.refresh(product)
        logger.debug(f"Refreshed product {product.id} from DB: current_price=${product.current_price}")

        # Step 2: Try to sync with live store price (may update DB + product object)
        price_synced = await self.price_sync.sync_product_price(product, user_id)
        if price_synced:
            logger.info(f"Product {product.id} price synced from store: ${product.current_price}")

        # Step 3: Check for existing pending recommendation
        if await self._has_pending_recommendation(product.id, user_id):
            logger.debug(f"Product {product.id} already has pending recommendation")
            return None

        # Step 4: Gather market signals
        signals = await self.signal_processor.gather_signals(product)

        # Step 5: Find matching rule
        result = await self.rule_evaluator.find_matching_rule(product, user_id, signals)

        # Step 6: No rule matched - try competitor fallback
        if not result or result[0] is None:
            logger.info(f"No rule matched for product {product.id}, trying competitor fallback")
            return await self.competitor_fallback.generate(product, user_id, signals)

        rule, match_details = result

        # Step 7: Generate rule-based recommendation
        return await self._create_rule_based_recommendation(product, user_id, rule, match_details, signals)

    async def _has_pending_recommendation(self, product_id: UUID, user_id: UUID) -> bool:
        """Check if pending recommendation already exists."""
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.product_id == product_id)
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until > datetime.now(UTC))
        )
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    # =========================================================================
    # Phase 5: Intelligence Environment Enhancement Layer
    # =========================================================================

    async def _try_ie_recommendation(
        self,
        product: Product,
        signals,
        rule: PricingRule | None,
    ) -> IERecommendation | None:
        """
        Try to get an IE-enhanced recommendation.

        Returns IERecommendation if IE is enabled and succeeds,
        None if IE is disabled or fails (caller falls back to existing flow).

        The IE orchestrator runs:
          ExperimentManager → ScoringEngine → ContextInjector → Calibrator

        All components have circuit breakers — if any single component fails,
        the others continue. If the overall pipeline fails, we return None
        and the existing PipelineAdapter flow handles the recommendation.
        """
        try:
            # Build product context for the IE orchestrator
            competitor_prices = []
            if hasattr(signals, "competitor_prices"):
                competitor_prices = [float(p.price) for p in (signals.competitor_prices or []) if hasattr(p, "price")]
            elif isinstance(signals, dict) and "competitor_prices" in signals:
                competitor_prices = [
                    float(p.price) if hasattr(p, "price") else float(p)
                    for p in (signals.get("competitor_prices") or [])
                ]

            product_context = {
                "product_id": str(product.id),
                "merchant_id": str(product.merchant_id) if hasattr(product, "merchant_id") else str(product.user_id),
                "category_id": str(product.category_id) if getattr(product, "category_id", None) else None,
                "current_price": float(product.current_price),
                "cost": float(product.cost) if getattr(product, "cost", None) else None,
                "competitor_prices": competitor_prices,
                "historical_sales": getattr(signals, "historical_sales", [])
                if not isinstance(signals, dict)
                else signals.get("historical_sales", []),
                "sentiment_score": getattr(signals, "sentiment_score", None)
                if not isinstance(signals, dict)
                else signals.get("sentiment_score"),
                "review_count": getattr(signals, "review_count", None)
                if not isinstance(signals, dict)
                else signals.get("review_count"),
                "search_volume_trend": getattr(signals, "search_volume_trend", None)
                if not isinstance(signals, dict)
                else signals.get("search_volume_trend"),
            }

            # Create orchestrator with DB session factory
            orchestrator = create_ie_orchestrator(
                db_session_factory=lambda: self.db,
            )

            # Generate IE recommendation
            ie_result = await asyncio.to_thread(orchestrator.generate_recommendation, product_context)

            if ie_result.status in (IEStatus.SUCCESS, IEStatus.PARTIAL):
                logger.info(
                    "IE recommendation for product %s: %s → %s (conf: %.3f, status: %s, duration: %dms)",
                    product.id,
                    ie_result.current_price,
                    ie_result.suggested_price,
                    ie_result.calibrated_confidence,
                    ie_result.status.value,
                    ie_result.total_duration_ms,
                )
                return ie_result
            else:
                logger.info(
                    "IE returned %s for product %s, falling back to existing pipeline",
                    ie_result.status.value,
                    product.id,
                )
                return None

        except Exception as exc:
            logger.warning(
                "IE orchestrator failed for product %s: %s. Falling back to existing pipeline.",
                product.id,
                exc,
            )
            return None

    # =========================================================================
    # Rule-Based Recommendation (with IE enhancement)
    # =========================================================================

    async def _create_rule_based_recommendation(
        self, product: Product, user_id: UUID, rule: PricingRule, match_details: dict, signals
    ) -> PriceRecommendation | None:
        """Create recommendation based on a matched pricing rule."""
        # Calculate new price
        new_price = PriceCalculator.calculate_new_price(product, rule, signals)

        if new_price is None or new_price == product.current_price:
            logger.debug(
                f"No price change needed for product {product.id}: "
                f"current=${product.current_price}, calculated=${new_price}"
            )
            return None

        # ── Capture raw price before boundary enforcement ──
        raw_price_before_boundaries = new_price

        # Apply boundaries
        new_price = BoundaryEnforcer.apply_boundaries(new_price, product, rule)
        change_percent = BoundaryEnforcer.calculate_change_percent(product.current_price, new_price)

        # Calculate confidence
        price_impacts = self.signal_processor.calculate_price_impact(signals, product)
        confidence = self.confidence_calculator.calculate(signals, price_impacts, rule.rule_type.value)

        # Get confidence breakdown (feeds AnalystOutput)
        confidence_breakdown = self.confidence_calculator.get_confidence_breakdown(
            signals, price_impacts, rule.rule_type.value
        )

        # ══════════════════════════════════════════════════════════════
        # PHASE 5: Try IE-enhanced recommendation
        # If IE succeeds, override price + confidence with IE values.
        # If IE fails, continue with existing PipelineAdapter flow.
        # ══════════════════════════════════════════════════════════════

        ie_result = await self._try_ie_recommendation(product, signals, rule)
        ie_was_used = False

        if ie_result is not None:
            # IE succeeded — use its suggested price and calibrated confidence
            ie_suggested_price = Decimal(str(ie_result.suggested_price))

            # Still enforce boundaries for safety (merchant guardrails)
            new_price = BoundaryEnforcer.apply_boundaries(ie_suggested_price, product, rule)
            change_percent = BoundaryEnforcer.calculate_change_percent(product.current_price, new_price)

            # Override confidence with IE's calibrated confidence
            confidence = ie_result.calibrated_confidence
            ie_was_used = True

            logger.info(
                "Using IE recommendation for product %s: %s → %s (IE conf: %.3f)",
                product.id,
                product.current_price,
                new_price,
                confidence,
            )

        # ══════════════════════════════════════════════════════════════
        # INTELLIGENCE ENVIRONMENT: Build typed agent evidence chains
        # (runs regardless of IE — provides structured evidence for
        #  record_merchant_decision → calibration → backward learning)
        # ══════════════════════════════════════════════════════════════

        try:
            scout_output = PipelineAdapter.build_scout_output(product, signals)
            analyst_output = PipelineAdapter.build_analyst_output(scout_output, confidence_breakdown, signals, rule)
        except Exception as e:
            logger.warning(f"Failed to build Scout/Analyst outputs: {e}")
            scout_output = None
            analyst_output = None

        # Build factors dict (includes typed evidence when available)
        factors = {
            "match_details": match_details,
            "price_impacts": price_impacts,
            "confidence_breakdown": confidence_breakdown,
        }

        # ── Phase 5: Store IE metadata in factors ──
        if ie_was_used and ie_result is not None:
            factors["ie_status"] = ie_result.status.value
            factors["ie_pipeline_version"] = ie_result.pipeline_version
            factors["ie_calibrated_confidence"] = ie_result.calibrated_confidence
            factors["ie_raw_confidence"] = ie_result.raw_confidence
            factors["ie_total_duration_ms"] = ie_result.total_duration_ms

            if ie_result.experiment:
                factors["ie_experiment"] = {
                    "strategy_name": ie_result.experiment.strategy_name,
                    "arm_index": ie_result.experiment.arm_index,
                    "is_exploration": ie_result.experiment.is_exploration,
                }

            if ie_result.calibration:
                factors["ie_calibration"] = {
                    "method": ie_result.calibration.calibration_method,
                    "sample_count": ie_result.calibration.sample_count,
                    "is_reliable": ie_result.calibration.is_reliable,
                }

            if ie_result.warnings:
                factors["ie_warnings"] = ie_result.warnings

            if ie_result.timings:
                factors["ie_timings"] = {
                    t.component: {
                        "duration_ms": t.duration_ms,
                        "success": t.success,
                        "error": t.error,
                    }
                    for t in ie_result.timings
                }

        # Generate reasoning
        reasoning = ReasoningGenerator.generate(product, rule, match_details, new_price, change_percent, signals)

        # Build StrategistOutput (needs reasoning + factors)
        try:
            if analyst_output is not None:
                strategist_output = PipelineAdapter.build_strategist_output(
                    analyst_output,
                    product,
                    new_price,
                    change_percent,
                    confidence,
                    reasoning,
                    factors,
                    rule,
                    raw_price_before_boundaries,
                )
                # Store typed evidence in factors for record_merchant_decision()
                factors["scout_evidence"] = scout_output.to_evidence()
                factors["analyst_evidence"] = analyst_output.to_evidence()
                factors["strategist_evidence"] = strategist_output.to_evidence()
            else:
                strategist_output = None
        except Exception as e:
            logger.warning(f"Failed to build Strategist output: {e}")
            strategist_output = None

        # ══════════════════════════════════════════════════════════════
        # END INTELLIGENCE ENVIRONMENT
        # ══════════════════════════════════════════════════════════════

        # Get settings (Priority 2 fix ensures defaults exist)
        settings = await self.settings_service.get_or_create(user_id)
        valid_until = datetime.now(UTC) + timedelta(hours=settings.recommendation_valid_hours)

        # Check approval requirement
        requires_approval = self.settings_service.check_requires_approval(product, change_percent, confidence, settings)

        # Create recommendation
        recommendation = PriceRecommendation(
            user_id=user_id,
            product_id=product.id,
            triggered_rule_id=rule.id,
            current_price=product.current_price,
            recommended_price=new_price,
            change_percent=change_percent,
            confidence_score=confidence,
            reasoning=reasoning,
            factors=factors,
            status=RecommendationStatus.PENDING,
            requires_approval=requires_approval,
            valid_until=valid_until,
        )

        # Update rule's last_triggered_at
        rule.last_triggered_at = datetime.now(UTC)
        self.db.add(rule)

        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)

        evidence_status = "ie+pipeline" if ie_was_used else ("pipeline" if strategist_output else "partial")
        logger.info(
            f"Recommendation created for product {product.id}: "
            f"${product.current_price} → ${new_price} ({change_percent:+.1f}%), "
            f"confidence={confidence:.2f}, requires_approval={requires_approval}, "
            f"evidence_chain={evidence_status}"
        )

        # Auto-apply if eligible
        if not requires_approval and settings.auto_approve_enabled:
            await self._try_auto_apply(recommendation, user_id)

        return recommendation

    async def _try_auto_apply(self, recommendation: PriceRecommendation, user_id: UUID) -> None:
        """Attempt to auto-approve and apply recommendation."""
        try:
            from services.pricing.approval_service import ApprovalService

            approval_service = ApprovalService(self.db)
            await approval_service.auto_approve_and_apply(recommendation.id, user_id)
            logger.info(f"Auto-applied recommendation {recommendation.id}")
        except Exception as e:
            logger.warning(f"Auto-apply failed for recommendation {recommendation.id}: {e}")

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_pending_recommendations(
        self, user_id: UUID, product_id: UUID | None = None, limit: int = 20, offset: int = 0
    ) -> list[PriceRecommendation]:
        """Get pending recommendations for a user."""
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until > datetime.now(UTC))
        )

        if product_id:
            stmt = stmt.where(PriceRecommendation.product_id == product_id)

        stmt = stmt.order_by(PriceRecommendation.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def expire_old_recommendations(self) -> int:
        """Mark expired recommendations. Returns count of expired."""
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until <= datetime.now(UTC))
        )

        result = await self.db.execute(stmt)
        expired = list(result.scalars().all())

        for rec in expired:
            rec.status = RecommendationStatus.EXPIRED
            self.db.add(rec)

        await self.db.commit()

        logger.info(f"Expired {len(expired)} old recommendations")
        return len(expired)
