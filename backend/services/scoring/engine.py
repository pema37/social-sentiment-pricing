"""
Scoring Engine — Orchestrator for the deterministic scoring pipeline.

Single entry point that replaces PipelineAdapter.build_analyst_output().
Wires ScoutOutput through all four scoring components and produces
a valid AnalystOutput + FusionResult.

Data flow:
  ScoutOutput ──┬──► ElasticityCalculator ──► ElasticityResult ──┐
                ├──► CompetitivePositionCalc ► PositionResult ───┤
                └──► UrgencyScorer ──────────► UrgencyResult ────┤
                                                                  │
                Product + Cost + History ─────────────────────────┤
                                                                  ▼
                                              ScoreFusion ──► FusionResult
                                                                  │
                                              AnalystOutput ◄─────┘

Usage in pipeline_adapter.py or recommendation_service.py:

    engine = ScoringEngine()
    analyst_output, fusion_result = engine.score(
        scout=scout_output,
        signals=market_signals,    # From SignalProcessor
        product_category="electronics",
        product_cost=30.0,
        price_change_history=[...],  # Optional
    )

Phase 2 Scoring Engine — Orchestrator.
Zero LLM calls. Pure Python math.

Place at: backend/services/scoring/engine.py
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from .category_priors import CategoryPriorStore
from .competitive_position import (
    CompetitivePositionCalculator,
    CompetitorPricePoint,
    PositionResult,
)
from .elasticity_calculator import (
    ElasticityCalculator,
    ElasticityResult,
    PriceChangeEvent,
)
from .fusion_types import (
    FusionResult,
    GuardrailConfig,
    PriceChange,
    ProductContext,
)
from .score_fusion import ScoreFusion
from .urgency_scorer import (
    UrgencyResult,
    UrgencyScorer,
    UrgencySignals,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# ──────────────────────────────────────────────────────────
# TYPE ALIASES (for bridge layer)
# ──────────────────────────────────────────────────────────

# These represent the typed agent contracts that engine.py
# produces but doesn't directly import — the caller (pipeline_adapter
# or recommendation_service) is responsible for wrapping the
# engine's output into the Pydantic contract models.
# This keeps engine.py independent of schema imports.


class ScoringEngineResult:
    """
    Complete output of the scoring engine.

    Contains all component results plus pre-built dicts that map
    directly to AnalystOutput fields, so the caller can construct
    the Pydantic model without re-interpreting the math.
    """

    __slots__ = (
        "analyst_fields",
        "elasticity",
        "fusion",
        "position",
        "processing_time_ms",
        "urgency",
    )

    def __init__(
        self,
        elasticity: ElasticityResult,
        position: PositionResult,
        urgency: UrgencyResult,
        fusion: FusionResult,
        analyst_fields: dict,
        processing_time_ms: int,
    ):
        self.elasticity = elasticity
        self.position = position
        self.urgency = urgency
        self.fusion = fusion
        self.analyst_fields = analyst_fields
        self.processing_time_ms = processing_time_ms


# ──────────────────────────────────────────────────────────
# ENGINE
# ──────────────────────────────────────────────────────────


class ScoringEngine:
    """
    Orchestrates the deterministic scoring pipeline.

    Stateless per-call. The only state is the CategoryPriorStore
    which holds research-based priors (updated by Tier 2 batch jobs,
    not by the hot recommendation path).

    Thread-safe for reads. Writes to priors happen only in batch jobs.
    """

    def __init__(
        self,
        guardrail_config: GuardrailConfig | None = None,
        prior_store: CategoryPriorStore | None = None,
    ):
        self._prior_store = prior_store or CategoryPriorStore()
        self._elasticity_calc = ElasticityCalculator(self._prior_store)
        self._position_calc = CompetitivePositionCalculator()
        self._urgency_scorer = UrgencyScorer()
        self._fusion = ScoreFusion(guardrails=guardrail_config)

    def score(
        self,
        scout_output: object,
        signals: object = None,
        product_category: str = "unknown",
        product_cost: float | None = None,
        price_change_history: Sequence[PriceChangeEvent] | None = None,
        recent_price_changes: Sequence[PriceChange] | None = None,
        merchant_bias: float = 0.0,
    ) -> ScoringEngineResult:
        """
        Run the full scoring pipeline.

        Args:
            scout_output: ScoutOutput from PipelineAdapter.build_scout_output().
                Duck-typed to avoid circular import with schemas.
            signals: MarketSignals from SignalProcessor.gather_signals().
                Duck-typed. Optional — urgency will use ScoutOutput data if missing.
            product_category: Product category string for elasticity priors.
            product_cost: Product cost for margin floor guardrail. None = skip margin check.
            price_change_history: Historical price+sales events for Bayesian elasticity.
                Empty = use category prior only (typical for new merchants).
            recent_price_changes: Recent price changes for velocity/rate limit guardrails.
            merchant_bias: -1 to 1. Learned from merchant modification patterns.

        Returns:
            ScoringEngineResult with all component results and pre-built
            AnalystOutput field dict.
        """
        start_ms = time.monotonic_ns() // 1_000_000

        # ── Step 1: Elasticity ──
        elasticity_result = self._compute_elasticity(
            product_category,
            price_change_history,
        )

        # ── Step 2: Competitive Position ──
        position_result = self._compute_position(scout_output)

        # ── Step 3: Urgency ──
        urgency_result = self._compute_urgency(
            scout_output,
            signals,
            position_result,
        )

        # ── Step 4: Score Fusion ──
        product_ctx = ProductContext(
            current_price=self._get_our_price(scout_output),
            cost=product_cost,
            category=product_category,
            recent_changes=list(recent_price_changes or []),
            merchant_bias=merchant_bias,
        )

        sentiment_score = self._get_sentiment_score(scout_output)

        fusion_result = self._fusion.compute(
            elasticity=elasticity_result,
            position=position_result,
            urgency=urgency_result,
            product=product_ctx,
            sentiment_score=sentiment_score,
        )

        # ── Step 5: Build AnalystOutput fields ──
        analyst_fields = self._build_analyst_fields(
            scout_output,
            elasticity_result,
            position_result,
            urgency_result,
            fusion_result,
        )

        elapsed_ms = (time.monotonic_ns() // 1_000_000) - start_ms

        return ScoringEngineResult(
            elasticity=elasticity_result,
            position=position_result,
            urgency=urgency_result,
            fusion=fusion_result,
            analyst_fields=analyst_fields,
            processing_time_ms=elapsed_ms,
        )

    # ──────────────────────────────────────────────
    # COMPONENT DISPATCHERS
    # ──────────────────────────────────────────────

    def _compute_elasticity(
        self,
        category: str,
        events: Sequence[PriceChangeEvent] | None,
    ) -> ElasticityResult:
        """Run the Bayesian elasticity calculator."""
        return self._elasticity_calc.compute(
            category=category,
            price_change_events=events,
        )

    def _compute_position(self, scout: object) -> PositionResult:
        """
        Run the competitive position calculator.

        Bridges ScoutOutput.competitors (CompetitorPrice Pydantic models)
        to CompetitorPricePoint dataclasses.
        """
        our_price = self._get_our_price(scout)
        competitors_raw = getattr(scout, "competitors", []) or []

        comp_points = []
        for c in competitors_raw:
            comp_points.append(
                CompetitorPricePoint(
                    price=float(getattr(c, "price", 0)),
                    scraped_at=getattr(c, "scraped_at", datetime.now(UTC)),
                    competitor_name=getattr(c, "competitor_name", ""),
                    is_on_sale=getattr(c, "is_on_sale", False),
                    sale_price=(float(c.sale_price) if getattr(c, "sale_price", None) is not None else None),
                )
            )

        return self._position_calc.compute(
            our_price=our_price,
            competitors=comp_points,
        )

    def _compute_urgency(
        self,
        scout: object,
        signals: object,
        position: PositionResult,
    ) -> UrgencyResult:
        """
        Run the urgency scorer.

        Bridges ScoutOutput + MarketSignals to UrgencySignals.
        Uses whatever data is available — missing fields are None,
        and the scorer redistributes weights automatically.
        """
        urgency_signals = self._build_urgency_signals(
            scout,
            signals,
            position,
        )
        return self._urgency_scorer.compute(urgency_signals)

    # ──────────────────────────────────────────────
    # BRIDGE HELPERS
    # ──────────────────────────────────────────────

    @staticmethod
    def _get_our_price(scout: object) -> float:
        """Extract our_price from ScoutOutput, handling Decimal."""
        price = getattr(scout, "our_price", 0)
        if isinstance(price, Decimal):
            return float(price)
        return float(price) if price else 0.0

    @staticmethod
    def _get_sentiment_score(scout: object) -> float | None:
        """Extract sentiment score from ScoutOutput.sentiment."""
        sentiment = getattr(scout, "sentiment", None)
        if sentiment is None:
            return None
        score = getattr(sentiment, "overall_score", None)
        return float(score) if score is not None else None

    @staticmethod
    def _build_urgency_signals(
        scout: object,
        signals: object,
        position: PositionResult,
    ) -> UrgencySignals:
        """
        Build UrgencySignals from ScoutOutput + MarketSignals.

        ScoutOutput provides: sentiment, competitor data, data completeness.
        MarketSignals provides: trend velocity, mention growth, momentum.
        PositionResult provides: competitive_position_index.
        """
        # ── Sentiment signals ──
        sentiment_score = None
        sentiment_change = None
        crisis_detected = False
        crisis_severity = None

        sentiment = getattr(scout, "sentiment", None)
        if sentiment is not None:
            sentiment_score = float(getattr(sentiment, "overall_score", 0))
            crisis_detected = getattr(sentiment, "crisis_detected", False)
            crisis_severity = (
                float(sentiment.crisis_severity) if getattr(sentiment, "crisis_severity", None) is not None else None
            )

        if signals is not None:
            raw_change = getattr(signals, "sentiment_change_24h", None)
            if raw_change is not None:
                sentiment_change = float(raw_change)
            # Override crisis from signals if scout didn't catch it
            if not crisis_detected:
                crisis_detected = getattr(signals, "viral_detected", False) and (
                    sentiment_score is not None and sentiment_score < -0.5
                )

        # ── Trend signals ──
        mention_growth = None
        trend_velocity = None
        sentiment_momentum = None
        is_trending = False

        if signals is not None:
            raw_growth = getattr(signals, "mention_growth_rate", None)
            if raw_growth is not None:
                mention_growth = float(raw_growth)

            raw_velocity = getattr(signals, "trend_velocity", None)
            if raw_velocity is not None:
                trend_velocity = float(raw_velocity)

            raw_momentum = getattr(signals, "sentiment_momentum", None)
            if raw_momentum is not None:
                sentiment_momentum = float(raw_momentum)

            is_trending = getattr(signals, "is_trending", False)

        # ── Competitor signals ──
        competitor_count = getattr(scout, "competitor_count", 0)

        return UrgencySignals(
            sentiment_score=sentiment_score,
            sentiment_change_24h=sentiment_change,
            crisis_detected=crisis_detected,
            crisis_severity=crisis_severity,
            mention_growth_rate=mention_growth,
            trend_velocity=trend_velocity,
            sentiment_momentum=sentiment_momentum,
            is_trending=is_trending,
            competitor_count=competitor_count,
            competitive_position_index=position.position_index,
            # Inventory and search signals will be added when those
            # data sources are connected (Phase 3+). UrgencyScorer
            # handles None gracefully via weight redistribution.
            days_of_inventory=None,
            stockout_risk=False,
            search_volume_trend=None,
            search_volume_index=None,
        )

    # ──────────────────────────────────────────────
    # ANALYST OUTPUT FIELD BUILDER
    # ──────────────────────────────────────────────

    @staticmethod
    def _build_analyst_fields(
        scout: object,
        elasticity: ElasticityResult,
        position: PositionResult,
        urgency: UrgencyResult,
        fusion: FusionResult,
    ) -> dict:
        """
        Build a dict that maps directly to AnalystOutput constructor kwargs.

        The caller (pipeline_adapter.py or recommendation_service.py)
        can do:
            analyst_output = AnalystOutput(
                product_id=scout.product_id,
                scout_scouted_at=scout.scouted_at,
                **engine_result.analyst_fields,
            )

        This keeps engine.py independent of the Pydantic schema imports
        while providing a drop-in replacement.
        """
        now = datetime.now(UTC)

        # Map urgency score to level label for the enum
        level_map = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "none": "none",
        }
        urgency_level_value = level_map.get(urgency.level_label, "medium")

        # Map fusion direction to PriceDirection enum value
        direction_map = {
            "increase": "increase",
            "decrease": "decrease",
            "hold": "hold",
        }
        direction_value = direction_map.get(fusion.direction, "hold")

        # Sentiment interpretation
        sentiment_score = None
        sentiment_impact = None
        sentiment = getattr(scout, "sentiment", None)
        if sentiment is not None:
            sentiment_score = float(getattr(sentiment, "overall_score", 0))
            if sentiment_score > 0.3:
                sentiment_impact = "supports_increase"
            elif sentiment_score < -0.3:
                sentiment_impact = "suggests_decrease"
            else:
                sentiment_impact = "neutral"
            # Crisis overrides normal interpretation
            if getattr(sentiment, "crisis_detected", False):
                sentiment_impact = "crisis_override"

        return {
            "analyzed_at": now,
            # Elasticity
            "elasticity": {
                "point_estimate": elasticity.estimate,
                "confidence_interval_low": elasticity.ci_lower,
                "confidence_interval_high": elasticity.ci_upper,
                "method": elasticity.method,
                "prior_source": elasticity.prior_source,
                "sample_size": elasticity.n_observations,
            },
            # Confidence decomposition
            "confidence": {
                "elasticity": elasticity.confidence,
                "position": position.confidence,
                "urgency": urgency.confidence,
                "data_quality": fusion.confidence_components.get("data_quality", 0.5),
            },
            # Urgency
            "urgency_level": urgency_level_value,
            "urgency_score": urgency.score,
            "urgency_reasons": urgency.reasons,
            # Sentiment
            "sentiment_score": sentiment_score,
            "sentiment_impact": sentiment_impact,
            # Position
            "competitive_position_index": position.position_index,
            "market_pressure": position.market_pressure,
            # Direction
            "recommended_direction": direction_value,
            "direction_reasoning": fusion.reasoning,
            # Data quality
            "data_completeness": float(getattr(scout, "data_completeness", 0.0)),
            "competitor_count": position.competitor_count,
            # Metadata
            "analyst_version": "2.0-scoring-engine",
            "processing_time_ms": None,  # Set by caller from engine_result.processing_time_ms
            "model_used": "deterministic_scoring_v1.0",
        }

    # ──────────────────────────────────────────────
    # ADMIN / TIER 2 ACCESS
    # ──────────────────────────────────────────────

    @property
    def prior_store(self) -> CategoryPriorStore:
        """Expose prior store for Tier 2 batch update jobs."""
        return self._prior_store
