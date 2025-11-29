# backend/services/sentiment_analyzer.py

from decimal import Decimal
from typing import List, Dict
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


class SentimentAnalyzer:
    """
    VADER-based sentiment analysis service.
    VADER is optimized for social media text (handles emojis, slang, etc.)
    """

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> Dict:
        """
        Analyze a single piece of text.
        
        Returns:
            {
                "compound": Decimal,  # -1 (negative) to +1 (positive)
                "positive": Decimal,  # 0 to 1
                "negative": Decimal,  # 0 to 1
                "neutral": Decimal,   # 0 to 1
                "label": str          # "positive", "negative", or "neutral"
            }
        """
        scores = self.analyzer.polarity_scores(text)

        # Determine label based on compound score
        compound = scores["compound"]
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        return {
            "compound": Decimal(str(round(scores["compound"], 3))),
            "positive": Decimal(str(round(scores["pos"], 3))),
            "negative": Decimal(str(round(scores["neg"], 3))),
            "neutral": Decimal(str(round(scores["neu"], 3))),
            "label": label
        }

    def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """Analyze multiple texts at once."""
        return [self.analyze(text) for text in texts]

    def calculate_aggregate(self, sentiments: List[Dict]) -> Dict:
        """
        Calculate aggregate sentiment from multiple analyses.
        
        Returns:
            {
                "average_compound": Decimal,
                "total_count": int,
                "positive_count": int,
                "negative_count": int,
                "neutral_count": int,
                "trend": str  # "positive", "negative", or "mixed"
            }
        """
        if not sentiments:
            return {
                "average_compound": Decimal("0"),
                "total_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "trend": "neutral"
            }

        total = len(sentiments)
        compound_sum = sum(s["compound"] for s in sentiments)
        average_compound = compound_sum / total

        positive_count = sum(1 for s in sentiments if s["label"] == "positive")
        negative_count = sum(1 for s in sentiments if s["label"] == "negative")
        neutral_count = sum(1 for s in sentiments if s["label"] == "neutral")

        # Determine overall trend
        if positive_count > negative_count * 1.5:
            trend = "positive"
        elif negative_count > positive_count * 1.5:
            trend = "negative"
        else:
            trend = "mixed"

        return {
            "average_compound": Decimal(str(round(average_compound, 3))),
            "total_count": total,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "trend": trend
        }


# Singleton instance
sentiment_analyzer = SentimentAnalyzer()

