"""
Urgency Scorer — Weighted composite of market signals into a single urgency score.

Replaces the ad-hoc max() urgency logic in PipelineAdapter.build_analyst_output()
with a formal weighted composite matching the pricing ontology from the
Intelligence Environment Architecture v2:

    urgency = (sentiment × 0.15) + (trend_velocity × 0.25)
            + (competitor_signal × 0.25) + (inventory_pressure × 0.20)
            + (search_demand × 0.15)

Each signal is normalized to [0, 1] where 1 = maximum urgency to act.
Missing signals are handled by redistributing their weight proportionally
to available signals — so the scorer works from Day 1 even when inventory
and search data aren't yet connected.

UrgencyLevel thresholds (from pricing ontology):
    CRITICAL: > 0.8 — act immediately
    HIGH:    0.6 - 0.8
    MEDIUM:  0.4 - 0.6
    LOW:     0.2 - 0.4
    NONE:    < 0.2 — no urgency

Phase 2 Scoring Engine — Component 3.
Zero LLM calls. Pure Python math.

Place at: backend/services/scoring/urgency_scorer.py
"""

from __future__ import annotations

from dataclasses import dataclass

# ──────────────────────────────────────────────────────────
# SIGNAL INPUTS
# ──────────────────────────────────────────────────────────


@dataclass
class UrgencySignals:
    """
    Raw market signals for urgency calculation.

    Built by engine.py from ScoutOutput + MarketSignals.
    All fields are Optional — the scorer handles missing data gracefully
    by redistributing weight to available signals.

    This means the scorer works from Day 1 when only sentiment and
    competitor data exist. As inventory feeds and search APIs are
    connected, they automatically contribute without code changes.
    """

    # ── Sentiment signals (weight: 15%) ──
    sentiment_score: float | None = None  # -1.0 to 1.0 (Scout compound score)
    sentiment_change_24h: float | None = None  # Delta from previous 24h
    crisis_detected: bool = False  # From Scout crisis detection
    crisis_severity: float | None = None  # 0.0-1.0 if crisis detected

    # ── Trend velocity signals (weight: 25%) ──
    mention_growth_rate: float | None = None  # From SignalProcessor (Decimal as float)
    trend_velocity: float | None = None  # Rate of acceleration (0-1)
    sentiment_momentum: float | None = None  # Direction of sentiment change (-1 to 1)
    is_trending: bool = False  # From SignalProcessor

    # ── Competitor signals (weight: 25%) ──
    competitor_count: int = 0
    # How our position changed: None = unknown, positive = we got more expensive relative to market
    position_change_7d: float | None = None
    # What percentage of competitors changed price in last 7 days
    pct_competitors_changed: float | None = None
    # Average magnitude of competitor price changes
    avg_competitor_change_pct: float | None = None
    # Current position index (0 = cheapest, 1 = most expensive)
    competitive_position_index: float | None = None

    # ── Inventory pressure signals (weight: 20%) ──
    days_of_inventory: float | None = None  # Current stock / avg daily sales
    stockout_risk: bool = False  # < 7 days of inventory

    # ── Search demand signals (weight: 15%) ──
    search_volume_trend: float | None = None  # Rate of change in search volume
    search_volume_index: float | None = None  # Absolute level (normalized 0-1)


# ──────────────────────────────────────────────────────────
# RESULT TYPE
# ──────────────────────────────────────────────────────────


@dataclass
class UrgencyResult:
    """
    Internal result from the urgency scorer.

    Maps to AnalystOutput fields:
      score           → urgency_score
      level           → urgency_level (via level_label)
      reasons         → urgency_reasons
      confidence      → confidence.urgency in ConfidenceDecomposition
      breakdown       → stored in evidence chain for tracing
    """

    score: float  # 0.0-1.0 composite urgency
    level_label: str  # "critical", "high", "medium", "low", "none"
    reasons: list[str]  # Human-readable urgency reasons
    dominant_signal: str  # Which component contributed most
    confidence: float  # 0.0-1.0 how much we trust this score
    breakdown: dict[str, float]  # Per-component scores for transparency
    signals_available: int  # How many of the 5 signals had data
    signals_total: int = 5  # Always 5


# ──────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────

# Canonical weights from Intelligence Environment Architecture v2
WEIGHTS = {
    "sentiment": 0.15,
    "trend_velocity": 0.25,
    "competitor_signal": 0.25,
    "inventory_pressure": 0.20,
    "search_demand": 0.15,
}

# Level thresholds (from pricing ontology)
CRITICAL_THRESHOLD: float = 0.80
HIGH_THRESHOLD: float = 0.60
MEDIUM_THRESHOLD: float = 0.40
LOW_THRESHOLD: float = 0.20

# Sentiment thresholds
SENTIMENT_STRONG_THRESHOLD: float = 0.5  # |score| > this = strong signal
SENTIMENT_MODERATE_THRESHOLD: float = 0.2  # |score| > this = moderate signal

# Trend thresholds
TRENDING_GROWTH_RATE: float = 0.5  # 50% growth rate = significant
STRONG_GROWTH_RATE: float = 1.0  # 100% = very significant

# Competitor activity thresholds
SIGNIFICANT_COMP_CHANGE_PCT: float = 0.30  # 30% of competitors changed
HIGH_COMP_CHANGE_MAGNITUDE: float = 0.05  # 5% avg price change

# Inventory thresholds
CRITICAL_INVENTORY_DAYS: float = 7.0
LOW_INVENTORY_DAYS: float = 14.0
HEALTHY_INVENTORY_DAYS: float = 30.0
OVERSTOCK_INVENTORY_DAYS: float = 90.0


# ──────────────────────────────────────────────────────────
# SCORER
# ──────────────────────────────────────────────────────────


class UrgencyScorer:
    """
    Computes a weighted urgency score from 5 signal components.

    Handles missing signals by redistributing weight proportionally.
    This means: if inventory and search data aren't available (typical
    for new merchants), the remaining 3 signals (sentiment, trend,
    competitor) get their weights boosted proportionally so the total
    still sums to 1.0.

    Usage:
        scorer = UrgencyScorer()
        signals = UrgencySignals(
            sentiment_score=0.7,
            is_trending=True,
            mention_growth_rate=0.8,
            competitor_count=5,
            competitive_position_index=0.85,
        )
        result = scorer.compute(signals)
        # result.score, result.level_label, result.reasons, etc.
    """

    def compute(self, signals: UrgencySignals) -> UrgencyResult:
        """
        Compute urgency from available signals.

        Returns UrgencyResult with score, level, reasons, and breakdown.
        """
        # Compute each component (None = no data for this signal)
        components: dict[str, float | None] = {
            "sentiment": self._score_sentiment(signals),
            "trend_velocity": self._score_trend_velocity(signals),
            "competitor_signal": self._score_competitor_signal(signals),
            "inventory_pressure": self._score_inventory_pressure(signals),
            "search_demand": self._score_search_demand(signals),
        }

        # Separate available from missing
        available = {k: v for k, v in components.items() if v is not None}
        signals_available = len(available)

        if signals_available == 0:
            return UrgencyResult(
                score=0.3,  # Default: low urgency when no data
                level_label="low",
                reasons=["no_market_signals_available"],
                dominant_signal="none",
                confidence=0.0,
                breakdown={k: 0.0 for k in WEIGHTS},
                signals_available=0,
            )

        # Redistribute weights proportionally to available signals
        available_weight_sum = sum(WEIGHTS[k] for k in available)
        effective_weights = {k: WEIGHTS[k] / available_weight_sum for k in available}

        # Compute weighted score
        score = sum(available[k] * effective_weights[k] for k in available)
        score = max(0.0, min(1.0, score))

        # Build breakdown (include zeros for missing signals)
        breakdown = {}
        for k in WEIGHTS:
            if k in available:
                breakdown[k] = round(available[k], 4)
            else:
                breakdown[k] = 0.0

        # Find dominant signal
        dominant = max(available, key=lambda k: available[k])

        # Build reasons
        reasons = self._build_reasons(signals, components)

        # Crisis override: if crisis detected, urgency floor is 0.8
        if signals.crisis_detected:
            score = max(score, 0.8)
            if "crisis_detected" not in [r for r in reasons]:
                reasons.insert(0, "crisis_detected")

        # Classify level
        level_label = self._classify_level(score)

        # Confidence: based on how many signals we have
        confidence = self._compute_confidence(signals_available, signals)

        return UrgencyResult(
            score=round(score, 4),
            level_label=level_label,
            reasons=reasons,
            dominant_signal=dominant,
            confidence=round(confidence, 4),
            breakdown=breakdown,
            signals_available=signals_available,
        )

    # ──────────────────────────────────────────────
    # SIGNAL SCORERS (each returns 0-1 or None)
    # ──────────────────────────────────────────────

    def _score_sentiment(self, signals: UrgencySignals) -> float | None:
        """
        Sentiment urgency: extreme sentiment (positive OR negative) = high urgency.

        Logic:
        - Strong negative → urgency (reputation risk, need to act)
        - Strong positive → urgency (capitalize on buzz)
        - Neutral → low urgency
        - Crisis → maximum urgency
        - Sentiment CHANGE amplifies urgency (rapid shift = something happened)
        """
        if signals.sentiment_score is None:
            return None

        # Base: absolute sentiment = urgency
        # Strong sentiment in either direction means something is happening
        base = abs(signals.sentiment_score)

        # Amplify for rapid change
        change_boost = 0.0
        if signals.sentiment_change_24h is not None:
            # Large swings (>0.2 in 24h) amplify urgency
            change_magnitude = abs(signals.sentiment_change_24h)
            if change_magnitude > 0.2:
                change_boost = min(change_magnitude / 0.5, 0.3)  # Up to 0.3 boost

        # Crisis override
        if signals.crisis_detected:
            crisis_score = signals.crisis_severity if signals.crisis_severity is not None else 0.9
            return max(base + change_boost, crisis_score)

        return min(1.0, base + change_boost)

    def _score_trend_velocity(self, signals: UrgencySignals) -> float | None:
        """
        Trend velocity urgency: rapid acceleration in either direction = urgency.

        Uses mention_growth_rate (primary), trend_velocity (secondary),
        and sentiment_momentum (tertiary).
        """
        has_data = signals.mention_growth_rate is not None or signals.trend_velocity is not None or signals.is_trending
        if not has_data:
            return None

        score = 0.0

        # Primary: mention growth rate (0 = flat, 1.0 = doubled, >1.0 = explosive)
        if signals.mention_growth_rate is not None:
            growth = abs(float(signals.mention_growth_rate))
            # Normalize: 50% growth → 0.5 urgency, 100% → 0.8, 200%+ → 1.0
            if growth >= STRONG_GROWTH_RATE:
                score = max(score, 0.8 + min((growth - STRONG_GROWTH_RATE) / 2.0, 0.2))
            elif growth >= TRENDING_GROWTH_RATE:
                score = max(score, 0.5 + (growth - TRENDING_GROWTH_RATE) / TRENDING_GROWTH_RATE * 0.3)
            else:
                score = max(score, growth / TRENDING_GROWTH_RATE * 0.5)

        # Secondary: velocity (acceleration of change)
        if signals.trend_velocity is not None:
            velocity_score = float(signals.trend_velocity) * 0.8  # Cap at 0.8 from velocity alone
            score = max(score, velocity_score)

        # Tertiary: trending flag as floor
        if signals.is_trending:
            score = max(score, 0.5)

        # Sentiment momentum amplifies
        if signals.sentiment_momentum is not None:
            momentum_magnitude = abs(float(signals.sentiment_momentum))
            if momentum_magnitude > 0.3:
                score = min(1.0, score + 0.1)

        return min(1.0, score)

    def _score_competitor_signal(self, signals: UrgencySignals) -> float | None:
        """
        Competitor urgency: significant competitor activity = urgency.

        Two components:
        1. How many competitors are changing prices (breadth)
        2. How large the changes are (magnitude)

        Also: extreme competitive position = urgency (too cheap or too expensive).
        """
        if signals.competitor_count == 0:
            return None

        score = 0.0
        has_activity_data = False

        # Component 1: Breadth of competitor changes
        if signals.pct_competitors_changed is not None:
            has_activity_data = True
            if signals.pct_competitors_changed >= 0.6:
                score = max(score, 0.9)  # 60%+ changing = very urgent
            elif signals.pct_competitors_changed >= SIGNIFICANT_COMP_CHANGE_PCT:
                score = max(score, 0.5 + signals.pct_competitors_changed * 0.5)
            else:
                score = max(score, signals.pct_competitors_changed)

        # Component 2: Magnitude of changes
        if signals.avg_competitor_change_pct is not None:
            has_activity_data = True
            magnitude = abs(signals.avg_competitor_change_pct)
            if magnitude >= 0.10:  # 10%+ avg change
                score = max(score, 0.8)
            elif magnitude >= HIGH_COMP_CHANGE_MAGNITUDE:
                score = max(score, 0.5 + magnitude * 5.0)
            else:
                score = max(score, magnitude / HIGH_COMP_CHANGE_MAGNITUDE * 0.5)

        # Component 3: Extreme position = urgency
        if signals.competitive_position_index is not None:
            pos = signals.competitive_position_index
            if pos > 0.85:
                # We're very expensive relative to market
                position_urgency = 0.5 + (pos - 0.85) / 0.15 * 0.3
                score = max(score, position_urgency)
            elif pos < 0.15:
                # We're very cheap — potential to increase
                position_urgency = 0.4 + (0.15 - pos) / 0.15 * 0.2
                score = max(score, position_urgency)
            has_activity_data = True

        if not has_activity_data:
            return None

        return min(1.0, score)

    def _score_inventory_pressure(self, signals: UrgencySignals) -> float | None:
        """
        Inventory urgency: running out or overstocked both create urgency.

        Shape: U-curve
        - < 7 days → urgency 0.9-1.0 (running out, price up to manage demand)
        - 7-14 days → 0.5-0.7 (getting low)
        - 14-30 days → 0.2-0.3 (healthy, low urgency)
        - 30-90 days → 0.1-0.2 (comfortable)
        - > 90 days → 0.4-0.6 (overstock, markdown urgency rises)
        """
        if signals.days_of_inventory is None:
            return None

        days = signals.days_of_inventory

        if days <= 0:
            # Stockout
            return 1.0

        if signals.stockout_risk or days < CRITICAL_INVENTORY_DAYS:
            # Critical: running out
            return 0.9 + min((CRITICAL_INVENTORY_DAYS - days) / CRITICAL_INVENTORY_DAYS, 0.1)

        if days < LOW_INVENTORY_DAYS:
            # Low: linearly scale from 0.7 to 0.5
            progress = (days - CRITICAL_INVENTORY_DAYS) / (LOW_INVENTORY_DAYS - CRITICAL_INVENTORY_DAYS)
            return 0.7 - progress * 0.2

        if days <= HEALTHY_INVENTORY_DAYS:
            # Healthy: linearly scale from 0.5 to 0.2
            progress = (days - LOW_INVENTORY_DAYS) / (HEALTHY_INVENTORY_DAYS - LOW_INVENTORY_DAYS)
            return 0.5 - progress * 0.3

        if days <= OVERSTOCK_INVENTORY_DAYS:
            # Comfortable to overstock: low urgency, slowly rising
            progress = (days - HEALTHY_INVENTORY_DAYS) / (OVERSTOCK_INVENTORY_DAYS - HEALTHY_INVENTORY_DAYS)
            return 0.2 + progress * 0.2

        # Severe overstock: markdown urgency
        excess = min((days - OVERSTOCK_INVENTORY_DAYS) / 90.0, 1.0)
        return 0.4 + excess * 0.2

    def _score_search_demand(self, signals: UrgencySignals) -> float | None:
        """
        Search demand urgency: spiking search interest = urgency to optimize price.

        Combines trend (rate of change) with absolute level.
        """
        if signals.search_volume_trend is None and signals.search_volume_index is None:
            return None

        score = 0.0

        # Trend: rate of change matters most
        if signals.search_volume_trend is not None:
            trend_magnitude = abs(signals.search_volume_trend)
            # Normalize: similar to mention growth rate
            score = min(1.0, trend_magnitude / 1.0)  # 100% change → 1.0

        # Absolute level: amplifies trend
        if signals.search_volume_index is not None:
            # High absolute search + positive trend = very urgent
            if signals.search_volume_trend is not None and signals.search_volume_trend > 0:
                score = min(1.0, score + signals.search_volume_index * 0.2)

        return min(1.0, score)

    # ──────────────────────────────────────────────
    # CLASSIFICATION & REASONS
    # ──────────────────────────────────────────────

    @staticmethod
    def _classify_level(score: float) -> str:
        """Map score to UrgencyLevel label."""
        if score >= CRITICAL_THRESHOLD:
            return "critical"
        elif score >= HIGH_THRESHOLD:
            return "high"
        elif score >= MEDIUM_THRESHOLD:
            return "medium"
        elif score >= LOW_THRESHOLD:
            return "low"
        return "none"

    @staticmethod
    def _build_reasons(
        signals: UrgencySignals,
        components: dict[str, float | None],
    ) -> list[str]:
        """Build human-readable urgency reasons from signal scores."""
        reasons = []

        # Crisis is always the top reason
        if signals.crisis_detected:
            severity = f"_{signals.crisis_severity:.0%}" if signals.crisis_severity else ""
            reasons.append(f"crisis_detected{severity}")

        # Sentiment reasons
        sent_score = components.get("sentiment")
        if sent_score is not None and sent_score >= 0.5:
            if signals.sentiment_score is not None:
                if signals.sentiment_score < -0.3:
                    reasons.append("negative_sentiment_high")
                elif signals.sentiment_score > 0.3:
                    reasons.append("positive_sentiment_high")
            if signals.sentiment_change_24h is not None and abs(signals.sentiment_change_24h) > 0.2:
                direction = "positive" if signals.sentiment_change_24h > 0 else "negative"
                reasons.append(f"sentiment_{direction}_spike")

        # Trend reasons
        trend_score = components.get("trend_velocity")
        if trend_score is not None and trend_score >= 0.5:
            if signals.is_trending:
                reasons.append("trending_detected")
            if signals.mention_growth_rate is not None and abs(float(signals.mention_growth_rate)) >= 0.5:
                reasons.append(f"mention_growth_{abs(float(signals.mention_growth_rate)):.0%}")

        # Competitor reasons
        comp_score = components.get("competitor_signal")
        if comp_score is not None and comp_score >= 0.5:
            if signals.competitive_position_index is not None:
                if signals.competitive_position_index > 0.85:
                    reasons.append("significantly_overpriced")
                elif signals.competitive_position_index < 0.15:
                    reasons.append("significantly_underpriced")
            if signals.pct_competitors_changed is not None and signals.pct_competitors_changed >= 0.3:
                reasons.append(f"competitors_changing_prices_{signals.pct_competitors_changed:.0%}")

        # Inventory reasons (lower threshold — overstock is actionable at 0.4+)
        inv_score = components.get("inventory_pressure")
        if inv_score is not None and inv_score >= 0.4 and signals.days_of_inventory is not None:
            if signals.days_of_inventory < CRITICAL_INVENTORY_DAYS:
                reasons.append(f"low_inventory_{signals.days_of_inventory:.0f}_days")
            elif signals.days_of_inventory > OVERSTOCK_INVENTORY_DAYS:
                reasons.append(f"overstock_{signals.days_of_inventory:.0f}_days")

        # Search demand reasons
        search_score = components.get("search_demand")
        if search_score is not None and search_score >= 0.5:
            reasons.append("search_demand_spike")

        return reasons if reasons else ["baseline_urgency"]

    # ──────────────────────────────────────────────
    # CONFIDENCE
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_confidence(signals_available: int, signals: UrgencySignals) -> float:
        """
        Confidence in the urgency score.

        Based on:
        1. How many of the 5 signal types have data (more = better)
        2. Quality of the data (e.g., sentiment with many mentions > few)
        """
        if signals_available == 0:
            return 0.0

        # Base: fraction of signals available (0.2 per signal)
        base = signals_available / 5.0

        # Boost for high-quality signals
        quality_boost = 0.0

        # Sentiment quality: more mentions = better signal
        if signals.sentiment_score is not None:
            # We don't have direct access to mention_count here,
            # but mention_growth_rate being available suggests data richness
            if signals.mention_growth_rate is not None:
                quality_boost += 0.05

        # Competitor quality: more competitors = better signal
        if signals.competitor_count >= 5:
            quality_boost += 0.1
        elif signals.competitor_count >= 3:
            quality_boost += 0.05

        confidence = min(1.0, base + quality_boost)
        return confidence
