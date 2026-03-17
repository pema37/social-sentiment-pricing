# backend/services/trust_scoring/content_analyzer.py

"""
Content Analysis Module.

Analyzes social media content for:
- Spam patterns
- Duplicate/copy-paste detection
- Quality signals
- Manipulation indicators
"""

import logging
from datetime import UTC, datetime

from .schemas import (
    ContentAnalysis,
    RiskFlag,
    TrustScoringConfig,
)
from .utils import (
    calculate_spam_score,
    compute_content_hash,
    compute_fuzzy_hash,
    get_content_metrics,
    has_excessive_caps,
    has_keyword_stuffing,
    has_spam_phrases,
    jaccard_similarity,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Content Analyzer
# ─────────────────────────────────────────────────────────────────────────────


class ContentAnalyzer:
    """
    Analyzes social media content for quality and authenticity.

    Detects spam, duplicates, and manipulation patterns.
    """

    def __init__(self, config: TrustScoringConfig | None = None):
        self.config = config or TrustScoringConfig()

        # Content hash cache for duplicate detection
        # Maps hash -> (content_id, timestamp, count)
        self._hash_cache: dict[str, tuple[str, datetime, int]] = {}

        # Fuzzy hash cache for similarity detection
        # Maps content_id -> fuzzy_hash (set of shingles)
        self._fuzzy_cache: dict[str, set[str]] = {}

        # Recent content for similarity comparison (sliding window)
        self._recent_content: list[tuple[str, str, set[str], datetime]] = []
        self._max_recent = 1000

    def analyze(
        self,
        content_id: str,
        text: str,
        author_username: str | None = None,
    ) -> ContentAnalysis:
        """
        Analyze a piece of content for quality and authenticity.

        Args:
            content_id: Unique identifier for this content
            text: The text content to analyze
            author_username: Optional username for additional checks

        Returns:
            ContentAnalysis with quality scores and risk flags
        """
        risk_flags: list[RiskFlag] = []

        # Compute hashes
        content_hash = compute_content_hash(text)
        fuzzy_hash = compute_fuzzy_hash(text)

        # Get basic metrics
        metrics = get_content_metrics(text)

        # 1. Check for exact duplicates
        is_duplicate, duplicate_count = self._check_duplicate(content_hash, content_id)
        if is_duplicate:
            risk_flags.append(RiskFlag.COPY_PASTE)

        # 2. Check for near-duplicates (similar content)
        similarity_to_recent = self._check_similarity(fuzzy_hash, content_id)
        if similarity_to_recent > self.config.duplicate_similarity_threshold:
            if RiskFlag.COPY_PASTE not in risk_flags:
                risk_flags.append(RiskFlag.REPETITIVE_CONTENT)

        # 3. Spam pattern detection
        has_excessive_hashtags = metrics["hashtag_count"] > self.config.max_hashtags
        if has_excessive_hashtags:
            risk_flags.append(RiskFlag.KEYWORD_STUFFING)

        has_excessive_links = metrics["link_count"] > self.config.max_links
        if has_excessive_links:
            risk_flags.append(RiskFlag.LINK_SPAM)

        has_stuffing = has_keyword_stuffing(text)
        if has_stuffing and RiskFlag.KEYWORD_STUFFING not in risk_flags:
            risk_flags.append(RiskFlag.KEYWORD_STUFFING)

        has_caps = has_excessive_caps(text)
        has_spam = has_spam_phrases(text)

        # 4. Calculate quality scores
        content_quality_score = self._calculate_quality_score(text, metrics, risk_flags, author_username)

        originality_score = self._calculate_originality_score(is_duplicate, duplicate_count, similarity_to_recent)

        # 5. Store for future comparison
        self._store_content(content_id, text, content_hash, fuzzy_hash)

        return ContentAnalysis(
            content_id=content_id,
            content_hash=content_hash,
            word_count=metrics["word_count"],
            character_count=metrics["character_count"],
            hashtag_count=metrics["hashtag_count"],
            mention_count=metrics["mention_count"],
            link_count=metrics["link_count"],
            emoji_count=metrics["emoji_count"],
            is_duplicate=is_duplicate,
            duplicate_count=duplicate_count,
            similarity_to_recent=similarity_to_recent,
            has_excessive_hashtags=has_excessive_hashtags,
            has_excessive_links=has_excessive_links,
            has_keyword_stuffing=has_stuffing,
            has_all_caps=has_caps,
            has_spam_phrases=has_spam,
            content_quality_score=content_quality_score,
            originality_score=originality_score,
            risk_flags=risk_flags,
        )

    def analyze_batch(
        self,
        contents: list[tuple[str, str, str | None]],
    ) -> list[ContentAnalysis]:
        """
        Analyze multiple pieces of content.

        Args:
            contents: List of (content_id, text, author_username) tuples

        Returns:
            List of ContentAnalysis results
        """
        return [self.analyze(content_id, text, username) for content_id, text, username in contents]

    def _check_duplicate(
        self,
        content_hash: str,
        content_id: str,
    ) -> tuple[bool, int]:
        """
        Check if content is an exact duplicate.

        Returns (is_duplicate, count_of_duplicates).
        """
        if content_hash in self._hash_cache:
            existing_id, timestamp, count = self._hash_cache[content_hash]
            if existing_id != content_id:
                # Update count
                self._hash_cache[content_hash] = (existing_id, timestamp, count + 1)
                return True, count + 1

        return False, 0

    def _check_similarity(
        self,
        fuzzy_hash: set[str],
        content_id: str,
    ) -> float:
        """
        Check similarity to recent content.

        Returns maximum similarity score (0-1).
        """
        if not fuzzy_hash or not self._recent_content:
            return 0.0

        max_similarity = 0.0

        for recent_id, recent_text, recent_hash, timestamp in self._recent_content[-100:]:
            if recent_id == content_id:
                continue

            similarity = jaccard_similarity(fuzzy_hash, recent_hash)
            max_similarity = max(max_similarity, similarity)

            # Early exit if we find a very similar post
            if max_similarity > 0.95:
                break

        return max_similarity

    def _calculate_quality_score(
        self,
        text: str,
        metrics: dict,
        risk_flags: list[RiskFlag],
        username: str | None = None,
    ) -> float:
        """
        Calculate overall content quality score (0-1).

        Higher = better quality, more trustworthy.
        """
        score = 0.7  # Start with decent baseline

        # Penalize for risk flags
        score -= len(risk_flags) * 0.1

        # Penalize very short content
        if metrics["word_count"] < self.config.min_word_count:
            score -= 0.15
        elif metrics["word_count"] < 5:
            score -= 0.1

        # Penalize spam indicators
        spam_score = calculate_spam_score(text, username)
        score -= spam_score * 0.3

        # Bonus for substantive content
        if metrics["word_count"] > 20:
            score += 0.1
        if metrics["word_count"] > 50:
            score += 0.05

        # Slight penalty for excessive emojis
        if metrics["emoji_count"] > 5:
            score -= 0.05

        # Penalty for all caps
        if metrics.get("uppercase_ratio", 0) > 0.5:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _calculate_originality_score(
        self,
        is_duplicate: bool,
        duplicate_count: int,
        similarity_to_recent: float,
    ) -> float:
        """
        Calculate originality score (0-1).

        1 = completely unique, 0 = exact copy.
        """
        if is_duplicate:
            # Exact duplicates get very low score
            # More copies = lower score
            return max(0.0, 0.2 - (duplicate_count * 0.05))

        # Reduce score based on similarity
        return max(0.0, 1.0 - similarity_to_recent)

    def _store_content(
        self,
        content_id: str,
        text: str,
        content_hash: str,
        fuzzy_hash: set[str],
    ) -> None:
        """Store content for future duplicate/similarity detection."""
        now = datetime.now(UTC)

        # Store exact hash
        if content_hash not in self._hash_cache:
            self._hash_cache[content_hash] = (content_id, now, 1)

        # Store fuzzy hash
        self._fuzzy_cache[content_id] = fuzzy_hash

        # Add to recent content
        self._recent_content.append((content_id, text, fuzzy_hash, now))

        # Trim if too large
        if len(self._recent_content) > self._max_recent:
            self._recent_content = self._recent_content[-self._max_recent :]

    def find_duplicates(
        self,
        text: str,
        threshold: float = 0.9,
    ) -> list[tuple[str, float]]:
        """
        Find content similar to the given text.

        Returns list of (content_id, similarity) tuples.
        """
        fuzzy_hash = compute_fuzzy_hash(text)
        results = []

        for content_id, cached_hash in self._fuzzy_cache.items():
            similarity = jaccard_similarity(fuzzy_hash, cached_hash)
            if similarity >= threshold:
                results.append((content_id, similarity))

        return sorted(results, key=lambda x: x[1], reverse=True)

    def get_duplicate_groups(self) -> list[list[str]]:
        """
        Get groups of duplicate/similar content.

        Returns list of groups, where each group is a list of content_ids.
        """
        # Group by exact hash
        hash_groups: dict[str, list[str]] = {}

        for content_hash, (content_id, _, count) in self._hash_cache.items():
            if count > 1:
                if content_hash not in hash_groups:
                    hash_groups[content_hash] = []
                hash_groups[content_hash].append(content_id)

        return list(hash_groups.values())

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._hash_cache.clear()
        self._fuzzy_cache.clear()
        self._recent_content.clear()

    def get_stats(self) -> dict[str, int]:
        """Get analyzer statistics."""
        return {
            "hash_cache_size": len(self._hash_cache),
            "fuzzy_cache_size": len(self._fuzzy_cache),
            "recent_content_size": len(self._recent_content),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

# Global analyzer instance
_default_analyzer: ContentAnalyzer | None = None


def get_content_analyzer() -> ContentAnalyzer:
    """Get or create the default content analyzer."""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = ContentAnalyzer()
    return _default_analyzer


def analyze_content(
    content_id: str,
    text: str,
    author_username: str | None = None,
) -> ContentAnalysis:
    """
    Convenience function to analyze content.

    Uses the default analyzer instance.
    """
    analyzer = get_content_analyzer()
    return analyzer.analyze(content_id, text, author_username)


def is_spam(text: str, threshold: float = 0.5) -> bool:
    """
    Quick check if content is likely spam.

    Args:
        text: Content to check
        threshold: Spam score threshold (0-1)

    Returns:
        True if content is likely spam
    """
    return calculate_spam_score(text) >= threshold


def is_duplicate(text: str, threshold: float = 0.9) -> bool:
    """
    Quick check if content is a duplicate of recent content.

    Args:
        text: Content to check
        threshold: Similarity threshold (0-1)

    Returns:
        True if content is a duplicate
    """
    analyzer = get_content_analyzer()
    duplicates = analyzer.find_duplicates(text, threshold)
    return len(duplicates) > 0
