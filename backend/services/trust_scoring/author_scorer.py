# backend/services/trust_scoring/author_scorer.py

"""
Author Trust Scoring Module.

Calculates trust scores for social media authors based on:
- Account age
- Follower count and ratio
- Historical behavior
- Verification status
- Engagement patterns
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

from .models import (
    AuthorProfile,
    AuthorTrustScore,
    TrustLevel,
    RiskFlag,
    TrustScoringConfig,
)
from .utils import (
    calculate_account_age_score,
    calculate_follower_score,
    is_bot_username,
    analyze_posting_times,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Author Scorer
# ─────────────────────────────────────────────────────────────────────────────

class AuthorScorer:
    """
    Calculates trust scores for social media authors.
    
    Uses multiple signals to assess how trustworthy an author's
    content should be considered for sentiment analysis.
    """
    
    def __init__(self, config: Optional[TrustScoringConfig] = None):
        self.config = config or TrustScoringConfig()
        
        # Cache for author scores (author_id -> score)
        self._cache: Dict[str, AuthorTrustScore] = {}
        self._cache_ttl_seconds = 3600  # 1 hour
    
    def score_author(
        self,
        profile: AuthorProfile,
        historical_posts: Optional[List[Dict[str, Any]]] = None,
    ) -> AuthorTrustScore:
        """
        Calculate trust score for an author.
        
        Args:
            profile: Author profile information
            historical_posts: Optional list of author's previous posts
                              Each post should have 'published_at' and 'sentiment_score'
        
        Returns:
            AuthorTrustScore with overall score and component breakdown
        """
        risk_flags: List[RiskFlag] = []
        
        # 1. Account age score
        account_age_score = calculate_account_age_score(
            profile.account_age_days,
            self.config.new_account_threshold,
            self.config.established_account_threshold,
        )
        
        if profile.is_new_account:
            risk_flags.append(RiskFlag.NEW_ACCOUNT)
        
        # 2. Follower score
        follower_score = calculate_follower_score(
            profile.follower_count,
            profile.following_count,
        )
        
        if profile.has_low_followers:
            risk_flags.append(RiskFlag.LOW_FOLLOWERS)
        
        if profile.has_suspicious_ratio:
            risk_flags.append(RiskFlag.BOT_PATTERN)
        
        # 3. Engagement score (based on follower engagement patterns)
        engagement_score = self._calculate_engagement_score(profile)
        
        # 4. Historical behavior score
        history_score, history_flags = self._calculate_history_score(
            profile, historical_posts
        )
        risk_flags.extend(history_flags)
        
        # 5. Verification bonus
        verification_bonus = 0.0
        if profile.is_verified:
            verification_bonus = 1.0
        
        # 6. Check for bot-like username
        if is_bot_username(profile.username):
            risk_flags.append(RiskFlag.BOT_PATTERN)
        
        # Calculate weighted total
        total_score = (
            account_age_score * self.config.account_age_weight +
            follower_score * self.config.follower_weight +
            engagement_score * self.config.engagement_weight +
            history_score * self.config.history_weight +
            verification_bonus * self.config.verification_weight
        )
        
        # Apply penalties for risk flags
        risk_penalty = len(risk_flags) * 0.05
        total_score = max(0.0, total_score - risk_penalty)
        
        # Boost for verified accounts
        if profile.is_verified:
            total_score = min(1.0, total_score + 0.15)
        
        # Determine trust level
        trust_level = self._determine_trust_level(total_score, risk_flags)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(risk_flags, profile)
        
        # Calculate confidence in our assessment
        confidence = self._calculate_confidence(profile)
        
        return AuthorTrustScore(
            author_id=profile.author_id,
            source=profile.source,
            trust_score=round(total_score, 4),
            trust_level=trust_level,
            account_age_score=account_age_score,
            follower_score=follower_score,
            engagement_score=engagement_score,
            history_score=history_score,
            verification_bonus=verification_bonus,
            risk_flags=risk_flags,
            risk_score=risk_score,
            confidence=confidence,
        )
    
    def score_author_from_mention(
        self,
        author_id: str,
        username: str,
        source: str,
        follower_count: Optional[int] = None,
        created_at: Optional[datetime] = None,
        is_verified: bool = False,
    ) -> AuthorTrustScore:
        """
        Convenience method to score an author from mention data.
        
        Creates a minimal AuthorProfile and scores it.
        """
        profile = AuthorProfile(
            author_id=author_id,
            username=username,
            source=source,
            follower_count=follower_count,
            created_at=created_at,
            is_verified=is_verified,
        )
        return self.score_author(profile)
    
    def _calculate_engagement_score(self, profile: AuthorProfile) -> float:
        """
        Calculate engagement quality score.
        
        Based on follower/following ratio and post frequency.
        """
        score = 0.5  # Default neutral
        
        # Good follower ratio indicates organic growth
        if profile.follower_ratio is not None:
            if profile.follower_ratio >= 2.0:
                score = 0.8
            elif profile.follower_ratio >= 1.0:
                score = 0.7
            elif profile.follower_ratio >= 0.5:
                score = 0.6
            elif profile.follower_ratio >= 0.1:
                score = 0.4
            else:
                score = 0.2  # Following way more than followers
        
        # Adjust based on post count (active accounts are more trustworthy)
        if profile.post_count is not None:
            if profile.post_count > 1000:
                score = min(1.0, score + 0.1)
            elif profile.post_count > 100:
                score = min(1.0, score + 0.05)
            elif profile.post_count < 10:
                score = max(0.0, score - 0.1)
        
        return score
    
    def _calculate_history_score(
        self,
        profile: AuthorProfile,
        historical_posts: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[float, List[RiskFlag]]:
        """
        Calculate score based on author's historical behavior.
        
        Returns (score, list of risk flags).
        """
        flags: List[RiskFlag] = []
        
        # If we have no history, return neutral
        if not historical_posts:
            return 0.5, flags
        
        score = 0.5
        
        # Check posting frequency
        timestamps = [
            p.get('published_at') for p in historical_posts
            if p.get('published_at')
        ]
        
        if timestamps:
            timing_analysis = analyze_posting_times(timestamps)
            
            if timing_analysis.get('is_suspicious'):
                flags.append(RiskFlag.HIGH_POST_FREQUENCY)
                score -= 0.15
            
            # Very regular posting pattern (bot-like)
            if timing_analysis.get('regularity_score', 0) > 0.8:
                flags.append(RiskFlag.BOT_PATTERN)
                score -= 0.2
        
        # Check sentiment patterns
        sentiments = [
            p.get('sentiment_score') for p in historical_posts
            if p.get('sentiment_score') is not None
        ]
        
        if sentiments:
            # Calculate variance
            avg_sentiment = sum(sentiments) / len(sentiments)
            variance = sum((s - avg_sentiment) ** 2 for s in sentiments) / len(sentiments)
            
            # Extremely consistent sentiment (always positive or negative) is suspicious
            if variance < 0.01 and len(sentiments) > 5:
                flags.append(RiskFlag.SENTIMENT_EXTREME)
                score -= 0.1
            
            # Always extreme sentiment is suspicious
            extreme_count = sum(1 for s in sentiments if abs(s) > 0.8)
            if extreme_count / len(sentiments) > 0.8:
                flags.append(RiskFlag.SENTIMENT_EXTREME)
                score -= 0.1
        
        # More history = more confidence in the score
        if len(historical_posts) > 50:
            score = min(1.0, score + 0.2)
        elif len(historical_posts) > 20:
            score = min(1.0, score + 0.1)
        
        return max(0.0, min(1.0, score)), flags
    
    def _determine_trust_level(
        self,
        score: float,
        risk_flags: List[RiskFlag],
    ) -> TrustLevel:
        """
        Determine trust level category from score and flags.
        """
        # Block if too many severe flags
        severe_flags = {
            RiskFlag.BOT_PATTERN,
            RiskFlag.COORDINATED_TIMING,
            RiskFlag.FAKE_ENGAGEMENT,
        }
        severe_count = sum(1 for f in risk_flags if f in severe_flags)
        
        if severe_count >= 2:
            return TrustLevel.BLOCKED
        
        if score >= self.config.verified_threshold:
            return TrustLevel.VERIFIED
        elif score >= self.config.high_trust_threshold:
            return TrustLevel.HIGH
        elif score >= self.config.medium_trust_threshold:
            return TrustLevel.MEDIUM
        elif score >= self.config.low_trust_threshold:
            return TrustLevel.LOW
        else:
            return TrustLevel.UNTRUSTED
    
    def _calculate_risk_score(
        self,
        risk_flags: List[RiskFlag],
        profile: AuthorProfile,
    ) -> float:
        """
        Calculate overall risk score (0-1, higher = more risky).
        """
        # Base risk from flags
        flag_weights = {
            RiskFlag.NEW_ACCOUNT: 0.1,
            RiskFlag.LOW_FOLLOWERS: 0.1,
            RiskFlag.HIGH_POST_FREQUENCY: 0.15,
            RiskFlag.REPETITIVE_CONTENT: 0.2,
            RiskFlag.COORDINATED_TIMING: 0.25,
            RiskFlag.SUSPICIOUS_ENGAGEMENT: 0.2,
            RiskFlag.KEYWORD_STUFFING: 0.15,
            RiskFlag.LINK_SPAM: 0.2,
            RiskFlag.COPY_PASTE: 0.2,
            RiskFlag.SENTIMENT_EXTREME: 0.15,
            RiskFlag.BOT_PATTERN: 0.3,
            RiskFlag.FAKE_ENGAGEMENT: 0.3,
        }
        
        risk_score = sum(flag_weights.get(f, 0.1) for f in risk_flags)
        
        # Additional risk factors
        if profile.is_new_account and profile.has_low_followers:
            risk_score += 0.1
        
        if profile.has_suspicious_ratio:
            risk_score += 0.15
        
        return min(1.0, risk_score)
    
    def _calculate_confidence(self, profile: AuthorProfile) -> float:
        """
        Calculate confidence in our trust assessment.
        
        Higher when we have more data about the author.
        """
        confidence = 0.3  # Base confidence
        
        # More metadata = higher confidence
        if profile.created_at is not None:
            confidence += 0.15
        
        if profile.follower_count is not None:
            confidence += 0.15
        
        if profile.following_count is not None:
            confidence += 0.1
        
        if profile.post_count is not None:
            confidence += 0.1
        
        if profile.posts_analyzed > 0:
            # We've seen this author before
            confidence += min(0.2, profile.posts_analyzed * 0.02)
        
        return min(1.0, confidence)
    
    def get_cached_score(self, author_id: str) -> Optional[AuthorTrustScore]:
        """Get cached score if available and not expired."""
        return self._cache.get(author_id)
    
    def cache_score(self, score: AuthorTrustScore) -> None:
        """Cache a score for later retrieval."""
        self._cache[score.author_id] = score
    
    def clear_cache(self) -> None:
        """Clear the score cache."""
        self._cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

# Global scorer instance
_default_scorer: Optional[AuthorScorer] = None


def get_author_scorer() -> AuthorScorer:
    """Get or create the default author scorer."""
    global _default_scorer
    if _default_scorer is None:
        _default_scorer = AuthorScorer()
    return _default_scorer


def score_author(
    author_id: str,
    username: str,
    source: str,
    follower_count: Optional[int] = None,
    created_at: Optional[datetime] = None,
    is_verified: bool = False,
) -> AuthorTrustScore:
    """
    Convenience function to score an author.
    
    Uses the default scorer instance.
    """
    scorer = get_author_scorer()
    return scorer.score_author_from_mention(
        author_id=author_id,
        username=username,
        source=source,
        follower_count=follower_count,
        created_at=created_at,
        is_verified=is_verified,
    )



