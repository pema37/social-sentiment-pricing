# backend/services/ai_support_service.py
"""
AI Support Chat service using OpenAI GPT-4o-mini.
"""

from typing import Dict, List, Optional
from openai import AsyncOpenAI
from core.config import settings


SYSTEM_PROMPT = """You are the AI Support Assistant for ActualPrice, an AI-powered pricing optimization platform for e-commerce merchants.

## About ActualPrice
ActualPrice helps Shopify and WooCommerce merchants optimize their product pricing using:
- **AI Sentiment Analysis**: Analyzes social media (Twitter, Reddit, TikTok) to understand customer perception
- **Competitor Price Intelligence**: Tracks competitor pricing in real-time
- **Smart Price Recommendations**: AI suggests optimal prices based on sentiment + competition + market trends
- **MNEE Payments**: Accept cryptocurrency payments via MNEE tokens (Ethereum ERC-20)

## Your Role
Help users with:
1. **Market Insights**: Sentiment analysis, what scores mean
2. **Analytics Support**: Dashboard data, trends, reports
3. **Payment Support**: MNEE payments, wallet connection, transactions
4. **Pricing Strategy**: Price recommendations, pricing rules
5. **Technical Help**: Connecting stores, adding products

## Guidelines
- Be friendly, professional, and concise
- Use bullet points for lists when helpful
- For billing issues, suggest support@getactualprice.com

## Key Features
- Sentiment scores: -1.0 (negative) to +1.0 (positive)
- Price recommendations include confidence scores and reasoning
- Products can be imported via CSV or Shopify/WooCommerce
- MNEE payments support Ethereum and BSV tokens"""


TOPIC_CONTEXT = {
    "market_insights": "Focus on sentiment analysis, social media monitoring, and market trends.",
    "analytics": "Focus on dashboard metrics, reports, charts, and data interpretation.",
    "payments": "Focus on MNEE tokens, wallet connection, Ethereum/BSV, and transactions.",
    "pricing": "Focus on price recommendations, pricing rules, competitor tracking.",
    "general": "Provide general platform help and guidance."
}

TOPIC_ACTIONS = {
    "market_insights": ["View Sentiment Dashboard", "Check Trending Products", "Analyze Competitor Sentiment"],
    "analytics": ["View Dashboard", "Export Report", "Set Up Alerts"],
    "payments": ["Connect Wallet", "View Transaction History", "Check MNEE Balance"],
    "pricing": ["View Price Recommendations", "Configure Pricing Rules", "Compare Competitor Prices"],
    "general": ["Explore Dashboard", "Add a Product", "Connect Your Store"]
}

TOPIC_SUGGESTIONS = [
    {"id": "market_insights", "label": "📊 Market Insights", "description": "Sentiment analysis & trends"},
    {"id": "analytics", "label": "📈 Analytics Help", "description": "Understanding your data"},
    {"id": "payments", "label": "💳 Payment Support", "description": "MNEE & transactions"},
    {"id": "pricing", "label": "💰 Pricing Strategy", "description": "Price recommendations"},
    {"id": "general", "label": "❓ General Help", "description": "Getting started & more"}
]

DEFAULT_GREETING = "Hi! 👋 I'm your ActualPrice AI assistant. How can I help you today?"

SUGGESTED_QUESTIONS = [
    "How does sentiment analysis work?",
    "How do I connect my Shopify store?",
    "What do the price recommendations mean?",
    "How do I accept MNEE payments?",
    "How is the confidence score calculated?"
]


class AISupportService:
    """AI-powered support chat service."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.model = "gpt-4o-mini"
    
    def is_available(self) -> bool:
        return self.client is not None
    
    async def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        topic: Optional[str] = None
    ) -> Dict:
        if not self.client:
            return self._fallback_response("I'm having trouble connecting. Please try again or contact support@getactualprice.com")
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if conversation_history:
            for msg in conversation_history[-20:]:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        messages.append({"role": "user", "content": message})
        
        if topic and topic in TOPIC_CONTEXT:
            messages.append({"role": "system", "content": f"Context: User selected '{topic}' topic. {TOPIC_CONTEXT[topic]}"})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            assistant_message = response.choices[0].message.content
            topic_detected = self._detect_topic(message + " " + (assistant_message or ""))
            suggested_actions = TOPIC_ACTIONS.get(topic_detected, TOPIC_ACTIONS["general"])
            
            return {
                "message": assistant_message,
                "topic_detected": topic_detected,
                "suggested_actions": suggested_actions
            }
        except Exception as e:
            print(f"AI Support error: {e}")
            return self._fallback_response("I apologize, but I'm having trouble right now. Please try again.")
    
    def _detect_topic(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["sentiment", "social", "twitter", "reddit", "trending"]):
            return "market_insights"
        elif any(w in text_lower for w in ["dashboard", "chart", "report", "analytics", "metric"]):
            return "analytics"
        elif any(w in text_lower for w in ["mnee", "payment", "wallet", "token", "ethereum", "crypto"]):
            return "payments"
        elif any(w in text_lower for w in ["price", "pricing", "recommend", "competitor"]):
            return "pricing"
        return "general"
    
    def _fallback_response(self, message: str) -> Dict:
        return {"message": message, "topic_detected": "general", "suggested_actions": ["Try again", "Contact support"]}
    
    def get_topics(self) -> Dict:
        return {"topics": TOPIC_SUGGESTIONS, "default_greeting": DEFAULT_GREETING, "suggested_questions": SUGGESTED_QUESTIONS}
    
    def get_health(self) -> Dict:
        return {
            "status": "healthy" if self.is_available() else "degraded",
            "service": "ai_support",
            "openai_configured": self.is_available(),
            "model": self.model,
            "features": ["contextual_responses", "conversation_history", "topic_detection", "suggested_actions"]
        }


# Singleton instance
ai_support_service = AISupportService()

