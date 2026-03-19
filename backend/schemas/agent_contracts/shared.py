"""Shared types used across all agent contract schemas."""

from enum import StrEnum


class PriceDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    HOLD = "hold"


class UrgencyLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class DataSource(StrEnum):
    COMPETITOR_SCRAPE = "competitor_scrape"
    SOCIAL_SENTIMENT = "social_sentiment"
    PRICE_HISTORY = "price_history"
    SALES_DATA = "sales_data"
    MARKET_TREND = "market_trend"
    CRISIS_DETECTION = "crisis_detection"
