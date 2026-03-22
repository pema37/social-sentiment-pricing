"""Shared types used across all agent contract schemas."""

import hashlib
import json
from enum import StrEnum


def compute_provenance_hash(data: dict) -> str:
    """
    Compute a deterministic hash of agent output for provenance chain.

    Used by downstream agents to verify they're working with the exact
    output from the upstream agent (not a stale or modified version).
    """
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


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
