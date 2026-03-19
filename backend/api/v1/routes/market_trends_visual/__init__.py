"""
Market Trends Visual Analyzer Module

Multi-Agent Trend Analysis System using Gemini 3 with multimodal support.

Agents:
1. Observer Agent - Scans market data and visual charts for patterns
2. Analyst Agent - Interprets correlations, drivers, and risks
3. Forecaster Agent - Predicts trends and recommends pricing actions

Usage:
    # In main.py
    from api.v1.routes.market_trends_visual import router as market_trends_visual_router
    app.include_router(market_trends_visual_router, prefix="/api/v1")

    # Direct service usage
    from api.v1.routes.market_trends_visual import market_trends_analyzer
    async for msg in market_trends_analyzer.analyze_stream(...):
        print(msg.content)
"""

# Export router for FastAPI app registration
from .router import router

# Export schemas for type hints
from .schemas import (
    MarketDataInput,
    MarketDataPoint,
    TrendAgent,
    TrendAnalysisResponse,
    TrendDirection,
    TrendForecast,
    TrendHealthResponse,
    TrendMessage,
    TrendTimeframe,
)

# Export service for direct usage
from .service import MarketTrendsAnalyzer, market_trends_analyzer

__all__ = [
    # Pydantic models
    "MarketDataInput",
    "MarketDataPoint",
    "MarketTrendsAnalyzer",
    # Enums
    "TrendAgent",
    "TrendAnalysisResponse",
    "TrendDirection",
    "TrendForecast",
    "TrendHealthResponse",
    # Data classes
    "TrendMessage",
    "TrendTimeframe",
    # Service
    "market_trends_analyzer",
    # Router
    "router",
]
