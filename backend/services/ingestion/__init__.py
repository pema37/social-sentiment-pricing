# backend/services/ingestion/__init__.py


from .base import BaseCollector, CollectedMention, SocialSource
from .reddit_service import RedditCollector, get_reddit_collector

__all__ = [
    "BaseCollector", 
    "CollectedMention", 
    "SocialSource",
    "RedditCollector",
    "get_reddit_collector",
]

