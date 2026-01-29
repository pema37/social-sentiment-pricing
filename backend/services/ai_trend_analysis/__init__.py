"""
AI Trend Analysis Module

Provides AI-powered market analysis, trend predictions,
pricing opportunities, and risk detection.

NEW: Visual Pricing Intelligence with multi-agent analysis.
"""

from .analyzer import AITrendAnalyzer
from .ai_clients import (
    ai_clients,
    AIClients,
    StreamChunk,
    ThoughtType,
    ImageAnalysisResult,
)
from .visual_analyzer import (
    visual_analyzer,
    VisualPricingAnalyzer,
    AgentRole,
    AgentMessage,
    ProductInfo,
    PricingRecommendation,
)
from .models import (
    TrendAnalysisResult,
    TrendPrediction,
    PricingOpportunity,
    RiskAlert,
    AIInsight,
    TrendSignal,
    TrendDirection,
    TrendCategory,
    OpportunityType,
    RiskLevel,
    ConfidenceLevel,
)

__all__ = [
    # Existing
    "AITrendAnalyzer",
    "TrendAnalysisResult",
    "TrendPrediction",
    "PricingOpportunity",
    "RiskAlert",
    "AIInsight",
    "TrendSignal",
    "TrendDirection",
    "TrendCategory",
    "OpportunityType",
    "RiskLevel",
    "ConfidenceLevel",
    # AI Clients (new exports)
    "ai_clients",
    "AIClients",
    "StreamChunk",
    "ThoughtType",
    "ImageAnalysisResult",
    # Visual Analyzer (NEW)
    "visual_analyzer",
    "VisualPricingAnalyzer",
    "AgentRole",
    "AgentMessage",
    "ProductInfo",
    "PricingRecommendation",
]


