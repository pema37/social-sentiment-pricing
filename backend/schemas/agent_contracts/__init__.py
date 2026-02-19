"""
Agent Semantic Contracts - Typed schemas for the Scout → Analyst → Strategist pipeline.

Modularized into focused files:
  shared.py       → Enums (PriceDirection, UrgencyLevel, DataSource)
  scout.py        → ScoutOutput + sub-models
  analyst.py      → AnalystOutput + ConfidenceDecomposition + ElasticityEstimate
  strategist.py   → StrategistOutput + GuardrailCheck
  pipeline.py     → PipelineResult (full trace)
  intelligence.py → IE response schemas (calibration, benchmarks, data gaps, etc.)

Phase 4 additions:
  contracts_v2.py        → Enhanced input AND output contracts with provenance hashing
  validation.py          → Runtime boundary enforcement (AgentValidator, PipelineValidator)
  conflict_resolution.py → Deterministic conflict resolution protocols
  tracing.py             → Pipeline observability (PipelineTracer, TraceSpan)

All imports still work from the package root:
    from schemas.agent_contracts import ScoutOutput, AnalystOutput, StrategistOutput
    from schemas.agent_contracts import ConfidenceCalibrationResponse, DataGapResponse
    from schemas.agent_contracts import AgentValidator, ConflictResolver, PipelineTracer
"""

# ── Shared types ──
from .shared import (
    PriceDirection,
    UrgencyLevel,
    DataSource,
)

# ── Scout ──
from .scout import (
    CompetitorPrice,
    SentimentSnapshot,
    PriceHistoryPoint,
    ScoutOutput,
)

# ── Analyst ──
from .analyst import (
    ElasticityEstimate,
    ConfidenceDecomposition,
    AnalystOutput,
)

# ── Strategist ──
from .strategist import (
    GuardrailCheck,
    StrategistOutput,
)

# ── Pipeline ──
from .pipeline import (
    PipelineResult,
)

# ── Intelligence Environment Responses ──
from .intelligence import (
    CalibrationBucket,
    ConfidenceCalibrationResponse,
    ModificationDetail,
    MerchantPatternResponse,
    CategoryBenchmarkResponse,
    DataGapDetail,
    DataGapFailureRate,
    DataGapResponse,
    ElasticityAccuracyBucket,
    ElasticityAccuracyResponse,
    OutcomeCardData,
    AccuracyStats,
)

# ── Phase 4: Enhanced Semantic Contracts ──
from .contracts_v2 import (
    # Shared types (prefixed to avoid collision with Phase 1 PriceDirection)
    PriceDirection as PriceDirectionV2,
    DataQualityLevel,
    ContractViolation,
    compute_provenance_hash,
    # Scout V2
    CompetitorPrice as CompetitorPriceV2,
    ScoutInput,
    ScoutOutput as ScoutOutputV2,
    # Analyst V2
    ElasticityEstimate as ElasticityEstimateV2,
    PositionIndex,
    UrgencyScore,
    AnalystInput,
    AnalystOutput as AnalystOutputV2,
    # Strategist V2
    GuardrailVerification,
    StrategistInput,
    StrategistOutput as StrategistOutputV2,
)

from .validation import (
    AgentValidator,
    PipelineValidator,
    ValidationResult,
    ValidationStatus,
)

from .conflict_resolution import (
    ConflictResolver,
    ConflictResolution,
    ConflictType,
)

from .tracing import (
    PipelineTracer,
    PipelineTrace,
    TraceSpan,
)

__all__ = [
    # Shared
    "PriceDirection",
    "UrgencyLevel",
    "DataSource",
    # Scout
    "CompetitorPrice",
    "SentimentSnapshot",
    "PriceHistoryPoint",
    "ScoutOutput",
    # Analyst
    "ElasticityEstimate",
    "ConfidenceDecomposition",
    "AnalystOutput",
    # Strategist
    "GuardrailCheck",
    "StrategistOutput",
    # Pipeline
    "PipelineResult",
    # Intelligence
    "CalibrationBucket",
    "ConfidenceCalibrationResponse",
    "ModificationDetail",
    "MerchantPatternResponse",
    "CategoryBenchmarkResponse",
    "DataGapDetail",
    "DataGapFailureRate",
    "DataGapResponse",
    "ElasticityAccuracyBucket",
    "ElasticityAccuracyResponse",
    "OutcomeCardData",
    "AccuracyStats",
    # Phase 4: Enhanced Contracts V2
    "PriceDirectionV2",
    "DataQualityLevel",
    "ContractViolation",
    "compute_provenance_hash",
    "CompetitorPriceV2",
    "ScoutInput",
    "ScoutOutputV2",
    "ElasticityEstimateV2",
    "PositionIndex",
    "UrgencyScore",
    "AnalystInput",
    "AnalystOutputV2",
    "GuardrailVerification",
    "StrategistInput",
    "StrategistOutputV2",
    # Phase 4: Validation
    "AgentValidator",
    "PipelineValidator",
    "ValidationResult",
    "ValidationStatus",
    # Phase 4: Conflict Resolution
    "ConflictResolver",
    "ConflictResolution",
    "ConflictType",
    # Phase 4: Tracing
    "PipelineTracer",
    "PipelineTrace",
    "TraceSpan",
]


