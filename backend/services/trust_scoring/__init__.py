# backend/services/trust_scoring/__init__.py

"""
Trust Scoring / Bot Detection Service.

Provides trust-adjusted sentiment analysis by detecting and filtering:
- Bot accounts
- Spam content
- Coordinated manipulation campaigns
- Fake engagement

Usage:
    from backend.services.trust_scoring import (
        calculate_weighted_sentiment,
        is_trustworthy_author,
        filter_trusted_mentions,
        get_trust_scoring_service,
    )
    
    # Calculate trust-adjusted sentiment
    result = calculate_weighted_sentiment(mentions, product_id="123")
    print(f"Raw sentiment: {result.raw_average_sentiment}")
    print(f"Adjusted sentiment: {result.adjusted_average_sentiment}")
    print(f"Filtered {result.filtered_count} suspicious mentions")
    
    # Check if author is trustworthy
    if is_trustworthy_author(author_id="abc", username="user123", source="twitter"):
        print("Author is trustworthy")
    
    # Filter to trusted mentions only
    trusted = filter_trusted_mentions(mentions, min_trust=0.4)
"""

# Models
from .models import (
    # Enums
    TrustLevel,
    RiskFlag,
    ContentType,
    # Author models
    AuthorProfile,
    AuthorTrustScore,
    # Content models
    ContentAnalysis,
    # Campaign models
    CampaignSignal,
    CampaignDetectionResult,
    # Weighted sentiment
    WeightedMention,
    TrustAdjustedSentiment,
    # Configuration
    TrustScoringConfig,
)

# Author scoring
from .author_scorer import (
    AuthorScorer,
    get_author_scorer,
    score_author,
)

# Content analysis
from .content_analyzer import (
    ContentAnalyzer,
    get_content_analyzer,
    analyze_content,
    is_spam,
    is_duplicate,
)

# Campaign detection
from .campaign_detector import (
    CampaignDetector,
    MentionData,
    get_campaign_detector,
    detect_campaign,
)

# Main service
from .service import (
    TrustScoringService,
    get_trust_scoring_service,
    calculate_weighted_sentiment,
    is_trustworthy_author,
    filter_trusted_mentions,
)

# Utilities (for advanced usage)
from .utils import (
    normalize_text,
    compute_content_hash,
    text_similarity,
    calculate_spam_score,
    calculate_account_age_score,
    calculate_follower_score,
    is_bot_username,
)


__all__ = [
    # Enums
    "TrustLevel",
    "RiskFlag",
    "ContentType",
    # Models
    "AuthorProfile",
    "AuthorTrustScore",
    "ContentAnalysis",
    "CampaignSignal",
    "CampaignDetectionResult",
    "WeightedMention",
    "TrustAdjustedSentiment",
    "TrustScoringConfig",
    "MentionData",
    # Author scoring
    "AuthorScorer",
    "get_author_scorer",
    "score_author",
    # Content analysis
    "ContentAnalyzer",
    "get_content_analyzer",
    "analyze_content",
    "is_spam",
    "is_duplicate",
    # Campaign detection
    "CampaignDetector",
    "get_campaign_detector",
    "detect_campaign",
    # Main service
    "TrustScoringService",
    "get_trust_scoring_service",
    "calculate_weighted_sentiment",
    "is_trustworthy_author",
    "filter_trusted_mentions",
    # Utilities
    "normalize_text",
    "compute_content_hash",
    "text_similarity",
    "calculate_spam_score",
    "calculate_account_age_score",
    "calculate_follower_score",
    "is_bot_username",
]



