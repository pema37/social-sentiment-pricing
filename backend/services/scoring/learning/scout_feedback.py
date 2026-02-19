"""
Scout Feedback — Backward learning: outcomes → scraping priorities.

When a recommendation fails, we ask: was it because the Scout agent
didn't have enough data? This module correlates poor outcomes with
data quality signals to prioritize future scraping.

Feedback loops:
  1. Low data_quality_score + negative outcome → increase scraping priority
     for that category/product's competitor prices
  2. Missing sentiment data + negative outcome → increase social monitoring
     priority for that category
  3. Stale data (days since last scrape) + negative outcome → reduce
     scrape interval for that category

The output is a list of ScrapingPriorityAdjustment objects consumed
by the scraping scheduler to allocate crawl budget.

Phase 3 Intelligence Environment — Block C, File 9.

Place at: backend/services/scoring/learning/scout_feedback.py
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, Sequence


# ──────────────────────────────────────────────────────────
# INPUT: Outcome records with data quality signals
# ──────────────────────────────────────────────────────────

@dataclass
class OutcomeWithDataQuality:
    """
    Outcome record enriched with data quality signals at recommendation time.

    These signals capture what the Scout knew (or didn't) when the
    recommendation was generated. They come from the recommendation
    metadata stored in pricing_recommendations.

    The Celery task joins pricing_recommendations + pricing_outcomes +
    pricing_impacts + recommendation metadata to build these.
    """

    recommendation_id: str
    category: str
    product_id: Optional[str] = None

    # ── Outcome ──
    action: str = "unknown"                # accepted, modified, rejected, ignored
    revenue_delta_pct: Optional[float] = None

    # ── Data quality signals at recommendation time ──
    data_quality_score: float = 0.5
    """Overall data quality score (0-1) from the scoring engine.
    Low score = Scout had limited data when recommendation was made."""

    competitor_count: int = 0
    """Number of competitor prices available at recommendation time."""

    sentiment_available: bool = True
    """Whether sentiment data was available for this product/category."""

    days_since_last_scrape: Optional[float] = None
    """Days since the most recent competitor price scrape."""

    price_data_completeness: float = 1.0
    """Fraction of expected price data points that were actually available (0-1)."""

    sentiment_data_completeness: float = 1.0
    """Fraction of expected sentiment data points available (0-1)."""

    @property
    def was_successful(self) -> bool:
        """Recommendation was acted on and produced positive revenue."""
        acted_on = self.action in ("accepted", "modified")
        positive = self.revenue_delta_pct is not None and self.revenue_delta_pct > 0
        return acted_on and positive

    @property
    def was_failure(self) -> bool:
        """Recommendation was acted on but produced negative revenue,
        OR was rejected/ignored."""
        if self.action in ("rejected", "ignored"):
            return True
        if self.action in ("accepted", "modified"):
            return self.revenue_delta_pct is not None and self.revenue_delta_pct < 0
        return False

    @property
    def has_data_gap(self) -> bool:
        """Any data quality signal is below threshold."""
        return (
            self.data_quality_score < 0.5
            or self.competitor_count < 2
            or not self.sentiment_available
            or self.price_data_completeness < 0.7
            or self.sentiment_data_completeness < 0.7
            or (self.days_since_last_scrape is not None and self.days_since_last_scrape > 7)
        )


# ──────────────────────────────────────────────────────────
# OUTPUT: Scraping priority adjustments
# ──────────────────────────────────────────────────────────

@dataclass
class ScrapingPriorityAdjustment:
    """
    A recommended change to scraping priority for a category.

    Consumed by the scraping scheduler to allocate crawl budget.
    Higher priority_boost = more frequent scraping.
    """

    category: str
    adjustment_type: str
    """Type: 'competitor_price', 'sentiment', 'freshness'"""

    priority_boost: float
    """Additive boost to scraping priority (0.0 to 1.0).
    0.0 = no change, 1.0 = maximum urgency."""

    reason: str
    """Human-readable explanation for dashboards."""

    # ── Evidence ──
    failure_count: int = 0
    """Number of failures correlated with this data gap."""

    gap_severity: float = 0.0
    """Severity of the data gap (0-1). Higher = worse gap."""

    avg_revenue_loss_pct: float = 0.0
    """Average revenue loss from failures with this gap."""

    confidence: float = 0.0
    """How confident we are in this adjustment (0-1).
    Based on sample size and consistency of the pattern."""

    @property
    def is_significant(self) -> bool:
        """Adjustment is worth acting on."""
        return self.priority_boost >= 0.05 and self.confidence >= 0.3


@dataclass
class ScoutFeedbackReport:
    """Complete output from one feedback analysis cycle."""

    analyzed_at: datetime
    total_outcomes_analyzed: int
    total_failures: int
    total_failures_with_data_gaps: int
    adjustments: list[ScrapingPriorityAdjustment]
    category_summaries: dict[str, dict]

    @property
    def significant_adjustments(self) -> list[ScrapingPriorityAdjustment]:
        """Only adjustments worth acting on."""
        return [a for a in self.adjustments if a.is_significant]

    @property
    def summary(self) -> str:
        n_sig = len(self.significant_adjustments)
        return (
            f"ScoutFeedback: {self.total_outcomes_analyzed} outcomes, "
            f"{self.total_failures} failures, "
            f"{self.total_failures_with_data_gaps} with data gaps → "
            f"{n_sig} significant adjustments"
        )


# ──────────────────────────────────────────────────────────
# SCOUT FEEDBACK ANALYZER
# ──────────────────────────────────────────────────────────

# Thresholds
_MIN_FAILURES_FOR_SIGNAL = 3        # Need at least 3 failures to detect pattern
_LOW_DQ_THRESHOLD = 0.5             # data_quality_score below this is "low"
_LOW_COMPETITOR_THRESHOLD = 2       # Fewer than 2 competitors is a gap
_STALE_DATA_THRESHOLD_DAYS = 7.0    # Data older than 7 days is stale
_LOW_COMPLETENESS_THRESHOLD = 0.7   # Below 70% completeness is a gap


class ScoutFeedbackAnalyzer:
    """
    Analyzes outcome failures to identify data gaps and prioritize scraping.

    Pure Python analysis. No DB queries. The Celery task provides
    the input data; this module produces priority adjustments.

    Usage:
        analyzer = ScoutFeedbackAnalyzer()
        report = analyzer.analyze(outcome_records)
        for adj in report.significant_adjustments:
            update_scraping_priority(adj.category, adj.adjustment_type, adj.priority_boost)
    """

    def analyze(
        self,
        outcomes: Sequence[OutcomeWithDataQuality],
    ) -> ScoutFeedbackReport:
        """
        Analyze outcomes and produce scraping priority adjustments.

        Looks for patterns where:
        - Failures are correlated with low data quality
        - Specific data gaps (competitor, sentiment, freshness)
          co-occur with poor outcomes

        Returns ScoutFeedbackReport with prioritized adjustments.
        """
        now = datetime.now(UTC)

        if not outcomes:
            return ScoutFeedbackReport(
                analyzed_at=now,
                total_outcomes_analyzed=0,
                total_failures=0,
                total_failures_with_data_gaps=0,
                adjustments=[],
                category_summaries={},
            )

        # ── Group by category ──
        by_category: dict[str, list[OutcomeWithDataQuality]] = defaultdict(list)
        for o in outcomes:
            by_category[o.category].append(o)

        all_adjustments = []
        category_summaries = {}
        total_failures = 0
        total_with_gaps = 0

        for category, records in by_category.items():
            failures = [r for r in records if r.was_failure]
            failures_with_gaps = [r for r in failures if r.has_data_gap]

            total_failures += len(failures)
            total_with_gaps += len(failures_with_gaps)

            # ── Category summary ──
            n = len(records)
            n_fail = len(failures)
            category_summaries[category] = {
                "total": n,
                "failures": n_fail,
                "failure_rate": round(n_fail / n, 4) if n > 0 else 0,
                "failures_with_data_gaps": len(failures_with_gaps),
                "gap_correlation_rate": (
                    round(len(failures_with_gaps) / n_fail, 4)
                    if n_fail > 0 else 0
                ),
            }

            if len(failures) < _MIN_FAILURES_FOR_SIGNAL:
                continue

            # ── Analyze specific gap types ──
            adjs = self._analyze_competitor_gaps(category, records, failures)
            all_adjustments.extend(adjs)

            adjs = self._analyze_sentiment_gaps(category, records, failures)
            all_adjustments.extend(adjs)

            adjs = self._analyze_freshness_gaps(category, records, failures)
            all_adjustments.extend(adjs)

        # Sort by priority_boost descending
        all_adjustments.sort(key=lambda a: a.priority_boost, reverse=True)

        return ScoutFeedbackReport(
            analyzed_at=now,
            total_outcomes_analyzed=len(outcomes),
            total_failures=total_failures,
            total_failures_with_data_gaps=total_with_gaps,
            adjustments=all_adjustments,
            category_summaries=category_summaries,
        )

    # ──────────────────────────────────────────────
    # GAP-SPECIFIC ANALYZERS
    # ──────────────────────────────────────────────

    @staticmethod
    def _analyze_competitor_gaps(
        category: str,
        all_records: list[OutcomeWithDataQuality],
        failures: list[OutcomeWithDataQuality],
    ) -> list[ScrapingPriorityAdjustment]:
        """
        Check if failures correlate with insufficient competitor data.

        Signal: failures have lower competitor_count or price_data_completeness
        than successes.
        """
        adjustments = []

        # Failures with low competitor count
        low_comp_failures = [
            r for r in failures
            if r.competitor_count < _LOW_COMPETITOR_THRESHOLD
        ]

        # Failures with low price completeness
        low_price_failures = [
            r for r in failures
            if r.price_data_completeness < _LOW_COMPLETENESS_THRESHOLD
        ]

        # Compare: do failures have lower competitor counts than successes?
        successes = [r for r in all_records if r.was_successful]
        if successes and failures:
            avg_comp_fail = statistics.mean(r.competitor_count for r in failures)
            avg_comp_success = statistics.mean(r.competitor_count for r in successes)
            comp_gap = avg_comp_success - avg_comp_fail

            if comp_gap > 0 and len(low_comp_failures) >= _MIN_FAILURES_FOR_SIGNAL:
                # Calculate priority boost proportional to the gap and sample size
                severity = min(1.0, len(low_comp_failures) / len(failures))
                confidence = min(1.0, len(failures) / 10)
                avg_loss = _avg_loss(low_comp_failures)
                boost = min(1.0, severity * 0.5 + abs(avg_loss) / 20)

                adjustments.append(ScrapingPriorityAdjustment(
                    category=category,
                    adjustment_type="competitor_price",
                    priority_boost=round(boost, 4),
                    reason=(
                        f"{len(low_comp_failures)} failures had <{_LOW_COMPETITOR_THRESHOLD} "
                        f"competitors (avg {avg_comp_fail:.1f} vs {avg_comp_success:.1f} for successes)"
                    ),
                    failure_count=len(low_comp_failures),
                    gap_severity=round(severity, 4),
                    avg_revenue_loss_pct=round(avg_loss, 4),
                    confidence=round(confidence, 4),
                ))

        if len(low_price_failures) >= _MIN_FAILURES_FOR_SIGNAL:
            avg_completeness = statistics.mean(
                r.price_data_completeness for r in low_price_failures
            )
            severity = 1.0 - avg_completeness
            confidence = min(1.0, len(low_price_failures) / 10)
            avg_loss = _avg_loss(low_price_failures)
            boost = min(1.0, severity * 0.6 + abs(avg_loss) / 25)

            adjustments.append(ScrapingPriorityAdjustment(
                category=category,
                adjustment_type="competitor_price",
                priority_boost=round(boost, 4),
                reason=(
                    f"{len(low_price_failures)} failures had "
                    f"price completeness={avg_completeness:.0%} (below {_LOW_COMPLETENESS_THRESHOLD:.0%})"
                ),
                failure_count=len(low_price_failures),
                gap_severity=round(severity, 4),
                avg_revenue_loss_pct=round(avg_loss, 4),
                confidence=round(confidence, 4),
            ))

        return adjustments

    @staticmethod
    def _analyze_sentiment_gaps(
        category: str,
        all_records: list[OutcomeWithDataQuality],
        failures: list[OutcomeWithDataQuality],
    ) -> list[ScrapingPriorityAdjustment]:
        """
        Check if failures correlate with missing sentiment data.
        """
        adjustments = []

        # Failures with no sentiment
        no_sentiment_failures = [
            r for r in failures if not r.sentiment_available
        ]

        # Failures with low sentiment completeness
        low_sent_failures = [
            r for r in failures
            if r.sentiment_data_completeness < _LOW_COMPLETENESS_THRESHOLD
        ]

        if len(no_sentiment_failures) >= _MIN_FAILURES_FOR_SIGNAL:
            severity = len(no_sentiment_failures) / len(failures)
            confidence = min(1.0, len(no_sentiment_failures) / 8)
            avg_loss = _avg_loss(no_sentiment_failures)
            boost = min(1.0, severity * 0.4 + abs(avg_loss) / 20)

            adjustments.append(ScrapingPriorityAdjustment(
                category=category,
                adjustment_type="sentiment",
                priority_boost=round(boost, 4),
                reason=(
                    f"{len(no_sentiment_failures)} failures had no sentiment data available"
                ),
                failure_count=len(no_sentiment_failures),
                gap_severity=round(severity, 4),
                avg_revenue_loss_pct=round(avg_loss, 4),
                confidence=round(confidence, 4),
            ))

        if len(low_sent_failures) >= _MIN_FAILURES_FOR_SIGNAL:
            avg_comp = statistics.mean(
                r.sentiment_data_completeness for r in low_sent_failures
            )
            severity = 1.0 - avg_comp
            confidence = min(1.0, len(low_sent_failures) / 8)
            avg_loss = _avg_loss(low_sent_failures)
            boost = min(1.0, severity * 0.4 + abs(avg_loss) / 25)

            adjustments.append(ScrapingPriorityAdjustment(
                category=category,
                adjustment_type="sentiment",
                priority_boost=round(boost, 4),
                reason=(
                    f"{len(low_sent_failures)} failures had "
                    f"sentiment completeness={avg_comp:.0%}"
                ),
                failure_count=len(low_sent_failures),
                gap_severity=round(severity, 4),
                avg_revenue_loss_pct=round(avg_loss, 4),
                confidence=round(confidence, 4),
            ))

        return adjustments

    @staticmethod
    def _analyze_freshness_gaps(
        category: str,
        all_records: list[OutcomeWithDataQuality],
        failures: list[OutcomeWithDataQuality],
    ) -> list[ScrapingPriorityAdjustment]:
        """
        Check if failures correlate with stale data.
        """
        adjustments = []

        stale_failures = [
            r for r in failures
            if r.days_since_last_scrape is not None
            and r.days_since_last_scrape > _STALE_DATA_THRESHOLD_DAYS
        ]

        if len(stale_failures) >= _MIN_FAILURES_FOR_SIGNAL:
            avg_staleness = statistics.mean(
                r.days_since_last_scrape for r in stale_failures
            )
            # Compare with successes
            successes_with_freshness = [
                r for r in all_records
                if r.was_successful and r.days_since_last_scrape is not None
            ]
            avg_success_freshness = (
                statistics.mean(r.days_since_last_scrape for r in successes_with_freshness)
                if successes_with_freshness else _STALE_DATA_THRESHOLD_DAYS
            )

            freshness_gap = avg_staleness - avg_success_freshness
            severity = min(1.0, freshness_gap / 14)  # Normalize: 14 day gap = max severity
            confidence = min(1.0, len(stale_failures) / 8)
            avg_loss = _avg_loss(stale_failures)
            boost = min(1.0, severity * 0.5 + abs(avg_loss) / 20)

            adjustments.append(ScrapingPriorityAdjustment(
                category=category,
                adjustment_type="freshness",
                priority_boost=round(max(0.0, boost), 4),
                reason=(
                    f"{len(stale_failures)} failures had stale data "
                    f"(avg {avg_staleness:.1f}d vs {avg_success_freshness:.1f}d for successes)"
                ),
                failure_count=len(stale_failures),
                gap_severity=round(max(0.0, severity), 4),
                avg_revenue_loss_pct=round(avg_loss, 4),
                confidence=round(confidence, 4),
            ))

        return adjustments


# ──────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────

def _avg_loss(records: list[OutcomeWithDataQuality]) -> float:
    """Average revenue loss across failures (returns negative or zero)."""
    losses = [
        r.revenue_delta_pct for r in records
        if r.revenue_delta_pct is not None
    ]
    if not losses:
        return 0.0
    return statistics.mean(losses)



