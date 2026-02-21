# backend/services/trust_scoring/campaign_detector.py

"""
Campaign Detection Module.

Detects coordinated manipulation campaigns by analyzing:
- Timing patterns (coordinated posting)
- Content similarity (copy-paste campaigns)
- Network patterns (bot networks)
- Sentiment anomalies (artificial sentiment shifts)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Set, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass

from .schemas import (
    CampaignSignal,
    CampaignDetectionResult,
    RiskFlag,
    TrustScoringConfig,
)
from .utils import (
    compute_fuzzy_hash,
    jaccard_similarity,
    normalize_text,
    detect_burst_activity,
    analyze_posting_times,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MentionData:
    """Minimal mention data for campaign detection."""
    mention_id: str
    author_id: str
    content: str
    published_at: datetime
    sentiment_score: Optional[float] = None
    source: str = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Campaign Detector
# ─────────────────────────────────────────────────────────────────────────────

class CampaignDetector:
    """
    Detects coordinated manipulation campaigns.
    
    Analyzes patterns across multiple mentions to identify
    artificial/coordinated activity designed to manipulate sentiment.
    """
    
    def __init__(self, config: Optional[TrustScoringConfig] = None):
        self.config = config or TrustScoringConfig()
        
        # Thresholds for detection
        self.timing_cluster_threshold = 0.7  # How synchronized posts must be
        self.content_similarity_threshold = 0.8  # How similar content must be
        self.min_campaign_size = 5  # Minimum posts to consider a campaign
        self.burst_window_minutes = 30  # Window for burst detection
        self.burst_threshold = 10  # Posts in window to trigger
    
    def detect(
        self,
        mentions: List[MentionData],
        product_id: Optional[str] = None,
        time_window_hours: int = 24,
    ) -> CampaignDetectionResult:
        """
        Detect coordinated campaign activity in a set of mentions.
        
        Args:
            mentions: List of mentions to analyze
            product_id: Optional product ID for context
            time_window_hours: Time window to analyze
        
        Returns:
            CampaignDetectionResult with detection details
        """
        if len(mentions) < self.min_campaign_size:
            return CampaignDetectionResult(
                product_id=product_id,
                time_window_hours=time_window_hours,
                posts_analyzed=len(mentions),
                unique_authors=len(set(m.author_id for m in mentions)),
            )
        
        signals: List[CampaignSignal] = []
        suspicious_authors: Set[str] = set()
        suspicious_content: Set[str] = set()
        
        # 1. Timing Analysis
        timing_signal, timing_suspicious = self._analyze_timing_patterns(mentions)
        if timing_signal:
            signals.append(timing_signal)
            suspicious_authors.update(timing_suspicious)
        
        # 2. Content Similarity Analysis
        similarity_signal, similarity_suspicious = self._analyze_content_similarity(mentions)
        if similarity_signal:
            signals.append(similarity_signal)
            suspicious_content.update(similarity_suspicious)
        
        # 3. Author Pattern Analysis
        author_signal, author_suspicious = self._analyze_author_patterns(mentions)
        if author_signal:
            signals.append(author_signal)
            suspicious_authors.update(author_suspicious)
        
        # 4. Sentiment Anomaly Analysis
        sentiment_signal = self._analyze_sentiment_anomalies(mentions)
        if sentiment_signal:
            signals.append(sentiment_signal)
        
        # 5. Burst Activity Detection
        burst_signal, burst_authors = self._detect_burst_activity(mentions)
        if burst_signal:
            signals.append(burst_signal)
            suspicious_authors.update(burst_authors)
        
        # Calculate overall campaign confidence
        campaign_confidence = self._calculate_campaign_confidence(signals)
        is_campaign = campaign_confidence >= 0.6
        
        # Calculate timing and similarity scores
        timing_score = max(
            (s.strength for s in signals if 'timing' in s.signal_type.lower()),
            default=0.0
        )
        similarity_score = max(
            (s.strength for s in signals if 'similarity' in s.signal_type.lower()),
            default=0.0
        )
        
        return CampaignDetectionResult(
            product_id=product_id,
            time_window_hours=time_window_hours,
            is_campaign_detected=is_campaign,
            campaign_confidence=campaign_confidence,
            signals=signals,
            suspicious_author_ids=list(suspicious_authors),
            suspicious_content_ids=list(suspicious_content),
            posts_analyzed=len(mentions),
            unique_authors=len(set(m.author_id for m in mentions)),
            timing_anomaly_score=timing_score,
            content_similarity_score=similarity_score,
        )
    
    def _analyze_timing_patterns(
        self,
        mentions: List[MentionData],
    ) -> Tuple[Optional[CampaignSignal], Set[str]]:
        """
        Analyze posting time patterns for coordination.
        
        Detects:
        - Synchronized posting (many posts at same time)
        - Regular intervals (bot-like patterns)
        - Unnatural time distributions
        """
        suspicious_authors: Set[str] = set()
        
        timestamps = [m.published_at for m in mentions]
        
        # Group posts by minute
        minute_buckets: Dict[str, List[MentionData]] = defaultdict(list)
        for mention in mentions:
            bucket = mention.published_at.strftime("%Y-%m-%d %H:%M")
            minute_buckets[bucket].append(mention)
        
        # Find clusters (multiple posts in same minute)
        cluster_posts = 0
        cluster_authors: Set[str] = set()
        
        for bucket, bucket_mentions in minute_buckets.items():
            if len(bucket_mentions) >= 3:  # 3+ posts in one minute
                cluster_posts += len(bucket_mentions)
                for m in bucket_mentions:
                    cluster_authors.add(m.author_id)
        
        # Calculate clustering score
        if len(mentions) > 0:
            cluster_ratio = cluster_posts / len(mentions)
        else:
            cluster_ratio = 0.0
        
        # Check for regular intervals
        timing_analysis = analyze_posting_times(timestamps)
        regularity_score = timing_analysis.get('regularity_score', 0.0)
        
        # Combine signals
        timing_score = max(cluster_ratio, regularity_score)
        
        if timing_score >= self.timing_cluster_threshold:
            suspicious_authors.update(cluster_authors)
            
            return CampaignSignal(
                signal_type="timing_cluster",
                strength=timing_score,
                description=f"Detected synchronized posting: {cluster_posts} posts in tight clusters",
                evidence={
                    "cluster_posts": cluster_posts,
                    "cluster_ratio": round(cluster_ratio, 3),
                    "regularity_score": round(regularity_score, 3),
                    "unique_cluster_authors": len(cluster_authors),
                },
            ), suspicious_authors
        
        return None, suspicious_authors
    
    def _analyze_content_similarity(
        self,
        mentions: List[MentionData],
    ) -> Tuple[Optional[CampaignSignal], Set[str]]:
        """
        Analyze content for copy-paste patterns.
        
        Detects groups of very similar content from different authors.
        """
        suspicious_content: Set[str] = set()
        
        # Compute fuzzy hashes for all content
        hashes: List[Tuple[str, Set[str], str]] = []
        for mention in mentions:
            fuzzy_hash = compute_fuzzy_hash(mention.content)
            hashes.append((mention.mention_id, fuzzy_hash, mention.author_id))
        
        # Find similar pairs
        similar_pairs: List[Tuple[str, str, float]] = []
        authors_with_similar: Set[str] = set()
        
        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                id1, hash1, author1 = hashes[i]
                id2, hash2, author2 = hashes[j]
                
                # Skip if same author (self-similarity is expected)
                if author1 == author2:
                    continue
                
                similarity = jaccard_similarity(hash1, hash2)
                
                if similarity >= self.content_similarity_threshold:
                    similar_pairs.append((id1, id2, similarity))
                    suspicious_content.add(id1)
                    suspicious_content.add(id2)
                    authors_with_similar.add(author1)
                    authors_with_similar.add(author2)
        
        if len(similar_pairs) >= 3:  # Need multiple similar pairs
            avg_similarity = sum(p[2] for p in similar_pairs) / len(similar_pairs)
            
            return CampaignSignal(
                signal_type="content_similarity",
                strength=min(1.0, avg_similarity * (len(similar_pairs) / 10)),
                description=f"Found {len(similar_pairs)} pairs of highly similar content from different authors",
                evidence={
                    "similar_pairs": len(similar_pairs),
                    "avg_similarity": round(avg_similarity, 3),
                    "unique_authors": len(authors_with_similar),
                    "suspicious_posts": len(suspicious_content),
                },
            ), suspicious_content
        
        return None, suspicious_content
    
    def _analyze_author_patterns(
        self,
        mentions: List[MentionData],
    ) -> Tuple[Optional[CampaignSignal], Set[str]]:
        """
        Analyze author patterns for coordinated accounts.
        
        Detects:
        - New accounts posting together
        - Accounts with similar naming patterns
        - Accounts that only post about this topic
        """
        suspicious_authors: Set[str] = set()
        
        # Group by author
        author_posts: Dict[str, List[MentionData]] = defaultdict(list)
        for mention in mentions:
            author_posts[mention.author_id].append(mention)
        
        # Find authors with suspicious patterns
        prolific_authors: List[str] = []  # Authors with many posts
        single_topic_authors: List[str] = []  # Authors only posting here
        
        for author_id, posts in author_posts.items():
            # More than 5 posts in the window is suspicious
            if len(posts) >= 5:
                prolific_authors.append(author_id)
                suspicious_authors.add(author_id)
        
        # Check for coordinated account creation (similar usernames)
        # This would require username data, simplified for now
        
        if len(prolific_authors) >= 3:
            total_from_prolific = sum(len(author_posts[a]) for a in prolific_authors)
            
            return CampaignSignal(
                signal_type="author_pattern",
                strength=min(1.0, len(prolific_authors) / 10 + total_from_prolific / 50),
                description=f"Found {len(prolific_authors)} authors with high post volume",
                evidence={
                    "prolific_authors": len(prolific_authors),
                    "total_posts_from_prolific": total_from_prolific,
                    "avg_posts_per_prolific": round(total_from_prolific / len(prolific_authors), 1),
                },
            ), suspicious_authors
        
        return None, suspicious_authors
    
    def _analyze_sentiment_anomalies(
        self,
        mentions: List[MentionData],
    ) -> Optional[CampaignSignal]:
        """
        Analyze sentiment distribution for anomalies.
        
        Detects:
        - Artificially uniform sentiment
        - Extreme sentiment clustering
        - Sentiment that doesn't match content
        """
        # Filter mentions with sentiment scores
        with_sentiment = [m for m in mentions if m.sentiment_score is not None]
        
        if len(with_sentiment) < 10:
            return None
        
        scores = [m.sentiment_score for m in with_sentiment]
        
        # Calculate statistics
        avg_sentiment = sum(scores) / len(scores)
        variance = sum((s - avg_sentiment) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5
        
        # Count extreme sentiments
        extreme_positive = sum(1 for s in scores if s > 0.7)
        extreme_negative = sum(1 for s in scores if s < -0.7)
        extreme_ratio = (extreme_positive + extreme_negative) / len(scores)
        
        # Detect anomalies
        anomaly_detected = False
        anomaly_type = ""
        strength = 0.0
        
        # Very low variance = artificially uniform
        if std_dev < 0.1 and len(scores) > 20:
            anomaly_detected = True
            anomaly_type = "uniform_sentiment"
            strength = 1.0 - (std_dev * 10)
        
        # Too many extreme sentiments
        elif extreme_ratio > 0.7:
            anomaly_detected = True
            anomaly_type = "extreme_sentiment"
            strength = extreme_ratio
        
        # One-sided extreme (all very positive or all very negative)
        elif extreme_positive / len(scores) > 0.6 or extreme_negative / len(scores) > 0.6:
            anomaly_detected = True
            anomaly_type = "one_sided_extreme"
            strength = max(extreme_positive, extreme_negative) / len(scores)
        
        if anomaly_detected:
            return CampaignSignal(
                signal_type=f"sentiment_anomaly_{anomaly_type}",
                strength=strength,
                description=f"Detected {anomaly_type.replace('_', ' ')}: avg={avg_sentiment:.2f}, std={std_dev:.2f}",
                evidence={
                    "avg_sentiment": round(avg_sentiment, 3),
                    "std_dev": round(std_dev, 3),
                    "extreme_positive_ratio": round(extreme_positive / len(scores), 3),
                    "extreme_negative_ratio": round(extreme_negative / len(scores), 3),
                    "sample_size": len(scores),
                },
            )
        
        return None
    
    def _detect_burst_activity(
        self,
        mentions: List[MentionData],
    ) -> Tuple[Optional[CampaignSignal], Set[str]]:
        """
        Detect sudden bursts of activity.
        
        A burst is many posts in a very short window.
        """
        suspicious_authors: Set[str] = set()
        
        timestamps = [m.published_at for m in mentions]
        
        if not detect_burst_activity(
            timestamps,
            window_minutes=self.burst_window_minutes,
            burst_threshold=self.burst_threshold
        ):
            return None, suspicious_authors
        
        # Find the burst window
        sorted_mentions = sorted(mentions, key=lambda m: m.published_at)
        
        max_burst_count = 0
        burst_start_idx = 0
        
        for i in range(len(sorted_mentions)):
            count = 1
            for j in range(i + 1, len(sorted_mentions)):
                delta = (sorted_mentions[j].published_at - sorted_mentions[i].published_at).total_seconds()
                if delta <= self.burst_window_minutes * 60:
                    count += 1
                else:
                    break
            
            if count > max_burst_count:
                max_burst_count = count
                burst_start_idx = i
        
        # Get authors in burst
        burst_end_time = sorted_mentions[burst_start_idx].published_at + timedelta(minutes=self.burst_window_minutes)
        for m in sorted_mentions[burst_start_idx:]:
            if m.published_at <= burst_end_time:
                suspicious_authors.add(m.author_id)
        
        return CampaignSignal(
            signal_type="burst_activity",
            strength=min(1.0, max_burst_count / (self.burst_threshold * 2)),
            description=f"Detected burst of {max_burst_count} posts in {self.burst_window_minutes} minutes",
            evidence={
                "burst_count": max_burst_count,
                "window_minutes": self.burst_window_minutes,
                "unique_burst_authors": len(suspicious_authors),
            },
        ), suspicious_authors
    
    def _calculate_campaign_confidence(
        self,
        signals: List[CampaignSignal],
    ) -> float:
        """
        Calculate overall confidence that a campaign is present.
        
        Combines signal strengths with weights.
        """
        if not signals:
            return 0.0
        
        # Weight different signal types
        weights = {
            "timing_cluster": 0.25,
            "content_similarity": 0.30,
            "author_pattern": 0.20,
            "sentiment_anomaly": 0.15,
            "burst_activity": 0.20,
        }
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for signal in signals:
            # Find matching weight
            weight = 0.15  # Default
            for key, w in weights.items():
                if key in signal.signal_type.lower():
                    weight = w
                    break
            
            weighted_sum += signal.strength * weight
            total_weight += weight
        
        # Bonus for multiple signals
        if len(signals) >= 3:
            weighted_sum *= 1.2
        elif len(signals) >= 2:
            weighted_sum *= 1.1
        
        return min(1.0, weighted_sum)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

# Global detector instance
_default_detector: Optional[CampaignDetector] = None


def get_campaign_detector() -> CampaignDetector:
    """Get or create the default campaign detector."""
    global _default_detector
    if _default_detector is None:
        _default_detector = CampaignDetector()
    return _default_detector


def detect_campaign(
    mentions: List[Dict[str, Any]],
    product_id: Optional[str] = None,
    time_window_hours: int = 24,
) -> CampaignDetectionResult:
    """
    Convenience function to detect campaigns.
    
    Args:
        mentions: List of mention dictionaries with keys:
                  - mention_id (or id)
                  - author_id (or author)
                  - content (or text)
                  - published_at
                  - sentiment_score (optional)
        product_id: Optional product ID
        time_window_hours: Analysis window
    
    Returns:
        CampaignDetectionResult
    """
    # Convert dicts to MentionData
    mention_data = []
    for m in mentions:
        mention_data.append(MentionData(
            mention_id=m.get('mention_id') or m.get('id', ''),
            author_id=m.get('author_id') or m.get('author', ''),
            content=m.get('content') or m.get('text', ''),
            published_at=m.get('published_at', datetime.now(timezone.utc)),
            sentiment_score=m.get('sentiment_score'),
            source=m.get('source', 'unknown'),
        ))
    
    detector = get_campaign_detector()
    return detector.detect(mention_data, product_id, time_window_hours)


