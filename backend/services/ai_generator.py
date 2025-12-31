# backend/services/ai_generator.py
"""
AI Content Generation Service
=============================
Uses OpenAI GPT-4o-mini to generate product content.
"""

import json
from typing import Dict, Optional, List

from openai import AsyncOpenAI
from core.config import settings


class AIGeneratorService:
    """AI-powered content generation for products."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.model = "gpt-4o-mini"
    
    def is_available(self) -> bool:
        """Check if OpenAI is configured."""
        return self.client is not None
    
    async def generate_product_description(
        self,
        name: str,
        category: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        current_description: Optional[str] = None,
        tone: str = "professional",
        length: str = "medium",
    ) -> Dict:
        """
        Generate SEO-optimized product description.
        
        Args:
            name: Product name
            category: Product category
            keywords: Keywords for SEO
            current_description: Existing description to improve
            tone: "professional", "casual", "luxury", "technical"
            length: "short" (50 words), "medium" (100 words), "long" (200 words)
        
        Returns:
            {
                "description": str,
                "seo_title": str,
                "meta_description": str,
                "suggested_keywords": list
            }
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
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

Focus on:
- Benefits over features
- Emotional connection with buyers
- Natural keyword integration
- Clear call-to-action
- Scannable formatting"""

        user_message = f"Generate a product description for:\n\nProduct Name: {name}"
        
        if category:
            user_message += f"\nCategory: {category}"
        
        if keywords:
            user_message += f"\nKeywords to include: {', '.join(keywords)}"
        
        if current_description:
            user_message += f"\n\nCurrent description (improve this):\n{current_description}"
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Handle markdown code blocks
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            
            return {
                "description": result.get("description", ""),
                "seo_title": result.get("seo_title", name)[:60],
                "meta_description": result.get("meta_description", "")[:160],
                "suggested_keywords": result.get("suggested_keywords", [])[:10],
                "ai_generated": True
            }
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse OpenAI response: {e}")
            raise ValueError("Failed to generate description")
        except Exception as e:
            print(f"OpenAI API error: {e}")
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
        """
        Generate human-readable explanation for a price recommendation.
        
        Returns:
            {
                "explanation": str,
                "key_factors": list,
                "confidence_reason": str
            }
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.5,
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            
            return {
                "explanation": result.get("explanation", ""),
                "key_factors": result.get("key_factors", []),
                "confidence_reason": result.get("confidence_reason", ""),
                "ai_generated": True
            }
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            # Return a basic explanation
            return {
                "explanation": f"Based on current market conditions, we recommend {'raising' if price_change > 0 else 'lowering'} the price to ${suggested_price:.2f}.",
                "key_factors": factors or ["Market analysis", "Sentiment data"],
                "confidence_reason": "Based on available data",
                "ai_generated": False
            }


# Singleton instance
ai_generator = AIGeneratorService()

