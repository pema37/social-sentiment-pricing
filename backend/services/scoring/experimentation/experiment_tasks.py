"""
Experiment Tasks — Background jobs for the experimentation system.

Schedule (via Celery Beat, add to workers/scheduler.py):
  - daily_bandit_update:       Daily 06:00 UTC
  - weekly_convergence_check:  Sunday 06:30 UTC (after batch learning)
  - persist_bandit_state:      Daily 07:00 UTC (after updates)

These tasks complement the learning cycle (batch_tasks.py):
  - batch_tasks runs Sunday 04:00-05:30 (features → priors → cache)
  - experiment_tasks runs daily 06:00-07:00 (outcomes → bandit → persist)

The daily_bandit_update processes outcomes that have been measured
since the last run and feeds them to the ExperimentManager.

Phase 3 Intelligence Environment — Block B, File 8.

Place at: backend/services/scoring/experimentation/experiment_tasks.py
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .experiment_manager import (
    ExperimentAssignment,
    ExperimentManager,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# TASK RESULTS
# ──────────────────────────────────────────────────────────


@dataclass
class BanditUpdateResult:
    """Result of a daily bandit update cycle."""

    task_id: str
    started_at: datetime
    completed_at: datetime | None = None

    # Processing stats
    outcomes_fetched: int = 0
    outcomes_processed: int = 0
    outcomes_skipped: int = 0  # Missing assignment data
    successes: int = 0
    failures: int = 0

    # Per-category breakdown
    category_breakdown: dict[str, dict[str, int]] = field(default_factory=dict)
    """{ category: { successes: N, failures: N, total: N } }"""

    # Timing
    fetch_time_ms: float = 0
    process_time_ms: float = 0
    total_time_ms: float = 0

    success: bool = False
    error: str | None = None

    @property
    def summary(self) -> str:
        status = "SUCCESS" if self.success else f"FAILED: {self.error}"
        return (
            f"BanditUpdate {self.task_id}: {status} | "
            f"{self.outcomes_fetched} fetched → "
            f"{self.outcomes_processed} processed "
            f"({self.successes} wins, {self.failures} losses) | "
            f"{self.total_time_ms:.0f}ms"
        )


@dataclass
class ConvergenceReport:
    """Result of a weekly convergence check."""

    task_id: str
    checked_at: datetime
    categories_checked: int = 0
    categories_converged: int = 0
    convergence_details: list[dict] = field(default_factory=list)
    """[ { category, converged, winner, leader, arms_summary } ]"""

    @property
    def summary(self) -> str:
        return f"Convergence {self.task_id}: {self.categories_converged}/{self.categories_checked} converged"


@dataclass
class PersistenceResult:
    """Result of persisting bandit state."""

    task_id: str
    persisted_at: datetime
    categories_persisted: int = 0
    state_size_bytes: int = 0
    success: bool = False
    error: str | None = None


# ──────────────────────────────────────────────────────────
# OUTCOME ROW STRUCTURE (from DB query)
# ──────────────────────────────────────────────────────────


@dataclass
class MeasuredOutcomeRow:
    """
    A measured outcome row from the DB, ready for bandit processing.

    The daily SQL query joins pricing_outcomes + pricing_impacts
    for recommendations that:
    - Have a strategy_arm assigned (from experiment_manager)
    - Have 7-day impact data measured (from Phase 1 tasks)
    - Haven't been processed by the bandit yet (processed_by_bandit = FALSE)
    """

    recommendation_id: str
    category: str
    strategy_name: str
    is_exploration: bool
    revenue_delta_pct: float | None
    action: str  # accepted, modified, rejected, ignored

    @property
    def success(self) -> bool:
        """
        A recommendation is successful if:
        - Merchant acted on it (accepted or modified)
        - Revenue impact is positive
        """
        acted_on = self.action in ("accepted", "modified")
        positive = self.revenue_delta_pct is not None and self.revenue_delta_pct > 0
        return acted_on and positive

    @property
    def reward(self) -> float:
        """Revenue lift as reward signal."""
        return self.revenue_delta_pct if self.revenue_delta_pct is not None else 0.0


# ──────────────────────────────────────────────────────────
# EXPERIMENT TASK RUNNER
# ──────────────────────────────────────────────────────────


class ExperimentTaskRunner:
    """
    Framework-agnostic runner for experiment background tasks.

    Like LearningCycleOrchestrator in batch_tasks.py, this separates
    task logic from Celery. Dependencies are injected.

    Usage:
        runner = ExperimentTaskRunner(
            experiment_manager=manager,
            outcome_fetcher=lambda: query_db_for_unprocessed_outcomes(),
            state_persister=lambda state: save_to_db(state),
        )
        result = runner.run_daily_update()
    """

    def __init__(
        self,
        experiment_manager: ExperimentManager,
        outcome_fetcher: Callable[[], Sequence[MeasuredOutcomeRow]],
        state_persister: Callable[[dict], bool] | None = None,
    ):
        self._manager = experiment_manager
        self._fetcher = outcome_fetcher
        self._persister = state_persister
        self._history: list[BanditUpdateResult] = []

    @property
    def manager(self) -> ExperimentManager:
        return self._manager

    @property
    def history(self) -> list[BanditUpdateResult]:
        return list(self._history)

    # ──────────────────────────────────────────────
    # DAILY BANDIT UPDATE
    # ──────────────────────────────────────────────

    def run_daily_update(self, task_id: str | None = None) -> BanditUpdateResult:
        """
        Process all unprocessed measured outcomes through the bandit.

        Steps:
        1. Fetch outcomes with strategy_arm and 7d impact data
        2. For each: determine success/failure, update bandit
        3. Log per-category breakdown

        Returns BanditUpdateResult with full audit trail.
        """
        if task_id is None:
            task_id = datetime.now(UTC).strftime("bandit_%Y%m%d_%H%M%S")

        result = BanditUpdateResult(
            task_id=task_id,
            started_at=datetime.now(UTC),
        )
        total_start = time.monotonic()

        try:
            # ── Step 1: Fetch outcomes ──
            t0 = time.monotonic()
            rows = self._fetcher()
            result.outcomes_fetched = len(rows)
            result.fetch_time_ms = (time.monotonic() - t0) * 1000

            if not rows:
                result.success = True
                result.completed_at = datetime.now(UTC)
                result.total_time_ms = (time.monotonic() - total_start) * 1000
                self._history.append(result)
                return result

            # ── Step 2: Process through experiment manager ──
            t1 = time.monotonic()
            category_counts: dict[str, dict[str, int]] = {}

            for row in rows:
                # Build outcome dict for batch processing
                proc_result = self._manager.process_outcome(
                    recommendation_id=row.recommendation_id,
                    success=row.success,
                    reward=row.reward,
                    assignment=ExperimentAssignment(
                        recommendation_id=row.recommendation_id,
                        category=row.category,
                        strategy_name=row.strategy_name,
                        is_exploration=row.is_exploration,
                        assigned_at=datetime.now(UTC),
                        selection_reason="db_replay",
                    ),
                )

                if proc_result is None:
                    result.outcomes_skipped += 1
                    continue

                result.outcomes_processed += 1
                if row.success:
                    result.successes += 1
                else:
                    result.failures += 1

                # Per-category tracking
                cat = row.category
                if cat not in category_counts:
                    category_counts[cat] = {"successes": 0, "failures": 0, "total": 0}
                category_counts[cat]["total"] += 1
                if row.success:
                    category_counts[cat]["successes"] += 1
                else:
                    category_counts[cat]["failures"] += 1

            result.category_breakdown = category_counts
            result.process_time_ms = (time.monotonic() - t1) * 1000
            result.success = True

        except Exception as e:
            result.error = f"{type(e).__name__}: {e!s}"
            logger.exception("Bandit update %s failed: %s", task_id, result.error)

        result.completed_at = datetime.now(UTC)
        result.total_time_ms = (time.monotonic() - total_start) * 1000
        self._history.append(result)
        logger.info(result.summary)

        return result

    # ──────────────────────────────────────────────
    # WEEKLY CONVERGENCE CHECK
    # ──────────────────────────────────────────────

    def run_convergence_check(self, task_id: str | None = None) -> ConvergenceReport:
        """
        Check which categories have converged on a winning strategy.

        Convergence means one strategy is statistically significantly
        better than others (see ThompsonSamplingBandit.has_converged).

        When a category converges:
        - The winner can be locked in (stop experimenting)
        - Or exploration can continue at reduced rate for monitoring
        """
        if task_id is None:
            task_id = datetime.now(UTC).strftime("conv_%Y%m%d_%H%M%S")

        report = ConvergenceReport(
            task_id=task_id,
            checked_at=datetime.now(UTC),
        )

        bandit = self._manager.bandit

        for category in bandit.categories:
            converged, winner = bandit.has_converged(category)
            status = self._manager.get_category_status(category)

            detail = {
                "category": category,
                "converged": converged,
                "winner": winner,
                "leader": status.get("leader"),
                "total_selections": status.get("total_selections", 0),
                "total_updates": status.get("total_updates", 0),
                "arms_summary": {
                    arm["strategy_name"]: {
                        "mean": arm["mean"],
                        "n_selections": arm["n_selections"],
                        "n_updates": arm["n_updates"],
                    }
                    for arm in status.get("arms", [])
                },
            }

            report.convergence_details.append(detail)
            report.categories_checked += 1
            if converged:
                report.categories_converged += 1

        logger.info(report.summary)
        return report

    # ──────────────────────────────────────────────
    # STATE PERSISTENCE
    # ──────────────────────────────────────────────

    def run_persist_state(self, task_id: str | None = None) -> PersistenceResult:
        """
        Persist bandit state to DB for recovery after restarts.

        The bandit state (all arm α/β values across categories) is
        serialized to JSON and stored. On startup, the state is
        restored via ThompsonSamplingBandit.from_dict().
        """
        if task_id is None:
            task_id = datetime.now(UTC).strftime("persist_%Y%m%d_%H%M%S")

        result = PersistenceResult(
            task_id=task_id,
            persisted_at=datetime.now(UTC),
        )

        try:
            state = self._manager.bandit.to_dict()
            result.categories_persisted = len(state.get("categories", {}))

            import json

            state_json = json.dumps(state)
            result.state_size_bytes = len(state_json.encode("utf-8"))

            if self._persister is not None:
                self._persister(state)

            result.success = True

        except Exception as e:
            result.error = f"{type(e).__name__}: {e!s}"
            logger.exception("State persistence %s failed: %s", task_id, result.error)

        return result


# ──────────────────────────────────────────────────────────
# SQL QUERY for fetching unprocessed outcomes
# ──────────────────────────────────────────────────────────


def build_unprocessed_outcomes_sql() -> str:
    """
    SQL query for outcomes that have:
    - A strategy_arm assigned (from experiment_manager)
    - 7-day impact measured (from Phase 1 measurement tasks)
    - Not yet been processed by the bandit

    Returns rows mapping to MeasuredOutcomeRow.
    """
    return """
    SELECT
        po.recommendation_id,
        pr.category_id AS category,
        po.strategy_arm AS strategy_name,
        po.is_exploration,
        pi.revenue_delta_pct,
        po.action
    FROM pricing_outcomes po
    JOIN pricing_recommendations pr
        ON po.recommendation_id = pr.recommendation_id
    JOIN pricing_impacts pi
        ON po.recommendation_id = pi.recommendation_id
        AND pi.measurement_window = '7d'
    WHERE po.strategy_arm IS NOT NULL
        AND po.bandit_processed = FALSE
    ORDER BY po.action_at ASC
    """


def row_to_measured_outcome(row: dict) -> MeasuredOutcomeRow:
    """Convert a DB row dict to MeasuredOutcomeRow."""
    return MeasuredOutcomeRow(
        recommendation_id=str(row["recommendation_id"]),
        category=str(row.get("category", "unknown")),
        strategy_name=str(row["strategy_name"]),
        is_exploration=bool(row.get("is_exploration", False)),
        revenue_delta_pct=(float(row["revenue_delta_pct"]) if row.get("revenue_delta_pct") is not None else None),
        action=str(row.get("action", "unknown")),
    )


# ──────────────────────────────────────────────────────────
# CELERY BEAT SCHEDULE
# ──────────────────────────────────────────────────────────

CELERY_BEAT_SCHEDULE = {
    "daily-bandit-update": {
        "task": "services.scoring.experimentation.experiment_tasks.daily_bandit_update",
        "schedule": {
            "minute": 0,
            "hour": 6,
        },
        "description": "Process measured outcomes through Thompson Sampling bandit",
    },
    "weekly-convergence-check": {
        "task": "services.scoring.experimentation.experiment_tasks.weekly_convergence_check",
        "schedule": {
            "minute": 30,
            "hour": 6,
            "day_of_week": 0,  # Sunday
        },
        "description": "Check which categories have converged on winning strategy",
    },
    "daily-persist-bandit-state": {
        "task": "services.scoring.experimentation.experiment_tasks.persist_bandit_state",
        "schedule": {
            "minute": 0,
            "hour": 7,
        },
        "description": "Persist bandit state to DB for crash recovery",
    },
}
