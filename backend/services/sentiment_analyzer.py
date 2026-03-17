# backend/services/sentiment_analyzer.py

from dataclasses import dataclass

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


@dataclass
class SentimentResult:
    """Standardized sentiment analysis result."""

    score: float  # -1.0 (negative) to +1.0 (positive)
    label: str  # "very_negative", "negative", "neutral", "positive", "very_positive"
    confidence: float  # 0.0 to 1.0
    emotions: dict[str, float]  # {"positive": 0.x, "negative": 0.x, "neutral": 0.x}
    raw_scores: dict[str, float] | None = None


class SentimentAnalyzer:
    """
    VADER-based sentiment analysis service.
    VADER is optimized for social media text (handles emojis, slang, etc.)

    All methods are async for consistency with the rest of the codebase.
    """

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()

    def _get_label(self, compound: float) -> str:
        """Convert compound score to descriptive label."""
        if compound >= 0.5:
            return "very_positive"
        elif compound >= 0.05:
            return "positive"
        elif compound <= -0.5:
            return "very_negative"
        elif compound <= -0.05:
            return "negative"
        else:
            return "neutral"

    def _calculate_confidence(self, scores: dict[str, float]) -> float:
        """
        Calculate confidence based on how decisive the sentiment is.
        High neutral = low confidence, strong pos/neg = high confidence.
        """
        compound_abs = abs(scores["compound"])
        non_neutral = scores["pos"] + scores["neg"]
        confidence = (compound_abs + non_neutral) / 2
        return round(min(confidence * 1.2, 1.0), 3)

    async def analyze(self, text: str) -> SentimentResult:
        """
        Analyze a single piece of text.

        Returns:
            SentimentResult with score, label, confidence, and emotions
        """
        # VADER is CPU-bound and fast, so we run it directly
        # For slower/IO-bound operations, use asyncio.to_thread()
        scores = self.analyzer.polarity_scores(text)

        return SentimentResult(
            score=round(scores["compound"], 3),
            label=self._get_label(scores["compound"]),
            confidence=self._calculate_confidence(scores),
            emotions={
                "positive": round(scores["pos"], 3),
                "negative": round(scores["neg"], 3),
                "neutral": round(scores["neu"], 3),
            },
            raw_scores=scores,
        )

    async def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Analyze multiple texts at once."""
        results = []
        for text in texts:
            result = await self.analyze(text)
            results.append(result)
        return results

    async def calculate_aggregate(self, results: list[SentimentResult]) -> dict:
        """Calculate aggregate sentiment from multiple analyses."""
        if not results:
            return {
                "average_score": 0.0,
                "total_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "very_positive_count": 0,
                "very_negative_count": 0,
                "trend": "neutral",
                "average_confidence": 0.0,
            }

        total = len(results)
        score_sum = sum(r.score for r in results)
        confidence_sum = sum(r.confidence for r in results)

        label_counts = {
            "very_positive": 0,
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "very_negative": 0,
        }
        for r in results:
            label_counts[r.label] += 1

        positive_total = label_counts["positive"] + label_counts["very_positive"]
        negative_total = label_counts["negative"] + label_counts["very_negative"]

        if positive_total > negative_total * 1.5:
            trend = "positive"
        elif negative_total > positive_total * 1.5:
            trend = "negative"
        else:
            trend = "mixed"

        return {
            "average_score": round(score_sum / total, 3),
            "average_confidence": round(confidence_sum / total, 3),
            "total_count": total,
            "positive_count": label_counts["positive"],
            "negative_count": label_counts["negative"],
            "neutral_count": label_counts["neutral"],
            "very_positive_count": label_counts["very_positive"],
            "very_negative_count": label_counts["very_negative"],
            "trend": trend,
        }


# Singleton instance
sentiment_analyzer = SentimentAnalyzer()
