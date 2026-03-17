"""
Pipeline Adapter - Bridges existing services to typed agent contracts.

This adapter does NOT replace any existing service. It captures snapshots
from what SignalProcessor, ConfidenceCalculator, RuleEvaluator, and
BoundaryEnforcer already produce, and packages them as typed
ScoutOutput / AnalystOutput / StrategistOutput.

WHY: The intelligence environment needs typed evidence chains stored on
RecommendationOutcome. Without this adapter, the outcome rows have
unstructured dicts in scout_evidence/analyst_evidence/strategist_evidence.
With it, calibration, benchmarking, and backward learning get structured
data to work with.

STRATEGY: Wrap, don't rewrite. When the full Gemini-powered pipeline
replaces the rule-based pipeline, this adapter becomes unnecessary —
the agents will return typed outputs natively. Until then, this bridges
the gap.

Place at: backend/services/pricing/pipeline_adapter.py
"""

from datetime import UTC, datetime
from decimal import Decimal

from schemas.agent_contracts.analyst import (
    AnalystOutput,
    ConfidenceDecomposition,
    ElasticityEstimate,
)
from schemas.agent_contracts.scout import (
    CompetitorPrice,
    ScoutOutput,
    SentimentSnapshot,
)
from schemas.agent_contracts.shared import (
    DataSource,
    PriceDirection,
    UrgencyLevel,
)
from schemas.agent_contracts.strategist import (
    GuardrailCheck,
    StrategistOutput,
)


class PipelineAdapter:
    """
    Static methods to build typed agent outputs from existing services.

    Usage in recommendation_service.py:

        scout_output = PipelineAdapter.build_scout_output(product, signals)
        analyst_output = PipelineAdapter.build_analyst_output(
            scout_output, confidence_breakdown, signals, rule
        )
        strategist_output = PipelineAdapter.build_strategist_output(
            analyst_output, product, new_price, change_percent,
            confidence, reasoning, factors, rule
        )

        # Store typed evidence in factors for record_merchant_decision()
        factors["scout_evidence"] = scout_output.to_evidence()
        factors["analyst_evidence"] = analyst_output.to_evidence()
        factors["strategist_evidence"] = strategist_output.to_evidence()
    """

    # ──────────────────────────────────────────────
    # SCOUT OUTPUT
    # ──────────────────────────────────────────────

    @staticmethod
    def build_scout_output(
        product,
        signals,
    ) -> ScoutOutput:
        """
        Build ScoutOutput from a Product + MarketSignals.

        Maps:
          signals.competitor_prices     → competitors list + count
          signals.sentiment_score       → sentiment snapshot
          signals.mention_count_24h     → sentiment.mention_count
          signals.viral_detected        → sentiment.crisis_detected
          product.current_price         → our_price
        """
        now = datetime.now(UTC)

        # ── Build competitor list ──
        competitors = []
        for comp_id, price in (signals.competitor_prices or {}).items():
            competitors.append(
                CompetitorPrice(
                    competitor_name=str(comp_id),
                    price=price,
                    currency="USD",
                    scraped_at=now,
                )
            )

        competitor_count = len(competitors)

        # ── Calculate competitive position index ──
        competitive_position_index = None
        our_position = None
        if competitors and product.current_price:
            all_prices = sorted([c.price for c in competitors] + [product.current_price])
            if len(all_prices) > 1:
                min_p = float(all_prices[0])
                max_p = float(all_prices[-1])
                if max_p > min_p:
                    competitive_position_index = round(
                        (float(product.current_price) - min_p) / (max_p - min_p),
                        4,
                    )
                else:
                    competitive_position_index = 0.5

                # Determine position label
                if competitive_position_index <= 0.1:
                    our_position = "cheapest"
                elif competitive_position_index <= 0.4:
                    our_position = "below_median"
                elif competitive_position_index <= 0.6:
                    our_position = "at_median"
                elif competitive_position_index <= 0.9:
                    our_position = "above_median"
                else:
                    our_position = "most_expensive"

        # ── Build sentiment snapshot ──
        sentiment = None
        if signals.sentiment_score is not None:
            sentiment = SentimentSnapshot(
                overall_score=float(signals.sentiment_score),
                mention_count=signals.mention_count_24h or 0,
                # Approximate ratios from compound score
                positive_ratio=max(0.0, min(1.0, (float(signals.sentiment_score) + 1) / 2)),
                negative_ratio=max(0.0, min(1.0, 1 - (float(signals.sentiment_score) + 1) / 2)),
                neutral_ratio=0.0,
                crisis_detected=signals.viral_detected
                and (signals.sentiment_score is not None and float(signals.sentiment_score) < -0.5),
            )

        # ── Calculate data completeness ──
        completeness_factors = []
        data_sources = []
        data_gaps = []

        if competitor_count > 0:
            completeness_factors.append(min(competitor_count / 3.0, 1.0))
            data_sources.append(DataSource.COMPETITOR_SCRAPE)
        else:
            completeness_factors.append(0.0)
            data_gaps.append("no_competitor_prices")

        if signals.sentiment_score is not None:
            data_sources.append(DataSource.SOCIAL_SENTIMENT)
            mention_score = min((signals.mention_count_24h or 0) / 25.0, 1.0)
            completeness_factors.append(mention_score)
        else:
            completeness_factors.append(0.0)
            data_gaps.append("no_social_data")

        if signals.is_trending:
            data_sources.append(DataSource.MARKET_TREND)

        data_completeness = sum(completeness_factors) / len(completeness_factors) if completeness_factors else 0.0

        # ── Determine price trend from signals ──
        price_trend = None
        if hasattr(signals, "trend_direction"):
            trend_map = {"up": "rising", "down": "falling", "stable": "stable"}
            price_trend = trend_map.get(signals.trend_direction, "stable")

        return ScoutOutput(
            product_id=product.id,
            scouted_at=now,
            competitors=competitors,
            competitor_count=competitor_count,
            our_price=product.current_price,
            our_position=our_position,
            competitive_position_index=competitive_position_index,
            sentiment=sentiment,
            price_history=[],
            price_trend=price_trend,
            data_completeness=round(data_completeness, 4),
            data_sources=data_sources,
            data_gaps=data_gaps,
            scout_version="1.0-adapter",
        )

    # ──────────────────────────────────────────────
    # ANALYST OUTPUT
    # ──────────────────────────────────────────────

    @staticmethod
    def build_analyst_output(
        scout: ScoutOutput,
        confidence_breakdown: dict,
        signals,
        rule=None,
    ) -> AnalystOutput:
        """
        Build AnalystOutput from ScoutOutput + ConfidenceCalculator breakdown.

        Maps:
          confidence_breakdown.components.data_quality.score      → confidence.data_quality
          confidence_breakdown.components.signal_agreement.score   → confidence.elasticity (proxy)
          confidence_breakdown.components.market_stability.score   → confidence.position
          confidence_breakdown.components.rule_confidence.score    → confidence.urgency
          scout.data_completeness                                  → data_completeness
          scout.competitive_position_index                         → competitive_position_index
          signals.sentiment_score                                  → sentiment_score
        """
        now = datetime.now(UTC)
        components = confidence_breakdown.get("components", {})

        # ── Build confidence decomposition ──
        # Map existing 5-component calculator to the 4-component contract.
        # data_quality maps directly. The others are best-effort proxies
        # until the full Gemini pipeline produces native AnalystOutput.
        data_quality_score = components.get("data_quality", {}).get("score", 0.5)
        signal_agreement_score = components.get("signal_agreement", {}).get("score", 0.5)
        market_stability_score = components.get("market_stability", {}).get("score", 0.5)
        rule_confidence_score = components.get("rule_confidence", {}).get("score", 0.5)
        historical_score = components.get("historical_accuracy", {}).get("score", 0.5)

        confidence = ConfidenceDecomposition(
            elasticity=signal_agreement_score,  # Best proxy: signal agreement
            position=market_stability_score,  # Best proxy: market stability
            urgency=rule_confidence_score,  # Best proxy: rule confidence
            data_quality=data_quality_score,  # Direct map
        )

        # ── Build elasticity estimate (placeholder) ──
        # The current pipeline doesn't estimate elasticity. Use a
        # category-default until the Bayesian hierarchical model is wired.
        elasticity = ElasticityEstimate(
            point_estimate=-1.0,
            method="category_prior",
            prior_source="default",
        )

        # ── Determine urgency ──
        urgency_score = 0.3  # Default: low urgency
        urgency_reasons = []

        if signals.viral_detected:
            urgency_score = max(urgency_score, 0.8)
            urgency_reasons.append("viral_content_detected")

        if signals.sentiment_change_24h is not None:
            change_val = float(signals.sentiment_change_24h)
            if abs(change_val) > 0.2:
                urgency_score = max(urgency_score, 0.7)
                direction = "positive" if change_val > 0 else "negative"
                urgency_reasons.append(f"sentiment_{direction}_spike_{abs(change_val):.0%}")

        if signals.is_trending:
            urgency_score = max(urgency_score, 0.6)
            urgency_reasons.append("trending_detected")

        if scout.competitor_count > 0 and scout.competitive_position_index is not None:
            if scout.competitive_position_index > 0.85:
                urgency_score = max(urgency_score, 0.7)
                urgency_reasons.append("significantly_overpriced")
            elif scout.competitive_position_index < 0.15:
                urgency_score = max(urgency_score, 0.5)
                urgency_reasons.append("significantly_underpriced")

        # Map score to level
        if urgency_score >= 0.8:
            urgency_level = UrgencyLevel.CRITICAL
        elif urgency_score >= 0.6:
            urgency_level = UrgencyLevel.HIGH
        elif urgency_score >= 0.4:
            urgency_level = UrgencyLevel.MEDIUM
        elif urgency_score >= 0.2:
            urgency_level = UrgencyLevel.LOW
        else:
            urgency_level = UrgencyLevel.NONE

        # ── Determine direction ──
        # Infer from the rule that matched
        recommended_direction = PriceDirection.HOLD
        direction_reasoning = "No clear signal for price change."

        if rule is not None:
            rule_action = getattr(rule, "action", None)
            if rule_action is not None:
                action_val = rule_action.value if hasattr(rule_action, "value") else str(rule_action)
                if "increase" in action_val.lower():
                    recommended_direction = PriceDirection.INCREASE
                    direction_reasoning = f"Rule '{rule.name}' triggered price increase."
                elif "decrease" in action_val.lower():
                    recommended_direction = PriceDirection.DECREASE
                    direction_reasoning = f"Rule '{rule.name}' triggered price decrease."
                else:
                    # For set/multiply actions, compare to current price
                    recommended_direction = PriceDirection.HOLD
                    direction_reasoning = f"Rule '{rule.name}' triggered with action '{action_val}'."

        # ── Sentiment interpretation ──
        sentiment_score = None
        sentiment_impact = None
        if signals.sentiment_score is not None:
            sentiment_score = float(signals.sentiment_score)
            if sentiment_score > 0.3:
                sentiment_impact = "supports_increase"
            elif sentiment_score < -0.3:
                sentiment_impact = "suggests_decrease"
            else:
                sentiment_impact = "neutral"

        # ── Market pressure ──
        market_pressure = "no_data"
        if scout.competitive_position_index is not None:
            if scout.competitive_position_index < 0.3:
                market_pressure = "underpriced"
            elif scout.competitive_position_index > 0.7:
                market_pressure = "overpriced"
            else:
                market_pressure = "fairly_priced"

        return AnalystOutput(
            product_id=scout.product_id,
            scout_scouted_at=scout.scouted_at,
            analyzed_at=now,
            elasticity=elasticity,
            confidence=confidence,
            urgency_level=urgency_level,
            urgency_score=urgency_score,
            urgency_reasons=urgency_reasons,
            sentiment_score=sentiment_score,
            sentiment_impact=sentiment_impact,
            competitive_position_index=(
                scout.competitive_position_index if scout.competitive_position_index is not None else 0.5
            ),
            market_pressure=market_pressure,
            recommended_direction=recommended_direction,
            direction_reasoning=direction_reasoning,
            data_completeness=scout.data_completeness,
            competitor_count=scout.competitor_count,
            analyst_version="1.0-adapter",
            model_used="rule_engine",
        )

    # ──────────────────────────────────────────────
    # STRATEGIST OUTPUT
    # ──────────────────────────────────────────────

    @staticmethod
    def build_strategist_output(
        analyst: AnalystOutput,
        product,
        recommended_price: Decimal,
        change_percent: Decimal,
        confidence_score: Decimal,
        reasoning: str,
        factors: dict,
        rule=None,
        raw_price_before_boundaries: Decimal | None = None,
    ) -> StrategistOutput:
        """
        Build StrategistOutput from AnalystOutput + recommendation data.

        Maps:
          recommended_price   → recommended_price
          change_percent      → change_percent
          confidence_score    → confidence_score
          analyst.confidence  → confidence_decomposition
          reasoning           → reasoning
          factors             → factors
        """
        # ── Determine direction ──
        if change_percent > Decimal("0.5"):
            direction = PriceDirection.INCREASE
        elif change_percent < Decimal("-0.5"):
            direction = PriceDirection.DECREASE
        else:
            direction = PriceDirection.HOLD

        # ── Build guardrail checks ──
        guardrails = []
        was_clamped = False

        if raw_price_before_boundaries is not None:
            if raw_price_before_boundaries != recommended_price:
                was_clamped = True
                guardrails.append(
                    GuardrailCheck(
                        name="boundary_enforcement",
                        passed=False,
                        original_value=str(raw_price_before_boundaries),
                        clamped_value=str(recommended_price),
                        reason="Price clamped by min/max boundaries or max_change_percent",
                    )
                )
            else:
                guardrails.append(
                    GuardrailCheck(
                        name="boundary_enforcement",
                        passed=True,
                    )
                )

        if rule is not None:
            min_price = getattr(rule, "min_price", None)
            max_price = getattr(rule, "max_price", None)
            if min_price is not None:
                guardrails.append(
                    GuardrailCheck(
                        name="min_price_floor",
                        passed=recommended_price >= min_price,
                        original_value=str(min_price),
                    )
                )
            if max_price is not None:
                guardrails.append(
                    GuardrailCheck(
                        name="max_price_ceiling",
                        passed=recommended_price <= max_price,
                        original_value=str(max_price),
                    )
                )

        return StrategistOutput(
            product_id=product.id,
            scout_scouted_at=analyst.scout_scouted_at,
            analyst_analyzed_at=analyst.analyzed_at,
            current_price=product.current_price,
            recommended_price=recommended_price,
            change_percent=change_percent,
            change_direction=direction,
            confidence_score=float(confidence_score),
            confidence_decomposition=analyst.confidence,
            reasoning=reasoning,
            factors=factors,
            guardrails_applied=guardrails,
            was_clamped=was_clamped,
            raw_recommended_price=(raw_price_before_boundaries if was_clamped else None),
            pipeline_source="rule_based",
            strategist_version="1.0-adapter",
            model_used="rule_engine",
        )
