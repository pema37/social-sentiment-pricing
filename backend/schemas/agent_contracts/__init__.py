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
# ── Analyst ──
from .analyst import (
    AnalystOutput,
    ConfidenceDecomposition,
    ElasticityEstimate,
)
from .conflict_resolution import (
    ConflictResolution,
    ConflictResolver,
    ConflictType,
)
from .contracts_v2 import (
    AnalystInput,
    ContractViolation,
    DataQualityLevel,
    # Strategist V2
    GuardrailVerification,
    PositionIndex,
    ScoutInput,
    StrategistInput,
    UrgencyScore,
    compute_provenance_hash,
)
from .contracts_v2 import (
    AnalystOutput as AnalystOutputV2,
)
from .contracts_v2 import (
    # Scout V2
    CompetitorPrice as CompetitorPriceV2,
)
from .contracts_v2 import (
    # Analyst V2
    ElasticityEstimate as ElasticityEstimateV2,
)

# ── Phase 4: Enhanced Semantic Contracts ──
from .contracts_v2 import (
    # Shared types (prefixed to avoid collision with Phase 1 PriceDirection)
    PriceDirection as PriceDirectionV2,
)
from .contracts_v2 import (
    ScoutOutput as ScoutOutputV2,
)
from .contracts_v2 import (
    StrategistOutput as StrategistOutputV2,
)

# ── Intelligence Environment Responses ──
from .intelligence import (
    AccuracyStats,
    CalibrationBucket,
    CategoryBenchmarkResponse,
    ConfidenceCalibrationResponse,
    DataGapDetail,
    DataGapFailureRate,
    DataGapResponse,
    ElasticityAccuracyBucket,
    ElasticityAccuracyResponse,
    MerchantPatternResponse,
    ModificationDetail,
    OutcomeCardData,
)

# ── Pipeline ──
from .pipeline import (
    PipelineResult,
)

# ── Scout ──
from .scout import (
    CompetitorPrice,
    PriceHistoryPoint,
    ScoutOutput,
    SentimentSnapshot,
)
from .shared import (
    DataSource,
    PriceDirection,
    UrgencyLevel,
)

# ── Strategist ──
from .strategist import (
    GuardrailCheck,
    StrategistOutput,
)
from .tracing import (
    PipelineTrace,
    PipelineTracer,
    TraceSpan,
)
from .validation import (
    AgentValidator,
    PipelineValidator,
    ValidationResult,
    ValidationStatus,
)

__all__ = [
    "AccuracyStats",
    # Phase 4: Validation
    "AgentValidator",
    "AnalystInput",
    "AnalystOutput",
    "AnalystOutputV2",
    # Intelligence
    "CalibrationBucket",
    "CategoryBenchmarkResponse",
    # Scout
    "CompetitorPrice",
    "CompetitorPriceV2",
    "ConfidenceCalibrationResponse",
    "ConfidenceDecomposition",
    "ConflictResolution",
    # Phase 4: Conflict Resolution
    "ConflictResolver",
    "ConflictType",
    "ContractViolation",
    "DataGapDetail",
    "DataGapFailureRate",
    "DataGapResponse",
    "DataQualityLevel",
    "DataSource",
    "ElasticityAccuracyBucket",
    "ElasticityAccuracyResponse",
    # Analyst
    "ElasticityEstimate",
    "ElasticityEstimateV2",
    # Strategist
    "GuardrailCheck",
    "GuardrailVerification",
    "MerchantPatternResponse",
    "ModificationDetail",
    "OutcomeCardData",
    # Pipeline
    "PipelineResult",
    "PipelineTrace",
    # Phase 4: Tracing
    "PipelineTracer",
    "PipelineValidator",
    "PositionIndex",
    # Shared
    "PriceDirection",
    # Phase 4: Enhanced Contracts V2
    "PriceDirectionV2",
    "PriceHistoryPoint",
    "ScoutInput",
    "ScoutOutput",
    "ScoutOutputV2",
    "SentimentSnapshot",
    "StrategistInput",
    "StrategistOutput",
    "StrategistOutputV2",
    "TraceSpan",
    "UrgencyLevel",
    "UrgencyScore",
    "ValidationResult",
    "ValidationStatus",
    "compute_provenance_hash",
]
