# backend/services/hybrid_sentiment_analyzer.py
"""
Hybrid Sentiment Analyzer - Combines VADER, Gemini, and OpenAI for robust sentiment analysis.

Strategy:
1. VADER runs always (instant, free baseline)
2. Gemini runs if API key configured (primary AI - fast and cost-effective)
3. OpenAI runs as fallback if Gemini fails (backup for accuracy)
4. Final score = weighted combination of available results
"""

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional
import logging

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class HybridSentimentResult:
    """Combined sentiment result from multiple analyzers."""
    # Final combined scores
    compound: float  # -1.0 to +1.0
    label: str  # very_negative, negative, neutral, positive, very_positive
    confidence: float  # 0.0 to 1.0
    
    # Component scores
    positive: float
    negative: float
    neutral: float
    
    # Metadata
    sources_used: List[str]  # Which analyzers contributed
    individual_scores: Dict[str, float]  # Score from each analyzer
    emotions: Dict[str, float]  # Detailed emotions (from Gemini/OpenAI)
    topics: List[str]  # Extracted topics (from Gemini/OpenAI)
    is_sarcastic: bool  # Sarcasm detection (from Gemini/OpenAI)


class HybridSentimentAnalyzer:
    """
    Multi-source sentiment analyzer combining:
    - VADER (always runs - fast, free, good for social media)
    - Gemini (primary AI - fast, cost-effective)
    - OpenAI GPT-4o-mini (fallback if Gemini fails - better nuance/sarcasm)
    """
    
    def __init__(self):
        # VADER - always available
        self.vader = None
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self.vader = SentimentIntensityAnalyzer()
            logger.info("VADER sentiment analyzer initialized")
        except ImportError:
            logger.warning("VADER not installed - pip install vaderSentiment")
        
        # Gemini - primary AI
        self.gemini_client = None
        self.gemini_model = "gemini-2.0-flash-exp"
        if getattr(settings, 'GEMINI_API_KEY', None):
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_client = genai.GenerativeModel(self.gemini_model)
                logger.info("Gemini sentiment analyzer initialized (primary AI)")
            except ImportError:
                logger.warning("Google GenAI not installed - pip install google-generativeai")
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")
        
        # OpenAI - fallback
        self.openai_client = None
        if settings.OPENAI_API_KEY:
            try:
                from openai import AsyncOpenAI
                self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI sentiment analyzer initialized (fallback)")
            except ImportError:
                logger.warning("OpenAI not installed - pip install openai")
    
    def get_available_sources(self) -> List[str]:
        """Return list of available analyzers."""
        sources = []
        if self.vader:
            sources.append("vader")
        if self.gemini_client:
            sources.append("gemini")
        if self.openai_client:
            sources.append("openai")
        return sources
    
    async def analyze(self, text: str, use_ai: bool = True) -> HybridSentimentResult:
        """
        Analyze text using all available analyzers.
        
        Args:
            text: The text to analyze
            use_ai: Whether to use Gemini/OpenAI (set False for speed)
        
        Returns:
            HybridSentimentResult with combined scores
        """
        results = {}
        sources_used = []
        emotions = {}
        topics = []
        is_sarcastic = False
        
        # 1. VADER (always runs - instant)
        if self.vader:
            try:
                vader_result = self._analyze_vader(text)
                results["vader"] = vader_result["compound"]
                sources_used.append("vader")
                logger.debug(f"VADER score: {vader_result['compound']}")
            except Exception as e:
                logger.error(f"VADER analysis failed: {e}")
        
        # 2. Gemini (primary AI - if available and use_ai=True)
        if use_ai and self.gemini_client:
            try:
                gemini_result = await self._analyze_gemini(text)
                results["gemini"] = float(gemini_result["compound"])
                sources_used.append("gemini")
                emotions = gemini_result.get("emotions", {})
                topics = gemini_result.get("topics", [])
                is_sarcastic = gemini_result.get("is_sarcastic", False)
                logger.debug(f"Gemini score: {gemini_result['compound']}")
            except Exception as e:
                logger.warning(f"Gemini analysis failed, trying OpenAI: {e}")
                
                # 3. OpenAI fallback
                if self.openai_client:
                    try:
                        openai_result = await self._analyze_openai(text)
                        results["openai"] = float(openai_result["compound"])
                        sources_used.append("openai")
                        emotions = openai_result.get("emotions", {})
                        topics = openai_result.get("topics", [])
                        is_sarcastic = openai_result.get("is_sarcastic", False)
                        logger.debug(f"OpenAI score: {openai_result['compound']}")
                    except Exception as e2:
                        logger.error(f"OpenAI also failed: {e2}")
        
        # If no Gemini but OpenAI is available and use_ai=True
        elif use_ai and self.openai_client and not self.gemini_client:
            try:
                openai_result = await self._analyze_openai(text)
                results["openai"] = float(openai_result["compound"])
                sources_used.append("openai")
                emotions = openai_result.get("emotions", {})
                topics = openai_result.get("topics", [])
                is_sarcastic = openai_result.get("is_sarcastic", False)
                logger.debug(f"OpenAI score: {openai_result['compound']}")
            except Exception as e:
                logger.error(f"OpenAI analysis failed: {e}")
        
        # 4. Combine results
        final_score = self._combine_scores(results)
        label = self._get_label(final_score)
        confidence = self._calculate_confidence(results, sources_used)
        
        # Calculate positive/negative/neutral from final score
        if final_score > 0:
            positive = (final_score + 1) / 2
            negative = 0.1
            neutral = 1 - positive - negative
        elif final_score < 0:
            negative = (abs(final_score) + 1) / 2
            positive = 0.1
            neutral = 1 - positive - negative
        else:
            positive = 0.2
            negative = 0.2
            neutral = 0.6
        
        return HybridSentimentResult(
            compound=round(final_score, 3),
            label=label,
            confidence=round(confidence, 3),
            positive=round(positive, 3),
            negative=round(negative, 3),
            neutral=round(neutral, 3),
            sources_used=sources_used,
            individual_scores={k: round(v, 3) for k, v in results.items()},
            emotions=emotions,
            topics=topics,
            is_sarcastic=is_sarcastic,
        )
    
    def _analyze_vader(self, text: str) -> Dict:
        """Run VADER analysis (synchronous, very fast)."""
        scores = self.vader.polarity_scores(text)
        return {
            "compound": scores["compound"],
            "positive": scores["pos"],
            "negative": scores["neg"],
            "neutral": scores["neu"],
        }
    
    async def _analyze_gemini(self, text: str) -> Dict:
        """Run Gemini analysis (primary AI)."""
        prompt = f"""Analyze the sentiment of this social media post about a product.

Post: "{text}"

Return ONLY valid JSON with no markdown formatting:
{{
    "sentiment_score": float from -1.0 to 1.0,
    "sentiment_label": "very_negative" | "negative" | "neutral" | "positive" | "very_positive",
    "confidence": float from 0.0 to 1.0,
    "positive_score": float 0-1,
    "negative_score": float 0-1,
    "neutral_score": float 0-1,
    "emotions": {{"joy": 0, "anger": 0, "fear": 0, "surprise": 0, "sadness": 0}},
    "topics": [],
    "is_sarcastic": false
}}"""

        # Run sync Gemini in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.gemini_client.generate_content(prompt)
        )
        
        result_text = response.text.strip()
        
        # Parse JSON (handle markdown code blocks)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        import json
        result = json.loads(result_text)
        
        return {
            "compound": result.get("sentiment_score", 0),
            "positive": result.get("positive_score", 0),
            "negative": result.get("negative_score", 0),
            "neutral": result.get("neutral_score", 0),
            "label": result.get("sentiment_label", "neutral"),
            "confidence": result.get("confidence", 0.5),
            "emotions": result.get("emotions", {}),
            "topics": result.get("topics", []),
            "is_sarcastic": result.get("is_sarcastic", False),
        }
    
    async def _analyze_openai(self, text: str) -> Dict:
        """Run OpenAI GPT-4o-mini analysis (fallback)."""
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

Consider context like sarcasm, irony, and cultural nuances."""

        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this: \"{text}\""}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON (handle markdown code blocks)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        import json
        result = json.loads(result_text)
        
        return {
            "compound": result.get("sentiment_score", 0),
            "positive": result.get("positive_score", 0),
            "negative": result.get("negative_score", 0),
            "neutral": result.get("neutral_score", 0),
            "label": result.get("sentiment_label", "neutral"),
            "confidence": result.get("confidence", 0.5),
            "emotions": result.get("emotions", {}),
            "topics": result.get("topics", []),
            "is_sarcastic": result.get("is_sarcastic", False),
        }
    
    def _combine_scores(self, results: Dict[str, float]) -> float:
        """
        Combine scores from multiple analyzers with weighted average.
        
        Weights:
        - Gemini: 0.5 (primary AI - fast and accurate)
        - OpenAI: 0.4 (fallback - excellent accuracy)
        - VADER: 0.3 (fast baseline, good for obvious sentiment)
        
        If AI analyzers agree and differ from VADER, trust AI more.
        """
        if not results:
            return 0.0
        
        weights = {
            "gemini": 0.5,  # Primary AI
            "openai": 0.4,  # Fallback AI
            "vader": 0.3,   # Baseline
        }
        
        total_weight = sum(weights.get(k, 0.1) for k in results.keys())
        weighted_sum = sum(
            score * weights.get(source, 0.1) 
            for source, score in results.items()
        )
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _get_label(self, compound: float) -> str:
        """Convert compound score to label."""
        if compound >= 0.5:
            return "very_positive"
        elif compound >= 0.1:
            return "positive"
        elif compound <= -0.5:
            return "very_negative"
        elif compound <= -0.1:
            return "negative"
        else:
            return "neutral"
    
    def _calculate_confidence(self, results: Dict[str, float], sources: List[str]) -> float:
        """
        Calculate confidence based on:
        - Number of sources agreeing
        - Strength of sentiment
        - Whether AI analyzers were used
        """
        if not results:
            return 0.0
        
        # Base confidence from number of sources
        source_confidence = min(len(sources) / 3, 1.0) * 0.4
        
        # Agreement bonus - if all scores are similar
        scores = list(results.values())
        if len(scores) > 1:
            spread = max(scores) - min(scores)
            agreement_confidence = max(0, (1 - spread)) * 0.3
        else:
            agreement_confidence = 0.15
        
        # Strength bonus - strong sentiment = higher confidence
        avg_score = sum(scores) / len(scores)
        strength_confidence = abs(avg_score) * 0.3
        
        # AI bonus - using Gemini/OpenAI increases confidence
        ai_used = "gemini" in sources or "openai" in sources
        ai_confidence = 0.2 if ai_used else 0.0
        
        return min(source_confidence + agreement_confidence + strength_confidence + ai_confidence, 1.0)
    
    async def analyze_batch(self, texts: List[str], use_ai: bool = True) -> List[HybridSentimentResult]:
        """Analyze multiple texts."""
        results = []
        for text in texts:
            result = await self.analyze(text, use_ai=use_ai)
            results.append(result)
        return results


# Singleton instance
hybrid_sentiment_analyzer = HybridSentimentAnalyzer()


