"""
Experiment Manager — Orchestrates pricing experimentation at recommendation time.

This is the integration layer between:
  - ThompsonSamplingBandit (selects which strategy to test)
  - StrategyRegistry (defines what each strategy does)
  - ScoringEngine (produces the actual recommendation)

Flow at recommendation time:
  1. ExperimentManager.get_experiment_config(category, product_context)
  2. → ThompsonSamplingBandit selects a strategy arm
  3. → Strategy's guardrail/weight overrides applied to scoring config
  4. → ScoringEngine runs with strategy-specific parameters
  5. → ExperimentManager.record_assignment(recommendation_id, arm, ...)
  6. ... time passes, outcome measured by Phase 1 tasks ...
  7. ExperimentManager.process_outcome(recommendation_id, outcome)
  8. → Bandit updated with success/failure

Phase 3 Intelligence Environment — Block B, File 7.

Place at: backend/services/scoring/experimentation/experiment_manager.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bandit import (
        ThompsonSamplingBandit,
    )
    from .strategies import (
        GuardrailOverride,
        StrategyRegistry,
        WeightOverride,
    )

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# EXPERIMENT CONFIG: What the scoring engine receives
# ──────────────────────────────────────────────────────────


@dataclass
class ExperimentConfig:
    """
    Configuration for one recommendation, shaped by experimentation.

    The recommendation service receives this and applies it to the
    ScoringEngine call. After the recommendation is served, the
    assignment metadata is persisted for outcome tracking.
    """

    # ── Strategy selection ──
    strategy_name: str
    """Which pricing strategy was selected for this recommendation."""

    strategy_type: str
    """Strategy type (conservative, competitive, etc.)."""

    is_exploration: bool
    """True if this was a random exploration selection (5% holdout)."""

    # ── Scoring overrides ──
    magnitude_multiplier: float = 1.0
    """Apply to raw recommended price change after scoring."""

    guardrail_override: GuardrailOverride | None = None
    """Selective guardrail overrides (max_change, min_margin, etc.)."""

    weight_override: WeightOverride | None = None
    """Selective scoring component weight overrides."""

    # ── Metadata for persistence ──
    selection_reason: str = ""
    """How the arm was selected (thompson_sampling / exploration_holdout)."""

    sampled_values: dict[str, float] | None = None
    """Thompson Sampling sampled θ values for each arm (for audit)."""

    arm_probabilities: dict[str, float] | None = None
    """Estimated probability each arm is best (optional, expensive)."""

    @property
    def has_overrides(self) -> bool:
        """True if this config changes default scoring behavior."""
        return (
            self.magnitude_multiplier != 1.0 or self.guardrail_override is not None or self.weight_override is not None
        )


@dataclass
class ExperimentAssignment:
    """
    Persisted record of a strategy assignment for one recommendation.

    Stored alongside the recommendation for outcome tracking.
    When the outcome is measured, this tells us which arm to credit.
    """

    recommendation_id: str
    category: str
    strategy_name: str
    is_exploration: bool
    assigned_at: datetime
    selection_reason: str
    magnitude_multiplier: float = 1.0
    sampled_values: dict[str, float] | None = None

    def to_dict(self) -> dict:
        """Serialize for DB persistence (JSONB column)."""
        return {
            "recommendation_id": self.recommendation_id,
            "category": self.category,
            "strategy_name": self.strategy_name,
            "is_exploration": self.is_exploration,
            "assigned_at": self.assigned_at.isoformat(),
            "selection_reason": self.selection_reason,
            "magnitude_multiplier": self.magnitude_multiplier,
            "sampled_values": self.sampled_values,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExperimentAssignment:
        return cls(
            recommendation_id=d["recommendation_id"],
            category=d["category"],
            strategy_name=d["strategy_name"],
            is_exploration=d["is_exploration"],
            assigned_at=datetime.fromisoformat(d["assigned_at"]),
            selection_reason=d["selection_reason"],
            magnitude_multiplier=d.get("magnitude_multiplier", 1.0),
            sampled_values=d.get("sampled_values"),
        )


@dataclass
class OutcomeProcessingResult:
    """Result of processing a single measured outcome."""

    recommendation_id: str
    category: str
    strategy_name: str
    success: bool
    reward: float
    arm_mean_before: float
    arm_mean_after: float
    is_exploration: bool


# ──────────────────────────────────────────────────────────
# EXPERIMENT MANAGER
# ──────────────────────────────────────────────────────────


class ExperimentManager:
    """
    Central experiment orchestrator.

    Wires together:
    - StrategyRegistry (what strategies exist)
    - ThompsonSamplingBandit (which to select)
    - Assignment persistence (tracking what was selected)
    - Outcome processing (feeding results back to bandit)

    Usage:
        manager = ExperimentManager(
            registry=StrategyRegistry(),
            bandit=ThompsonSamplingBandit(
                arm_names=registry.list_names()
            ),
        )

        # At recommendation time:
        config = manager.get_experiment_config("electronics")
        # → Use config.magnitude_multiplier, guardrail_override, etc.

        # After serving recommendation:
        manager.record_assignment("rec-123", "electronics", config)

        # After outcome measured (by Phase 1 tasks):
        result = manager.process_outcome("rec-123", success=True, reward=3.5)
    """

    def __init__(
        self,
        registry: StrategyRegistry,
        bandit: ThompsonSamplingBandit,
        compute_probabilities: bool = False,
    ):
        """
        Args:
            registry: Available pricing strategies.
            bandit: Thompson Sampling engine.
            compute_probabilities: If True, include arm probabilities
                in ExperimentConfig (expensive: ~1000 samples per call).
        """
        self._registry = registry
        self._bandit = bandit
        self._compute_probs = compute_probabilities

        # In-memory assignment store. In production, this is the DB.
        # Keyed by recommendation_id.
        self._assignments: dict[str, ExperimentAssignment] = {}

        # Counters for monitoring
        self._total_selections: int = 0
        self._total_explorations: int = 0
        self._total_outcomes_processed: int = 0

    @property
    def registry(self) -> StrategyRegistry:
        return self._registry

    @property
    def bandit(self) -> ThompsonSamplingBandit:
        return self._bandit

    @property
    def stats(self) -> dict[str, int]:
        """Monitoring counters."""
        return {
            "total_selections": self._total_selections,
            "total_explorations": self._total_explorations,
            "total_outcomes_processed": self._total_outcomes_processed,
            "active_assignments": len(self._assignments),
            "exploration_rate_actual": (
                round(self._total_explorations / self._total_selections, 4) if self._total_selections > 0 else 0.0
            ),
        }

    # ──────────────────────────────────────────────
    # RECOMMENDATION TIME: Get experiment config
    # ──────────────────────────────────────────────

    def get_experiment_config(
        self,
        category: str,
    ) -> ExperimentConfig:
        """
        Select a strategy and build experiment config for a recommendation.

        Called at recommendation time, BEFORE the scoring engine runs.
        The returned config tells the scoring engine how to behave.

        Args:
            category: Product category for this recommendation.

        Returns:
            ExperimentConfig with strategy overrides and metadata.
        """
        # ── Step 1: Select arm via Thompson Sampling ──
        selection = self._bandit.select_arm(category)
        strategy_name = selection.selected_arm

        self._total_selections += 1
        if selection.is_exploration:
            self._total_explorations += 1

        # ── Step 2: Get strategy definition ──
        try:
            strategy = self._registry.get(strategy_name)
        except KeyError:
            logger.warning(
                "Selected arm '%s' not in registry, using defaults",
                strategy_name,
            )
            return ExperimentConfig(
                strategy_name=strategy_name,
                strategy_type="unknown",
                is_exploration=selection.is_exploration,
                selection_reason=selection.selection_reason,
                sampled_values=selection.sampled_values,
            )

        # ── Step 3: Build config with strategy overrides ──
        config = ExperimentConfig(
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type.value,
            is_exploration=selection.is_exploration,
            magnitude_multiplier=strategy.magnitude_multiplier,
            guardrail_override=strategy.guardrail_override,
            weight_override=strategy.weight_override,
            selection_reason=selection.selection_reason,
            sampled_values=selection.sampled_values,
        )

        # ── Step 4: Optional probability estimation ──
        if self._compute_probs:
            config.arm_probabilities = self._bandit.get_probabilities(category, n_samples=1000)

        return config

    # ──────────────────────────────────────────────
    # AFTER RECOMMENDATION: Record assignment
    # ──────────────────────────────────────────────

    def record_assignment(
        self,
        recommendation_id: str,
        category: str,
        config: ExperimentConfig,
    ) -> ExperimentAssignment:
        """
        Record which strategy was assigned to a recommendation.

        Called AFTER the recommendation is served. The assignment is
        persisted so that when the outcome arrives (days later),
        we know which bandit arm to credit.

        In production, this writes to the pricing_outcomes table
        (strategy_arm and is_exploration columns from Phase 1 schema).
        """
        assignment = ExperimentAssignment(
            recommendation_id=recommendation_id,
            category=category,
            strategy_name=config.strategy_name,
            is_exploration=config.is_exploration,
            assigned_at=datetime.now(UTC),
            selection_reason=config.selection_reason,
            magnitude_multiplier=config.magnitude_multiplier,
            sampled_values=config.sampled_values,
        )

        self._assignments[recommendation_id] = assignment
        return assignment

    # ──────────────────────────────────────────────
    # OUTCOME PROCESSING: Feed results to bandit
    # ──────────────────────────────────────────────

    def process_outcome(
        self,
        recommendation_id: str,
        success: bool,
        reward: float = 0.0,
        assignment: ExperimentAssignment | None = None,
    ) -> OutcomeProcessingResult | None:
        """
        Process a measured outcome and update the bandit.

        Called by experiment_tasks.py when Phase 1 measurement jobs
        have computed the revenue impact for a recommendation.

        Args:
            recommendation_id: Which recommendation this outcome is for.
            success: True if revenue_delta > 0 AND recommendation was acted on.
            reward: Revenue lift % (for tracking, not used in Beta update).
            assignment: Pre-loaded assignment (skips lookup if provided).

        Returns:
            OutcomeProcessingResult, or None if assignment not found.
        """
        # ── Find the assignment ──
        if assignment is None:
            assignment = self._assignments.get(recommendation_id)

        if assignment is None:
            logger.warning("No assignment found for recommendation %s", recommendation_id)
            return None

        # ── Get arm state before update ──
        arm_before = self._bandit.get_arm_state(assignment.category, assignment.strategy_name)
        mean_before = arm_before.mean

        # ── Update bandit ──
        arm_after = self._bandit.update(
            category=assignment.category,
            arm_name=assignment.strategy_name,
            success=success,
            reward=reward,
        )

        self._total_outcomes_processed += 1

        # ── Clean up assignment (optional: keep for audit) ──
        # In production, assignments live in the DB permanently.
        # Here we remove from in-memory store to prevent unbounded growth.
        self._assignments.pop(recommendation_id, None)

        return OutcomeProcessingResult(
            recommendation_id=recommendation_id,
            category=assignment.category,
            strategy_name=assignment.strategy_name,
            success=success,
            reward=reward,
            arm_mean_before=round(mean_before, 6),
            arm_mean_after=round(arm_after.mean, 6),
            is_exploration=assignment.is_exploration,
        )

    def process_outcomes_batch(
        self,
        outcomes: list[dict],
    ) -> list[OutcomeProcessingResult]:
        """
        Process multiple outcomes at once.

        Args:
            outcomes: List of dicts with keys:
                recommendation_id, success, reward (optional),
                category (optional), strategy_name (optional).

                If category and strategy_name are provided, they're
                used directly (no assignment lookup needed). This is
                the path for the daily batch task.

        Returns:
            List of processing results (skips unknown assignments).
        """
        results = []

        for outcome in outcomes:
            rec_id = outcome["recommendation_id"]

            # If full assignment info provided, create assignment directly
            if "category" in outcome and "strategy_name" in outcome:
                assignment = ExperimentAssignment(
                    recommendation_id=rec_id,
                    category=outcome["category"],
                    strategy_name=outcome["strategy_name"],
                    is_exploration=outcome.get("is_exploration", False),
                    assigned_at=datetime.now(UTC),
                    selection_reason="batch_replay",
                )
            else:
                assignment = None

            result = self.process_outcome(
                recommendation_id=rec_id,
                success=outcome["success"],
                reward=outcome.get("reward", 0.0),
                assignment=assignment,
            )
            if result is not None:
                results.append(result)

        return results

    # ──────────────────────────────────────────────
    # ANALYSIS: Category-level experiment status
    # ──────────────────────────────────────────────

    def get_category_status(self, category: str) -> dict:
        """
        Get experiment status for a category.

        Returns a summary dict suitable for dashboards and API responses.
        """
        arms = self._bandit.get_category_states(category)
        leader = self._bandit.get_leader(category)
        converged, winner = self._bandit.has_converged(category)

        arm_summaries = []
        for name, arm in arms.items():
            summary = arm.to_dict()
            summary["is_leader"] = name == leader
            arm_summaries.append(summary)

        # Sort by mean descending
        arm_summaries.sort(key=lambda a: a["mean"], reverse=True)

        return {
            "category": category,
            "converged": converged,
            "winner": winner,
            "leader": leader,
            "arms": arm_summaries,
            "total_selections": sum(a["n_selections"] for a in arm_summaries),
            "total_updates": sum(a["n_updates"] for a in arm_summaries),
        }

    def get_all_category_statuses(self) -> list[dict]:
        """Get experiment status for all active categories."""
        return [self.get_category_status(cat) for cat in self._bandit.categories]

    # ──────────────────────────────────────────────
    # MANAGEMENT: Reset, persist, etc.
    # ──────────────────────────────────────────────

    def get_assignment(self, recommendation_id: str) -> ExperimentAssignment | None:
        """Look up a pending assignment."""
        return self._assignments.get(recommendation_id)

    def get_pending_count(self) -> int:
        """Number of assignments awaiting outcome measurement."""
        return len(self._assignments)

    def apply_magnitude(
        self,
        raw_change_pct: float,
        config: ExperimentConfig,
    ) -> float:
        """
        Apply experiment config's magnitude multiplier and guardrail cap.

        Convenience method: the recommendation service calls this after
        the scoring engine produces a raw recommendation.

        Args:
            raw_change_pct: Scoring engine's raw recommended change.
            config: ExperimentConfig from get_experiment_config().

        Returns:
            Adjusted change (multiplied and capped).
        """
        adjusted = raw_change_pct * config.magnitude_multiplier

        if config.guardrail_override and config.guardrail_override.max_change_pct is not None:
            cap = config.guardrail_override.max_change_pct
            adjusted = max(-cap, min(cap, adjusted))

        return round(adjusted, 6)
