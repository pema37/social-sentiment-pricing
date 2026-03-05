"""
Hybrid Sentiment Analyzer - Combines VADER, Gemini, and OpenAI for robust sentiment analysis.
NOW WITH TRUST SCORING INTEGRATION.

Strategy:
1. VADER runs always (instant, free baseline)
2. Gemini runs if API key configured (primary AI - fast and cost-effective)
3. OpenAI runs as fallback if Gemini fails (backup for accuracy)
4. Trust scoring adjusts final weight based on author/content quality
5. Final score = weighted combination of available results × trust weight

RATE LIMIT HANDLING:
- Detects 429 errors from Gemini/OpenAI
- Raises RateLimitError for caller to handle
- Caller should fall back to VADER-only on rate limit

FIX (2026-02-19): Migrated from deprecated google.generativeai to google-genai SDK.
- Uses google.genai.Client with native async (client.aio.models.generate_content)
- Removed run_in_executor hack for sync-to-async bridging
- Model updated from gemini-2.0-flash-exp to gemini-2.0-flash
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Rate Limit Exception
# =============================================================================

class RateLimitError(Exception):
    """
    Raised when an API returns 429 Too Many Requests.
    
    The caller should catch this and:
    1. Record the rate limit with the circuit breaker
    2. Fall back to VADER-only analysis
    """
    def __init__(self, api_name: str, retry_after: int = 60, message: str = ""):
        self.api_name = api_name
        self.retry_after = retry_after
        super().__init__(message or f"{api_name} rate limited, retry after {retry_after}s")


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
    
    # NEW: Trust scoring fields
    trust_score: float = 1.0  # 0-1, author/content trust
    trust_level: str = "medium"  # verified, high, medium, low, untrusted
    trust_adjusted_compound: float = 0.0  # compound × trust_weight
    is_filtered: bool = False  # True if filtered as spam/bot
    risk_flags: List[str] = field(default_factory=list)  # Detected risks


@dataclass 
class TrustEnrichedMention:
    """A social mention with both sentiment and trust analysis."""
    mention_id: str
    content: str
    author_id: str
    source: str
    
    # Sentiment
    sentiment: HybridSentimentResult
    
    # Trust
    author_trust_score: float
    content_quality_score: float
    final_weight: float  # Combined weight for aggregation
    
    # Metadata
    published_at: Optional[datetime] = None
    follower_count: Optional[int] = None


class HybridSentimentAnalyzer:
    """
    Multi-source sentiment analyzer combining:
    - VADER (always runs - fast, free, good for social media)
    - Gemini (primary AI - fast, cost-effective via google-genai SDK)
    - OpenAI GPT-4o-mini (fallback if Gemini fails - better nuance/sarcasm)
    - Trust Scoring (filters bots/spam, weights by author credibility)
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
        
        # Gemini - primary AI (using google-genai SDK)
        self.gemini_client = None
        self.gemini_model = "gemini-2.0-flash"
        if getattr(settings, 'GEMINI_API_KEY', None):
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Gemini sentiment analyzer initialized (primary AI - google-genai SDK)")
            except ImportError:
                logger.warning("Google GenAI not installed - pip install google-genai")
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
        
        # NEW: Trust Scoring Service
        self.trust_service = None
        try:
            from services.trust_scoring import get_trust_scoring_service
            self.trust_service = get_trust_scoring_service()
            logger.info("Trust scoring service initialized")
        except ImportError:
            logger.warning("Trust scoring service not available")
        except Exception as e:
            logger.warning(f"Trust scoring initialization failed: {e}")
    
    def get_available_sources(self) -> List[str]:
        """Return list of available analyzers."""
        sources = []
        if self.vader:
            sources.append("vader")
        if self.gemini_client:
            sources.append("gemini")
        if self.openai_client:
            sources.append("openai")
        if self.trust_service:
            sources.append("trust_scoring")
        return sources
    
    async def analyze(
        self, 
        text: str, 
        use_ai: bool = True,
        # NEW: Trust scoring parameters
        author_id: Optional[str] = None,
        username: Optional[str] = None,
        source: str = "unknown",
        follower_count: Optional[int] = None,
        account_created_at: Optional[datetime] = None,
        apply_trust_scoring: bool = True,
    ) -> HybridSentimentResult:
        """
        Analyze text using all available analyzers.
        
        Args:
            text: The text to analyze
            use_ai: Whether to use Gemini/OpenAI (set False for VADER-only)
            author_id: Optional author ID for trust scoring
            username: Optional username for trust scoring
            source: Platform source (twitter, reddit, etc.)
            follower_count: Optional follower count for trust scoring
            account_created_at: Optional account creation date
            apply_trust_scoring: Whether to apply trust-based weighting
        
        Returns:
            HybridSentimentResult with combined scores and trust info
            
        Raises:
            RateLimitError: When Gemini or OpenAI returns 429.
        """
        results = {}
        sources_used = []
        emotions = {}
        topics = []
        is_sarcastic = False
        
        # Trust scoring variables
        trust_score = 1.0
        trust_level = "medium"
        risk_flags = []
        is_filtered = False
        content_quality = 1.0
        
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
            except RateLimitError:
                raise
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
                    except RateLimitError:
                        raise
                    except Exception as e2:
                        logger.error(f"OpenAI also failed: {e2}")
        
        elif use_ai and self.openai_client and not self.gemini_client:
            try:
                openai_result = await self._analyze_openai(text)
                results["openai"] = float(openai_result["compound"])
                sources_used.append("openai")
                emotions = openai_result.get("emotions", {})
                topics = openai_result.get("topics", [])
                is_sarcastic = openai_result.get("is_sarcastic", False)
                logger.debug(f"OpenAI score: {openai_result['compound']}")
            except RateLimitError:
                raise
            except Exception as e:
                logger.error(f"OpenAI analysis failed: {e}")
        
        # NEW: 4. Apply Trust Scoring
        if apply_trust_scoring and self.trust_service and author_id:
            try:
                # Score the author
                author_score = self.trust_service.score_author(
                    author_id=author_id,
                    username=username or author_id,
                    source=source,
                    follower_count=follower_count,
                    created_at=account_created_at,
                )
                trust_score = author_score.trust_score
                trust_level = author_score.trust_level.value
                risk_flags = [f.value for f in author_score.risk_flags]
                
                # Analyze content quality
                content_analysis = self.trust_service.analyze_content(
                    content_id=f"{author_id}_{hash(text)}",
                    text=text,
                    author_username=username,
                )
                content_quality = content_analysis.content_quality_score
                
                # Add content risk flags
                risk_flags.extend([f.value for f in content_analysis.risk_flags])
                
                # Check if should be filtered
                if trust_score < 0.1 or content_quality < 0.2:
                    is_filtered = True
                    logger.debug(f"Mention filtered: trust={trust_score}, quality={content_quality}")
                
                sources_used.append("trust_scoring")
                
            except Exception as e:
                logger.warning(f"Trust scoring failed: {e}")
        
        # 5. Combine results
        final_score = self._combine_scores(results)
        label = self._get_label(final_score)
        confidence = self._calculate_confidence(results, sources_used)
        
        # NEW: Calculate trust-adjusted compound
        # Combine author trust (60%) and content quality (40%)
        combined_trust = (trust_score * 0.6 + content_quality * 0.4)
        trust_adjusted_compound = final_score * combined_trust
        
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
            # NEW: Trust fields
            trust_score=round(trust_score, 3),
            trust_level=trust_level,
            trust_adjusted_compound=round(trust_adjusted_compound, 3),
            is_filtered=is_filtered,
            risk_flags=list(set(risk_flags)),  # Dedupe
        )
    
    async def analyze_with_trust(
        self,
        mentions: List[Dict[str, Any]],
        use_ai: bool = True,
        check_campaign: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze multiple mentions with full trust scoring.
        
        This is the recommended method for batch analysis with
        bot/manipulation detection.
        
        Args:
            mentions: List of mention dicts with keys:
                - content (or text)
                - author_id
                - username (optional)
                - source
                - follower_count (optional)
                - account_created_at (optional)
                - published_at (optional)
            use_ai: Whether to use AI analyzers
            check_campaign: Whether to check for coordinated campaigns
        
        Returns:
            Dict with:
                - mentions: List of analyzed mentions
                - raw_sentiment: Average raw sentiment
                - adjusted_sentiment: Trust-adjusted sentiment
                - filtered_count: Number of filtered mentions
                - campaign_detected: Whether campaign was detected
                - trust_breakdown: Count by trust level
        """
        analyzed_mentions = []
        trust_breakdown = {
            "verified": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "untrusted": 0,
            "blocked": 0,
        }
        
        raw_scores = []
        weighted_scores = []
        total_weight = 0.0
        filtered_count = 0
        
        for mention in mentions:
            content = mention.get("content") or mention.get("text", "")
            author_id = mention.get("author_id", "")
            username = mention.get("username") or mention.get("author", author_id)
            source = mention.get("source", "unknown")
            
            try:
                result = await self.analyze(
                    text=content,
                    use_ai=use_ai,
                    author_id=author_id,
                    username=username,
                    source=source,
                    follower_count=mention.get("follower_count") or mention.get("author_followers"),
                    account_created_at=mention.get("account_created_at"),
                    apply_trust_scoring=True,
                )
                
                raw_scores.append(result.compound)
                
                if result.is_filtered:
                    filtered_count += 1
                else:
                    # Calculate weight
                    weight = result.trust_score * 0.6 + (1 - len(result.risk_flags) * 0.1) * 0.4
                    weight = max(0.1, min(1.5, weight))
                    
                    weighted_scores.append(result.compound * weight)
                    total_weight += weight
                
                # Track trust levels
                if result.trust_level in trust_breakdown:
                    trust_breakdown[result.trust_level] += 1
                
                analyzed_mentions.append({
                    "mention_id": mention.get("mention_id") or mention.get("id"),
                    "content": content[:200],  # Truncate for response
                    "author_id": author_id,
                    "source": source,
                    "sentiment": {
                        "compound": result.compound,
                        "label": result.label,
                        "confidence": result.confidence,
                    },
                    "trust": {
                        "score": result.trust_score,
                        "level": result.trust_level,
                        "adjusted_compound": result.trust_adjusted_compound,
                        "is_filtered": result.is_filtered,
                        "risk_flags": result.risk_flags,
                    },
                })
                
            except Exception as e:
                logger.error(f"Error analyzing mention: {e}")
                continue
        
        # Calculate aggregates
        raw_sentiment = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
        adjusted_sentiment = sum(weighted_scores) / total_weight if total_weight > 0 else 0.0
        
        # Check for campaign if enabled
        campaign_detected = False
        if check_campaign and self.trust_service and len(mentions) >= 10:
            try:
                campaign_result = self.trust_service.detect_campaign(
                    mentions=mentions,
                    time_window_hours=24,
                )
                campaign_detected = campaign_result.is_campaign_detected
                
                if campaign_detected:
                    logger.warning(
                        f"Campaign detected: confidence={campaign_result.campaign_confidence:.2f}"
                    )
            except Exception as e:
                logger.warning(f"Campaign detection failed: {e}")
        
        return {
            "mentions": analyzed_mentions,
            "summary": {
                "total_analyzed": len(analyzed_mentions),
                "filtered_count": filtered_count,
                "raw_sentiment": round(raw_sentiment, 4),
                "adjusted_sentiment": round(adjusted_sentiment, 4),
                "sentiment_shift": round(adjusted_sentiment - raw_sentiment, 4),
                "campaign_detected": campaign_detected,
            },
            "trust_breakdown": trust_breakdown,
        }
    
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
        """
        Run Gemini analysis (primary AI) using google-genai SDK.
        Uses native async via client.aio.models.generate_content().
        
        Raises:
            RateLimitError: When Gemini returns 429 or quota exceeded.
        """
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

        try:
            response = await self.gemini_client.aio.models.generate_content(
                model=self.gemini_model,
                contents=prompt,
            )
            
            result_text = response.text.strip()
            
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
        except Exception as e:
            error_str = str(e).lower()
            if "429" in str(e) or "rate" in error_str or "quota" in error_str or "resource" in error_str:
                logger.warning(f"Gemini rate limit detected: {e}")
                raise RateLimitError("gemini", 60, str(e))
            raise
    
    async def _analyze_openai(self, text: str) -> Dict:
        """
        Run OpenAI GPT-4o-mini analysis (fallback).
        
        Raises:
            RateLimitError: When OpenAI returns 429.
        """
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

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze this: \"{text}\""}
                ],
                temperature=0.1,
                max_tokens=300,
                timeout=25.0,
            )
            
            result_text = response.choices[0].message.content.strip()
            
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
        except Exception as e:
            error_str = str(e).lower()
            if "429" in str(e) or "rate" in error_str or "too many" in error_str:
                retry_after = 60
                if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                    retry_after = int(e.response.headers.get('retry-after', 60))
                logger.warning(f"OpenAI rate limit detected: {e}")
                raise RateLimitError("openai", retry_after, str(e))
            raise
    
    def _combine_scores(self, results: Dict[str, float]) -> float:
        """
        Combine scores from multiple analyzers with weighted average.
        """
        if not results:
            return 0.0
        
        weights = {
            "gemini": 0.5,
            "openai": 0.4,
            "vader": 0.3,
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
        """Calculate confidence based on sources and agreement."""
        if not results:
            return 0.0
        
        source_confidence = min(len(sources) / 3, 1.0) * 0.4
        
        scores = list(results.values())
        if len(scores) > 1:
            spread = max(scores) - min(scores)
            agreement_confidence = max(0, (1 - spread)) * 0.3
        else:
            agreement_confidence = 0.15
        
        avg_score = sum(scores) / len(scores)
        strength_confidence = abs(avg_score) * 0.3
        
        ai_used = "gemini" in sources or "openai" in sources
        ai_confidence = 0.2 if ai_used else 0.0
        
        return min(source_confidence + agreement_confidence + strength_confidence + ai_confidence, 1.0)
    
    async def analyze_batch(
        self, 
        texts: List[str], 
        use_ai: bool = True,
        apply_trust_scoring: bool = False,
    ) -> List[HybridSentimentResult]:
        """Analyze multiple texts."""
        results = []
        for text in texts:
            result = await self.analyze(text, use_ai=use_ai, apply_trust_scoring=apply_trust_scoring)
            results.append(result)
        return results


# Singleton instance
hybrid_sentiment_analyzer = HybridSentimentAnalyzer()


