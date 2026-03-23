# backend/services/openai_sentiment.py

import asyncio
import json
from decimal import Decimal

from core.logging import get_logger

logger = get_logger(__name__)


class OpenAISentimentAnalyzer:
    """
    Sentiment analysis using AI (routed through ai_generator).
    More accurate than VADER for nuanced text, sarcasm, and context.
    """

    def _get_generator(self):
        """Lazy import to avoid circular dependency at module load."""
        from services.ai_generator import ai_generator

        return ai_generator

    def is_available(self) -> bool:
        """Check if AI service is configured."""
        return self._get_generator().is_available()

    async def analyze(self, text: str, context: str | None = None) -> dict:
        """
        Analyze sentiment of a single text.

        Returns:
            {
                "compound": Decimal,  # -1 (negative) to +1 (positive)
                "positive": Decimal,
                "negative": Decimal,
                "neutral": Decimal,
                "label": str,  # "very_negative", "negative", "neutral", "positive", "very_positive"
                "confidence": Decimal,
                "emotions": dict,  # joy, anger, fear, surprise, sadness
                "topics": list,
                "is_sarcastic": bool
            }
        """
        generator = self._get_generator()
        if not generator.is_available():
            raise ValueError("No AI API key configured")

        system_prompt = """You are a sentiment analysis system for e-commerce products.
Analyze social media posts about products and brands.

Return ONLY valid JSON with these exact fields:
{
    "sentiment_score": float from -1.0 (very negative) to 1.0 (very positive),
    "sentiment_label": "very_negative" | "negative" | "neutral" | "positive" | "very_positive",
    "confidence": float from 0.0 to 1.0,
    "positive_score": float from 0.0 to 1.0,
    "negative_score": float from 0.0 to 1.0,
    "neutral_score": float from 0.0 to 1.0,
    "emotions": {"joy": float, "anger": float, "fear": float, "surprise": float, "sadness": float},
    "topics": ["list", "of", "topics"],
    "is_sarcastic": boolean
}

Consider context like sarcasm, irony, and cultural nuances.
The three scores (positive, negative, neutral) should roughly sum to 1.0."""

        user_message = f'Analyze this social media post:\n"{text}"'
        if context:
            user_message += f"\n\nContext: {context}"

        try:
            response_text, provider = await generator._generate(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=0.1,
                max_tokens=300,
            )

            result_text = response_text.strip()

            # Parse JSON response
            # Handle potential markdown code blocks
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]

            result = json.loads(result_text)

            return {
                "compound": Decimal(str(round(result.get("sentiment_score", 0), 3))),
                "positive": Decimal(str(round(result.get("positive_score", 0), 3))),
                "negative": Decimal(str(round(result.get("negative_score", 0), 3))),
                "neutral": Decimal(str(round(result.get("neutral_score", 0), 3))),
                "label": result.get("sentiment_label", "neutral"),
                "confidence": Decimal(str(round(result.get("confidence", 0.5), 3))),
                "emotions": result.get("emotions", {}),
                "topics": result.get("topics", []),
                "is_sarcastic": result.get("is_sarcastic", False),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            # Return neutral fallback
            return self._fallback_response()
        except Exception as e:
            logger.error(f"AI API error: {e}")
            return self._fallback_response()

    async def analyze_batch(self, texts: list[str], max_concurrent: int = 10) -> list[dict]:
        """
        Analyze multiple texts concurrently.

        Args:
            texts: List of texts to analyze
            max_concurrent: Maximum concurrent API calls (to avoid rate limits)

        Returns:
            List of sentiment analysis results in same order as input
        """
        if not texts:
            return []

        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(text: str) -> dict:
            async with semaphore:
                return await self.analyze(text)

        # Run all analyses concurrently (with limit)
        results = await asyncio.gather(*[analyze_with_limit(text) for text in texts], return_exceptions=True)

        # Replace exceptions with fallback responses
        return [result if isinstance(result, dict) else self._fallback_response() for result in results]

    def _fallback_response(self) -> dict:
        """Return neutral response when analysis fails."""
        return {
            "compound": Decimal("0"),
            "positive": Decimal("0.33"),
            "negative": Decimal("0.33"),
            "neutral": Decimal("0.34"),
            "label": "neutral",
            "confidence": Decimal("0"),
            "emotions": {"joy": 0, "anger": 0, "fear": 0, "surprise": 0, "sadness": 0},
            "topics": [],
            "is_sarcastic": False,
        }


# Singleton instance for convenience (still works with async)
openai_sentiment_analyzer = OpenAISentimentAnalyzer()
