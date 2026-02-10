# backend/services/trust_scoring/models.py

"""
Data models for Trust Scoring / Bot Detection system.

These models represent trust assessments for social media authors
and their content, used to weight sentiment analysis appropriately.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class TrustLevel(str, Enum):
    """Trust level classification."""
    VERIFIED = "verified"      # Verified accounts, known influencers
    HIGH = "high"              # Established accounts with history
    MEDIUM = "medium"          # Normal accounts
    LOW = "low"                # New or suspicious accounts
    UNTRUSTED = "untrusted"    # Likely bots or spam
    BLOCKED = "blocked"        # Known bad actors


class RiskFlag(str, Enum):
    """Risk indicators for suspicious activity."""
    NEW_ACCOUNT = "new_account"
    LOW_FOLLOWERS = "low_followers"
    HIGH_POST_FREQUENCY = "high_post_frequency"
    REPETITIVE_CONTENT = "repetitive_content"
    COORDINATED_TIMING = "coordinated_timing"
    SUSPICIOUS_ENGAGEMENT = "suspicious_engagement"
    KEYWORD_STUFFING = "keyword_stuffing"
    LINK_SPAM = "link_spam"
    COPY_PASTE = "copy_paste"
    SENTIMENT_EXTREME = "sentiment_extreme"
    BOT_PATTERN = "bot_pattern"
    FAKE_ENGAGEMENT = "fake_engagement"


class ContentType(str, Enum):
    """Type of social content."""
    ORIGINAL = "original"
    REPOST = "repost"
    REPLY = "reply"
    QUOTE = "quote"


# ─────────────────────────────────────────────────────────────────────────────
# Author Models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AuthorProfile:
    """
    Profile information about a social media author.
    
    Used to assess the trustworthiness of content sources.
    """
    author_id: str
    username: str
    source: str  # twitter, reddit, etc.
    
    # Account metadata
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    is_verified: bool = False
    
    # Calculated fields
    account_age_days: Optional[int] = None
    follower_ratio: Optional[float] = None  # followers / following
    
    # Historical behavior (from our database)
    posts_analyzed: int = 0
    avg_sentiment: Optional[float] = None
    sentiment_variance: Optional[float] = None
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.created_at:
            delta = datetime.now(timezone.utc) - self.created_at
            self.account_age_days = delta.days
        
        if self.follower_count is not None and self.following_count:
            if self.following_count > 0:
                self.follower_ratio = self.follower_count / self.following_count

    @property
    def is_new_account(self) -> bool:
        """Account less than 30 days old."""
        return self.account_age_days is not None and self.account_age_days < 30

    @property
    def has_low_followers(self) -> bool:
        """Less than 10 followers."""
        return self.follower_count is not None and self.follower_count < 10

    @property
    def has_suspicious_ratio(self) -> bool:
        """Following way more than followers (bot pattern)."""
        if self.follower_ratio is None:
            return False
        return self.follower_ratio < 0.1 and (self.following_count or 0) > 100


@dataclass
class AuthorTrustScore:
    """
    Trust assessment for a specific author.
    
    Combines multiple signals into a single trust score.
    """
    author_id: str
    source: str
    
    # Overall score (0-1, higher = more trusted)
    trust_score: float
    trust_level: TrustLevel
    
    # Component scores (0-1)
    account_age_score: float = 0.5
    follower_score: float = 0.5
    engagement_score: float = 0.5
    history_score: float = 0.5
    verification_bonus: float = 0.0
    
    # Risk assessment
    risk_flags: List[RiskFlag] = field(default_factory=list)
    risk_score: float = 0.0  # 0-1, higher = more risky
    
    # Metadata
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 0.5  # How confident we are in this score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "author_id": self.author_id,
            "source": self.source,
            "trust_score": round(self.trust_score, 3),
            "trust_level": self.trust_level.value,
            "risk_flags": [f.value for f in self.risk_flags],
            "risk_score": round(self.risk_score, 3),
            "component_scores": {
                "account_age": round(self.account_age_score, 3),
                "followers": round(self.follower_score, 3),
                "engagement": round(self.engagement_score, 3),
                "history": round(self.history_score, 3),
                "verification_bonus": round(self.verification_bonus, 3),
            },
            "confidence": round(self.confidence, 3),
            "calculated_at": self.calculated_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Content Models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ContentAnalysis:
    """
    Analysis results for a piece of social content.
    
    Identifies spam patterns, manipulation, and authenticity signals.
    """
    content_id: str
    content_hash: str  # For duplicate detection
    
    # Content metrics
    word_count: int = 0
    character_count: int = 0
    hashtag_count: int = 0
    mention_count: int = 0
    link_count: int = 0
    emoji_count: int = 0
    
    # Pattern detection
    is_duplicate: bool = False
    duplicate_count: int = 0  # How many times we've seen this exact content
    similarity_to_recent: float = 0.0  # 0-1, how similar to recent posts
    
    # Spam indicators
    has_excessive_hashtags: bool = False  # > 5 hashtags
    has_excessive_links: bool = False     # > 2 links
    has_keyword_stuffing: bool = False    # Unnatural keyword density
    has_all_caps: bool = False            # Majority uppercase
    has_spam_phrases: bool = False        # Known spam patterns
    
    # Quality indicators
    content_quality_score: float = 0.5  # 0-1
    originality_score: float = 1.0      # 0-1, 1 = unique
    
    # Risk
    risk_flags: List[RiskFlag] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content_id": self.content_id,
            "word_count": self.word_count,
            "is_duplicate": self.is_duplicate,
            "duplicate_count": self.duplicate_count,
            "content_quality_score": round(self.content_quality_score, 3),
            "originality_score": round(self.originality_score, 3),
            "risk_flags": [f.value for f in self.risk_flags],
            "spam_indicators": {
                "excessive_hashtags": self.has_excessive_hashtags,
                "excessive_links": self.has_excessive_links,
                "keyword_stuffing": self.has_keyword_stuffing,
                "all_caps": self.has_all_caps,
                "spam_phrases": self.has_spam_phrases,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Campaign Detection
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CampaignSignal:
    """
    Signal indicating potential coordinated campaign activity.
    """
    signal_type: str  # timing_cluster, content_similarity, network_pattern
    strength: float   # 0-1
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CampaignDetectionResult:
    """
    Result of campaign detection analysis.
    
    Identifies coordinated manipulation attempts.
    """
    product_id: Optional[str]
    time_window_hours: int
    
    # Detection results
    is_campaign_detected: bool = False
    campaign_confidence: float = 0.0  # 0-1
    
    # Signals
    signals: List[CampaignSignal] = field(default_factory=list)
    
    # Affected content
    suspicious_author_ids: List[str] = field(default_factory=list)
    suspicious_content_ids: List[str] = field(default_factory=list)
    
    # Metrics
    posts_analyzed: int = 0
    unique_authors: int = 0
    timing_anomaly_score: float = 0.0
    content_similarity_score: float = 0.0
    
    # Metadata
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "time_window_hours": self.time_window_hours,
            "is_campaign_detected": self.is_campaign_detected,
            "campaign_confidence": round(self.campaign_confidence, 3),
            "signals": [
                {
                    "type": s.signal_type,
                    "strength": round(s.strength, 3),
                    "description": s.description,
                }
                for s in self.signals
            ],
            "metrics": {
                "posts_analyzed": self.posts_analyzed,
                "unique_authors": self.unique_authors,
                "suspicious_authors": len(self.suspicious_author_ids),
                "suspicious_posts": len(self.suspicious_content_ids),
            },
            "analyzed_at": self.analyzed_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Weighted Sentiment
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WeightedMention:
    """
    A social mention with trust-adjusted weighting.
    
    Used to calculate weighted sentiment scores.
    """
    mention_id: str
    author_id: str
    content: str
    
    # Original sentiment
    raw_sentiment_score: float  # -1 to 1
    
    # Trust assessment
    author_trust_score: float  # 0-1
    content_quality_score: float  # 0-1
    
    # Final weight (0-1, how much this mention should count)
    weight: float = 1.0
    
    # Computed weighted sentiment
    weighted_sentiment: float = 0.0
    
    def __post_init__(self):
        """Calculate weighted sentiment."""
        # Weight combines author trust and content quality
        self.weight = (self.author_trust_score * 0.6 + self.content_quality_score * 0.4)
        self.weighted_sentiment = self.raw_sentiment_score * self.weight


@dataclass
class TrustAdjustedSentiment:
    """
    Sentiment summary with trust-based adjustments.
    
    Provides both raw and trust-adjusted sentiment scores.
    """
    product_id: str
    period_hours: int
    
    # Raw sentiment (all mentions equal)
    raw_average_sentiment: float
    raw_mention_count: int
    
    # Trust-adjusted sentiment
    adjusted_average_sentiment: float
    effective_mention_count: float  # Sum of weights
    
    # Quality metrics
    high_trust_ratio: float  # % of mentions from trusted sources
    filtered_count: int      # Mentions filtered as spam/bots
    
    # Confidence in the adjusted score
    confidence: float
    
    # Breakdown
    trust_level_breakdown: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "period_hours": self.period_hours,
            "raw": {
                "sentiment": round(self.raw_average_sentiment, 4),
                "mention_count": self.raw_mention_count,
            },
            "adjusted": {
                "sentiment": round(self.adjusted_average_sentiment, 4),
                "effective_mentions": round(self.effective_mention_count, 2),
            },
            "quality": {
                "high_trust_ratio": round(self.high_trust_ratio, 3),
                "filtered_count": self.filtered_count,
                "confidence": round(self.confidence, 3),
            },
            "trust_breakdown": self.trust_level_breakdown,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TrustScoringConfig:
    """
    Configuration for trust scoring thresholds and weights.
    """
    # Account age thresholds (days)
    new_account_threshold: int = 30
    established_account_threshold: int = 180
    
    # Follower thresholds
    low_follower_threshold: int = 10
    medium_follower_threshold: int = 100
    high_follower_threshold: int = 1000
    
    # Component weights (should sum to 1.0)
    account_age_weight: float = 0.25
    follower_weight: float = 0.20
    engagement_weight: float = 0.20
    history_weight: float = 0.25
    verification_weight: float = 0.10
    
    # Trust level thresholds
    verified_threshold: float = 0.9
    high_trust_threshold: float = 0.7
    medium_trust_threshold: float = 0.4
    low_trust_threshold: float = 0.2
    
    # Spam detection
    max_hashtags: int = 5
    max_links: int = 2
    min_word_count: int = 3
    duplicate_similarity_threshold: float = 0.9
    
    # Campaign detection
    campaign_time_window_hours: int = 24
    campaign_min_posts: int = 10
    campaign_timing_threshold: float = 0.7
    campaign_similarity_threshold: float = 0.8

    def __post_init__(self):
        """Validate configuration."""
        total_weight = (
            self.account_age_weight +
            self.follower_weight +
            self.engagement_weight +
            self.history_weight +
            self.verification_weight
        )
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError(f"Component weights must sum to 1.0, got {total_weight}")




            