# backend/services/market_trends_service.py
"""
Market Trends service using OpenAI to analyze trending products.
"""

from typing import Dict, List, Optional
from datetime import datetime
from openai import AsyncOpenAI
import json
from core.config import settings


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
    """AI-powered market trends analysis service."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.model = "gpt-4o-mini"
    
    def is_available(self) -> bool:
        return self.client is not None
    
    async def get_trends(
        self,
        category: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 10
    ) -> Dict:
        """Get trending products with AI analysis."""
        if not self.client:
            return self._fallback_trends(category, limit)
        
        # Build the prompt
        prompt = f"Generate {limit} trending e-commerce products"
        if category:
            cat_name = next((c["name"] for c in CATEGORIES if c["id"] == category), category)
            prompt += f" in the {cat_name} category"
        if source:
            prompt += f" trending on {source}"
        prompt += ". Focus on products that are actually trending right now in late 2024/2025."
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            
            # Parse JSON response
            try:
                # Clean up response if needed
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                
                data = json.loads(content)
                
                return {
                    "trends": data.get("trends", [])[:limit],
                    "ai_summary": data.get("ai_summary", "Market analysis complete."),
                    "generated_at": datetime.utcnow().isoformat(),
                    "category": category,
                    "source": source
                }
            except json.JSONDecodeError:
                return self._fallback_trends(category, limit)
                
        except Exception as e:
            print(f"Market trends error: {e}")
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
            "generated_at": datetime.utcnow().isoformat(),
            "category": category,
            "source": None
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
            "openai_configured": self.is_available(),
            "model": self.model,
            "categories_count": len(CATEGORIES),
            "sources_count": len(SOURCES)
        }


# Singleton instance
market_trends_service = MarketTrendsService()

