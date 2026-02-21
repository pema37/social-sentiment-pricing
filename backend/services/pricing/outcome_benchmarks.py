"""
Outcome Benchmarks Service - Cross-merchant intelligence layer.

UPDATED (2026-02-18): Now reads from materialized views for performance.
Falls back to programmatic aggregation if views don't exist yet
(e.g., migration not run, views empty, or test environment).

The network effect engine: the system becomes more valuable with each
merchant added. This module aggregates anonymized outcome data across
merchants to produce category-level insights no individual merchant
could generate alone.

Two capabilities:

1. CATEGORY BENCHMARKS → Cross-merchant intelligence
   "Merchants in Electronics who price in the 40th-60th percentile see
   highest conversions." Activates at 5+ merchants per category.
   k-anonymity enforced: never publish benchmarks from fewer than
   min_merchants. No merchant ever sees another merchant's individual data.

2. DATA GAP FAILURE RATES → Backward learning to Scout
   Identifies categories where low data completeness correlates with
   recommendation failures. The Scout uses this to prioritize broader
   competitor coverage for those categories.

Materialized views (refreshed daily at 4:30 AM by Celery):
  - mv_category_benchmarks    → get_category_benchmarks()
  - mv_category_data_gaps     → get_data_gap_failure_rates()
  - mv_available_categories   → list_available_categories()

Privacy architecture:
  - k-Anonymity (k=5 minimum): never publish from fewer than 5 merchants
  - All outputs are aggregated — no merchant IDs in responses
  - Differential privacy (ε=1-2) planned for 20+ merchants/category
"""

import logging
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlmodel import select

from models.recommendation_outcome import (
    RecommendationOutcome,
    OutcomeLabel,
)

logger = logging.getLogger(__name__)

# Privacy threshold: minimum distinct merchants for any benchmark output
DEFAULT_K_ANONYMITY = 5


class OutcomeBenchmarkService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────
    # 1. CATEGORY BENCHMARKS
    # ──────────────────────────────────────────────

    async def get_category_benchmarks(
        self,
        product_category: str,
        days: int = 90,
        min_merchants: int = DEFAULT_K_ANONYMITY,
    ) -> Optional[dict]:
        """Aggregate anonymized outcome data across merchants in a category.

        Reads from mv_category_benchmarks materialized view for speed.
        Falls back to programmatic aggregation if view is unavailable.

        Returns None if fewer than min_merchants have data (k-anonymity).
        """
        # ── Try materialized view first ──
        try:
            result = await self.db.execute(
                text("""
                    SELECT
                        product_category,
                        merchant_count,
                        total_outcomes,
                        positive_count,
                        success_rate,
                        avg_confidence,
                        avg_lift_7d,
                        avg_lift_14d,
                        avg_lift_30d,
                        change_p25,
                        change_median,
                        change_p75,
                        positive_sample_size,
                        refreshed_at
                    FROM mv_category_benchmarks
                    WHERE product_category = :category
                """),
                {"category": product_category},
            )
            row = result.mappings().first()

            if row and row["merchant_count"] >= min_merchants:
                optimal_range = None
                if row["change_p25"] is not None and row["positive_sample_size"] and row["positive_sample_size"] >= 3:
                    optimal_range = {
                        "p25": float(row["change_p25"]),
                        "median": float(row["change_median"]),
                        "p75": float(row["change_p75"]),
                        "sample_size": int(row["positive_sample_size"]),
                    }

                # Get source breakdown from programmatic method
                # (not materialized — it's a small secondary query)
                by_source = await self._get_source_breakdown(product_category, days)

                return {
                    "category": product_category,
                    "merchant_count": int(row["merchant_count"]),
                    "total_outcomes": int(row["total_outcomes"]),
                    "success_rate": float(row["success_rate"]) if row["success_rate"] else 0.0,
                    "avg_revenue_lift_7d": float(row["avg_lift_7d"]) if row["avg_lift_7d"] else None,
                    "avg_revenue_lift_14d": float(row["avg_lift_14d"]) if row["avg_lift_14d"] else None,
                    "avg_revenue_lift_30d": float(row["avg_lift_30d"]) if row["avg_lift_30d"] else None,
                    "avg_confidence": float(row["avg_confidence"]) if row["avg_confidence"] else None,
                    "optimal_price_change_range": optimal_range,
                    "by_recommendation_source": by_source,
                    "period_days": days,
                    "source": "materialized_view",
                    "refreshed_at": str(row["refreshed_at"]) if row["refreshed_at"] else None,
                }

            if row and row["merchant_count"] < min_merchants:
                return None  # k-anonymity not met

        except Exception as e:
            logger.debug(f"Materialized view unavailable, falling back to programmatic: {e}")

        # ── Fallback: programmatic aggregation ──
        return await self._get_category_benchmarks_programmatic(
            product_category, days, min_merchants
        )

    async def list_available_categories(
        self,
        min_merchants: int = DEFAULT_K_ANONYMITY,
        days: int = 90,
    ) -> list[dict]:
        """List all categories that have enough merchants for benchmarks.

        Reads from mv_available_categories materialized view for speed.
        Falls back to programmatic aggregation if view is unavailable.
        """
        # ── Try materialized view first ──
        try:
            result = await self.db.execute(
                text("""
                    SELECT
                        product_category,
                        merchant_count,
                        outcome_count
                    FROM mv_available_categories
                    WHERE merchant_count >= :min_merchants
                    ORDER BY merchant_count DESC
                """),
                {"min_merchants": min_merchants},
            )
            rows = result.mappings().all()

            if rows:
                return [
                    {
                        "category": row["product_category"],
                        "merchant_count": int(row["merchant_count"]),
                        "outcome_count": int(row["outcome_count"]),
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.debug(f"Materialized view unavailable, falling back: {e}")

        # ── Fallback: programmatic ──
        return await self._list_available_categories_programmatic(
            min_merchants, days
        )

    async def get_category_context_for_strategist(
        self,
        product_category: str,
        days: int = 90,
        min_merchants: int = DEFAULT_K_ANONYMITY,
    ) -> Optional[str]:
        """Generate a context string for injection into the Strategist's prompt.

        This is Tier 1 feedback (context injection): before generating any
        recommendation, the Strategist queries historical performance data
        for the merchant's category and receives a grounded summary.

        Returns None if insufficient data (k-anonymity not met).
        Returns a plain-text summary string for prompt injection.
        """
        benchmarks = await self.get_category_benchmarks(
            product_category, days, min_merchants
        )

        if not benchmarks:
            return None

        lines = [
            f"Category benchmark data for '{product_category}' "
            f"({benchmarks['merchant_count']} merchants, {benchmarks['period_days']}d window):",
            f"- Overall success rate: {benchmarks['success_rate']}%",
        ]

        if benchmarks.get("avg_revenue_lift_7d") is not None:
            lines.append(
                f"- Average 7-day revenue lift for successful recommendations: "
                f"{benchmarks['avg_revenue_lift_7d']}%"
            )

        if benchmarks.get("avg_revenue_lift_30d") is not None:
            lines.append(
                f"- Average 30-day revenue lift: {benchmarks['avg_revenue_lift_30d']}%"
            )

        if benchmarks.get("optimal_price_change_range"):
            r = benchmarks["optimal_price_change_range"]
            lines.append(
                f"- Optimal price change range (IQR of successes): "
                f"{r['p25']}% to {r['p75']}% (median {r['median']}%)"
            )

        lines.append(
            f"- Average confidence of measured recommendations: "
            f"{benchmarks.get('avg_confidence', 'N/A')}"
        )

        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # 2. DATA GAP FAILURE RATES (backward learning → Scout)
    # ──────────────────────────────────────────────

    async def get_data_gap_failure_rates(
        self,
        user_id: Optional[UUID] = None,
        days: int = 90,
    ) -> list[dict]:
        """Identify categories where low data completeness causes failures.

        Reads from mv_category_data_gaps for cross-merchant queries.
        Falls back to programmatic for user-scoped queries or if view unavailable.
        """
        # Cross-merchant queries can use the materialized view
        if user_id is None:
            try:
                result = await self.db.execute(
                    text("""
                        SELECT
                            product_category,
                            low_data_failure_rate,
                            high_data_failure_rate,
                            failure_gap,
                            low_data_total AS low_data_outcomes,
                            high_data_total AS high_data_outcomes,
                            total_outcomes,
                            scout_priority
                        FROM mv_category_data_gaps
                        ORDER BY failure_gap DESC
                    """)
                )
                rows = result.mappings().all()

                if rows:
                    return [
                        {
                            "category": row["product_category"],
                            "failure_rate_low_data": float(row["low_data_failure_rate"]),
                            "failure_rate_high_data": float(row["high_data_failure_rate"]),
                            "failure_gap": float(row["failure_gap"]),
                            "low_data_outcomes": int(row["low_data_outcomes"]),
                            "high_data_outcomes": int(row["high_data_outcomes"]),
                            "total_outcomes": int(row["total_outcomes"]),
                            "scout_priority": row["scout_priority"],
                        }
                        for row in rows
                    ]

            except Exception as e:
                logger.debug(f"Materialized view unavailable, falling back: {e}")

        # ── Fallback: programmatic (also handles user-scoped queries) ──
        return await self._get_data_gap_failure_rates_programmatic(user_id, days)

    async def get_scout_priority_queue(
        self,
        user_id: Optional[UUID] = None,
        days: int = 90,
    ) -> list[dict]:
        """Generate a priority queue for the Scout's scraping scheduler.

        Categories with high failure gaps from data incompleteness get
        more aggressive scraping schedules. Returns a list ordered by
        priority with suggested scraping intervals.
        """
        failure_rates = await self.get_data_gap_failure_rates(user_id, days)

        priority_queue = []
        for item in failure_rates:
            if item["low_data_outcomes"] < 2:
                continue

            if item["failure_gap"] > 20:
                interval_hours = 1
            elif item["failure_gap"] > 10:
                interval_hours = 2
            else:
                interval_hours = 4

            priority_queue.append({
                "category": item["category"],
                "scout_priority": item["scout_priority"],
                "suggested_scrape_interval_hours": interval_hours,
                "failure_gap": item["failure_gap"],
                "evidence_count": item["low_data_outcomes"],
            })

        return priority_queue

    # ──────────────────────────────────────────────
    # VIEW REFRESH (callable from API)
    # ──────────────────────────────────────────────

    async def refresh_views(self) -> dict:
        """Refresh all materialized views. Callable from API endpoint."""
        views = [
            "mv_category_benchmarks",
            "mv_category_data_gaps",
            "mv_available_categories",
        ]
        results = {}

        for view_name in views:
            try:
                await self.db.execute(
                    text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
                )
                await self.db.commit()
                results[view_name] = "refreshed"
            except Exception as e:
                await self.db.rollback()
                try:
                    await self.db.execute(
                        text(f"REFRESH MATERIALIZED VIEW {view_name}")
                    )
                    await self.db.commit()
                    results[view_name] = "refreshed_regular"
                except Exception as e2:
                    await self.db.rollback()
                    results[view_name] = f"failed: {e2}"

        return results

    # ──────────────────────────────────────────────
    # PRIVATE: PROGRAMMATIC FALLBACKS
    # ──────────────────────────────────────────────

    async def _get_category_benchmarks_programmatic(
        self,
        product_category: str,
        days: int = 90,
        min_merchants: int = DEFAULT_K_ANONYMITY,
    ) -> Optional[dict]:
        """Original programmatic aggregation — used as fallback."""
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.product_category == product_category,
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.outcome_label != OutcomeLabel.INCONCLUSIVE,
        )

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        if not outcomes:
            return None

        distinct_merchants = len(set(o.user_id for o in outcomes))
        if distinct_merchants < min_merchants:
            return None

        positive = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.POSITIVE)
        total = len(outcomes)

        lifts = [o.revenue_lift_7d for o in outcomes if o.revenue_lift_7d is not None]
        avg_lift = round(sum(lifts) / len(lifts), 2) if lifts else None

        confidences = [float(o.original_confidence) for o in outcomes]
        avg_confidence = round(sum(confidences) / len(confidences), 4)

        optimal_range = self._calculate_optimal_change_range(outcomes)
        by_source = self._aggregate_by_source(outcomes)

        return {
            "category": product_category,
            "merchant_count": distinct_merchants,
            "total_outcomes": total,
            "success_rate": round(positive / total * 100, 2),
            "avg_revenue_lift_7d": avg_lift,
            "avg_confidence": avg_confidence,
            "optimal_price_change_range": optimal_range,
            "by_recommendation_source": by_source,
            "period_days": days,
            "source": "programmatic",
        }

    async def _list_available_categories_programmatic(
        self,
        min_merchants: int = DEFAULT_K_ANONYMITY,
        days: int = 90,
    ) -> list[dict]:
        """Original programmatic aggregation — used as fallback."""
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.product_category.is_not(None),
            RecommendationOutcome.outcome_label != OutcomeLabel.INCONCLUSIVE,
        )

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        categories: dict = {}
        for o in outcomes:
            cat = o.product_category
            if cat not in categories:
                categories[cat] = {"merchants": set(), "count": 0}
            categories[cat]["merchants"].add(o.user_id)
            categories[cat]["count"] += 1

        available = []
        for cat, data in categories.items():
            merchant_count = len(data["merchants"])
            if merchant_count >= min_merchants:
                available.append({
                    "category": cat,
                    "merchant_count": merchant_count,
                    "outcome_count": data["count"],
                })

        available.sort(key=lambda x: x["merchant_count"], reverse=True)
        return available

    async def _get_data_gap_failure_rates_programmatic(
        self,
        user_id: Optional[UUID] = None,
        days: int = 90,
    ) -> list[dict]:
        """Original programmatic aggregation — used as fallback and for user-scoped queries."""
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.data_completeness.is_not(None),
            RecommendationOutcome.product_category.is_not(None),
            RecommendationOutcome.outcome_label != OutcomeLabel.INCONCLUSIVE,
        )
        if user_id:
            stmt = stmt.where(RecommendationOutcome.user_id == user_id)

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        categories: dict = {}
        for o in outcomes:
            cat = o.product_category
            if cat not in categories:
                categories[cat] = {
                    "low_data_failures": 0,
                    "low_data_total": 0,
                    "high_data_failures": 0,
                    "high_data_total": 0,
                    "total": 0,
                }
            categories[cat]["total"] += 1

            if o.data_completeness < 0.6:
                categories[cat]["low_data_total"] += 1
                if o.outcome_label == OutcomeLabel.NEGATIVE:
                    categories[cat]["low_data_failures"] += 1
            else:
                categories[cat]["high_data_total"] += 1
                if o.outcome_label == OutcomeLabel.NEGATIVE:
                    categories[cat]["high_data_failures"] += 1

        results = []
        for cat, stats in categories.items():
            low_failure_rate = 0.0
            if stats["low_data_total"] > 0:
                low_failure_rate = round(
                    stats["low_data_failures"] / stats["low_data_total"] * 100, 2
                )

            high_failure_rate = 0.0
            if stats["high_data_total"] > 0:
                high_failure_rate = round(
                    stats["high_data_failures"] / stats["high_data_total"] * 100, 2
                )

            failure_gap = round(low_failure_rate - high_failure_rate, 2)

            results.append({
                "category": cat,
                "failure_rate_low_data": low_failure_rate,
                "failure_rate_high_data": high_failure_rate,
                "failure_gap": failure_gap,
                "low_data_outcomes": stats["low_data_total"],
                "high_data_outcomes": stats["high_data_total"],
                "total_outcomes": stats["total"],
                "scout_priority": "high" if failure_gap > 20 else "medium" if failure_gap > 10 else "low",
            })

        results.sort(key=lambda x: x["failure_gap"], reverse=True)
        return results

    async def _get_source_breakdown(
        self,
        product_category: str,
        days: int = 90,
    ) -> dict:
        """Get recommendation source breakdown for a category.
        
        Not materialized — it's a lightweight secondary query.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.product_category == product_category,
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.outcome_label != OutcomeLabel.INCONCLUSIVE,
        )

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        return self._aggregate_by_source(outcomes)

    # ──────────────────────────────────────────────
    # PRIVATE: STATIC HELPERS
    # ──────────────────────────────────────────────

    @staticmethod
    def _calculate_optimal_change_range(
        outcomes: list[RecommendationOutcome],
    ) -> Optional[dict]:
        """IQR of price changes from successful outcomes."""
        positive_changes = [
            float(o.price_change_percent)
            for o in outcomes
            if o.outcome_label == OutcomeLabel.POSITIVE
        ]

        if len(positive_changes) < 3:
            return None

        sorted_changes = sorted(positive_changes)
        n = len(sorted_changes)

        return {
            "p25": round(sorted_changes[n // 4], 2),
            "median": round(sorted_changes[n // 2], 2),
            "p75": round(sorted_changes[n * 3 // 4], 2),
            "sample_size": n,
        }

    @staticmethod
    def _aggregate_by_source(outcomes: list[RecommendationOutcome]) -> dict:
        """Break down success rates by recommendation source."""
        sources: dict = {}
        for o in outcomes:
            src = o.recommendation_source or "unknown"
            if src not in sources:
                sources[src] = {"total": 0, "positive": 0}
            sources[src]["total"] += 1
            if o.outcome_label == OutcomeLabel.POSITIVE:
                sources[src]["positive"] += 1

        result = {}
        for src, data in sources.items():
            if data["total"] >= 2:
                result[src] = {
                    "count": data["total"],
                    "success_rate": round(data["positive"] / data["total"] * 100, 2),
                }

        return result
    

    