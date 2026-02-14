# backend/services/market_trends_service.py
"""
Market Trends service using Gemini (primary) + OpenAI (fallback) to analyze trending products.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, UTC

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


CATEGORIES = [
    {"id": "electronics", "name": "Electronics & Gadgets", "icon": "📱"},
    {"id": "fashion", "name": "Fashion & Apparel", "icon": "👕"},
    {"id": "beauty", "name": "Beauty & Skincare", "icon": "💄"},
    {"id": "home", "name": "Home & Kitchen", "icon": "🏠"},
    {"id": "fitness", "name": "Fitness & Sports", "icon": "💪"},
    {"id": "toys", "name": "Toys & Games", "icon": "🎮"},
    {"id": "pet", "name": "Pet Products", "icon": "🐕"},
    {"id": "food", "name": "Food & Beverages", "icon": "🍕"},
]

SOURCES = ["amazon", "walmart", "tiktok", "instagram", "google_trends"]


SYSTEM_PROMPT = """You are a market trend analyst for e-commerce. Analyze current trending products and provide insights.

You MUST respond with valid JSON only. No markdown, no explanations outside JSON.

Response format:
{
  "trends": [
    {
      "rank": 1,
      "name": "Product Name",
      "category": "electronics",
      "price_range": "$20-$50",
      "trend_score": 85,
      "sentiment": "positive",
      "source": "TikTok",
      "reason": "Brief reason why trending"
    }
  ],
  "ai_summary": "2-3 sentence market overview"
}

Rules:
- trend_score: 0-100 (100 = most trending)
- sentiment: "positive", "neutral", or "negative"
- source: Where the trend originated (Amazon, TikTok, Instagram, etc.)
- Be specific with product names (not generic)
- Include realistic price ranges
- Focus on products e-commerce sellers can actually sell"""


class MarketTrendsService:
    """AI-powered market trends analysis service with Gemini (primary) + OpenAI (fallback)."""
    
    def __init__(self):
        # Gemini (primary)
        self.gemini_client = None
        self.gemini_model_name = "gemini-2.0-flash-exp"
        self._using_new_api = False
        
        if GEMINI_AVAILABLE and getattr(settings, 'GEMINI_API_KEY', None):
            if GEMINI_NEW_API:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                self._using_new_api = True
                logger.info("Market Trends: Gemini client initialized (primary) - new API")
            else:
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_client = genai_legacy.GenerativeModel('gemini-pro')
                self.gemini_model_name = "gemini-pro"
                logger.info("Market Trends: Gemini client initialized (primary) - legacy API")
        
        # OpenAI (fallback)
        self.openai_client = None
        self.openai_model = "gpt-4o-mini"
        if OPENAI_AVAILABLE and settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != 'sk-xxxx':
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("Market Trends: OpenAI client initialized (fallback)")
        
        logger.info(f"Market Trends - Gemini: {self.gemini_client is not None}, OpenAI: {self.openai_client is not None}")
    
    def is_available(self) -> bool:
        """Check if any AI service is configured."""
        return self.gemini_client is not None or self.openai_client is not None
    
    def get_available_providers(self) -> List[str]:
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
    
    def _call_gemini_sync(self, prompt: str) -> str:
        """Call Gemini API (sync)."""
        full_prompt = f"{SYSTEM_PROMPT}\n\n---\n\n{prompt}"
        
        if self._using_new_api:
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model_name,
                contents=full_prompt
            )
            return response.text.strip()
        else:
            response = self.gemini_client.generate_content(full_prompt)
            return response.text.strip()
    
    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API with async wrapper."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_gemini_sync, prompt)
    
    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        response = await self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.7
        )
        return response.choices[0].message.content
    
    def _parse_json_response(self, content: str) -> dict:
        """Parse JSON from AI response, handling markdown code blocks."""
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())
    
    async def get_trends(
        self,
        category: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 10
    ) -> Dict:
        """Get trending products with AI analysis."""
        if not self.is_available():
            return self._fallback_trends(category, limit)
        
        # Build the prompt
        prompt = f"Generate {limit} trending e-commerce products"
        if category:
            cat_name = next((c["name"] for c in CATEGORIES if c["id"] == category), category)
            prompt += f" in the {cat_name} category"
        if source:
            prompt += f" trending on {source}"
        prompt += ". Focus on products that are actually trending right now in late 2024/2025."
        
        # Try Gemini first (primary)
        provider = "none"
        content = None
        
        if self.gemini_client:
            try:
                content = await self._call_gemini(prompt)
                provider = "gemini"
            except Exception as e:
                logger.warning(f"Market Trends: Gemini failed, trying OpenAI: {e}")
        
        # Fallback to OpenAI
        if content is None and self.openai_client:
            try:
                content = await self._call_openai(prompt)
                provider = "openai"
            except Exception as e:
                logger.error(f"Market Trends: OpenAI also failed: {e}")
                return self._fallback_trends(category, limit)
        
        if content is None:
            return self._fallback_trends(category, limit)
        
        # Parse JSON response
        try:
            data = self._parse_json_response(content)
            
            return {
                "trends": data.get("trends", [])[:limit],
                "ai_summary": data.get("ai_summary", "Market analysis complete."),
                "generated_at": datetime.now(UTC).isoformat(),
                "category": category,
                "source": source,
                "ai_provider": provider
            }
        except json.JSONDecodeError as e:
            logger.error(f"Market Trends: Failed to parse AI response: {e}")
            return self._fallback_trends(category, limit)
    
    def _fallback_trends(self, category: Optional[str], limit: int) -> Dict:
        """Return sample trends when AI is unavailable."""
        sample_trends = [
            {
                "rank": 1,
                "name": "Stanley Quencher Tumbler",
                "category": "home",
                "price_range": "$35-$50",
                "trend_score": 95,
                "sentiment": "positive",
                "source": "TikTok",
                "reason": "Viral on TikTok, celebrity endorsements"
            },
            {
                "rank": 2,
                "name": "Wireless Earbuds Pro",
                "category": "electronics",
                "price_range": "$25-$80",
                "trend_score": 88,
                "sentiment": "positive",
                "source": "Amazon",
                "reason": "High demand, great reviews, affordable alternative to AirPods"
            },
            {
                "rank": 3,
                "name": "LED Strip Lights",
                "category": "home",
                "price_range": "$15-$30",
                "trend_score": 82,
                "sentiment": "positive",
                "source": "TikTok",
                "reason": "Room makeover trends, affordable home decor"
            },
            {
                "rank": 4,
                "name": "Portable Blender",
                "category": "home",
                "price_range": "$20-$40",
                "trend_score": 79,
                "sentiment": "positive",
                "source": "Instagram",
                "reason": "Health & fitness trend, convenient for smoothies"
            },
            {
                "rank": 5,
                "name": "Oversized Hoodies",
                "category": "fashion",
                "price_range": "$30-$60",
                "trend_score": 76,
                "sentiment": "positive",
                "source": "Instagram",
                "reason": "Comfort fashion trend, streetwear influence"
            },
            {
                "rank": 6,
                "name": "Ring Light Kit",
                "category": "electronics",
                "price_range": "$20-$50",
                "trend_score": 73,
                "sentiment": "positive",
                "source": "Amazon",
                "reason": "Content creator demand, work from home essentials"
            },
            {
                "rank": 7,
                "name": "Skincare Fridge",
                "category": "beauty",
                "price_range": "$40-$80",
                "trend_score": 70,
                "sentiment": "positive",
                "source": "TikTok",
                "reason": "Skincare routine trend, aesthetic appeal"
            },
            {
                "rank": 8,
                "name": "Resistance Bands Set",
                "category": "fitness",
                "price_range": "$15-$35",
                "trend_score": 68,
                "sentiment": "positive",
                "source": "Amazon",
                "reason": "Home workout trend, affordable fitness"
            },
            {
                "rank": 9,
                "name": "Phone Camera Lens Kit",
                "category": "electronics",
                "price_range": "$20-$45",
                "trend_score": 65,
                "sentiment": "neutral",
                "source": "Instagram",
                "reason": "Mobile photography trend, content creation"
            },
            {
                "rank": 10,
                "name": "Reusable Water Bottle",
                "category": "fitness",
                "price_range": "$25-$45",
                "trend_score": 62,
                "sentiment": "positive",
                "source": "TikTok",
                "reason": "Sustainability trend, hydration awareness"
            }
        ]
        
        # Filter by category if specified
        if category:
            sample_trends = [t for t in sample_trends if t["category"] == category]
        
        # Re-rank after filtering
        for i, trend in enumerate(sample_trends[:limit], 1):
            trend["rank"] = i
        
        return {
            "trends": sample_trends[:limit],
            "ai_summary": "These are currently trending products based on social media activity and e-commerce data. Consider adding these to your store to capitalize on current demand.",
            "generated_at": datetime.now(UTC).isoformat(),
            "category": category,
            "source": None,
            "ai_provider": "fallback"
        }
    
    def get_categories(self) -> List[Dict]:
        """Return available categories."""
        return CATEGORIES
    
    def get_sources(self) -> List[str]:
        """Return available data sources."""
        return SOURCES
    
    def get_health(self) -> Dict:
        """Health check for the service."""
        return {
            "status": "healthy" if self.is_available() else "degraded",
            "service": "market_trends",
            "gemini_configured": self.gemini_client is not None,
            "openai_configured": self.openai_client is not None,
            "primary_provider": self._get_primary_provider(),
            "available_providers": self.get_available_providers(),
            "gemini_model": self.gemini_model_name if self.gemini_client else None,
            "openai_model": self.openai_model if self.openai_client else None,
            "categories_count": len(CATEGORIES),
            "sources_count": len(SOURCES)
        }


# Singleton instance
market_trends_service = MarketTrendsService()


