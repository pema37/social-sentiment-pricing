# backend/services/ai_generator.py
"""
AI Content Generation Service
=============================
Uses Google Gemini (primary) with OpenAI GPT-4o-mini fallback.
"""

import asyncio
import base64
import json
import logging
from collections.abc import AsyncGenerator

from core.config import settings

logger = logging.getLogger(__name__)

# Try to import Google GenAI (primary)
GEMINI_AVAILABLE = False
GEMINI_NEW_API = False

try:
    from google import genai

    GEMINI_AVAILABLE = True
    GEMINI_NEW_API = True
except ImportError:
    try:
        import google.generativeai as genai_legacy

        GEMINI_AVAILABLE = True
        logger.info("Using legacy google.generativeai package")
    except ImportError:
        logger.warning("Google GenAI not installed. Gemini unavailable.")

# Try to import OpenAI (fallback)
OPENAI_AVAILABLE = False
try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    logger.warning("OpenAI not installed. OpenAI fallback unavailable.")


class AIGeneratorService:
    """AI-powered content generation with Gemini (primary) + OpenAI (fallback)."""

    def __init__(self):
        # Gemini (primary)
        self.gemini_client = None
        self.gemini_model_name = "gemini-2.0-flash-exp"
        self._using_new_api = False

        if GEMINI_AVAILABLE and getattr(settings, "GEMINI_API_KEY", None):
            if GEMINI_NEW_API:
                from google import genai

                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                self._using_new_api = True
                logger.info("Gemini client initialized (primary) - new API")
            else:
                import google.generativeai as genai_legacy

                genai_legacy.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_client = genai_legacy.GenerativeModel("gemini-pro")
                self.gemini_model_name = "gemini-pro"
                logger.info("Gemini client initialized (primary) - legacy API")

        # OpenAI (fallback)
        self.openai_client = None
        self.openai_model = "gpt-4o-mini"
        if OPENAI_AVAILABLE and settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "sk-xxxx":
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized (fallback)")

        logger.info(
            f"AI Generator - Gemini: {self.gemini_client is not None}, OpenAI: {self.openai_client is not None}"
        )

    def is_available(self) -> bool:
        """Check if any AI service is configured."""
        return self.gemini_client is not None or self.openai_client is not None

    def get_available_providers(self) -> list[str]:
        """Return list of available providers."""
        providers = []
        if self.gemini_client:
            providers.append("gemini")
        if self.openai_client:
            providers.append("openai")
        return providers

    def _get_primary_provider(self) -> str:
        """Return which provider will be tried first."""
        if self.gemini_client:
            return "gemini"
        elif self.openai_client:
            return "openai"
        return "none"

    def _call_gemini_sync(self, system_prompt: str, user_message: str) -> str:
        """Call Gemini API (sync)."""
        full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"

        if self._using_new_api:
            response = self.gemini_client.models.generate_content(model=self.gemini_model_name, contents=full_prompt)
            return response.text.strip()
        else:
            response = self.gemini_client.generate_content(full_prompt)
            return response.text.strip()

    async def _call_gemini(self, system_prompt: str, user_message: str) -> str:
        """Call Gemini API with async wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_gemini_sync, system_prompt, user_message)

    async def _call_openai(
        self, system_prompt: str, user_message: str, temperature: float = 0.7, max_tokens: int = 800
    ) -> str:
        """Call OpenAI API."""
        response = await self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    async def _generate(
        self, system_prompt: str, user_message: str, temperature: float = 0.7, max_tokens: int = 800
    ) -> tuple:
        """
        Generate text using Gemini (primary) with OpenAI fallback.
        Returns (response_text, provider_used)
        """
        # Try Gemini first (primary)
        if self.gemini_client:
            try:
                result = await self._call_gemini(system_prompt, user_message)
                return result, "gemini"
            except Exception as e:
                logger.warning(f"Gemini failed, trying OpenAI: {e}")

        # Fallback to OpenAI
        if self.openai_client:
            try:
                result = await self._call_openai(system_prompt, user_message, temperature, max_tokens)
                return result, "openai"
            except Exception as e:
                logger.error(f"OpenAI also failed: {e}")
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
        category: str | None = None,
        keywords: list[str] | None = None,
        current_description: str | None = None,
        tone: str = "professional",
        length: str = "medium",
    ) -> dict:
        """Generate SEO-optimized product description."""
        if not self.is_available():
            raise ValueError("No AI API key configured (Gemini or OpenAI)")

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
                "ai_provider": provider,
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            raise ValueError("Failed to generate description")
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            raise ValueError(f"AI generation failed: {e!s}")

    async def generate_pricing_explanation(
        self,
        product_name: str,
        current_price: float,
        suggested_price: float,
        sentiment_score: float | None = None,
        competitor_prices: list[float] | None = None,
        factors: list[str] | None = None,
    ) -> dict:
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
            sentiment_label = (
                "positive" if sentiment_score > 0.2 else "negative" if sentiment_score < -0.2 else "neutral"
            )
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
                "ai_provider": provider,
            }
        except Exception as e:
            logger.warning(f"AI pricing explanation failed: {e}")
            return self._fallback_pricing_explanation(product_name, current_price, suggested_price, factors)

    def _fallback_pricing_explanation(
        self, product_name: str, current_price: float, suggested_price: float, factors: list[str] | None
    ) -> dict:
        """Fallback when AI is unavailable."""
        price_change = suggested_price - current_price
        return {
            "explanation": f"Based on current market conditions, we recommend {'raising' if price_change > 0 else 'lowering'} the price to ${suggested_price:.2f}.",
            "key_factors": factors or ["Market analysis", "Sentiment data"],
            "confidence_reason": "Based on available data",
            "ai_generated": False,
            "ai_provider": "none",
        }

    async def stream_content(
        self,
        prompt: str,
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream text content from Gemini. Central entry point for streaming AI calls."""
        if not self.gemini_client or not self._using_new_api:
            logger.warning("Gemini streaming not available (client not configured or legacy API)")
            return

        model = model or self.gemini_model_name

        try:
            response = self.gemini_client.models.generate_content_stream(
                model=model,
                contents=prompt,
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini streaming failed: {e}")

    async def stream_image_analysis(
        self,
        image_data: bytes,
        image_type: str,
        prompt: str,
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream image analysis from Gemini. Central entry point for multimodal streaming."""
        if not self.gemini_client or not self._using_new_api:
            logger.warning("Gemini image streaming not available")
            return

        model = model or self.gemini_model_name
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        contents = [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": f"image/{image_type}",
                            "data": image_base64,
                        }
                    },
                ]
            }
        ]

        try:
            response = self.gemini_client.models.generate_content_stream(
                model=model,
                contents=contents,
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini image streaming failed: {e}")

    def get_health(self) -> dict:
        """Health check for the service."""
        return {
            "status": "healthy" if self.is_available() else "degraded",
            "service": "ai_generator",
            "gemini_configured": self.gemini_client is not None,
            "openai_configured": self.openai_client is not None,
            "primary_provider": self._get_primary_provider(),
            "available_providers": self.get_available_providers(),
            "gemini_model": self.gemini_model_name if self.gemini_client else None,
            "openai_model": self.openai_model if self.openai_client else None,
        }


# Singleton instance
ai_generator = AIGeneratorService()
