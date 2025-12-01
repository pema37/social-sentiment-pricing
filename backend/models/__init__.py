# backend/models/__init__.py

"""
Database Models

All SQLModel entities for the Social Sentiment Pricing system.
"""

from backend.models.user import User
from backend.models.product import Product
from backend.models.sentiment import Sentiment
from backend.models.price_history import PriceHistory

# Phase 2: Competitor Tracking
from backend.models.competitor import Competitor
from backend.models.competitor_product import CompetitorProduct
from backend.models.competitor_price_history import CompetitorPriceHistory

# Phase 3: Social Media Ingestion
from backend.models.social_mention import SocialMention


__all__ = [
    # Core models (Phase 1)
    "User",
    "Product",
    "Sentiment",
    "PriceHistory",
    # Competitor models (Phase 2)
    "Competitor",
    "CompetitorProduct",
    "CompetitorPriceHistory",
    # Social ingestion models (Phase 3)
    "SocialMention",
]

