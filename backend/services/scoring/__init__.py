"""
Scoring Engine — Deterministic pricing intelligence.

Phase 2 of the Intelligence Environment Architecture.
Replaces LLM-dependent analysis with Bayesian math, percentile
ranking, weighted composites, and deterministic business rules.

Zero LLM calls. Pure Python math. Fully testable.

Phase 5 addition: IE Orchestrator wires ExperimentManager → ScoringEngine
→ ContextInjector → Calibrator into a single entry point for the
recommendation pipeline.

Usage:
    from services.scoring import ScoringEngine

    engine = ScoringEngine()
    result = engine.score(
        scout_output=scout_output,
        signals=market_signals,
        product_category="electronics",
        product_cost=30.0,
    )

    # result.analyst_fields → dict for AnalystOutput constructor
    # result.fusion → FusionResult with recommended price + reasoning
    # result.elasticity → ElasticityResult with Bayesian PED estimate
    # result.position → PositionResult with percentile rank
    # result.urgency → UrgencyResult with weighted composite

    # Phase 5: IE Orchestrator (full pipeline)
    from services.scoring import create_ie_orchestrator, IEStatus

    orchestrator = create_ie_orchestrator(db_session_factory=get_db)
    ie_result = orchestrator.generate_recommendation(product_context)
    if ie_result.status == IEStatus.SUCCESS:
        use ie_result.suggested_price, ie_result.calibrated_confidence

Package structure:
    scoring/
    ├── __init__.py              ← you are here
    ├── engine.py                ← orchestrator (entry point)
    ├── category_priors.py       ← Bayesian prior data store
    ├── elasticity_calculator.py ← Bayesian hierarchical PED model
    ├── competitive_position.py  ← percentile ranking + CPI
    ├── urgency_scorer.py        ← weighted 5-signal composite
    ├── score_fusion.py          ← direction + magnitude + conflict resolution
    ├── fusion_types.py          ← enums, configs, result types, magnitude tables
    ├── guardrails.py            ← margin floor, max change, velocity cap, rate limit
    ├── ie_orchestrator.py       ← Phase 5: full IE pipeline entry point
    ├── experimentation/         ← Phase 3B: Thompson Sampling bandits
    └── learning/                ← Phase 3A/C: batch learning, calibration, drift
"""

# ── Engine (primary entry point) ──
# ── Priors (exposed for Tier 2 batch updates) ──
from .category_priors import (
    CategoryPrior,
    CategoryPriorStore,
)
from .competitive_position import (
    CompetitivePositionCalculator,
    CompetitorPricePoint,
    PositionResult,
)

# ── Component calculators ──
from .elasticity_calculator import (
    ElasticityCalculator,
    ElasticityResult,
    PriceChangeEvent,
)
from .engine import ScoringEngine, ScoringEngineResult
from .fusion_types import (
    ELASTICITY_MAGNITUDE,
    POSITION_DIRECTION_BIAS,
    URGENCY_MULTIPLIER,
    ConflictType,
    FusionResult,
    GuardrailConfig,
    GuardrailResult,
    GuardrailType,
    PriceChange,
    ProductContext,
)
from .guardrails import GuardrailEnforcer

# ── Phase 5: IE Orchestrator (full pipeline entry point) ──
from .ie_orchestrator import (
    CalibrationAdjustment,
    ComponentTiming,
    ExperimentContext,
    IEOrchestrator,
    IEOrchestratorConfig,
    IERecommendation,
    IEStatus,
    create_ie_orchestrator,
)

# ── Fusion layer ──
from .score_fusion import ScoreFusion
from .urgency_scorer import (
    UrgencyResult,
    UrgencyScorer,
    UrgencySignals,
)

__all__ = [
    # Magnitude tables
    "ELASTICITY_MAGNITUDE",
    "POSITION_DIRECTION_BIAS",
    "URGENCY_MULTIPLIER",
    "CalibrationAdjustment",
    "CategoryPrior",
    # Priors
    "CategoryPriorStore",
    "CompetitivePositionCalculator",
    "CompetitorPricePoint",
    "ComponentTiming",
    "ConflictType",
    # Calculators
    "ElasticityCalculator",
    "ElasticityResult",
    "ExperimentContext",
    "FusionResult",
    "GuardrailConfig",
    "GuardrailEnforcer",
    "GuardrailResult",
    "GuardrailType",
    # Phase 5: IE Orchestrator
    "IEOrchestrator",
    "IEOrchestratorConfig",
    "IERecommendation",
    "IEStatus",
    "PositionResult",
    "PriceChange",
    "PriceChangeEvent",
    "ProductContext",
    # Fusion
    "ScoreFusion",
    # Engine
    "ScoringEngine",
    "ScoringEngineResult",
    "UrgencyResult",
    "UrgencyScorer",
    "UrgencySignals",
    "create_ie_orchestrator",
]
