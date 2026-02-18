"""
Agent Semantic Contracts - Typed schemas for the Scout → Analyst → Strategist pipeline.

Modularized into focused files:
  shared.py       → Enums (PriceDirection, UrgencyLevel, DataSource)
  scout.py        → ScoutOutput + sub-models
  analyst.py      → AnalystOutput + ConfidenceDecomposition + ElasticityEstimate
  strategist.py   → StrategistOutput + GuardrailCheck
  pipeline.py     → PipelineResult (full trace)
  intelligence.py → IE response schemas (calibration, benchmarks, data gaps, etc.)

All imports still work from the package root:
    from schemas.agent_contracts import ScoutOutput, AnalystOutput, StrategistOutput
    from schemas.agent_contracts import ConfidenceCalibrationResponse, DataGapResponse
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
]

