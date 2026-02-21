"""Create materialized views for category performance benchmarks.

Revision ID: ie002_materialized_benchmark_views
Revises: (depends on your latest migration — update down_revision)
Create Date: 2026-02-18

Three materialized views that replace programmatic aggregation in
OutcomeBenchmarkService with pre-computed PostgreSQL views:

1. mv_category_benchmarks
   - Per-category success rate, avg revenue lift, avg confidence
   - Optimal price change range (p25/median/p75)
   - k-anonymity enforced at query time (merchant_count column)

2. mv_category_data_gaps
   - Per-category failure rates split by data completeness
   - failure_gap = low_data_failure_rate - high_data_failure_rate
   - Scout priority derived from gap size

3. mv_available_categories
   - Categories with merchant_count >= 5 (k-anonymity threshold)
   - Quick lookup for frontend category cards and Strategist context

Refresh strategy: Celery task runs after 30d measurement window completes
(~4:30 AM daily) plus on-demand via API. Views use CONCURRENTLY refresh
so reads aren't blocked during refresh.

IMPORTANT: Materialized views require a UNIQUE INDEX to support
REFRESH CONCURRENTLY. Each view has one.
"""

from alembic import op


# Update this to your latest migration revision
revision = "ie002_materialized_benchmark_views"
down_revision = "ie001_feedback_loop"
branch_labels = None
depends_on = None


def upgrade():
    # ══════════════════════════════════════════════════════════════
    # VIEW 1: mv_category_benchmarks
    # ══════════════════════════════════════════════════════════════
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_category_benchmarks AS
        WITH category_outcomes AS (
            SELECT
                product_category,
                user_id,
                outcome_label,
                original_confidence,
                price_change_percent,
                revenue_lift_7d,
                revenue_lift_14d,
                revenue_lift_30d,
                recommendation_source,
                created_at
            FROM recommendation_outcomes
            WHERE product_category IS NOT NULL
              AND outcome_label != 'INCONCLUSIVE'
              AND created_at >= NOW() - INTERVAL '90 days'
        ),
        category_stats AS (
            SELECT
                product_category,
                COUNT(DISTINCT user_id) AS merchant_count,
                COUNT(*) AS total_outcomes,
                SUM(CASE WHEN outcome_label = 'POSITIVE' THEN 1 ELSE 0 END) AS positive_count,
                SUM(CASE WHEN outcome_label = 'NEGATIVE' THEN 1 ELSE 0 END) AS negative_count,
                ROUND(AVG(original_confidence)::numeric, 4) AS avg_confidence,
                ROUND(AVG(revenue_lift_7d)::numeric, 2) AS avg_lift_7d,
                ROUND(AVG(revenue_lift_14d)::numeric, 2) AS avg_lift_14d,
                ROUND(AVG(revenue_lift_30d)::numeric, 2) AS avg_lift_30d
            FROM category_outcomes
            GROUP BY product_category
        ),
        positive_changes AS (
            SELECT
                product_category,
                price_change_percent,
                PERCENT_RANK() OVER (
                    PARTITION BY product_category
                    ORDER BY price_change_percent
                ) AS pct_rank
            FROM category_outcomes
            WHERE outcome_label = 'POSITIVE'
        ),
        quartiles AS (
            SELECT
                product_category,
                ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY price_change_percent)::numeric, 2) AS change_p25,
                ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY price_change_percent)::numeric, 2) AS change_median,
                ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY price_change_percent)::numeric, 2) AS change_p75,
                COUNT(*) AS positive_sample_size
            FROM category_outcomes
            WHERE outcome_label = 'POSITIVE'
            GROUP BY product_category
            HAVING COUNT(*) >= 3
        )
        SELECT
            cs.product_category,
            cs.merchant_count,
            cs.total_outcomes,
            cs.positive_count,
            cs.negative_count,
            ROUND(cs.positive_count::numeric / NULLIF(cs.total_outcomes, 0) * 100, 2) AS success_rate,
            cs.avg_confidence,
            cs.avg_lift_7d,
            cs.avg_lift_14d,
            cs.avg_lift_30d,
            q.change_p25,
            q.change_median,
            q.change_p75,
            q.positive_sample_size,
            NOW() AS refreshed_at
        FROM category_stats cs
        LEFT JOIN quartiles q ON cs.product_category = q.product_category
        WITH DATA;
    """)

    # Required for REFRESH CONCURRENTLY
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_category_benchmarks_category
        ON mv_category_benchmarks (product_category);
    """)

    # ══════════════════════════════════════════════════════════════
    # VIEW 2: mv_category_data_gaps
    # ══════════════════════════════════════════════════════════════
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_category_data_gaps AS
        WITH gap_data AS (
            SELECT
                product_category,
                user_id,
                outcome_label,
                data_completeness,
                CASE
                    WHEN data_completeness < 0.6 THEN 'low'
                    ELSE 'high'
                END AS data_quality_tier
            FROM recommendation_outcomes
            WHERE product_category IS NOT NULL
              AND data_completeness IS NOT NULL
              AND outcome_label != 'INCONCLUSIVE'
              AND created_at >= NOW() - INTERVAL '90 days'
        ),
        tier_stats AS (
            SELECT
                product_category,
                data_quality_tier,
                COUNT(*) AS tier_total,
                SUM(CASE WHEN outcome_label = 'NEGATIVE' THEN 1 ELSE 0 END) AS tier_failures
            FROM gap_data
            GROUP BY product_category, data_quality_tier
        ),
        pivoted AS (
            SELECT
                product_category,
                COALESCE(MAX(CASE WHEN data_quality_tier = 'low' THEN tier_total END), 0) AS low_data_total,
                COALESCE(MAX(CASE WHEN data_quality_tier = 'low' THEN tier_failures END), 0) AS low_data_failures,
                COALESCE(MAX(CASE WHEN data_quality_tier = 'high' THEN tier_total END), 0) AS high_data_total,
                COALESCE(MAX(CASE WHEN data_quality_tier = 'high' THEN tier_failures END), 0) AS high_data_failures
            FROM tier_stats
            GROUP BY product_category
        )
        SELECT
            product_category,
            low_data_total,
            low_data_failures,
            ROUND(
                CASE WHEN low_data_total > 0
                    THEN low_data_failures::numeric / low_data_total * 100
                    ELSE 0
                END, 2
            ) AS low_data_failure_rate,
            high_data_total,
            high_data_failures,
            ROUND(
                CASE WHEN high_data_total > 0
                    THEN high_data_failures::numeric / high_data_total * 100
                    ELSE 0
                END, 2
            ) AS high_data_failure_rate,
            ROUND(
                CASE WHEN low_data_total > 0
                    THEN low_data_failures::numeric / low_data_total * 100
                    ELSE 0
                END
                -
                CASE WHEN high_data_total > 0
                    THEN high_data_failures::numeric / high_data_total * 100
                    ELSE 0
                END, 2
            ) AS failure_gap,
            CASE
                WHEN (
                    CASE WHEN low_data_total > 0
                        THEN low_data_failures::numeric / low_data_total * 100
                        ELSE 0
                    END
                    -
                    CASE WHEN high_data_total > 0
                        THEN high_data_failures::numeric / high_data_total * 100
                        ELSE 0
                    END
                ) > 20 THEN 'high'
                WHEN (
                    CASE WHEN low_data_total > 0
                        THEN low_data_failures::numeric / low_data_total * 100
                        ELSE 0
                    END
                    -
                    CASE WHEN high_data_total > 0
                        THEN high_data_failures::numeric / high_data_total * 100
                        ELSE 0
                    END
                ) > 10 THEN 'medium'
                ELSE 'low'
            END AS scout_priority,
            low_data_total + high_data_total AS total_outcomes,
            NOW() AS refreshed_at
        FROM pivoted
        WHERE low_data_total >= 2
        WITH DATA;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_category_data_gaps_category
        ON mv_category_data_gaps (product_category);
    """)

    # ══════════════════════════════════════════════════════════════
    # VIEW 3: mv_available_categories
    # ══════════════════════════════════════════════════════════════
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_available_categories AS
        SELECT
            product_category,
            COUNT(DISTINCT user_id) AS merchant_count,
            COUNT(*) AS outcome_count,
            NOW() AS refreshed_at
        FROM recommendation_outcomes
        WHERE product_category IS NOT NULL
          AND outcome_label != 'INCONCLUSIVE'
          AND created_at >= NOW() - INTERVAL '90 days'
        GROUP BY product_category
        HAVING COUNT(DISTINCT user_id) >= 5
        ORDER BY COUNT(DISTINCT user_id) DESC
        WITH DATA;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_available_categories_category
        ON mv_available_categories (product_category);
    """)


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_available_categories CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_category_data_gaps CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_category_benchmarks CASCADE;")


    