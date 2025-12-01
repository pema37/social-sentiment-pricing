# backend/services/ingestion/base.py


from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class SocialSource(str, Enum):
    """Supported social media sources."""
    TWITTER = "twitter"
    REDDIT = "reddit"
    TIKTOK = "tiktok"
    AGGREGATOR = "aggregator"


@dataclass
class CollectedMention:
    """
    Normalized data structure for social mentions from any source.
    All collectors transform platform-specific data into this format.
    """
    source: SocialSource
    source_id: str
    content: str
    author: str
    author_followers: Optional[int] = None
    engagement_count: int = 0
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    language: Optional[str] = None
    raw_data: Optional[dict] = None


class BaseCollector(ABC):
    """
    Abstract base class for social media collectors.
    Reddit, Twitter, TikTok, and aggregator services all implement this.
    """
    
    @property
    @abstractmethod
    def source(self) -> SocialSource:
        """Return the source type for this collector."""
        pass
    
    @abstractmethod
    async def collect(self, keywords: List[str], limit: int = 100) -> List[CollectedMention]:
        """
        Collect mentions matching the given keywords.
        
        Args:
            keywords: List of keywords/phrases to search for
            limit: Maximum number of mentions to return
            
        Returns:
            List of CollectedMention objects
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the collector's API connection is healthy."""
        pass

