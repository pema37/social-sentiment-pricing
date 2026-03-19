"""
Competitive Position Index — Percentile ranking against scraped competitor prices.

Replaces the simple min-max normalization in PipelineAdapter.build_scout_output()
with proper percentile ranking, outlier filtering, staleness detection,
and freshness-weighted confidence scoring.

Formulas (from Intelligence Environment Architecture v2):
  CPI = (Avg Competitor Price / Our Price) × 100
  Percentile = (competitors priced above us / total competitors) × 100

Output convention (matches AnalystOutput contract):
  competitive_position_index: 0.0 = cheapest in market, 1.0 = most expensive
  market_pressure: "underpriced" / "fairly_priced" / "overpriced" / "no_data"

Phase 2 Scoring Engine — Component 2.
Zero LLM calls. Pure Python math.

Place at: backend/services/scoring/competitive_position.py
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# ──────────────────────────────────────────────────────────
# INPUT TYPE
# ──────────────────────────────────────────────────────────


@dataclass
class CompetitorPricePoint:
    """
    A competitor's price observation for position calculation.

    Built from ScoutOutput.competitors (CompetitorPrice objects).
    The engine.py orchestrator converts CompetitorPrice → CompetitorPricePoint.
    """

    price: float
    scraped_at: datetime
    competitor_name: str = ""
    is_on_sale: bool = False
    sale_price: float | None = None

    @property
    def effective_price(self) -> float:
        """Use sale price if available and item is on sale."""
        if self.is_on_sale and self.sale_price is not None:
            return self.sale_price
        return self.price

    def age_hours(self, reference_time: datetime | None = None) -> float:
        """Hours since this price was scraped."""
        ref = reference_time or datetime.now(UTC)
        delta = ref - self.scraped_at
        return delta.total_seconds() / 3600.0


# ──────────────────────────────────────────────────────────
# RESULT TYPE
# ──────────────────────────────────────────────────────────


@dataclass
class PositionResult:
    """
    Internal result from the competitive position calculator.

    Maps to AnalystOutput fields:
      percentile          → competitive_position_index (divided by 100)
      direction           → feeds into recommended_direction logic
      market_pressure     → market_pressure
      confidence          → confidence.position in ConfidenceDecomposition
    """

    # Core position
    percentile: float  # 0-100. Higher = more expensive relative to competitors
    position_index: float  # 0.0-1.0 (percentile / 100). For AnalystOutput.competitive_position_index
    market_pressure: str  # "underpriced", "fairly_priced", "overpriced", "no_data"

    # Price gaps (for magnitude calculation in score_fusion)
    our_price: float
    median_competitor_price: float
    avg_competitor_price: float
    gap_to_median_pct: float  # (our_price - median) / median * 100. Positive = we're more expensive
    gap_to_cheapest_pct: float  # (our_price - cheapest) / cheapest * 100
    gap_to_most_expensive_pct: float  # (our_price - most_expensive) / most_expensive * 100

    # CPI (from architecture doc)
    cpi: float  # (avg_competitor_price / our_price) * 100. >100 = we're cheaper

    # Data quality
    competitor_count: int  # After filtering
    competitors_removed: int  # Stale + outliers removed
    confidence: float  # 0.0-1.0

    # Position label (matches ScoutOutput.our_position)
    position_label: str  # "cheapest", "below_median", "at_median", "above_median", "most_expensive"


# ──────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────

# Staleness: prices older than this are excluded
DEFAULT_MAX_AGE_HOURS: float = 168.0  # 7 days

# Freshness decay: confidence degrades as prices age
FULL_FRESHNESS_HOURS: float = 24.0  # < 24h old = full freshness
HALF_FRESHNESS_HOURS: float = 96.0  # 4 days = 50% freshness weight

# Outlier filtering: prices beyond this many std devs from median are excluded
OUTLIER_STD_DEVS: float = 3.0

# Minimum competitors for meaningful position
MIN_COMPETITORS_FOR_CONFIDENCE: int = 3  # Below this, confidence is degraded
IDEAL_COMPETITORS: int = 5  # At this point, competitor count stops boosting confidence

# Market pressure thresholds (on position_index 0.0-1.0)
UNDERPRICED_THRESHOLD: float = 0.30  # Below 30th percentile
OVERPRICED_THRESHOLD: float = 0.70  # Above 70th percentile

# Position label thresholds
CHEAPEST_THRESHOLD: float = 0.10
BELOW_MEDIAN_THRESHOLD: float = 0.40
AT_MEDIAN_UPPER: float = 0.60
ABOVE_MEDIAN_UPPER: float = 0.90


# ──────────────────────────────────────────────────────────
# CALCULATOR
# ──────────────────────────────────────────────────────────


class CompetitivePositionCalculator:
    """
    Computes competitive position as a percentile rank among competitor prices.

    Improvements over the current PipelineAdapter:
      1. Percentile rank instead of min-max normalization
         (min-max is distorted by a single extreme price)
      2. Stale price filtering (>7 days old excluded)
      3. Outlier removal (>3 std devs from median)
      4. Freshness-weighted confidence
      5. Price gap metrics for magnitude calculation
      6. CPI calculation per architecture doc

    Usage:
        calc = CompetitivePositionCalculator()
        result = calc.compute(
            our_price=49.99,
            competitors=[CompetitorPricePoint(price=44.99, ...), ...],
        )
    """

    def __init__(
        self,
        max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
        outlier_std_devs: float = OUTLIER_STD_DEVS,
    ):
        self._max_age_hours = max_age_hours
        self._outlier_std_devs = outlier_std_devs

    def compute(
        self,
        our_price: float,
        competitors: Sequence[CompetitorPricePoint],
        reference_time: datetime | None = None,
    ) -> PositionResult:
        """
        Compute competitive position for a product.

        Args:
            our_price: The merchant's current price.
            competitors: Competitor price observations from Scout.
            reference_time: Time reference for staleness checks (default: now).

        Returns:
            PositionResult with percentile, gaps, CPI, and confidence.
        """
        ref_time = reference_time or datetime.now(UTC)

        if our_price <= 0:
            return self._no_data_result(our_price)

        if not competitors:
            return self._no_data_result(our_price)

        # Step 1: Filter stale prices
        fresh = self._filter_stale(competitors, ref_time)

        # Step 2: Filter outliers (need at least 3 for stats)
        filtered, removed_count = self._filter_outliers(fresh)
        total_removed = (len(competitors) - len(fresh)) + removed_count

        if not filtered:
            return self._no_data_result(our_price, competitors_removed=total_removed)

        # Step 3: Extract effective prices
        comp_prices = [c.effective_price for c in filtered]

        # Step 4: Compute percentile rank
        # Percentile = (competitors priced ABOVE us / total competitors) × 100
        # Higher percentile = more competitors are above us = we're cheaper
        # But AnalystOutput convention: 0.0 = cheapest, 1.0 = most expensive
        # So we invert: position_index = 1 - (priced_above / total)
        sum(1 for p in comp_prices if p > our_price)
        priced_equal = sum(1 for p in comp_prices if abs(p - our_price) < 0.01)
        total = len(comp_prices)

        # Standard competition ranking percentile with tie handling
        # Position = fraction of competitors we are more expensive than
        priced_below = sum(1 for p in comp_prices if p < our_price)
        percentile_rank = ((priced_below + 0.5 * priced_equal) / total) * 100.0
        position_index = percentile_rank / 100.0

        # Clamp to [0, 1]
        position_index = max(0.0, min(1.0, position_index))
        percentile_rank = max(0.0, min(100.0, percentile_rank))

        # Step 5: Compute price gaps
        median_price = statistics.median(comp_prices)
        avg_price = statistics.mean(comp_prices)
        cheapest = min(comp_prices)
        most_expensive = max(comp_prices)

        gap_to_median = ((our_price - median_price) / median_price * 100.0) if median_price > 0 else 0.0
        gap_to_cheapest = ((our_price - cheapest) / cheapest * 100.0) if cheapest > 0 else 0.0
        gap_to_most_expensive = ((our_price - most_expensive) / most_expensive * 100.0) if most_expensive > 0 else 0.0

        # Step 6: CPI per architecture doc
        # CPI = (avg_competitor_price / our_price) * 100
        # >100 means competitors are more expensive (we're cheaper)
        # <100 means competitors are cheaper (we're more expensive)
        cpi = (avg_price / our_price) * 100.0

        # Step 7: Market pressure
        market_pressure = self._classify_pressure(position_index)

        # Step 8: Position label (matches ScoutOutput.our_position)
        position_label = self._classify_label(position_index)

        # Step 9: Confidence score
        confidence = self._compute_confidence(filtered, total_removed, ref_time)

        return PositionResult(
            percentile=round(percentile_rank, 2),
            position_index=round(position_index, 4),
            market_pressure=market_pressure,
            our_price=our_price,
            median_competitor_price=round(median_price, 2),
            avg_competitor_price=round(avg_price, 2),
            gap_to_median_pct=round(gap_to_median, 2),
            gap_to_cheapest_pct=round(gap_to_cheapest, 2),
            gap_to_most_expensive_pct=round(gap_to_most_expensive, 2),
            cpi=round(cpi, 2),
            competitor_count=total,
            competitors_removed=total_removed,
            confidence=round(confidence, 4),
            position_label=position_label,
        )

    # ──────────────────────────────────────────────
    # FILTERING
    # ──────────────────────────────────────────────

    def _filter_stale(
        self,
        competitors: Sequence[CompetitorPricePoint],
        ref_time: datetime,
    ) -> list[CompetitorPricePoint]:
        """Remove prices older than max_age_hours."""
        return [c for c in competitors if c.age_hours(ref_time) <= self._max_age_hours and c.effective_price > 0]

    def _filter_outliers(
        self,
        competitors: list[CompetitorPricePoint],
    ) -> tuple[list[CompetitorPricePoint], int]:
        """
        Remove price outliers using IQR (Interquartile Range) method.

        IQR is preferred over stdev because stdev is inflated by the
        very outliers we're trying to detect. IQR is robust — the
        extreme values don't affect the quartile boundaries.

        Bounds: [Q1 - multiplier*IQR, Q3 + multiplier*IQR]
        Default multiplier (outlier_std_devs) of 3.0 is conservative
        — only catches extreme outliers like bad scrape data.

        Returns (filtered_list, count_removed).
        Needs at least 3 competitors to compute meaningful statistics.
        """
        if len(competitors) < 3:
            return competitors, 0

        prices = sorted(c.effective_price for c in competitors)
        n = len(prices)

        # Compute Q1 and Q3 (using linear interpolation)
        q1_idx = (n - 1) * 0.25
        q3_idx = (n - 1) * 0.75

        q1 = self._interpolate_percentile(prices, q1_idx)
        q3 = self._interpolate_percentile(prices, q3_idx)

        iqr = q3 - q1
        if iqr == 0:
            # All prices are very similar — no outliers to remove
            return competitors, 0

        lower_bound = q1 - self._outlier_std_devs * iqr
        upper_bound = q3 + self._outlier_std_devs * iqr

        filtered = [c for c in competitors if lower_bound <= c.effective_price <= upper_bound]
        removed = len(competitors) - len(filtered)
        return filtered, removed

    @staticmethod
    def _interpolate_percentile(sorted_prices: list[float], idx: float) -> float:
        """Linear interpolation for percentile calculation."""
        lower = int(idx)
        upper = min(lower + 1, len(sorted_prices) - 1)
        fraction = idx - lower
        return sorted_prices[lower] + fraction * (sorted_prices[upper] - sorted_prices[lower])

    # ──────────────────────────────────────────────
    # CLASSIFICATION
    # ──────────────────────────────────────────────

    @staticmethod
    def _classify_pressure(position_index: float) -> str:
        """Map position index to market pressure label."""
        if position_index < UNDERPRICED_THRESHOLD:
            return "underpriced"
        elif position_index > OVERPRICED_THRESHOLD:
            return "overpriced"
        return "fairly_priced"

    @staticmethod
    def _classify_label(position_index: float) -> str:
        """Map position index to ScoutOutput.our_position label."""
        if position_index <= CHEAPEST_THRESHOLD:
            return "cheapest"
        elif position_index <= BELOW_MEDIAN_THRESHOLD:
            return "below_median"
        elif position_index <= AT_MEDIAN_UPPER:
            return "at_median"
        elif position_index <= ABOVE_MEDIAN_UPPER:
            return "above_median"
        return "most_expensive"

    # ──────────────────────────────────────────────
    # CONFIDENCE
    # ──────────────────────────────────────────────

    def _compute_confidence(
        self,
        competitors: list[CompetitorPricePoint],
        removed_count: int,
        ref_time: datetime,
    ) -> float:
        """
        Confidence in competitive position based on:
          1. Competitor count (more = better, up to IDEAL_COMPETITORS)
          2. Data freshness (newer = better)
          3. Removal ratio (high removal = noisy data)

        Returns 0.0-1.0.
        """
        count = len(competitors)
        if count == 0:
            return 0.0

        # Factor 1: Competitor count (0.0-1.0)
        # 1 competitor = 0.33, 3 = 1.0, 5+ = 1.0
        count_factor = min(count / MIN_COMPETITORS_FOR_CONFIDENCE, 1.0)

        # Factor 2: Average freshness (0.5-1.0)
        # < 24h old = 1.0, 96h = 0.5, 168h = ~0.3
        avg_age = statistics.mean([c.age_hours(ref_time) for c in competitors])
        if avg_age <= FULL_FRESHNESS_HOURS:
            freshness_factor = 1.0
        elif avg_age >= self._max_age_hours:
            freshness_factor = 0.3
        else:
            # Exponential decay between full freshness and max age
            decay_range = self._max_age_hours - FULL_FRESHNESS_HOURS
            progress = (avg_age - FULL_FRESHNESS_HOURS) / decay_range
            freshness_factor = 1.0 - 0.7 * progress  # Decays from 1.0 to 0.3

        # Factor 3: Removal ratio (1.0 = nothing removed, lower if lots removed)
        total_original = count + removed_count
        if total_original > 0:
            kept_ratio = count / total_original
            removal_factor = max(0.5, kept_ratio)  # Floor at 0.5
        else:
            removal_factor = 1.0

        # Combine: geometric-ish weighting
        # Count matters most, freshness second, removal third
        confidence = count_factor * 0.50 + freshness_factor * 0.35 + removal_factor * 0.15

        return max(0.0, min(1.0, confidence))

    # ──────────────────────────────────────────────
    # NO DATA FALLBACK
    # ──────────────────────────────────────────────

    @staticmethod
    def _no_data_result(
        our_price: float,
        competitors_removed: int = 0,
    ) -> PositionResult:
        """Return a neutral result when no competitor data is available."""
        return PositionResult(
            percentile=50.0,
            position_index=0.5,
            market_pressure="no_data",
            our_price=our_price,
            median_competitor_price=0.0,
            avg_competitor_price=0.0,
            gap_to_median_pct=0.0,
            gap_to_cheapest_pct=0.0,
            gap_to_most_expensive_pct=0.0,
            cpi=100.0,
            competitor_count=0,
            competitors_removed=competitors_removed,
            confidence=0.0,
            position_label="at_median",
        )
