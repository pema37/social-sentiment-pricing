# backend/services/trust_scoring/service.py

"""
Trust Scoring Service - Main Orchestrator.

Combines author scoring, content analysis, and campaign detection
to provide trust-adjusted sentiment analysis.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple
from decimal import Decimal

from .schemas import (
    AuthorProfile,
    AuthorTrustScore,
    ContentAnalysis,
    CampaignDetectionResult,
    WeightedMention,
    TrustAdjustedSentiment,
    TrustLevel,
    RiskFlag,
    TrustScoringConfig,
)
from .author_scorer import AuthorScorer
from .content_analyzer import ContentAnalyzer
from .campaign_detector import CampaignDetector, MentionData

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Trust Scoring Service
# ─────────────────────────────────────────────────────────────────────────────

class TrustScoringService:
    """
    Main service for trust-based sentiment analysis.
    
    Orchestrates author scoring, content analysis, and campaign detection
    to produce trust-adjusted sentiment scores.
    """
    
    def __init__(self, config: Optional[TrustScoringConfig] = None):
        self.config = config or TrustScoringConfig()
        
        # Initialize sub-components
        self.author_scorer = AuthorScorer(self.config)
        self.content_analyzer = ContentAnalyzer(self.config)
        self.campaign_detector = CampaignDetector(self.config)
        
        # Trust level weights for sentiment
        self.trust_weights = {
            TrustLevel.VERIFIED: 1.5,    # Boost verified accounts
            TrustLevel.HIGH: 1.2,
            TrustLevel.MEDIUM: 1.0,
            TrustLevel.LOW: 0.5,
            TrustLevel.UNTRUSTED: 0.2,
            TrustLevel.BLOCKED: 0.0,     # Completely ignore
        }
        
        # Minimum trust score to include in analysis
        self.min_trust_threshold = 0.1
    
    def analyze_mention(
        self,
        mention_id: str,
        content: str,
        raw_sentiment_score: float,
        author_id: str,
        username: str,
        source: str,
        follower_count: Optional[int] = None,
        account_created_at: Optional[datetime] = None,
        is_verified: bool = False,
    ) -> WeightedMention:
        """
        Analyze a single mention and calculate its trust-weighted sentiment.
        
        Args:
            mention_id: Unique mention identifier
            content: Text content of the mention
            raw_sentiment_score: Original sentiment score (-1 to 1)
            author_id: Author's unique ID
            username: Author's username
            source: Platform source (twitter, reddit, etc.)
            follower_count: Optional follower count
            account_created_at: Optional account creation date
            is_verified: Whether account is verified
        
        Returns:
            WeightedMention with trust-adjusted sentiment
        """
        # Score the author
        author_score = self.author_scorer.score_author_from_mention(
            author_id=author_id,
            username=username,
            source=source,
            follower_count=follower_count,
            created_at=account_created_at,
            is_verified=is_verified,
        )
        
        # Analyze the content
        content_analysis = self.content_analyzer.analyze(
            content_id=mention_id,
            text=content,
            author_username=username,
        )
        
        # Calculate final weight
        author_trust = author_score.trust_score
        content_quality = content_analysis.content_quality_score
        
        # Combine scores (author trust is more important)
        combined_weight = (author_trust * 0.6 + content_quality * 0.4)
        
        # Apply trust level multiplier
        level_multiplier = self.trust_weights.get(author_score.trust_level, 1.0)
        final_weight = combined_weight * level_multiplier
        
        # Penalize if content is duplicate or spam
        if content_analysis.is_duplicate:
            final_weight *= 0.3
        if content_analysis.has_spam_phrases:
            final_weight *= 0.5
        
        # Clamp weight
        final_weight = max(0.0, min(1.5, final_weight))
        
        return WeightedMention(
            mention_id=mention_id,
            author_id=author_id,
            content=content,
            raw_sentiment_score=raw_sentiment_score,
            author_trust_score=author_trust,
            content_quality_score=content_quality,
            weight=final_weight,
            weighted_sentiment=raw_sentiment_score * final_weight,
        )
    
    def analyze_mentions_batch(
        self,
        mentions: List[Dict[str, Any]],
    ) -> List[WeightedMention]:
        """
        Analyze a batch of mentions.
        
        Args:
            mentions: List of mention dictionaries with keys:
                - mention_id (or id)
                - content (or text)
                - sentiment_score
                - author_id
                - username (or author)
                - source
                - follower_count (optional)
                - account_created_at (optional)
                - is_verified (optional)
        
        Returns:
            List of WeightedMention objects
        """
        results = []
        
        for m in mentions:
            try:
                weighted = self.analyze_mention(
                    mention_id=m.get('mention_id') or m.get('id', ''),
                    content=m.get('content') or m.get('text', ''),
                    raw_sentiment_score=float(m.get('sentiment_score', 0)),
                    author_id=m.get('author_id', ''),
                    username=m.get('username') or m.get('author', ''),
                    source=m.get('source', 'unknown'),
                    follower_count=m.get('follower_count') or m.get('author_followers'),
                    account_created_at=m.get('account_created_at'),
                    is_verified=m.get('is_verified', False),
                )
                results.append(weighted)
            except Exception as e:
                logger.error(f"Error analyzing mention {m.get('mention_id')}: {e}")
                continue
        
        return results
    
    def calculate_trust_adjusted_sentiment(
        self,
        mentions: List[Dict[str, Any]],
        product_id: Optional[str] = None,
        period_hours: int = 24,
        check_campaign: bool = True,
    ) -> TrustAdjustedSentiment:
        """
        Calculate trust-adjusted sentiment for a set of mentions.
        
        This is the main entry point for getting sentiment with
        bot/manipulation filtering applied.
        
        Args:
            mentions: List of mention dictionaries
            product_id: Optional product ID for context
            period_hours: Time period being analyzed
            check_campaign: Whether to check for coordinated campaigns
        
        Returns:
            TrustAdjustedSentiment with raw and adjusted scores
        """
        if not mentions:
            return TrustAdjustedSentiment(
                product_id=product_id or "",
                period_hours=period_hours,
                raw_average_sentiment=0.0,
                raw_mention_count=0,
                adjusted_average_sentiment=0.0,
                effective_mention_count=0.0,
                high_trust_ratio=0.0,
                filtered_count=0,
                confidence=0.0,
            )
        
        # Analyze all mentions
        weighted_mentions = self.analyze_mentions_batch(mentions)
        
        # Check for coordinated campaigns
        campaign_result: Optional[CampaignDetectionResult] = None
        campaign_authors: set = set()
        
        if check_campaign and len(weighted_mentions) >= 10:
            mention_data = [
                MentionData(
                    mention_id=m.get('mention_id') or m.get('id', ''),
                    author_id=m.get('author_id', ''),
                    content=m.get('content') or m.get('text', ''),
                    published_at=m.get('published_at', datetime.now(timezone.utc)),
                    sentiment_score=m.get('sentiment_score'),
                    source=m.get('source', 'unknown'),
                )
                for m in mentions
            ]
            campaign_result = self.campaign_detector.detect(
                mention_data, product_id, period_hours
            )
            
            if campaign_result.is_campaign_detected:
                campaign_authors = set(campaign_result.suspicious_author_ids)
                logger.warning(
                    f"Campaign detected for product {product_id}: "
                    f"confidence={campaign_result.campaign_confidence:.2f}, "
                    f"suspicious_authors={len(campaign_authors)}"
                )
        
        # Calculate raw sentiment
        raw_scores = [wm.raw_sentiment_score for wm in weighted_mentions]
        raw_average = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
        
        # Calculate trust-adjusted sentiment
        filtered_count = 0
        total_weight = 0.0
        weighted_sum = 0.0
        trust_level_counts: Dict[str, int] = {level.value: 0 for level in TrustLevel}
        
        for wm in weighted_mentions:
            # Apply additional penalty if author is part of detected campaign
            weight = wm.weight
            if wm.author_id in campaign_authors:
                weight *= 0.2  # Heavily discount campaign participants
            
            # Filter out very low trust
            if weight < self.min_trust_threshold:
                filtered_count += 1
                continue
            
            weighted_sum += wm.raw_sentiment_score * weight
            total_weight += weight
            
            # Track trust levels
            level = self._get_trust_level(wm.author_trust_score)
            trust_level_counts[level.value] += 1
        
        # Calculate adjusted average
        if total_weight > 0:
            adjusted_average = weighted_sum / total_weight
        else:
            adjusted_average = 0.0
        
        # Calculate high trust ratio
        high_trust_count = (
            trust_level_counts.get(TrustLevel.VERIFIED.value, 0) +
            trust_level_counts.get(TrustLevel.HIGH.value, 0)
        )
        included_count = len(weighted_mentions) - filtered_count
        high_trust_ratio = high_trust_count / included_count if included_count > 0 else 0.0
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            mention_count=len(weighted_mentions),
            filtered_count=filtered_count,
            high_trust_ratio=high_trust_ratio,
            campaign_detected=campaign_result.is_campaign_detected if campaign_result else False,
        )
        
        return TrustAdjustedSentiment(
            product_id=product_id or "",
            period_hours=period_hours,
            raw_average_sentiment=round(raw_average, 4),
            raw_mention_count=len(mentions),
            adjusted_average_sentiment=round(adjusted_average, 4),
            effective_mention_count=round(total_weight, 2),
            high_trust_ratio=round(high_trust_ratio, 3),
            filtered_count=filtered_count,
            confidence=round(confidence, 3),
            trust_level_breakdown=trust_level_counts,
        )
    
    def score_author(
        self,
        author_id: str,
        username: str,
        source: str,
        **kwargs,
    ) -> AuthorTrustScore:
        """
        Score a single author.
        
        Convenience method for direct author scoring.
        """
        return self.author_scorer.score_author_from_mention(
            author_id=author_id,
            username=username,
            source=source,
            **kwargs,
        )
    
    def analyze_content(
        self,
        content_id: str,
        text: str,
        author_username: Optional[str] = None,
    ) -> ContentAnalysis:
        """
        Analyze a single piece of content.
        
        Convenience method for direct content analysis.
        """
        return self.content_analyzer.analyze(
            content_id=content_id,
            text=text,
            author_username=author_username,
        )
    
    def detect_campaign(
        self,
        mentions: List[Dict[str, Any]],
        product_id: Optional[str] = None,
        time_window_hours: int = 24,
    ) -> CampaignDetectionResult:
        """
        Detect coordinated campaigns.
        
        Convenience method for direct campaign detection.
        """
        mention_data = [
            MentionData(
                mention_id=m.get('mention_id') or m.get('id', ''),
                author_id=m.get('author_id', ''),
                content=m.get('content') or m.get('text', ''),
                published_at=m.get('published_at', datetime.now(timezone.utc)),
                sentiment_score=m.get('sentiment_score'),
                source=m.get('source', 'unknown'),
            )
            for m in mentions
        ]
        return self.campaign_detector.detect(
            mention_data, product_id, time_window_hours
        )
    
    def _get_trust_level(self, score: float) -> TrustLevel:
        """Convert trust score to trust level."""
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
    
    def _calculate_confidence(
        self,
        mention_count: int,
        filtered_count: int,
        high_trust_ratio: float,
        campaign_detected: bool,
    ) -> float:
        """
        Calculate confidence in the adjusted sentiment score.
        """
        confidence = 0.5  # Base confidence
        
        # More mentions = higher confidence
        if mention_count >= 100:
            confidence += 0.2
        elif mention_count >= 50:
            confidence += 0.15
        elif mention_count >= 20:
            confidence += 0.1
        elif mention_count < 5:
            confidence -= 0.2
        
        # Higher trust ratio = higher confidence
        confidence += high_trust_ratio * 0.2
        
        # High filter rate = lower confidence
        if mention_count > 0:
            filter_ratio = filtered_count / mention_count
            if filter_ratio > 0.5:
                confidence -= 0.2
            elif filter_ratio > 0.3:
                confidence -= 0.1
        
        # Campaign detected = lower confidence
        if campaign_detected:
            confidence -= 0.15
        
        return max(0.1, min(1.0, confidence))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "content_analyzer": self.content_analyzer.get_stats(),
            "config": {
                "min_trust_threshold": self.min_trust_threshold,
                "new_account_threshold_days": self.config.new_account_threshold,
                "established_account_threshold_days": self.config.established_account_threshold,
            },
        }
    
    def clear_caches(self) -> None:
        """Clear all internal caches."""
        self.author_scorer.clear_cache()
        self.content_analyzer.clear_cache()


# ─────────────────────────────────────────────────────────────────────────────
# Global Service Instance
# ─────────────────────────────────────────────────────────────────────────────

_trust_service: Optional[TrustScoringService] = None


def get_trust_scoring_service() -> TrustScoringService:
    """Get or create the global trust scoring service."""
    global _trust_service
    if _trust_service is None:
        _trust_service = TrustScoringService()
    return _trust_service


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

def calculate_weighted_sentiment(
    mentions: List[Dict[str, Any]],
    product_id: Optional[str] = None,
    period_hours: int = 24,
) -> TrustAdjustedSentiment:
    """
    Calculate trust-adjusted sentiment for mentions.
    
    Main convenience function for getting filtered sentiment.
    """
    service = get_trust_scoring_service()
    return service.calculate_trust_adjusted_sentiment(
        mentions=mentions,
        product_id=product_id,
        period_hours=period_hours,
    )


def is_trustworthy_author(
    author_id: str,
    username: str,
    source: str,
    follower_count: Optional[int] = None,
    account_created_at: Optional[datetime] = None,
    min_trust: float = 0.4,
) -> bool:
    """
    Quick check if an author meets minimum trust threshold.
    """
    service = get_trust_scoring_service()
    score = service.score_author(
        author_id=author_id,
        username=username,
        source=source,
        follower_count=follower_count,
        created_at=account_created_at,
    )
    return score.trust_score >= min_trust


def filter_trusted_mentions(
    mentions: List[Dict[str, Any]],
    min_trust: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Filter mentions to only include those from trusted authors.
    
    Returns mentions that pass the trust threshold.
    """
    service = get_trust_scoring_service()
    weighted = service.analyze_mentions_batch(mentions)
    
    trusted_ids = {
        wm.mention_id for wm in weighted
        if wm.author_trust_score >= min_trust and wm.weight >= min_trust
    }
    
    return [m for m in mentions if m.get('mention_id') or m.get('id') in trusted_ids]



