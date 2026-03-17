"""
Intelligence Environment Orchestrator
======================================
Phase 5 — Integration Wiring

The single entry point that makes Phases 1-3 live. Calls:
  ExperimentManager > ScoringEngine > ContextInjector > Calibrator

Location: backend/services/scoring/ie_orchestrator.py

Design:
  - Dependency injection: all collaborators are callables, not DB sessions
  - Circuit breakers: each component can fail independently
  - Feature flag: per-merchant IE enable/disable
  - Latency budget: total p99 < 500ms target
  - Every call returns typed IERecommendation with full evidence chain
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types (frozen dataclasses — immutable after creation)
# ---------------------------------------------------------------------------


class IEStatus(str, Enum):
    """Overall status of the IE recommendation pipeline."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Some components failed, result still usable
    FALLBACK = "fallback"  # IE unavailable, fell back to legacy
    ERROR = "error"  # Complete failure


@dataclass(frozen=True)
class ComponentTiming:
    """Latency tracking per component for observability."""

    component: str
    duration_ms: float
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class ExperimentContext:
    """What the ExperimentManager decided for this recommendation."""

    strategy_name: str
    arm_index: int
    is_exploration: bool
    magnitude_multiplier: float
    guardrail_overrides: dict[str, Any]
    weight_overrides: dict[str, float]
    assignment_id: str | None = None


@dataclass(frozen=True)
class CalibrationAdjustment:
    """How the Calibrator modified the raw confidence."""

    raw_confidence: float
    calibrated_confidence: float
    calibration_method: str  # "isotonic", "identity", "uncalibrated"
    sample_count: int  # How many outcomes backed this calibration
    is_reliable: bool  # True if sample_count >= min_threshold


@dataclass(frozen=True)
class IERecommendation:
    """
    The final output — a fully-traced recommendation with experiment
    metadata, calibrated confidence, and evidence chain.
    """

    recommendation_id: str
    product_id: str
    merchant_id: str
    category_id: str | None
    timestamp: datetime

    # The recommendation itself
    current_price: float
    suggested_price: float
    change_pct: float
    direction: str  # "increase" | "decrease" | "hold"

    # Scoring
    raw_confidence: float
    calibrated_confidence: float
    confidence_decomposition: dict[str, Any]
    scoring_evidence: dict[str, Any]

    # Experiment
    experiment: ExperimentContext | None
    calibration: CalibrationAdjustment | None

    # Context injection
    category_context: dict[str, Any] | None

    # Observability
    status: IEStatus
    timings: list[ComponentTiming]
    total_duration_ms: float
    pipeline_version: str
    warnings: list[str]
    ie_enabled: bool  # Was IE actually used?


# ---------------------------------------------------------------------------
# Protocol definitions (what each collaborator must provide)
# ---------------------------------------------------------------------------


class ExperimentManagerProtocol(Protocol):
    """Interface for the Thompson Sampling experiment manager."""

    def get_experiment_config(self, category_id: str, merchant_id: str) -> dict[str, Any]:
        """Select a strategy arm for this category. Returns config dict."""
        ...

    def record_assignment(self, recommendation_id: str, category_id: str, arm_index: int, is_exploration: bool) -> str:
        """Persist which arm was selected. Returns assignment_id."""
        ...


class ScoringEngineProtocol(Protocol):
    """Interface for the deterministic scoring engine."""

    def score(self, product_context: dict[str, Any]) -> dict[str, Any]:
        """Run all 4 scorers, fuse, apply guardrails. Returns ScoringResult dict."""
        ...


class ContextInjectorProtocol(Protocol):
    """Interface for Tier 1 context injection."""

    def get_scoring_context(self, category_id: str) -> dict[str, Any]:
        """Return structured historical context for this category."""
        ...

    def get_agent_context_string(self, category_id: str) -> str:
        """Return natural language context for Gemini prompts."""
        ...


class CalibratorProtocol(Protocol):
    """Interface for confidence calibration."""

    def calibrate(self, raw_confidence: float, category_id: str) -> dict[str, Any]:
        """Adjust confidence based on historical accuracy. Returns calibration dict."""
        ...


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IEOrchestratorConfig:
    """Configuration for the orchestrator. Frozen = immutable after creation."""

    pipeline_version: str = "ie-v1.0"
    min_calibration_samples: int = 30
    enable_experiments: bool = True
    enable_calibration: bool = True
    enable_context_injection: bool = True
    component_timeout_ms: float = 200.0  # Per-component timeout budget
    total_timeout_ms: float = 500.0  # Total p99 target
    fallback_on_error: bool = True  # Fall back to legacy on IE failure


# ---------------------------------------------------------------------------
# The Orchestrator
# ---------------------------------------------------------------------------


class IEOrchestrator:
    """
    Wires the Intelligence Environment pipeline into a live recommendation.

    Flow:
      1. Check feature flag (is IE enabled for this merchant?)
      2. ExperimentManager.get_experiment_config() → selects strategy arm
      3. ContextInjector.get_scoring_context() → historical category data
      4. ScoringEngine.score() → deterministic scores with strategy overrides
      5. Calibrator.calibrate() → adjust confidence from historical accuracy
      6. ExperimentManager.record_assignment() → persist experiment metadata
      7. Return IERecommendation with full evidence chain

    All components are injected. Any component can fail independently —
    the orchestrator degrades gracefully and tracks what failed.
    """

    def __init__(
        self,
        experiment_manager: ExperimentManagerProtocol,
        scoring_engine: ScoringEngineProtocol,
        context_injector: ContextInjectorProtocol,
        calibrator: CalibratorProtocol,
        config: IEOrchestratorConfig | None = None,
        is_ie_enabled: Callable[[str], bool] | None = None,
    ):
        self._experiment_manager = experiment_manager
        self._scoring_engine = scoring_engine
        self._context_injector = context_injector
        self._calibrator = calibrator
        self._config = config or IEOrchestratorConfig()
        # Feature flag check — defaults to always-on if not provided
        self._is_ie_enabled = is_ie_enabled or (lambda merchant_id: True)

    def generate_recommendation(
        self,
        product_context: dict[str, Any],
    ) -> IERecommendation:
        """
        Generate a fully-traced IE recommendation for a product.

        Args:
            product_context: Dict containing at minimum:
                - product_id: str
                - merchant_id: str
                - category_id: str (optional)
                - current_price: float
                - cost: float (optional, for margin calc)
                - competitor_prices: list[float]
                - historical_sales: list[dict] (optional)

        Returns:
            IERecommendation with full evidence chain and experiment metadata.
        """
        start_time = time.monotonic()
        timings: list[ComponentTiming] = []
        warnings: list[str] = []

        product_id = product_context.get("product_id", "unknown")
        merchant_id = product_context.get("merchant_id", "unknown")
        category_id = product_context.get("category_id")
        current_price = product_context.get("current_price", 0.0)
        recommendation_id = str(uuid.uuid4())

        # ── Step 0: Feature flag check ──
        ie_enabled = self._is_ie_enabled(merchant_id)
        if not ie_enabled:
            return self._build_legacy_fallback(
                recommendation_id, product_context, timings, warnings, reason="IE disabled for merchant"
            )

        # ── Step 1: Experiment selection ──
        experiment_ctx = None
        if self._config.enable_experiments and category_id:
            experiment_ctx, timing = self._run_experiment_selection(category_id, merchant_id)
            timings.append(timing)
            if experiment_ctx:
                # Apply strategy overrides to product_context
                product_context = self._apply_strategy_overrides(product_context, experiment_ctx)
            else:
                warnings.append("Experiment selection failed; using default weights")

        # ── Step 2: Context injection ──
        category_context = None
        if self._config.enable_context_injection and category_id:
            category_context, timing = self._run_context_injection(category_id)
            timings.append(timing)
            if category_context:
                product_context["category_context"] = category_context
            else:
                warnings.append("Context injection failed; scoring without historical context")

        # ── Step 3: Deterministic scoring ──
        scoring_result, timing = self._run_scoring(product_context)
        timings.append(timing)
        if not scoring_result:
            if self._config.fallback_on_error:
                return self._build_legacy_fallback(
                    recommendation_id, product_context, timings, warnings, reason="Scoring engine failed"
                )
            return self._build_error_result(
                recommendation_id, product_context, timings, warnings, reason="Scoring engine failed"
            )

        # ── Step 4: Calibration ──
        calibration_adj = None
        raw_confidence = scoring_result.get("confidence", 0.5)
        calibrated_confidence = raw_confidence

        if self._config.enable_calibration and category_id:
            calibration_adj, timing = self._run_calibration(raw_confidence, category_id)
            timings.append(timing)
            if calibration_adj:
                calibrated_confidence = calibration_adj.calibrated_confidence
            else:
                warnings.append("Calibration failed; using raw confidence")

        # ── Step 5: Record experiment assignment ──
        if experiment_ctx and self._config.enable_experiments:
            assignment_timing = self._run_experiment_recording(
                recommendation_id, category_id, experiment_ctx.arm_index, experiment_ctx.is_exploration
            )
            timings.append(assignment_timing)

        # ── Step 6: Build final recommendation ──
        suggested_price = scoring_result.get("suggested_price", current_price)
        change_pct = ((suggested_price - current_price) / current_price * 100) if current_price > 0 else 0.0
        direction = "increase" if change_pct > 0.1 else "decrease" if change_pct < -0.1 else "hold"

        total_ms = (time.monotonic() - start_time) * 1000

        # Latency warning
        if total_ms > self._config.total_timeout_ms:
            warnings.append(f"Total latency {total_ms:.0f}ms exceeded budget {self._config.total_timeout_ms:.0f}ms")

        status = IEStatus.SUCCESS
        if warnings:
            status = IEStatus.PARTIAL

        return IERecommendation(
            recommendation_id=recommendation_id,
            product_id=product_id,
            merchant_id=merchant_id,
            category_id=category_id,
            timestamp=datetime.now(UTC),
            current_price=current_price,
            suggested_price=round(suggested_price, 2),
            change_pct=round(change_pct, 2),
            direction=direction,
            raw_confidence=round(raw_confidence, 4),
            calibrated_confidence=round(calibrated_confidence, 4),
            confidence_decomposition=scoring_result.get("confidence_decomposition", {}),
            scoring_evidence=scoring_result.get("evidence", {}),
            experiment=experiment_ctx,
            calibration=calibration_adj,
            category_context=category_context,
            status=status,
            timings=timings,
            total_duration_ms=round(total_ms, 2),
            pipeline_version=self._config.pipeline_version,
            warnings=warnings,
            ie_enabled=True,
        )

    # -------------------------------------------------------------------
    # Private: run each component with timing + error isolation
    # -------------------------------------------------------------------

    def _run_experiment_selection(
        self, category_id: str, merchant_id: str
    ) -> tuple[ExperimentContext | None, ComponentTiming]:
        """Call ExperimentManager.get_experiment_config() with circuit breaker."""
        t0 = time.monotonic()
        try:
            config = self._experiment_manager.get_experiment_config(category_id, merchant_id)
            duration = (time.monotonic() - t0) * 1000
            ctx = ExperimentContext(
                strategy_name=config.get("strategy_name", "default"),
                arm_index=config.get("arm_index", 0),
                is_exploration=config.get("is_exploration", False),
                magnitude_multiplier=config.get("magnitude_multiplier", 1.0),
                guardrail_overrides=config.get("guardrail_overrides", {}),
                weight_overrides=config.get("weight_overrides", {}),
            )
            return ctx, ComponentTiming(
                component="experiment_manager",
                duration_ms=round(duration, 2),
                success=True,
            )
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.warning("ExperimentManager.get_experiment_config failed: %s", exc)
            return None, ComponentTiming(
                component="experiment_manager",
                duration_ms=round(duration, 2),
                success=False,
                error=str(exc),
            )

    def _run_context_injection(self, category_id: str) -> tuple[dict[str, Any] | None, ComponentTiming]:
        """Call ContextInjector.get_scoring_context() with circuit breaker."""
        t0 = time.monotonic()
        try:
            context = self._context_injector.get_scoring_context(category_id)
            duration = (time.monotonic() - t0) * 1000
            return context, ComponentTiming(
                component="context_injector",
                duration_ms=round(duration, 2),
                success=True,
            )
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.warning("ContextInjector.get_scoring_context failed: %s", exc)
            return None, ComponentTiming(
                component="context_injector",
                duration_ms=round(duration, 2),
                success=False,
                error=str(exc),
            )

    def _run_scoring(self, product_context: dict[str, Any]) -> tuple[dict[str, Any] | None, ComponentTiming]:
        """Call ScoringEngine.score() with circuit breaker."""
        t0 = time.monotonic()
        try:
            result = self._scoring_engine.score(product_context)
            duration = (time.monotonic() - t0) * 1000
            return result, ComponentTiming(
                component="scoring_engine",
                duration_ms=round(duration, 2),
                success=True,
            )
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.error("ScoringEngine.score failed: %s", exc, exc_info=True)
            return None, ComponentTiming(
                component="scoring_engine",
                duration_ms=round(duration, 2),
                success=False,
                error=str(exc),
            )

    def _run_calibration(
        self, raw_confidence: float, category_id: str
    ) -> tuple[CalibrationAdjustment | None, ComponentTiming]:
        """Call Calibrator.calibrate() with circuit breaker."""
        t0 = time.monotonic()
        try:
            result = self._calibrator.calibrate(raw_confidence, category_id)
            duration = (time.monotonic() - t0) * 1000
            adj = CalibrationAdjustment(
                raw_confidence=raw_confidence,
                calibrated_confidence=result.get("calibrated", raw_confidence),
                calibration_method=result.get("method", "uncalibrated"),
                sample_count=result.get("sample_count", 0),
                is_reliable=result.get("sample_count", 0) >= self._config.min_calibration_samples,
            )
            return adj, ComponentTiming(
                component="calibrator",
                duration_ms=round(duration, 2),
                success=True,
            )
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.warning("Calibrator.calibrate failed: %s", exc)
            return None, ComponentTiming(
                component="calibrator",
                duration_ms=round(duration, 2),
                success=False,
                error=str(exc),
            )

    def _run_experiment_recording(
        self, recommendation_id: str, category_id: str, arm_index: int, is_exploration: bool
    ) -> ComponentTiming:
        """Call ExperimentManager.record_assignment() — fire-and-forget."""
        t0 = time.monotonic()
        try:
            self._experiment_manager.record_assignment(recommendation_id, category_id, arm_index, is_exploration)
            duration = (time.monotonic() - t0) * 1000
            return ComponentTiming(
                component="experiment_recording",
                duration_ms=round(duration, 2),
                success=True,
            )
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.warning("ExperimentManager.record_assignment failed: %s", exc)
            return ComponentTiming(
                component="experiment_recording",
                duration_ms=round(duration, 2),
                success=False,
                error=str(exc),
            )

    # -------------------------------------------------------------------
    # Strategy override application
    # -------------------------------------------------------------------

    def _apply_strategy_overrides(
        self, product_context: dict[str, Any], experiment: ExperimentContext
    ) -> dict[str, Any]:
        """
        Apply Thompson Sampling strategy overrides to the product context.

        The ScoringEngine reads these overrides to adjust:
        - Weight distribution across 4 scorers
        - Guardrail caps (max_change_pct, min_margin)
        - Magnitude multiplier on final suggested price change
        """
        # Shallow copy — don't mutate the caller's dict
        ctx = dict(product_context)
        ctx["strategy_overrides"] = {
            "strategy_name": experiment.strategy_name,
            "magnitude_multiplier": experiment.magnitude_multiplier,
            "guardrail_overrides": experiment.guardrail_overrides,
            "weight_overrides": experiment.weight_overrides,
            "is_exploration": experiment.is_exploration,
        }
        return ctx

    # -------------------------------------------------------------------
    # Fallback / error builders
    # -------------------------------------------------------------------

    def _build_legacy_fallback(
        self,
        recommendation_id: str,
        product_context: dict[str, Any],
        timings: list[ComponentTiming],
        warnings: list[str],
        reason: str,
    ) -> IERecommendation:
        """Build a recommendation that signals 'use legacy pipeline instead'."""
        warnings.append(f"IE fallback: {reason}")
        current_price = product_context.get("current_price", 0.0)
        return IERecommendation(
            recommendation_id=recommendation_id,
            product_id=product_context.get("product_id", "unknown"),
            merchant_id=product_context.get("merchant_id", "unknown"),
            category_id=product_context.get("category_id"),
            timestamp=datetime.now(UTC),
            current_price=current_price,
            suggested_price=current_price,  # No change in fallback
            change_pct=0.0,
            direction="hold",
            raw_confidence=0.0,
            calibrated_confidence=0.0,
            confidence_decomposition={},
            scoring_evidence={},
            experiment=None,
            calibration=None,
            category_context=None,
            status=IEStatus.FALLBACK,
            timings=timings,
            total_duration_ms=0.0,
            pipeline_version=self._config.pipeline_version,
            warnings=warnings,
            ie_enabled=False,
        )

    def _build_error_result(
        self,
        recommendation_id: str,
        product_context: dict[str, Any],
        timings: list[ComponentTiming],
        warnings: list[str],
        reason: str,
    ) -> IERecommendation:
        """Build an error result when fallback is disabled."""
        warnings.append(f"IE error: {reason}")
        current_price = product_context.get("current_price", 0.0)
        return IERecommendation(
            recommendation_id=recommendation_id,
            product_id=product_context.get("product_id", "unknown"),
            merchant_id=product_context.get("merchant_id", "unknown"),
            category_id=product_context.get("category_id"),
            timestamp=datetime.now(UTC),
            current_price=current_price,
            suggested_price=current_price,
            change_pct=0.0,
            direction="hold",
            raw_confidence=0.0,
            calibrated_confidence=0.0,
            confidence_decomposition={},
            scoring_evidence={},
            experiment=None,
            calibration=None,
            category_context=None,
            status=IEStatus.ERROR,
            timings=timings,
            total_duration_ms=0.0,
            pipeline_version=self._config.pipeline_version,
            warnings=warnings,
            ie_enabled=True,
        )


# ---------------------------------------------------------------------------
# Factory: wires real implementations together
# ---------------------------------------------------------------------------


def create_ie_orchestrator(
    db_session_factory: Callable,
    merchant_feature_flags: dict[str, bool] | None = None,
) -> IEOrchestrator:
    """
    Factory that wires the real implementations from Phases 2-3.

    Call this from your FastAPI dependency injection or Celery task setup.

    Args:
        db_session_factory: Callable that returns a SQLAlchemy async session
        merchant_feature_flags: Optional dict of merchant_id -> ie_enabled

    Example:
        orchestrator = create_ie_orchestrator(get_db)
        result = orchestrator.generate_recommendation(product_context)
    """
    # Lazy imports to avoid circular deps — these are the Phase 2-3 modules
    from services.scoring.engine import ScoringEngine
    from services.scoring.experimentation.experiment_manager import (
        ExperimentManager,
    )
    from services.scoring.learning.calibrator import Calibrator
    from services.scoring.learning.context_injector import ContextInjector

    # Feature flag check
    flags = merchant_feature_flags or {}

    def is_ie_enabled(merchant_id: str) -> bool:
        # Default: enabled for all merchants (can be overridden per-merchant)
        return flags.get(merchant_id, True)

    return IEOrchestrator(
        experiment_manager=ExperimentManager(db_session_factory),
        scoring_engine=ScoringEngine(),
        context_injector=ContextInjector(db_session_factory),
        calibrator=Calibrator(db_session_factory),
        config=IEOrchestratorConfig(),
        is_ie_enabled=is_ie_enabled,
    )
