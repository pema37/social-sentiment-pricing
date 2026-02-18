"""Shared types used across all agent contract schemas."""

from enum import Enum


class PriceDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    HOLD = "hold"


class UrgencyLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class DataSource(str, Enum):
    COMPETITOR_SCRAPE = "competitor_scrape"
    SOCIAL_SENTIMENT = "social_sentiment"
    PRICE_HISTORY = "price_history"
    SALES_DATA = "sales_data"
    MARKET_TREND = "market_trend"
    CRISIS_DETECTION = "crisis_detection"


    