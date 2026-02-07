"""
Tests for the ActualPrice sentiment analysis pipeline.
Aligned with actual service signatures:
  - SentimentAnalyzer.analyze(text) → async, returns SentimentResult
  - HybridSentimentAnalyzer._analyze_vader(text) → sync dict
  - HybridSentimentAnalyzer.analyze(text) → async
  - SentimentAggregator(db) / TrendDetector(db) → require AsyncSession
"""

import pytest
import asyncio


# ===================================================================
# VADER / SentimentAnalyzer Tests (async)
# ===================================================================

class TestSentimentAnalyzer:
    """SentimentResult has .score (not .compound), .label, .confidence, .raw_scores"""

    @pytest.mark.asyncio
    async def test_positive_text_returns_positive(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze("This product is absolutely amazing, best purchase ever!")
        assert result.score > 0

    @pytest.mark.asyncio
    async def test_negative_text_returns_negative(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze("Terrible quality, completely broken, worst purchase of my life.")
        assert result.score < 0

    @pytest.mark.asyncio
    async def test_neutral_text_returns_near_zero(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze("The product arrived on Tuesday.")
        assert -0.4 <= result.score <= 0.4

    @pytest.mark.asyncio
    async def test_score_range_bounded(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze("Great product!!!")
        assert -1.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_result_has_label(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze("I love these headphones so much!")
        assert result.label in ("very_positive", "positive", "negative", "very_negative", "neutral")

    @pytest.mark.asyncio
    async def test_result_has_confidence(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze("Great product, highly recommend!")
        assert hasattr(result, "confidence")
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_empty_string_returns_neutral(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze("")
        assert -0.4 <= result.score <= 0.4

    @pytest.mark.asyncio
    async def test_emoji_text_handled(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze("Love it! 😍🔥👍")
        assert result.score >= 0

    @pytest.mark.asyncio
    async def test_batch_analysis(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        results = await analyzer.analyze_batch([
            "Amazing product!", "Terrible quality.", "It's okay."
        ])
        assert len(results) == 3
        assert results[0].score > results[1].score

    @pytest.mark.asyncio
    async def test_raw_scores_contain_compound(self):
        from services.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze("Great headphones!")
        assert hasattr(result, "raw_scores")
        assert "compound" in result.raw_scores


# ===================================================================
# HybridSentimentAnalyzer Tests
# ===================================================================

class TestHybridSentimentAnalyzer:

    def test_vader_baseline_works(self):
        """The internal _analyze_vader method should return a dict with scores."""
        from services.hybrid_sentiment_analyzer import HybridSentimentAnalyzer
        analyzer = HybridSentimentAnalyzer()
        result = analyzer._analyze_vader("This is a great product!")
        assert "compound" in result
        assert result["compound"] > 0

    def test_vader_negative(self):
        from services.hybrid_sentiment_analyzer import HybridSentimentAnalyzer
        analyzer = HybridSentimentAnalyzer()
        result = analyzer._analyze_vader("This is terrible and broken.")
        assert result["compound"] < 0

    def test_vader_neutral(self):
        from services.hybrid_sentiment_analyzer import HybridSentimentAnalyzer
        analyzer = HybridSentimentAnalyzer()
        result = analyzer._analyze_vader("The package arrived today.")
        assert -0.3 <= result["compound"] <= 0.3

    def test_available_sources(self):
        from services.hybrid_sentiment_analyzer import HybridSentimentAnalyzer
        analyzer = HybridSentimentAnalyzer()
        sources = analyzer.get_available_sources()
        assert "vader" in sources
        assert isinstance(sources, list)

    def test_has_analyze_with_trust(self):
        """HybridSentimentAnalyzer should have analyze_with_trust method."""
        from services.hybrid_sentiment_analyzer import HybridSentimentAnalyzer
        analyzer = HybridSentimentAnalyzer()
        assert callable(getattr(analyzer, "analyze_with_trust", None))


# ===================================================================
# SentimentAggregator Tests (requires db mock)
# ===================================================================

class TestSentimentAggregator:

    def test_aggregator_initializes_with_db(self, mock_db):
        from services.analysis.sentiment_aggregator import SentimentAggregator
        agg = SentimentAggregator(db=mock_db)
        assert agg is not None

    def test_aggregator_has_get_product_sentiment(self, mock_db):
        from services.analysis.sentiment_aggregator import SentimentAggregator
        agg = SentimentAggregator(db=mock_db)
        assert callable(getattr(agg, "get_product_sentiment", None))

    def test_aggregator_has_get_sentiment_velocity(self, mock_db):
        from services.analysis.sentiment_aggregator import SentimentAggregator
        agg = SentimentAggregator(db=mock_db)
        assert callable(getattr(agg, "get_sentiment_velocity", None))


# ===================================================================
# TrendDetector Tests (requires db mock)
# ===================================================================

class TestTrendDetector:

    def test_detector_initializes_with_db(self, mock_db):
        from services.analysis.trend_detector import TrendDetector
        detector = TrendDetector(db=mock_db)
        assert detector is not None

    def test_detector_has_detect_all(self, mock_db):
        from services.analysis.trend_detector import TrendDetector
        detector = TrendDetector(db=mock_db)
        assert callable(getattr(detector, "detect_all", None))

    def test_detector_has_get_pricing_signal(self, mock_db):
        from services.analysis.trend_detector import TrendDetector
        detector = TrendDetector(db=mock_db)
        assert callable(getattr(detector, "get_pricing_signal", None))

    def test_detector_has_detect_volume_spike(self, mock_db):
        from services.analysis.trend_detector import TrendDetector
        detector = TrendDetector(db=mock_db)
        assert callable(getattr(detector, "detect_volume_spike", None))

    def test_detector_has_detect_sentiment_shift(self, mock_db):
        from services.analysis.trend_detector import TrendDetector
        detector = TrendDetector(db=mock_db)
        assert callable(getattr(detector, "detect_sentiment_shift", None))


        