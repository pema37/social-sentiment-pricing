# backend/tests/test_sentiment_analyzer.py
"""
Comprehensive tests for the VADER-based SentimentAnalyzer service.

Tests cover:
- SentimentResult dataclass
- _get_label mapping (compound → label)
- _calculate_confidence scoring
- analyze() single text (async, real VADER)
- analyze_batch() multiple texts (async)
- calculate_aggregate() statistics and trends
- Singleton instance
- Edge cases (empty strings, special characters, emojis)

Total: ~85 tests
"""

import sys
from unittest.mock import MagicMock

# === Import isolation ===
if "db.session" not in sys.modules:
    sys.modules["db.session"] = MagicMock()

import pytest

from services.sentiment_analyzer import (
    SentimentAnalyzer,
    SentimentResult,
    sentiment_analyzer,
)

# ============================================================
# Helpers
# ============================================================


def make_result(
    score=0.5,
    label="positive",
    confidence=0.7,
    emotions=None,
    raw_scores=None,
):
    """Create a SentimentResult for testing."""
    return SentimentResult(
        score=score,
        label=label,
        confidence=confidence,
        emotions=emotions or {"positive": 0.5, "negative": 0.1, "neutral": 0.4},
        raw_scores=raw_scores,
    )


# ============================================================
# 1. SentimentResult Dataclass
# ============================================================


class TestSentimentResult:
    def test_basic_creation(self):
        result = make_result()
        assert result.score == 0.5
        assert result.label == "positive"
        assert result.confidence == 0.7

    def test_emotions_dict(self):
        result = make_result(emotions={"positive": 0.6, "negative": 0.2, "neutral": 0.2})
        assert result.emotions["positive"] == 0.6
        assert result.emotions["negative"] == 0.2

    def test_raw_scores_default_none(self):
        result = SentimentResult(
            score=0.0,
            label="neutral",
            confidence=0.5,
            emotions={"positive": 0.0, "negative": 0.0, "neutral": 1.0},
        )
        assert result.raw_scores is None

    def test_raw_scores_explicit(self):
        raw = {"pos": 0.5, "neg": 0.1, "neu": 0.4, "compound": 0.6}
        result = make_result(raw_scores=raw)
        assert result.raw_scores == raw

    def test_negative_score(self):
        result = make_result(score=-0.8, label="very_negative")
        assert result.score == -0.8
        assert result.label == "very_negative"


# ============================================================
# 2. _get_label
# ============================================================


class TestGetLabel:
    """Tests for compound score → label mapping."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    def test_very_positive(self):
        assert self.analyzer._get_label(0.5) == "very_positive"

    def test_very_positive_high(self):
        assert self.analyzer._get_label(0.9) == "very_positive"

    def test_very_positive_at_boundary(self):
        assert self.analyzer._get_label(0.5) == "very_positive"

    def test_positive(self):
        assert self.analyzer._get_label(0.3) == "positive"

    def test_positive_at_lower_boundary(self):
        assert self.analyzer._get_label(0.05) == "positive"

    def test_neutral_zero(self):
        assert self.analyzer._get_label(0.0) == "neutral"

    def test_neutral_just_below_positive(self):
        assert self.analyzer._get_label(0.04) == "neutral"

    def test_neutral_just_above_negative(self):
        assert self.analyzer._get_label(-0.04) == "neutral"

    def test_negative(self):
        assert self.analyzer._get_label(-0.3) == "negative"

    def test_negative_at_boundary(self):
        assert self.analyzer._get_label(-0.05) == "negative"

    def test_very_negative(self):
        assert self.analyzer._get_label(-0.7) == "very_negative"

    def test_very_negative_at_boundary(self):
        assert self.analyzer._get_label(-0.5) == "very_negative"

    def test_very_negative_extreme(self):
        assert self.analyzer._get_label(-1.0) == "very_negative"

    def test_very_positive_extreme(self):
        assert self.analyzer._get_label(1.0) == "very_positive"


# ============================================================
# 3. _calculate_confidence
# ============================================================


class TestCalculateConfidence:
    """Tests for confidence calculation from VADER scores."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    def test_strong_positive_high_confidence(self):
        scores = {"compound": 0.9, "pos": 0.7, "neg": 0.0, "neu": 0.3}
        conf = self.analyzer._calculate_confidence(scores)
        assert conf > 0.5

    def test_strong_negative_high_confidence(self):
        scores = {"compound": -0.9, "pos": 0.0, "neg": 0.7, "neu": 0.3}
        conf = self.analyzer._calculate_confidence(scores)
        assert conf > 0.5

    def test_neutral_low_confidence(self):
        scores = {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}
        conf = self.analyzer._calculate_confidence(scores)
        assert conf < 0.3

    def test_mixed_moderate_confidence(self):
        scores = {"compound": 0.3, "pos": 0.3, "neg": 0.2, "neu": 0.5}
        conf = self.analyzer._calculate_confidence(scores)
        assert 0.1 < conf < 0.9

    def test_confidence_capped_at_1(self):
        scores = {"compound": 1.0, "pos": 0.9, "neg": 0.1, "neu": 0.0}
        conf = self.analyzer._calculate_confidence(scores)
        assert conf <= 1.0

    def test_confidence_rounded_to_3_decimals(self):
        scores = {"compound": 0.5, "pos": 0.4, "neg": 0.1, "neu": 0.5}
        conf = self.analyzer._calculate_confidence(scores)
        assert conf == round(conf, 3)

    def test_formula_correctness(self):
        """Verify the exact formula: (|compound| + pos + neg) / 2 * 1.2, capped at 1.0"""
        scores = {"compound": 0.6, "pos": 0.4, "neg": 0.1, "neu": 0.5}
        expected = round(min((abs(0.6) + 0.4 + 0.1) / 2 * 1.2, 1.0), 3)
        assert self.analyzer._calculate_confidence(scores) == expected

    def test_zero_everything(self):
        scores = {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}
        conf = self.analyzer._calculate_confidence(scores)
        assert conf == 0.0


# ============================================================
# 4. analyze() — Single Text (Async, Real VADER)
# ============================================================


class TestAnalyze:
    """Tests for single-text analysis using real VADER."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_positive_text(self):
        result = await self.analyzer.analyze("This product is absolutely amazing and wonderful!")
        assert result.score > 0
        assert result.label in ("positive", "very_positive")

    @pytest.mark.asyncio
    async def test_negative_text(self):
        result = await self.analyzer.analyze("This is terrible, awful, and completely broken.")
        assert result.score < 0
        assert result.label in ("negative", "very_negative")

    @pytest.mark.asyncio
    async def test_neutral_text(self):
        result = await self.analyzer.analyze("The product is available in the store.")
        assert abs(result.score) < 0.3

    @pytest.mark.asyncio
    async def test_returns_sentiment_result(self):
        result = await self.analyzer.analyze("Test text")
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_score_in_range(self):
        result = await self.analyzer.analyze("Some random text for testing purposes.")
        assert -1.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_confidence_in_range(self):
        result = await self.analyzer.analyze("Great product!")
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_emotions_keys(self):
        result = await self.analyzer.analyze("I love this!")
        assert "positive" in result.emotions
        assert "negative" in result.emotions
        assert "neutral" in result.emotions

    @pytest.mark.asyncio
    async def test_raw_scores_present(self):
        result = await self.analyzer.analyze("Testing raw scores")
        assert result.raw_scores is not None
        assert "compound" in result.raw_scores
        assert "pos" in result.raw_scores
        assert "neg" in result.raw_scores
        assert "neu" in result.raw_scores

    @pytest.mark.asyncio
    async def test_score_rounded_to_3_decimals(self):
        result = await self.analyzer.analyze("A decent product overall.")
        assert result.score == round(result.score, 3)

    @pytest.mark.asyncio
    async def test_emotions_rounded_to_3_decimals(self):
        result = await self.analyzer.analyze("Pretty good stuff here!")
        for key in ("positive", "negative", "neutral"):
            assert result.emotions[key] == round(result.emotions[key], 3)

    @pytest.mark.asyncio
    async def test_label_matches_score(self):
        """Label should be consistent with the score value."""
        result = await self.analyzer.analyze("This is the best thing ever created!")
        if result.score >= 0.5:
            assert result.label == "very_positive"
        elif result.score >= 0.05:
            assert result.label == "positive"

    @pytest.mark.asyncio
    async def test_emoji_handling(self):
        """VADER handles emojis — this should score positive."""
        result = await self.analyzer.analyze("😊👍🎉")
        assert result.score > 0

    @pytest.mark.asyncio
    async def test_social_media_slang(self):
        """VADER handles social media slang like 'lol', caps, etc."""
        result = await self.analyzer.analyze("LOVE this!!! SO GOOD lol")
        assert result.score > 0

    @pytest.mark.asyncio
    async def test_empty_string(self):
        """Empty text should return a neutral-ish result without crashing."""
        result = await self.analyzer.analyze("")
        assert isinstance(result, SentimentResult)
        assert result.score == 0.0


# ============================================================
# 5. analyze_batch() — Multiple Texts
# ============================================================


class TestAnalyzeBatch:
    """Tests for batch text analysis."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_batch_returns_list(self):
        texts = ["Good product", "Bad product"]
        results = await self.analyzer.analyze_batch(texts)
        assert isinstance(results, list)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_batch_all_sentiment_results(self):
        texts = ["Great!", "Terrible!", "Okay."]
        results = await self.analyzer.analyze_batch(texts)
        for r in results:
            assert isinstance(r, SentimentResult)

    @pytest.mark.asyncio
    async def test_batch_empty_list(self):
        results = await self.analyzer.analyze_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_single_item(self):
        results = await self.analyzer.analyze_batch(["Just one text"])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_batch_preserves_order(self):
        texts = ["Amazing wonderful excellent!", "Horrible terrible awful!"]
        results = await self.analyzer.analyze_batch(texts)
        assert results[0].score > results[1].score

    @pytest.mark.asyncio
    async def test_batch_many_items(self):
        texts = [f"Text number {i}" for i in range(20)]
        results = await self.analyzer.analyze_batch(texts)
        assert len(results) == 20


# ============================================================
# 6. calculate_aggregate()
# ============================================================


class TestCalculateAggregate:
    """Tests for aggregate sentiment statistics."""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_empty_results(self):
        agg = await self.analyzer.calculate_aggregate([])
        assert agg["average_score"] == 0.0
        assert agg["total_count"] == 0
        assert agg["positive_count"] == 0
        assert agg["negative_count"] == 0
        assert agg["neutral_count"] == 0
        assert agg["very_positive_count"] == 0
        assert agg["very_negative_count"] == 0
        assert agg["trend"] == "neutral"
        assert agg["average_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_single_positive_result(self):
        results = [make_result(score=0.6, label="very_positive", confidence=0.8)]
        agg = await self.analyzer.calculate_aggregate(results)
        assert agg["total_count"] == 1
        assert agg["very_positive_count"] == 1
        assert agg["average_score"] == 0.6

    @pytest.mark.asyncio
    async def test_mixed_results_counts(self):
        results = [
            make_result(label="positive"),
            make_result(label="negative"),
            make_result(label="neutral"),
            make_result(label="very_positive"),
            make_result(label="very_negative"),
        ]
        agg = await self.analyzer.calculate_aggregate(results)
        assert agg["total_count"] == 5
        assert agg["positive_count"] == 1
        assert agg["negative_count"] == 1
        assert agg["neutral_count"] == 1
        assert agg["very_positive_count"] == 1
        assert agg["very_negative_count"] == 1

    @pytest.mark.asyncio
    async def test_average_score_calculation(self):
        results = [
            make_result(score=0.8),
            make_result(score=0.2),
            make_result(score=-0.4),
        ]
        agg = await self.analyzer.calculate_aggregate(results)
        # (0.8 + 0.2 + -0.4) / 3 = 0.2
        assert agg["average_score"] == 0.2

    @pytest.mark.asyncio
    async def test_average_confidence(self):
        results = [
            make_result(confidence=0.9),
            make_result(confidence=0.3),
        ]
        agg = await self.analyzer.calculate_aggregate(results)
        assert agg["average_confidence"] == 0.6

    @pytest.mark.asyncio
    async def test_trend_positive(self):
        """Positive trend when positive_total > negative_total * 1.5."""
        results = [
            make_result(label="positive"),
            make_result(label="positive"),
            make_result(label="very_positive"),
            make_result(label="negative"),
        ]
        agg = await self.analyzer.calculate_aggregate(results)
        # positive_total = 3, negative_total = 1, 3 > 1*1.5 → positive
        assert agg["trend"] == "positive"

    @pytest.mark.asyncio
    async def test_trend_negative(self):
        """Negative trend when negative_total > positive_total * 1.5."""
        results = [
            make_result(label="negative"),
            make_result(label="negative"),
            make_result(label="very_negative"),
            make_result(label="positive"),
        ]
        agg = await self.analyzer.calculate_aggregate(results)
        # negative_total = 3, positive_total = 1, 3 > 1*1.5 → negative
        assert agg["trend"] == "negative"

    @pytest.mark.asyncio
    async def test_trend_mixed(self):
        """Mixed trend when neither side dominates by 1.5x."""
        results = [
            make_result(label="positive"),
            make_result(label="negative"),
        ]
        agg = await self.analyzer.calculate_aggregate(results)
        # 1 vs 1 → neither > other*1.5 → mixed
        assert agg["trend"] == "mixed"

    @pytest.mark.asyncio
    async def test_trend_all_neutral(self):
        """All neutral → both positive and negative are 0, neither condition met → mixed."""
        results = [
            make_result(label="neutral"),
            make_result(label="neutral"),
        ]
        agg = await self.analyzer.calculate_aggregate(results)
        # positive_total=0, negative_total=0
        # 0 > 0*1.5 is False, 0 > 0*1.5 is False → mixed
        assert agg["trend"] == "mixed"

    @pytest.mark.asyncio
    async def test_average_score_rounded(self):
        results = [
            make_result(score=0.333),
            make_result(score=0.333),
            make_result(score=0.333),
        ]
        agg = await self.analyzer.calculate_aggregate(results)
        assert agg["average_score"] == round(0.999 / 3, 3)

    @pytest.mark.asyncio
    async def test_all_keys_present(self):
        results = [make_result()]
        agg = await self.analyzer.calculate_aggregate(results)
        expected_keys = {
            "average_score",
            "average_confidence",
            "total_count",
            "positive_count",
            "negative_count",
            "neutral_count",
            "very_positive_count",
            "very_negative_count",
            "trend",
        }
        assert set(agg.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_trend_boundary_exactly_1_5x(self):
        """Test the exact 1.5x boundary — need >1.5x, not >=1.5x."""
        results = [
            make_result(label="positive"),
            make_result(label="positive"),
            make_result(label="positive"),
            make_result(label="negative"),
            make_result(label="negative"),
        ]
        agg = await self.analyzer.calculate_aggregate(results)
        # positive_total = 3, negative_total = 2, 3 > 2*1.5=3.0 is False → mixed
        assert agg["trend"] == "mixed"


# ============================================================
# 7. Singleton Instance
# ============================================================


class TestSingletonInstance:
    def test_singleton_exists(self):
        assert sentiment_analyzer is not None

    def test_singleton_is_analyzer(self):
        assert isinstance(sentiment_analyzer, SentimentAnalyzer)

    def test_singleton_has_vader(self):
        assert hasattr(sentiment_analyzer, "analyzer")

    @pytest.mark.asyncio
    async def test_singleton_can_analyze(self):
        result = await sentiment_analyzer.analyze("Works great!")
        assert isinstance(result, SentimentResult)


# ============================================================
# 8. Edge Cases
# ============================================================


class TestEdgeCases:
    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_very_long_text(self):
        text = "This is great! " * 500
        result = await self.analyzer.analyze(text)
        assert isinstance(result, SentimentResult)
        assert result.score > 0

    @pytest.mark.asyncio
    async def test_special_characters(self):
        result = await self.analyzer.analyze("@#$%^&*()")
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_numbers_only(self):
        result = await self.analyzer.analyze("12345 67890")
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_mixed_language(self):
        result = await self.analyzer.analyze("This is great! C'est magnifique!")
        assert isinstance(result, SentimentResult)

    @pytest.mark.asyncio
    async def test_all_caps_intensifier(self):
        """VADER treats ALL CAPS as emphasis/intensifier."""
        normal = await self.analyzer.analyze("this is great")
        caps = await self.analyzer.analyze("THIS IS GREAT")
        # Caps version should have higher positive score
        assert caps.score >= normal.score

    @pytest.mark.asyncio
    async def test_exclamation_intensifier(self):
        """VADER treats exclamation marks as intensifiers."""
        no_exclaim = await self.analyzer.analyze("this is great")
        with_exclaim = await self.analyzer.analyze("this is great!!!")
        assert with_exclaim.score >= no_exclaim.score

    @pytest.mark.asyncio
    async def test_negation_handling(self):
        """VADER handles negation words."""
        positive = await self.analyzer.analyze("This is good")
        negated = await self.analyzer.analyze("This is not good")
        assert negated.score < positive.score

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        result = await self.analyzer.analyze("   ")
        assert isinstance(result, SentimentResult)
        assert result.score == 0.0
