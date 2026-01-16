# backend/services/trust_scoring/utils.py

"""
Utility functions for trust scoring and bot detection.

Contains pure functions for text analysis, hashing, and pattern detection.
"""

import re
import hashlib
from datetime import datetime, timezone
from typing import List, Set, Optional, Tuple
from collections import Counter


# ─────────────────────────────────────────────────────────────────────────────
# Text Normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """
    Normalize text for comparison and duplicate detection.
    
    - Lowercase
    - Remove extra whitespace
    - Remove URLs
    - Remove mentions (@user)
    - Remove hashtags (#tag)
    """
    if not text:
        return ""
    
    # Lowercase
    normalized = text.lower()
    
    # Remove URLs
    normalized = re.sub(r'https?://\S+', '', normalized)
    normalized = re.sub(r'www\.\S+', '', normalized)
    
    # Remove mentions
    normalized = re.sub(r'@\w+', '', normalized)
    
    # Remove hashtags
    normalized = re.sub(r'#\w+', '', normalized)
    
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def compute_content_hash(text: str) -> str:
    """
    Compute a hash for content deduplication.
    
    Uses normalized text to detect duplicates even with minor variations.
    """
    normalized = normalize_text(text)
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def compute_fuzzy_hash(text: str, shingle_size: int = 3) -> Set[str]:
    """
    Compute a fuzzy hash (set of shingles) for similarity comparison.
    
    Shingles are overlapping word sequences.
    """
    normalized = normalize_text(text)
    words = normalized.split()
    
    if len(words) < shingle_size:
        return {normalized}
    
    shingles = set()
    for i in range(len(words) - shingle_size + 1):
        shingle = ' '.join(words[i:i + shingle_size])
        shingles.add(shingle)
    
    return shingles


# ─────────────────────────────────────────────────────────────────────────────
# Similarity Calculation
# ─────────────────────────────────────────────────────────────────────────────

def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """
    Calculate Jaccard similarity between two sets.
    
    Returns 0-1, where 1 means identical.
    """
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def text_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two texts using fuzzy hashing.
    """
    hash1 = compute_fuzzy_hash(text1)
    hash2 = compute_fuzzy_hash(text2)
    return jaccard_similarity(hash1, hash2)


def find_similar_texts(
    target: str,
    candidates: List[str],
    threshold: float = 0.7
) -> List[Tuple[int, float]]:
    """
    Find texts similar to target above threshold.
    
    Returns list of (index, similarity_score) tuples.
    """
    target_hash = compute_fuzzy_hash(target)
    results = []
    
    for i, candidate in enumerate(candidates):
        candidate_hash = compute_fuzzy_hash(candidate)
        similarity = jaccard_similarity(target_hash, candidate_hash)
        if similarity >= threshold:
            results.append((i, similarity))
    
    return sorted(results, key=lambda x: x[1], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# Content Metrics
# ─────────────────────────────────────────────────────────────────────────────

def extract_hashtags(text: str) -> List[str]:
    """Extract all hashtags from text."""
    return re.findall(r'#(\w+)', text)


def extract_mentions(text: str) -> List[str]:
    """Extract all @mentions from text."""
    return re.findall(r'@(\w+)', text)


def extract_urls(text: str) -> List[str]:
    """Extract all URLs from text."""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text)


def count_emojis(text: str) -> int:
    """Count emoji characters in text."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    return len(emoji_pattern.findall(text))


def get_content_metrics(text: str) -> dict:
    """
    Extract various metrics from content.
    """
    words = text.split()
    
    return {
        "character_count": len(text),
        "word_count": len(words),
        "hashtag_count": len(extract_hashtags(text)),
        "mention_count": len(extract_mentions(text)),
        "link_count": len(extract_urls(text)),
        "emoji_count": count_emojis(text),
        "uppercase_ratio": sum(1 for c in text if c.isupper()) / max(len(text), 1),
        "avg_word_length": sum(len(w) for w in words) / max(len(words), 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Spam Pattern Detection
# ─────────────────────────────────────────────────────────────────────────────

# Common spam phrases (lowercase)
SPAM_PHRASES = {
    "click here",
    "check out my",
    "follow me",
    "follow back",
    "free money",
    "make money fast",
    "get rich quick",
    "dm me",
    "link in bio",
    "promo code",
    "use my code",
    "sign up now",
    "limited time offer",
    "act now",
    "don't miss out",
    "crypto giveaway",
    "free giveaway",
    "send me dm",
    "100% guaranteed",
    "double your",
    "triple your",
}

# Bot-like username patterns
BOT_USERNAME_PATTERNS = [
    r'^[a-z]+\d{4,}$',           # word + 4+ digits (john12345)
    r'^\d+[a-z]+\d+$',           # digits + word + digits
    r'^[a-z]{2,4}\d{6,}$',       # 2-4 letters + 6+ digits
    r'_bot$',                     # ends with _bot
    r'^bot_',                     # starts with bot_
    r'[a-z]{1,3}\d{8,}',         # 1-3 letters + 8+ digits
]


def has_spam_phrases(text: str) -> bool:
    """Check if text contains known spam phrases."""
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in SPAM_PHRASES)


def has_excessive_caps(text: str, threshold: float = 0.5) -> bool:
    """Check if text has excessive uppercase (likely spam/shouting)."""
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 10:
        return False
    uppercase_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return uppercase_ratio > threshold


def has_keyword_stuffing(text: str, threshold: float = 0.3) -> bool:
    """
    Detect keyword stuffing (same word repeated unnaturally).
    """
    words = normalize_text(text).split()
    if len(words) < 5:
        return False
    
    word_counts = Counter(words)
    most_common_count = word_counts.most_common(1)[0][1]
    
    # If any word appears in more than threshold% of the text, it's stuffing
    return most_common_count / len(words) > threshold


def is_bot_username(username: str) -> bool:
    """Check if username matches common bot patterns."""
    if not username:
        return False
    
    username_lower = username.lower()
    return any(
        re.match(pattern, username_lower)
        for pattern in BOT_USERNAME_PATTERNS
    )


def calculate_spam_score(text: str, username: Optional[str] = None) -> float:
    """
    Calculate overall spam likelihood score (0-1).
    
    Higher = more likely spam.
    """
    score = 0.0
    metrics = get_content_metrics(text)
    
    # Spam phrase detection (major signal)
    if has_spam_phrases(text):
        score += 0.35
    
    # Excessive hashtags
    if metrics["hashtag_count"] > 5:
        score += 0.15
    elif metrics["hashtag_count"] > 3:
        score += 0.05
    
    # Excessive links
    if metrics["link_count"] > 2:
        score += 0.15
    elif metrics["link_count"] > 1:
        score += 0.05
    
    # All caps
    if has_excessive_caps(text):
        score += 0.10
    
    # Keyword stuffing
    if has_keyword_stuffing(text):
        score += 0.15
    
    # Very short content
    if metrics["word_count"] < 3:
        score += 0.05
    
    # Bot-like username
    if username and is_bot_username(username):
        score += 0.20
    
    return min(score, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Account Age Scoring
# ─────────────────────────────────────────────────────────────────────────────

def calculate_account_age_score(
    account_age_days: Optional[int],
    new_threshold: int = 30,
    established_threshold: int = 180
) -> float:
    """
    Calculate trust score based on account age.
    
    Returns 0-1, where older accounts get higher scores.
    """
    if account_age_days is None:
        return 0.5  # Unknown, neutral
    
    if account_age_days < new_threshold:
        # New accounts: 0.1 to 0.3
        return 0.1 + (account_age_days / new_threshold) * 0.2
    
    if account_age_days < established_threshold:
        # Growing accounts: 0.3 to 0.7
        progress = (account_age_days - new_threshold) / (established_threshold - new_threshold)
        return 0.3 + progress * 0.4
    
    # Established accounts: 0.7 to 1.0 (caps at 2 years)
    max_age = 730  # 2 years
    if account_age_days >= max_age:
        return 1.0
    
    progress = (account_age_days - established_threshold) / (max_age - established_threshold)
    return 0.7 + progress * 0.3


def calculate_follower_score(
    follower_count: Optional[int],
    following_count: Optional[int] = None
) -> float:
    """
    Calculate trust score based on follower metrics.
    
    Returns 0-1.
    """
    if follower_count is None:
        return 0.5  # Unknown
    
    # Base score from follower count (logarithmic scale)
    if follower_count <= 0:
        base_score = 0.1
    elif follower_count < 10:
        base_score = 0.2
    elif follower_count < 100:
        base_score = 0.3 + (follower_count / 100) * 0.2
    elif follower_count < 1000:
        base_score = 0.5 + (follower_count / 1000) * 0.2
    elif follower_count < 10000:
        base_score = 0.7 + (follower_count / 10000) * 0.15
    else:
        base_score = 0.85 + min(follower_count / 100000, 0.15)
    
    # Adjust for follower/following ratio (suspicious if following >> followers)
    if following_count and following_count > 100:
        ratio = follower_count / following_count
        if ratio < 0.1:
            # Following 10x more people than followers - suspicious
            base_score *= 0.5
        elif ratio < 0.5:
            base_score *= 0.8
    
    return min(base_score, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Time Pattern Analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyze_posting_times(timestamps: List[datetime]) -> dict:
    """
    Analyze posting time patterns to detect bot-like behavior.
    
    Returns metrics about timing patterns.
    """
    if len(timestamps) < 2:
        return {
            "count": len(timestamps),
            "is_suspicious": False,
            "regularity_score": 0.0,
        }
    
    # Sort timestamps
    sorted_times = sorted(timestamps)
    
    # Calculate intervals between posts
    intervals = []
    for i in range(1, len(sorted_times)):
        delta = (sorted_times[i] - sorted_times[i-1]).total_seconds()
        intervals.append(delta)
    
    if not intervals:
        return {
            "count": len(timestamps),
            "is_suspicious": False,
            "regularity_score": 0.0,
        }
    
    # Calculate statistics
    avg_interval = sum(intervals) / len(intervals)
    min_interval = min(intervals)
    max_interval = max(intervals)
    
    # Check for suspicious patterns
    is_suspicious = False
    regularity_score = 0.0
    
    # Very regular intervals (bot-like)
    if avg_interval > 0:
        variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
        std_dev = variance ** 0.5
        coefficient_of_variation = std_dev / avg_interval if avg_interval > 0 else 0
        
        # Low CV means very regular posting (suspicious)
        if coefficient_of_variation < 0.1 and len(intervals) > 5:
            is_suspicious = True
            regularity_score = 1.0 - coefficient_of_variation
    
    # Very fast posting (< 10 seconds between posts)
    if min_interval < 10 and len(intervals) > 3:
        is_suspicious = True
    
    return {
        "count": len(timestamps),
        "avg_interval_seconds": avg_interval,
        "min_interval_seconds": min_interval,
        "max_interval_seconds": max_interval,
        "is_suspicious": is_suspicious,
        "regularity_score": regularity_score,
    }


def detect_burst_activity(
    timestamps: List[datetime],
    window_minutes: int = 60,
    burst_threshold: int = 10
) -> bool:
    """
    Detect if there's a burst of activity in a short window.
    
    Returns True if activity exceeds threshold in any window.
    """
    if len(timestamps) < burst_threshold:
        return False
    
    sorted_times = sorted(timestamps)
    window_seconds = window_minutes * 60
    
    for i, start_time in enumerate(sorted_times):
        count = 1
        for j in range(i + 1, len(sorted_times)):
            delta = (sorted_times[j] - start_time).total_seconds()
            if delta <= window_seconds:
                count += 1
            else:
                break
        
        if count >= burst_threshold:
            return True
    
    return False



