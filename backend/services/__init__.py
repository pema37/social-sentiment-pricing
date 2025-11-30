# backend/services/__init__.py

"""
Business Logic Services

Core services for sentiment analysis, pricing, and competitor tracking.
"""

from backend.services.sentiment_analyzer import (
    SentimentAnalyzer,
    sentiment_analyzer,
)
from backend.services.pricing_engine import (
    PricingEngine,
    pricing_engine,
    CompetitorPriceData,
)

# Phase 2: Competitor Scraping
from backend.services.competitor_scraper import (
    CompetitorScraperService,
    competitor_scraper,
    ScrapeResult,
)


__all__ = [
    # Sentiment Analysis
    "SentimentAnalyzer",
    "sentiment_analyzer",
    # Pricing Engine
    "PricingEngine",
    "pricing_engine",
    "CompetitorPriceData",
    # Competitor Scraping (Phase 2)
    "CompetitorScraperService",
    "competitor_scraper",
    "ScrapeResult",
]

