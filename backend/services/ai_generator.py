# backend/services/ai_generator.py
"""
AI Content Generation Service
=============================
Uses OpenAI GPT-4o-mini with Google Gemini fallback.
"""

import json
import logging
from typing import Dict, Optional, List

from openai import AsyncOpenAI
from core.config import settings

logger = logging.getLogger(__name__)

# Try to import new Google GenAI
GEMINI_AVAILABLE = False

try:
    from google import genai
    GEMINI_AVAILABLE = True
    GEMINI_NEW_API = True
except ImportError:
    GEMINI_NEW_API = False
    try:
        import google.generativeai as genai_legacy
        GEMINI_AVAILABLE = True
        logger.info("Using legacy google.generativeai package")
    except ImportError:
        logger.warning("Google GenAI not installed. Gemini fallback unavailable.")


class AIGeneratorService:
    """AI-powered content generation with OpenAI + Gemini fallback."""
    
    def __init__(self):
        # OpenAI (primary)
        self.openai_client = None
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != 'sk-xxxx':
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info(f"OpenAI client initialized: {self.openai_client is not None}")
        logger.info(f"API key starts with: {settings.OPENAI_API_KEY[:10] if settings.OPENAI_API_KEY else 'None'}...")
        
        # Gemini (fallback)
        self.gemini_client = None
        self.gemini_model_name = "gemini-2.0-flash-exp"
        self._using_new_api = False
        
        if GEMINI_AVAILABLE and getattr(settings, 'GEMINI_API_KEY', None):
            if GEMINI_NEW_API:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                self._using_new_api = True
            else:
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_client = genai_legacy.GenerativeModel('gemini-pro')
                self.gemini_model_name = "gemini-pro"
        
        self.model = "gpt-4o-mini"
    
    def is_available(self) -> bool:
        """Check if any AI service is configured."""
        return self.openai_client is not None or self.gemini_client is not None
    
    def _get_provider(self) -> str:
        """Return which provider is being used."""
        if self.openai_client:
            return "openai"
        elif self.gemini_client:
            return "gemini"
        return "none"
    
    async def _call_openai(self, system_prompt: str, user_message: str, temperature: float = 0.7, max_tokens: int = 800) -> str:
        """Call OpenAI API."""
        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    
    def _call_gemini_sync(self, system_prompt: str, user_message: str) -> str:
        """Call Gemini API (sync)."""
        full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"
        
        if self._using_new_api:
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model_name,
                contents=full_prompt
            )
            return response.text.strip()
        else:
            response = self.gemini_client.generate_content(full_prompt)
            return response.text.strip()
    
    async def _call_gemini(self, system_prompt: str, user_message: str) -> str:
        """Call Gemini API with async wrapper."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_gemini_sync, system_prompt, user_message)
    
    async def _generate(self, system_prompt: str, user_message: str, temperature: float = 0.7, max_tokens: int = 800) -> tuple:
        """
        Generate text using OpenAI with Gemini fallback.
        Returns (response_text, provider_used)
        """
        # Try OpenAI first
        if self.openai_client:
            try:
                result = await self._call_openai(system_prompt, user_message, temperature, max_tokens)
                return result, "openai"
            except Exception as e:
                logger.warning(f"OpenAI failed, trying Gemini: {e}")
        
        # Fallback to Gemini
        if self.gemini_client:
            try:
                result = await self._call_gemini(system_prompt, user_message)
                return result, "gemini"
            except Exception as e:
                logger.error(f"Gemini also failed: {e}")
                raise ValueError(f"All AI services failed: {e}")
        
        raise ValueError("No AI service available")
    
    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from AI response, handling markdown code blocks."""
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    
    async def generate_product_description(
        self,
        name: str,
        category: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        current_description: Optional[str] = None,
        tone: str = "professional",
        length: str = "medium",
    ) -> Dict:
        """Generate SEO-optimized product description."""
        if not self.is_available():
            raise ValueError("No AI API key configured (OpenAI or Gemini)")
        
        length_words = {"short": 50, "medium": 100, "long": 200}.get(length, 100)
        
        system_prompt = f"""You are an expert e-commerce copywriter specializing in SEO-optimized product descriptions.

Write in a {tone} tone.
Target length: approximately {length_words} words for the main description.

Return ONLY valid JSON with these exact fields:
{{
    "description": "The main product description (HTML allowed: <p>, <ul>, <li>, <strong>)",
    "seo_title": "SEO-optimized title (max 60 characters)",
    "meta_description": "Meta description for search engines (max 160 characters)",
    "suggested_keywords": ["keyword1", "keyword2", "keyword3"]
}}

Focus on benefits over features, emotional connection, natural keyword integration."""

        user_message = f"Generate a product description for:\n\nProduct Name: {name}"
        if category:
            user_message += f"\nCategory: {category}"
        if keywords:
            user_message += f"\nKeywords to include: {', '.join(keywords)}"
        if current_description:
            user_message += f"\n\nCurrent description (improve this):\n{current_description}"
        
        try:
            result_text, provider = await self._generate(system_prompt, user_message)
            result = self._parse_json_response(result_text)
            
            return {
                "description": result.get("description", ""),
                "seo_title": result.get("seo_title", name)[:60],
                "meta_description": result.get("meta_description", "")[:160],
                "suggested_keywords": result.get("suggested_keywords", [])[:10],
                "ai_generated": True,
                "ai_provider": provider
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            raise ValueError("Failed to generate description")
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            raise ValueError(f"AI generation failed: {str(e)}")
    
    async def generate_pricing_explanation(
        self,
        product_name: str,
        current_price: float,
        suggested_price: float,
        sentiment_score: Optional[float] = None,
        competitor_prices: Optional[List[float]] = None,
        factors: Optional[List[str]] = None,
    ) -> Dict:
        """Generate human-readable explanation for a price recommendation."""
        if not self.is_available():
            return self._fallback_pricing_explanation(product_name, current_price, suggested_price, factors)
        
        price_change = suggested_price - current_price
        direction = "increase" if price_change > 0 else "decrease" if price_change < 0 else "maintain"
        
        system_prompt = """You are a pricing strategy expert explaining price recommendations to e-commerce merchants.

Return ONLY valid JSON:
{
    "explanation": "2-3 sentence explanation of why this price is recommended",
    "key_factors": ["factor1", "factor2", "factor3"],
    "confidence_reason": "Why we're confident in this recommendation"
}

Be specific, data-driven, and actionable."""

        user_message = f"""Explain this price recommendation:

Product: {product_name}
Current Price: ${current_price:.2f}
Suggested Price: ${suggested_price:.2f}
Change: {direction} by ${abs(price_change):.2f}"""

        if sentiment_score is not None:
            sentiment_label = "positive" if sentiment_score > 0.2 else "negative" if sentiment_score < -0.2 else "neutral"
            user_message += f"\nSocial Sentiment: {sentiment_label} ({sentiment_score:.2f})"
        if competitor_prices:
            avg_competitor = sum(competitor_prices) / len(competitor_prices)
            user_message += f"\nCompetitor Average: ${avg_competitor:.2f}"
        if factors:
            user_message += f"\nFactors considered: {', '.join(factors)}"
        
        try:
            result_text, provider = await self._generate(system_prompt, user_message, temperature=0.5, max_tokens=300)
            result = self._parse_json_response(result_text)
            
            return {
                "explanation": result.get("explanation", ""),
                "key_factors": result.get("key_factors", []),
                "confidence_reason": result.get("confidence_reason", ""),
                "ai_generated": True,
                "ai_provider": provider
            }
        except Exception as e:
            logger.warning(f"AI pricing explanation failed: {e}")
            return self._fallback_pricing_explanation(product_name, current_price, suggested_price, factors)
    
    def _fallback_pricing_explanation(self, product_name: str, current_price: float, suggested_price: float, factors: Optional[List[str]]) -> Dict:
        """Fallback when AI is unavailable."""
        price_change = suggested_price - current_price
        return {
            "explanation": f"Based on current market conditions, we recommend {'raising' if price_change > 0 else 'lowering'} the price to ${suggested_price:.2f}.",
            "key_factors": factors or ["Market analysis", "Sentiment data"],
            "confidence_reason": "Based on available data",
            "ai_generated": False,
            "ai_provider": "none"
        }


# Singleton instance
ai_generator = AIGeneratorService()

