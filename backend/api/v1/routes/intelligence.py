"""
Intelligence Environment API Endpoints
=======================================
Phase 5 — Integration Wiring

Dashboard endpoints for:
  - Experiment status (per category)
  - Calibration reports
  - Drift alerts
  - Category performance overview
  - IE pipeline health

Location: backend/api/v1/routes/intelligence.py

All endpoints require authentication via get_current_user dependency.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["Intelligence Environment"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ExperimentArmStatus(BaseModel):
    """Status of a single Thompson Sampling arm."""

    arm_name: str
    alpha: float = Field(description="Beta distribution alpha (successes + prior)")
    beta: float = Field(description="Beta distribution beta (failures + prior)")
    pulls: int = Field(description="Total assignments to this arm")
    wins: int = Field(description="Total successful outcomes")
    expected_reward: float = Field(description="alpha / (alpha + beta)")
    is_leader: bool = Field(description="Currently the best-performing arm")


class ExperimentStatus(BaseModel):
    """Experiment status for a product category."""

    category_id: str
    total_pulls: int
    converged: bool
    converged_arm: str | None = None
    convergence_confidence: float | None = None
    arms: list[ExperimentArmStatus]
    last_updated: datetime | None = None
    exploration_rate: float = Field(default=0.05, description="% of pulls reserved for exploration")


class CalibrationReport(BaseModel):
    """Calibration accuracy for a category or global."""

    category_id: str | None = None
    sample_count: int
    pearson_r: float | None = Field(None, description="Correlation between confidence and outcomes")
    calibration_method: str
    confidence_bands: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-band accuracy: [{band: '0.7-0.8', predicted: 0.75, actual: 0.68, count: 42}]",
    )
    is_reliable: bool = Field(description="True if sample_count >= 30")
    overconfidence_score: float | None = Field(None, description="Positive = overconfident, negative = underconfident")
    last_calibrated: datetime | None = None


class DriftAlert(BaseModel):
    """Drift detection alert."""

    alert_id: str
    category_id: str
    drift_type: str = Field(description="correlation_drop | distribution_shift | acceptance_change | lift_decline")
    severity: str = Field(description="info | warning | critical")
    metric_name: str
    current_value: float
    threshold: float
    message: str
    detected_at: datetime
    requires_action: bool


class CategoryPerformance(BaseModel):
    """Performance summary for a product category."""

    category_id: str
    category_name: str | None = None
    total_recommendations: int
    acceptance_rate: float
    avg_confidence: float
    avg_revenue_lift_7d: float | None = None
    avg_revenue_lift_14d: float | None = None
    avg_revenue_lift_30d: float | None = None
    confidence_accuracy_corr: float | None = None
    active_experiment: bool
    converged_strategy: str | None = None
    data_quality_score: float = Field(description="0-1 score based on data completeness")
    merchant_count: int = Field(description="Merchants with outcomes in this category")


class IEHealthStatus(BaseModel):
    """Overall health of the Intelligence Environment pipeline."""

    status: str = Field(description="healthy | degraded | unhealthy")
    scoring_engine_healthy: bool
    experiment_manager_healthy: bool
    calibrator_healthy: bool
    context_injector_healthy: bool
    last_measurement_run: datetime | None = None
    last_learning_cycle: datetime | None = None
    last_bandit_update: datetime | None = None
    last_calibration: datetime | None = None
    active_experiments: int
    converged_categories: int
    total_categories: int
    drift_alerts_active: int
    pipeline_version: str


class IEDashboard(BaseModel):
    """Combined dashboard payload — single API call for the frontend."""

    health: IEHealthStatus
    top_categories: list[CategoryPerformance]
    active_drift_alerts: list[DriftAlert]
    recent_calibration: CalibrationReport | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/health", response_model=IEHealthStatus)
async def get_ie_health(
    db: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
):
    """
    Get overall health status of the Intelligence Environment.

    Checks:
    - Scoring engine importability
    - Last Celery task run times
    - Active experiment count
    - Drift alert count
    """
    try:
        health = await _build_health_status(db, current_user)
        return health
    except Exception as exc:
        logger.error("IE health check failed: %s", exc, exc_info=True)
        return IEHealthStatus(
            status="unhealthy",
            scoring_engine_healthy=False,
            experiment_manager_healthy=False,
            calibrator_healthy=False,
            context_injector_healthy=False,
            active_experiments=0,
            converged_categories=0,
            total_categories=0,
            drift_alerts_active=0,
            pipeline_version="unknown",
        )


@router.get("/dashboard", response_model=IEDashboard)
async def get_ie_dashboard(
    db: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
    top_n: int = Query(default=10, ge=1, le=50, description="Number of top categories to return"),
):
    """
    Combined dashboard payload — single call for the frontend.

    Returns health, top categories by recommendation volume,
    active drift alerts, and latest calibration report.
    """
    health = await _build_health_status(db, current_user)
    categories = await _get_top_categories(db, current_user, top_n)
    alerts = await _get_active_drift_alerts(db, current_user)
    calibration = await _get_latest_calibration(db, current_user)

    return IEDashboard(
        health=health,
        top_categories=categories,
        active_drift_alerts=alerts,
        recent_calibration=calibration,
    )


@router.get("/experiments", response_model=list[ExperimentStatus])
async def get_experiment_statuses(
    db: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
    category_id: str | None = Query(default=None, description="Filter by category"),
):
    """
    Get Thompson Sampling experiment status for all (or specific) categories.

    Returns per-arm statistics including expected reward, pull counts,
    and convergence detection.
    """
    from sqlalchemy import text

    query = text(
        """
        SELECT
            bs.category_id,
            bs.arm_states,
            bs.total_pulls,
            bs.converged_arm,
            bs.convergence_confidence,
            bs.last_updated,
            bs.metadata
        FROM bandit_state bs
        WHERE 1=1
        {category_filter}
        ORDER BY bs.total_pulls DESC
    """.format(category_filter="AND bs.category_id = :category_id" if category_id else "")
    )

    params = {}
    if category_id:
        params["category_id"] = category_id

    result = await db.execute(query, params)
    rows = result.fetchall()

    statuses = []
    for row in rows:
        arm_states = row.arm_states or {}
        arms = []
        max_reward = 0.0
        for arm_name, state in arm_states.items():
            alpha = state.get("alpha", 1)
            beta_val = state.get("beta", 19)
            expected = alpha / (alpha + beta_val) if (alpha + beta_val) > 0 else 0
            max_reward = max(max_reward, expected)
            arms.append(
                ExperimentArmStatus(
                    arm_name=arm_name,
                    alpha=alpha,
                    beta=beta_val,
                    pulls=state.get("pulls", 0),
                    wins=state.get("wins", 0),
                    expected_reward=round(expected, 4),
                    is_leader=False,  # Set below
                )
            )

        # Mark the leader
        for arm in arms:
            if arm.expected_reward == max_reward and max_reward > 0:
                arm.is_leader = True
                break

        metadata = row.metadata or {}
        statuses.append(
            ExperimentStatus(
                category_id=row.category_id,
                total_pulls=row.total_pulls or 0,
                converged=row.converged_arm is not None,
                converged_arm=row.converged_arm,
                convergence_confidence=row.convergence_confidence,
                arms=arms,
                last_updated=row.last_updated,
                exploration_rate=metadata.get("exploration_rate", 0.05),
            )
        )

    return statuses


@router.get("/experiments/{category_id}", response_model=ExperimentStatus)
async def get_experiment_status(
    category_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
):
    """Get experiment status for a specific category."""
    statuses = await get_experiment_statuses(db, current_user, category_id)
    if not statuses:
        raise HTTPException(status_code=404, detail=f"No experiment found for category {category_id}")
    return statuses[0]


@router.get("/calibration", response_model=list[CalibrationReport])
async def get_calibration_reports(
    db: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
    category_id: str | None = Query(default=None),
):
    """
    Get calibration accuracy reports.

    Shows how well predicted confidence correlates with actual outcomes,
    broken down by confidence bands.
    """
    reports = await _get_calibration_reports(db, current_user, category_id)
    return reports


@router.get("/drift-alerts", response_model=list[DriftAlert])
async def get_drift_alerts(
    db: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
    severity: str | None = Query(default=None, description="Filter: info | warning | critical"),
    active_only: bool = Query(default=True, description="Only show unresolved alerts"),
):
    """
    Get drift detection alerts.

    Types:
    - correlation_drop: confidence-outcome correlation below threshold
    - distribution_shift: KS statistic detected scoring distribution change
    - acceptance_change: merchant acceptance rate shifted significantly
    - lift_decline: revenue lift trending downward
    """
    alerts = await _get_active_drift_alerts(db, current_user, severity)
    return alerts


@router.get("/categories", response_model=list[CategoryPerformance])
async def get_category_performance(
    db: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
    min_recommendations: int = Query(default=5, ge=1, description="Minimum recommendations to include"),
    sort_by: str = Query(default="total_recommendations", description="Sort field"),
):
    """
    Get performance metrics for all product categories.

    Reads from mv_category_benchmarks materialized view for fast lookups.
    """
    categories = await _get_top_categories(db, current_user, limit=100, min_recommendations=min_recommendations)
    return categories


@router.get("/categories/{category_id}", response_model=CategoryPerformance)
async def get_category_detail(
    category_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
):
    """Get detailed performance for a specific category."""
    from sqlalchemy import text

    query = text("""
        SELECT
            cb.category_id,
            cb.total_recommendations,
            cb.accepted,
            cb.avg_confidence,
            cb.avg_revenue_lift_7d,
            cb.avg_revenue_lift_14d,
            cb.avg_revenue_lift_30d,
            cb.confidence_accuracy_corr
        FROM mv_category_benchmarks cb
        WHERE cb.category_id = :category_id
        ORDER BY cb.total_recommendations DESC
        LIMIT 1
    """)

    result = await db.execute(query, {"category_id": category_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"No data for category {category_id}")

    total = row.total_recommendations or 1
    acceptance_rate = (row.accepted or 0) / total

    # Check experiment status
    exp_result = await db.execute(
        text("SELECT converged_arm FROM bandit_state WHERE category_id = :cid"), {"cid": category_id}
    )
    exp_row = exp_result.fetchone()

    return CategoryPerformance(
        category_id=row.category_id,
        total_recommendations=total,
        acceptance_rate=round(acceptance_rate, 3),
        avg_confidence=round(row.avg_confidence or 0, 3),
        avg_revenue_lift_7d=round(row.avg_revenue_lift_7d, 3) if row.avg_revenue_lift_7d else None,
        avg_revenue_lift_14d=round(row.avg_revenue_lift_14d, 3) if row.avg_revenue_lift_14d else None,
        avg_revenue_lift_30d=round(row.avg_revenue_lift_30d, 3) if row.avg_revenue_lift_30d else None,
        confidence_accuracy_corr=round(row.confidence_accuracy_corr, 3) if row.confidence_accuracy_corr else None,
        active_experiment=exp_row is not None and exp_row.converged_arm is None if exp_row else False,
        converged_strategy=exp_row.converged_arm if exp_row else None,
        data_quality_score=min(1.0, total / 50),  # Simple heuristic: 50+ recs = 1.0
        merchant_count=1,  # TODO: compute from materialized view
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _build_health_status(db: AsyncSession, user: Any) -> IEHealthStatus:
    """Build the IE health status by checking component availability."""
    from sqlalchemy import text

    # Check scoring engine importability
    scoring_healthy = True
    try:
        from services.scoring.engine import ScoringEngine  # noqa: F401
    except Exception:
        scoring_healthy = False

    experiment_healthy = True
    try:
        from services.scoring.experimentation.experiment_manager import ExperimentManager  # noqa: F401
    except Exception:
        experiment_healthy = False

    calibrator_healthy = True
    try:
        from services.scoring.learning.calibrator import Calibrator  # noqa: F401
    except Exception:
        calibrator_healthy = False

    context_healthy = True
    try:
        from services.scoring.learning.context_injector import ContextInjector  # noqa: F401
    except Exception:
        context_healthy = False

    # Count experiments
    try:
        result = await db.execute(text("SELECT COUNT(*) as total, COUNT(converged_arm) as converged FROM bandit_state"))
        row = result.fetchone()
        total_cats = row.total if row else 0
        converged_cats = row.converged if row else 0
        active_experiments = total_cats - converged_cats
    except Exception:
        total_cats = 0
        converged_cats = 0
        active_experiments = 0

    # Overall status
    all_healthy = all([scoring_healthy, experiment_healthy, calibrator_healthy, context_healthy])
    some_healthy = any([scoring_healthy, experiment_healthy, calibrator_healthy, context_healthy])
    status = "healthy" if all_healthy else ("degraded" if some_healthy else "unhealthy")

    return IEHealthStatus(
        status=status,
        scoring_engine_healthy=scoring_healthy,
        experiment_manager_healthy=experiment_healthy,
        calibrator_healthy=calibrator_healthy,
        context_injector_healthy=context_healthy,
        active_experiments=active_experiments,
        converged_categories=converged_cats,
        total_categories=total_cats,
        drift_alerts_active=0,  # TODO: count from drift detector
        pipeline_version="ie-v1.0",
    )


async def _get_top_categories(
    db: AsyncSession, user: Any, limit: int = 10, min_recommendations: int = 5
) -> list[CategoryPerformance]:
    """Read category performance from mv_category_benchmarks."""
    from sqlalchemy import text

    try:
        result = await db.execute(
            text("""
            SELECT
                cb.category_id,
                cb.total_recommendations,
                cb.accepted,
                cb.avg_confidence,
                cb.avg_revenue_lift_7d,
                cb.confidence_accuracy_corr
            FROM mv_category_benchmarks cb
            WHERE cb.total_recommendations >= :min_recs
            ORDER BY cb.total_recommendations DESC
            LIMIT :lim
        """),
            {"min_recs": min_recommendations, "lim": limit},
        )

        rows = result.fetchall()
        categories = []
        for row in rows:
            total = row.total_recommendations or 1
            categories.append(
                CategoryPerformance(
                    category_id=row.category_id,
                    total_recommendations=total,
                    acceptance_rate=round((row.accepted or 0) / total, 3),
                    avg_confidence=round(row.avg_confidence or 0, 3),
                    avg_revenue_lift_7d=round(row.avg_revenue_lift_7d, 3) if row.avg_revenue_lift_7d else None,
                    confidence_accuracy_corr=round(row.confidence_accuracy_corr, 3)
                    if row.confidence_accuracy_corr
                    else None,
                    active_experiment=False,  # Enriched later if needed
                    data_quality_score=min(1.0, total / 50),
                    merchant_count=1,
                )
            )
        return categories
    except Exception as exc:
        logger.warning("Failed to read mv_category_benchmarks: %s", exc)
        return []


async def _get_active_drift_alerts(db: AsyncSession, user: Any, severity: str | None = None) -> list[DriftAlert]:
    """
    Get active drift alerts.

    NOTE: Until the drift_detector has a persistence layer,
    this returns empty. The drift_detector currently runs in-memory
    during the weekly Celery task. Phase 5+ should persist alerts
    to a drift_alerts table.
    """
    # TODO: Query drift_alerts table once created
    # For now, return empty — drift detection runs but doesn't persist
    return []


async def _get_calibration_reports(
    db: AsyncSession, user: Any, category_id: str | None = None
) -> list[CalibrationReport]:
    """
    Get calibration reports.

    Computes per-band accuracy from pricing_outcomes with measured results.
    """
    from sqlalchemy import text

    query = text(
        """
        SELECT
            po.confidence_decomposition->>'overall' as raw_confidence,
            CASE WHEN pi.revenue_delta_pct > 0 THEN 1 ELSE 0 END as success,
            pr.category_id
        FROM pricing_outcomes po
        JOIN pricing_recommendations pr ON po.recommendation_id = pr.recommendation_id
        LEFT JOIN pricing_impacts pi ON pr.recommendation_id = pi.recommendation_id
            AND pi.measurement_window = '7d'
        WHERE po.action IN ('accepted', 'modified')
        AND pi.revenue_delta_pct IS NOT NULL
        {category_filter}
        ORDER BY po.created_at DESC
        LIMIT 500
    """.format(category_filter="AND pr.category_id = :category_id" if category_id else "")
    )

    params = {}
    if category_id:
        params["category_id"] = category_id

    try:
        result = await db.execute(query, params)
        rows = result.fetchall()

        if not rows:
            return [
                CalibrationReport(
                    category_id=category_id,
                    sample_count=0,
                    calibration_method="insufficient_data",
                    is_reliable=False,
                )
            ]

        # Compute per-band accuracy
        bands: dict[str, dict] = {}
        confidences = []
        outcomes = []

        for row in rows:
            try:
                conf = float(row.raw_confidence) if row.raw_confidence else 0.5
            except (ValueError, TypeError):
                conf = 0.5
            success = row.success or 0

            confidences.append(conf)
            outcomes.append(success)

            # Bin into 0.1-wide bands
            band_lower = int(conf * 10) / 10
            band_upper = band_lower + 0.1
            band_key = f"{band_lower:.1f}-{band_upper:.1f}"

            if band_key not in bands:
                bands[band_key] = {"predicted_sum": 0, "actual_sum": 0, "count": 0}
            bands[band_key]["predicted_sum"] += conf
            bands[band_key]["actual_sum"] += success
            bands[band_key]["count"] += 1

        # Pearson r (simple)
        n = len(confidences)
        pearson_r = None
        if n >= 10:
            mean_c = sum(confidences) / n
            mean_o = sum(outcomes) / n
            num = sum((c - mean_c) * (o - mean_o) for c, o in zip(confidences, outcomes))
            den_c = sum((c - mean_c) ** 2 for c in confidences) ** 0.5
            den_o = sum((o - mean_o) ** 2 for o in outcomes) ** 0.5
            if den_c > 0 and den_o > 0:
                pearson_r = round(num / (den_c * den_o), 4)

        band_list = []
        overconfidence_sum = 0
        for band_key, data in sorted(bands.items()):
            predicted = data["predicted_sum"] / data["count"]
            actual = data["actual_sum"] / data["count"]
            overconfidence_sum += (predicted - actual) * data["count"]
            band_list.append(
                {
                    "band": band_key,
                    "predicted": round(predicted, 3),
                    "actual": round(actual, 3),
                    "count": data["count"],
                }
            )

        return [
            CalibrationReport(
                category_id=category_id,
                sample_count=n,
                pearson_r=pearson_r,
                calibration_method="isotonic" if n >= 30 else "insufficient_data",
                confidence_bands=band_list,
                is_reliable=n >= 30,
                overconfidence_score=round(overconfidence_sum / n, 4) if n > 0 else None,
            )
        ]

    except Exception as exc:
        logger.warning("Calibration report query failed: %s", exc)
        return [
            CalibrationReport(
                category_id=category_id,
                sample_count=0,
                calibration_method="error",
                is_reliable=False,
            )
        ]


async def _get_latest_calibration(db: AsyncSession, user: Any) -> CalibrationReport | None:
    """Get the most recent global calibration report."""
    reports = await _get_calibration_reports(db, user, category_id=None)
    return reports[0] if reports else None
