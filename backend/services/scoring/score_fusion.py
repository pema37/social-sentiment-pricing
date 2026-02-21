"""
Score Fusion — Combines component scores into a price recommendation.

This is the Strategist's deterministic core. It takes the three scored
outputs (elasticity, position, urgency) and produces a concrete price
recommendation with conflict resolution and guardrail enforcement.

Pipeline:
  1. Component direction votes (elasticity, position, urgency)
  2. Conflict resolution protocols (from IE Architecture v2)
  3. Magnitude computation (elasticity × urgency × position bias)
  4. Guardrail enforcement (delegated to GuardrailEnforcer)
  5. Confidence computation (matching ConfidenceDecomposition weights)
  6. Deterministic reasoning chain

Phase 2 Scoring Engine — Fusion orchestrator.
Zero LLM calls. Pure Python math.

Place at: backend/services/scoring/score_fusion.py
"""

from __future__ import annotations

from typing import Optional

from .elasticity_calculator import ElasticityResult
from .competitive_position import PositionResult
from .urgency_scorer import UrgencyResult
from .fusion_types import (
    ConflictType,
    FusionResult,
    GuardrailConfig,
    ProductContext,
    ELASTICITY_MAGNITUDE,
    URGENCY_MULTIPLIER,
    POSITION_DIRECTION_BIAS,
)
from .guardrails import GuardrailEnforcer


class ScoreFusion:
    """
    Combines component scores into a final price recommendation.

    Usage:
        fusion = ScoreFusion()
        result = fusion.compute(
            elasticity=elasticity_result,
            position=position_result,
            urgency=urgency_result,
            product=product_context,
        )
    """

    def __init__(self, guardrails: Optional[GuardrailConfig] = None):
        self._enforcer = GuardrailEnforcer(guardrails)

    def compute(
        self,
        elasticity: ElasticityResult,
        position: PositionResult,
        urgency: UrgencyResult,
        product: ProductContext,
        sentiment_score: Optional[float] = None,
    ) -> FusionResult:
        """Run the full fusion pipeline."""
        reasoning_steps: list[str] = []
        conflicts: list[ConflictType] = []
        resolutions: list[str] = []

        # ── Step 1: Component direction votes ──
        elast_dir = self._elasticity_direction(elasticity)
        pos_dir = self._position_direction(position)
        urg_dir = self._urgency_direction(urgency)

        reasoning_steps.append(
            f"Component votes: elasticity={elast_dir}, "
            f"position={pos_dir}, urgency={urg_dir}"
        )

        # ── Step 2: Resolve direction conflicts ──
        raw_direction, conflict_info = self._resolve_direction(
            elast_dir, pos_dir, urg_dir,
            elasticity, position, urgency, sentiment_score,
        )
        conflicts.extend(conflict_info["conflicts"])
        resolutions.extend(conflict_info["resolutions"])
        reasoning_steps.extend(conflict_info["steps"])

        # ── Step 3: Low confidence override ──
        overall_conf_prelim = self._compute_overall_confidence(
            elasticity, position, urgency,
        )
        if overall_conf_prelim < 0.3:
            raw_direction = "hold"
            conflicts.append(ConflictType.LOW_CONFIDENCE)
            resolutions.append(
                f"Overall confidence {overall_conf_prelim:.2f} < 0.3 threshold. "
                f"Recommending hold until more data accumulates."
            )
            reasoning_steps.append(
                f"Low confidence override: {overall_conf_prelim:.2f} < 0.3 → hold"
            )

        # ── Step 4: Compute raw magnitude ──
        raw_magnitude_pct = self._compute_magnitude(
            raw_direction, elasticity, position, urgency,
        )

        # Apply conflict damping
        damping = conflict_info.get("magnitude_damping", 1.0)
        raw_magnitude_pct *= damping
        if damping < 1.0:
            reasoning_steps.append(
                f"Conflict damping applied: magnitude × {damping:.0%}"
            )

        # Apply merchant bias
        if product.merchant_bias != 0.0:
            bias_factor = 1.0 + (product.merchant_bias * 0.2)
            raw_magnitude_pct *= bias_factor
            reasoning_steps.append(
                f"Merchant bias adjustment: × {bias_factor:.2f}"
            )

        # Compute raw price
        if raw_direction == "increase":
            raw_change_pct = abs(raw_magnitude_pct)
        elif raw_direction == "decrease":
            raw_change_pct = -abs(raw_magnitude_pct)
        else:
            raw_change_pct = 0.0

        raw_price = product.current_price * (1.0 + raw_change_pct)
        reasoning_steps.append(
            f"Raw recommendation: {product.current_price:.2f} → {raw_price:.2f} "
            f"({raw_change_pct:+.2%})"
        )

        # ── Step 5: Apply guardrails ──
        final_price, guardrail_results, was_clamped = self._enforcer.apply(
            raw_price, raw_change_pct, product,
        )

        if was_clamped:
            reasoning_steps.append(
                f"Guardrails applied: {raw_price:.2f} → {final_price:.2f}"
            )

        # Final change percentage
        if product.current_price > 0:
            final_change_pct = (final_price - product.current_price) / product.current_price
        else:
            final_change_pct = 0.0

        # Final direction (may differ from raw if guardrails clamped to hold)
        if abs(final_change_pct) < 0.005:
            final_direction = "hold"
        elif final_change_pct > 0:
            final_direction = "increase"
        else:
            final_direction = "decrease"

        # ── Step 6: Confidence ──
        confidence_components = {
            "elasticity": elasticity.confidence,
            "position": position.confidence,
            "urgency": urgency.confidence,
            "data_quality": self._data_quality_score(elasticity, position, urgency),
        }
        overall_confidence = self._compute_overall_confidence(
            elasticity, position, urgency,
        )

        # Reduce confidence if conflicts detected
        if conflicts:
            conflict_penalty = 0.05 * len(conflicts)
            overall_confidence = max(0.1, overall_confidence - conflict_penalty)

        # ── Step 7: Build reasoning ──
        needs_review = any(
            c in (ConflictType.POSITION_VS_SENTIMENT, ConflictType.LOW_CONFIDENCE)
            for c in conflicts
        )
        suggest_data = overall_confidence < 0.4 or elasticity.n_observations == 0

        reasoning = self._build_reasoning(
            final_direction, final_change_pct, product,
            elasticity, position, urgency,
            conflicts, was_clamped,
        )

        return FusionResult(
            recommended_price=round(final_price, 2),
            change_pct=round(final_change_pct, 4),
            direction=final_direction,
            raw_price=round(raw_price, 2),
            raw_change_pct=round(raw_change_pct, 4),
            raw_direction=raw_direction,
            confidence=round(overall_confidence, 4),
            confidence_components=confidence_components,
            conflicts_detected=conflicts,
            conflict_resolutions=resolutions,
            guardrails=guardrail_results,
            was_clamped=was_clamped,
            reasoning=reasoning,
            reasoning_steps=reasoning_steps,
            needs_manual_review=needs_review,
            suggest_data_collection=suggest_data,
        )

    # ──────────────────────────────────────────────
    # DIRECTION VOTES
    # ──────────────────────────────────────────────

    @staticmethod
    def _elasticity_direction(e: ElasticityResult) -> str:
        """
        Elasticity-implied direction.

        Elasticity primarily tells us HOW MUCH the market can tolerate,
        not WHICH WAY to go. But very inelastic demand is a soft signal
        that a price increase is safe. Very elastic demand is a soft
        signal to be cautious (hold rather than change).
        """
        ped = abs(e.estimate)
        if ped < 0.6 and e.confidence > 0.5:
            return "increase"   # Inelastic + confident: safe to raise
        elif ped > 2.0 and e.confidence > 0.5:
            return "decrease"   # Very elastic + confident: consider lowering
        return "hold"           # Moderate or uncertain: no direction from elasticity

    @staticmethod
    def _position_direction(p: PositionResult) -> str:
        """
        Position-implied direction. This is the PRIMARY directional signal.

        Underpriced = room to increase. Overpriced = need to decrease.
        Fairly priced = hold.
        """
        if p.market_pressure == "underpriced":
            return "increase"
        elif p.market_pressure == "overpriced":
            return "decrease"
        return "hold"

    @staticmethod
    def _urgency_direction(u: UrgencyResult) -> str:
        """
        Urgency-implied direction.

        Urgency primarily amplifies HOW FAST to act, but specific
        urgency reasons carry directional information.
        """
        if u.score < 0.2:
            return "hold"

        # Check reasons for directional hints
        for reason in u.reasons:
            if "low_inventory" in reason or "stockout" in reason:
                return "increase"
            if "overstock" in reason:
                return "decrease"
            if "significantly_overpriced" in reason:
                return "decrease"
            if "significantly_underpriced" in reason:
                return "increase"
            if "negative_sentiment" in reason:
                return "decrease"
            if "positive_sentiment" in reason:
                return "increase"

        return "hold"

    # ──────────────────────────────────────────────
    # CONFLICT RESOLUTION
    # ──────────────────────────────────────────────

    @staticmethod
    def _resolve_direction(
        elast_dir: str,
        pos_dir: str,
        urg_dir: str,
        elasticity: ElasticityResult,
        position: PositionResult,
        urgency: UrgencyResult,
        sentiment_score: Optional[float],
    ) -> tuple[str, dict]:
        """
        Apply conflict resolution protocols from IE Architecture v2.

        Returns (resolved_direction, conflict_info_dict).
        """
        conflicts: list[ConflictType] = []
        resolutions: list[str] = []
        steps: list[str] = []
        damping = 1.0

        votes = [elast_dir, pos_dir, urg_dir]
        increase_votes = votes.count("increase")
        decrease_votes = votes.count("decrease")
        hold_votes = votes.count("hold")

        # ── Protocol 1: Elasticity INCREASE + urgency HOLD ──
        if elast_dir == "increase" and urg_dir == "hold":
            if elasticity.confidence > 0.7 and urgency.score < 0.5:
                conflicts.append(ConflictType.ELASTICITY_VS_URGENCY)
                resolutions.append(
                    "Elasticity suggests increase but urgency is low. "
                    "Proceeding with increase at 50% magnitude."
                )
                steps.append(
                    "Conflict: elasticity↑ vs urgency→ | Resolution: magnitude × 50%"
                )
                damping = 0.5

        # ── Protocol 2: Position cheapest + sentiment negative ──
        if position.market_pressure == "underpriced" and sentiment_score is not None:
            if sentiment_score < -0.3:
                conflicts.append(ConflictType.POSITION_VS_SENTIMENT)
                resolutions.append(
                    "We're the cheapest but sentiment is negative. "
                    "Possible quality perception issue — holding price for manual review."
                )
                steps.append(
                    "Conflict: cheapest + negative sentiment | Resolution: hold + manual review"
                )
                return "hold", {
                    "conflicts": conflicts,
                    "resolutions": resolutions,
                    "steps": steps,
                    "magnitude_damping": 0.0,
                }

        # ── Protocol 3: Contradictory signals ──
        if increase_votes > 0 and decrease_votes > 0:
            conflicts.append(ConflictType.CONTRADICTORY_SIGNALS)

            confidences = {"increase": 0.0, "decrease": 0.0}
            if elast_dir == "increase":
                confidences["increase"] += elasticity.confidence
            elif elast_dir == "decrease":
                confidences["decrease"] += elasticity.confidence

            if pos_dir == "increase":
                confidences["increase"] += position.confidence
            elif pos_dir == "decrease":
                confidences["decrease"] += position.confidence

            if urg_dir == "increase":
                confidences["increase"] += urgency.confidence
            elif urg_dir == "decrease":
                confidences["decrease"] += urgency.confidence

            if confidences["increase"] >= confidences["decrease"]:
                winner = "increase"
            else:
                winner = "decrease"

            resolutions.append(
                f"Contradictory signals: increase conf={confidences['increase']:.2f}, "
                f"decrease conf={confidences['decrease']:.2f}. "
                f"Higher confidence ({winner}) wins at 70% magnitude."
            )
            steps.append(
                f"Conflict: contradictory | Winner: {winner} "
                f"(conf {confidences[winner]:.2f}) | Damping: 70%"
            )
            damping = min(damping, 0.7)
            return winner, {
                "conflicts": conflicts,
                "resolutions": resolutions,
                "steps": steps,
                "magnitude_damping": damping,
            }

        # ── No conflict: majority vote ──
        if increase_votes > decrease_votes and increase_votes > hold_votes:
            direction = "increase"
        elif decrease_votes > increase_votes and decrease_votes > hold_votes:
            direction = "decrease"
        elif increase_votes == decrease_votes and increase_votes > 0:
            direction = "hold"
            steps.append("Direction tie: increase=decrease → conservative hold")
        else:
            direction = "hold"

        if not steps:
            steps.append(
                f"Direction vote: increase={increase_votes}, "
                f"decrease={decrease_votes}, hold={hold_votes} → {direction}"
            )

        return direction, {
            "conflicts": conflicts,
            "resolutions": resolutions,
            "steps": steps,
            "magnitude_damping": damping,
        }

    # ──────────────────────────────────────────────
    # MAGNITUDE COMPUTATION
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_magnitude(
        direction: str,
        elasticity: ElasticityResult,
        position: PositionResult,
        urgency: UrgencyResult,
    ) -> float:
        """
        Compute the raw magnitude of price change (before guardrails).

        Three factors:
          1. Elasticity → base magnitude (how much can the market tolerate?)
          2. Urgency → multiplier (how fast should we move?)
          3. Position → directional bias (amplify/dampen based on where we sit)
        """
        if direction == "hold":
            return 0.0

        # 1. Base magnitude from elasticity
        ped = abs(elasticity.estimate)
        if ped > 2.0:
            level = "highly_elastic"
        elif ped > 1.0:
            level = "elastic"
        elif ped > 0.8:
            level = "unit_elastic"
        elif ped > 0.5:
            level = "inelastic"
        else:
            level = "highly_inelastic"

        inc_base, dec_base = ELASTICITY_MAGNITUDE[level]
        base_magnitude = inc_base if direction == "increase" else dec_base

        # 2. Urgency multiplier
        urg_mult = URGENCY_MULTIPLIER.get(urgency.level_label, 1.0)
        magnitude = base_magnitude * urg_mult

        # 3. Position bias
        bias_table = POSITION_DIRECTION_BIAS.get(
            position.market_pressure, POSITION_DIRECTION_BIAS["no_data"]
        )
        pos_mult = bias_table.get(direction, 1.0)
        magnitude *= pos_mult

        # 4. Gap-based adjustment: limit the move to close no more
        #    than half the gap per change.
        if position.gap_to_median_pct != 0 and position.competitor_count > 0:
            gap_magnitude = abs(position.gap_to_median_pct) / 100.0 * 0.5
            if direction == "increase" and position.market_pressure == "underpriced":
                magnitude = min(magnitude, gap_magnitude)
            elif direction == "decrease" and position.market_pressure == "overpriced":
                magnitude = min(magnitude, gap_magnitude)

        return magnitude

    # ──────────────────────────────────────────────
    # CONFIDENCE
    # ──────────────────────────────────────────────

    def _compute_overall_confidence(
        self,
        elasticity: ElasticityResult,
        position: PositionResult,
        urgency: UrgencyResult,
    ) -> float:
        """
        Overall confidence matching ConfidenceDecomposition weights:
          elasticity: 30%, position: 25%, urgency: 20%, data_quality: 25%
        """
        dq = self._data_quality_score(elasticity, position, urgency)
        return (
            elasticity.confidence * 0.30
            + position.confidence * 0.25
            + urgency.confidence * 0.20
            + dq * 0.25
        )

    @staticmethod
    def _data_quality_score(
        elasticity: ElasticityResult,
        position: PositionResult,
        urgency: UrgencyResult,
    ) -> float:
        """
        Data quality score for ConfidenceDecomposition.data_quality.

        Composite of:
        - Did we have elasticity observations? (vs pure prior)
        - How many competitors? (more = better)
        - How many urgency signals? (more = better)
        """
        if elasticity.n_observations >= 5:
            e_quality = 1.0
        elif elasticity.n_observations >= 1:
            e_quality = 0.4 + elasticity.n_observations * 0.12
        else:
            e_quality = 0.2

        if position.competitor_count >= 5:
            p_quality = 1.0
        elif position.competitor_count >= 3:
            p_quality = 0.7
        elif position.competitor_count >= 1:
            p_quality = 0.4
        else:
            p_quality = 0.1

        u_quality = urgency.signals_available / urgency.signals_total

        return round((e_quality + p_quality + u_quality) / 3.0, 4)

    # ──────────────────────────────────────────────
    # REASONING
    # ──────────────────────────────────────────────

    @staticmethod
    def _build_reasoning(
        direction: str,
        change_pct: float,
        product: ProductContext,
        elasticity: ElasticityResult,
        position: PositionResult,
        urgency: UrgencyResult,
        conflicts: list[ConflictType],
        was_clamped: bool,
    ) -> str:
        """Build a human-readable reasoning string (deterministic, no LLM)."""
        parts = []

        # Direction rationale
        if direction == "hold":
            parts.append("Recommending HOLD on current price.")
            if any(c == ConflictType.LOW_CONFIDENCE for c in conflicts):
                parts.append("Insufficient data confidence to recommend a change.")
            elif any(c == ConflictType.POSITION_VS_SENTIMENT for c in conflicts):
                parts.append(
                    "Although competitively underpriced, negative sentiment "
                    "suggests a potential quality perception issue."
                )
        elif direction == "increase":
            parts.append(f"Recommending {abs(change_pct):.1%} price INCREASE.")
        else:
            parts.append(f"Recommending {abs(change_pct):.1%} price DECREASE.")

        # Elasticity context
        ped = abs(elasticity.estimate)
        if ped > 1.5:
            parts.append(
                f"Demand is elastic (PED={elasticity.estimate:.2f}) — "
                f"customers are price-sensitive."
            )
        elif ped < 0.7:
            parts.append(
                f"Demand is inelastic (PED={elasticity.estimate:.2f}) — "
                f"pricing power is strong."
            )
        else:
            parts.append(
                f"Demand has moderate elasticity (PED={elasticity.estimate:.2f})."
            )

        # Position context
        if position.market_pressure == "underpriced":
            parts.append(
                f"Competitively positioned below "
                f"{(1 - position.position_index) * 100:.0f}% "
                f"of {position.competitor_count} competitors."
            )
        elif position.market_pressure == "overpriced":
            parts.append(
                f"Competitively positioned above "
                f"{position.position_index * 100:.0f}% "
                f"of {position.competitor_count} competitors."
            )
        elif position.competitor_count > 0:
            parts.append(
                f"Fairly positioned among {position.competitor_count} "
                f"competitors (CPI={position.cpi:.0f})."
            )

        # Urgency context
        if urgency.score >= 0.6:
            parts.append(
                f"Urgency is {urgency.level_label} ({urgency.score:.2f})."
            )
            if urgency.reasons:
                parts.append(f"Drivers: {', '.join(urgency.reasons[:3])}.")

        # Guardrail note
        if was_clamped:
            parts.append("Price was adjusted by guardrail constraints.")

        # Confidence note
        conf = (
            elasticity.confidence * 0.30
            + position.confidence * 0.25
            + urgency.confidence * 0.20
            + 0.5 * 0.25
        )
        if conf < 0.4:
            parts.append(
                "Confidence is low — consider gathering more data before acting."
            )

        return " ".join(parts)
    


    