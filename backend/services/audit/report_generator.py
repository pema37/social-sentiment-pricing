"""
Report Generator — assembles the final PriceCheckReport from all agent outputs.

Inputs:
  - Store scan results (products + prices)
  - Competitor matches + prices
  - Sentiment analysis
  - Pricing recommendations

Output:
  - PriceCheckReport with all metrics, opportunities, and revenue estimates
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from schemas.price_check import (
    CompetitorMatch,
    PriceCheckOpportunity,
    PriceCheckReport,
    SentimentSummary,
)

if TYPE_CHECKING:
    from services.audit.store_scanner import ScannedProduct

logger = logging.getLogger(__name__)


# ── Intermediate data containers ──────────────────────────────────────


@dataclass
class CompetitorData:
    """Raw competitor comparison data from the Scout agent."""

    matches: list[CompetitorMatch] = field(default_factory=list)


@dataclass
class SentimentData:
    """Raw sentiment data from the Analyst agent."""

    total_mentions: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    avg_score: float = 0.0
    trend: str = "stable"
    trend_pct: float = 0.0
    top_mentions: list[str] = field(default_factory=list)


@dataclass
class RecommendationData:
    """Raw recommendation data from the Strategist agent."""

    opportunities: list[PriceCheckOpportunity] = field(default_factory=list)
    overall_confidence: float = 50.0


# ── Price position calculation ────────────────────────────────────────


def _calc_price_position(
    products: list[ScannedProduct],
    competitor_matches: list[CompetitorMatch],
) -> tuple[float, str]:
    """
    Calculate the average price position relative to competitors.

    Returns (avg_gap_percent, label) where:
      - positive = priced above market
      - negative = priced below market
      - label is "above", "below", or "at"
    """
    if not competitor_matches:
        return 0.0, "at"

    gaps: list[float] = []
    for match in competitor_matches:
        if match.competitor_price > 0:
            gap = ((match.your_price - match.competitor_price) / match.competitor_price) * 100
            gaps.append(gap)

    if not gaps:
        return 0.0, "at"

    avg = sum(gaps) / len(gaps)

    if avg > 2.0:
        label = "above"
    elif avg < -2.0:
        label = "below"
    else:
        label = "at"

    return round(avg, 1), label


# ── Revenue impact estimation ─────────────────────────────────────────


def _estimate_monthly_impact(opportunities: list[PriceCheckOpportunity]) -> float:
    """
    Estimate monthly revenue impact from repricing opportunities.

    Uses a conservative estimate:
    - For underpriced products: (suggested - current) * estimated_monthly_units
    - For overpriced products: potential units gained * margin improvement
    - Estimated 30 units/month per product as a baseline (conservative for SMB)
    """
    if not opportunities:
        return 0.0

    total = 0.0
    for opp in opportunities:
        price_diff = abs(opp.suggested_price - opp.current_price)
        est_units = 30 * (opp.confidence / 100)
        total += price_diff * est_units

    return round(total, 2)


# ── Sentiment summary builder ─────────────────────────────────────────


def _build_sentiment_summary(data: SentimentData) -> SentimentSummary:
    """Convert raw sentiment data into the schema-friendly summary."""
    total = data.total_mentions or 1

    return SentimentSummary(
        total_mentions=data.total_mentions,
        positive_pct=round((data.positive_count / total) * 100, 1),
        negative_pct=round((data.negative_count / total) * 100, 1),
        neutral_pct=round((data.neutral_count / total) * 100, 1),
        avg_score=round(data.avg_score, 3),
        trend=data.trend,
        trend_pct=round(data.trend_pct, 1),
        top_mentions=data.top_mentions[:5],
    )


# ── Main report assembly ─────────────────────────────────────────────


def generate_report(
    store_name: str,
    store_url: str,
    email: str,
    products: list[ScannedProduct],
    competitor_data: CompetitorData,
    sentiment_data: SentimentData,
    recommendation_data: RecommendationData,
) -> PriceCheckReport:
    """
    Assemble the final PriceCheckReport from all agent outputs.

    This is called after all three agents (Scout, Analyst, Strategist)
    have completed their work.
    """
    competitor_names = set()
    for m in competitor_data.matches:
        competitor_names.add(m.competitor_name)

    avg_pos, pos_label = _calc_price_position(products, competitor_data.matches)

    sentiment = _build_sentiment_summary(sentiment_data)

    monthly_impact = _estimate_monthly_impact(recommendation_data.opportunities)
    annual_impact = round(monthly_impact * 12, 2)

    report = PriceCheckReport(
        store_name=store_name,
        store_url=store_url,
        products_scanned=len(products),
        competitors_found=len(competitor_names),
        avg_price_position=avg_pos,
        price_position_label=pos_label,
        competitor_matches=competitor_data.matches[:10],
        sentiment=sentiment,
        opportunities=recommendation_data.opportunities[:10],
        estimated_monthly_impact=monthly_impact,
        estimated_annual_impact=annual_impact,
        confidence=recommendation_data.overall_confidence,
        email=email,
    )

    logger.info(
        "Generated report for %s: %d products, %d competitors, $%.0f/mo impact",
        store_name,
        len(products),
        len(competitor_names),
        monthly_impact,
    )

    return report
