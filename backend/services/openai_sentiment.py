# backend/services/openai_sentiment.py

import json
from decimal import Decimal
from typing import Dict, List, Optional

from openai import OpenAI

from backend.core.config import settings


class OpenAISentimentAnalyzer:
    """
    Sentiment analysis using OpenAI GPT-4o-mini.
    More accurate than VADER for nuanced text, sarcasm, and context.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.model = "gpt-4o-mini"
    
    def is_available(self) -> bool:
        """Check if OpenAI is configured."""
        return self.client is not None
    
    def analyze(self, text: str, context: Optional[str] = None) -> Dict:
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
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
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

        user_message = f"Analyze this social media post:\n\"{text}\""
        if context:
            user_message += f"\n\nContext: {context}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
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
                "is_sarcastic": result.get("is_sarcastic", False)
            }
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse OpenAI response: {e}")
            # Return neutral fallback
            return self._fallback_response()
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return self._fallback_response()
    
    def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """Analyze multiple texts."""
        return [self.analyze(text) for text in texts]
    
    def _fallback_response(self) -> Dict:
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
            "is_sarcastic": False
        }


# Singleton instance
openai_sentiment_analyzer = OpenAISentimentAnalyzer()

