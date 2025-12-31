# backend/services/ai_support_service.py
"""
AI Support Chat service with OpenAI + Google Gemini fallback.
"""

import logging
from typing import Dict, List, Optional

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
    """AI-powered support chat service with OpenAI + Gemini fallback."""
    
    def __init__(self):
        # OpenAI (primary)
        self.openai_client = None
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != 'sk-xxxx':
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
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
        """Return which provider is active."""
        if self.openai_client:
            return "openai"
        elif self.gemini_client:
            return "gemini"
        return "none"
    
    async def _call_openai(self, messages: List[Dict]) -> str:
        """Call OpenAI API."""
        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        return response.choices[0].message.content
    
    def _call_gemini_sync(self, messages: List[Dict]) -> str:
        """Call Gemini API (sync) - convert chat format to single prompt."""
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"Instructions: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"User: {content}")
        
        full_prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"
        
        if self._using_new_api:
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model_name,
                contents=full_prompt
            )
            return response.text
        else:
            response = self.gemini_client.generate_content(full_prompt)
            return response.text
    
    async def _call_gemini(self, messages: List[Dict]) -> str:
        """Call Gemini API with async wrapper."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_gemini_sync, messages)
    
    async def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        topic: Optional[str] = None
    ) -> Dict:
        """
        Send a message and get AI response.
        Tries OpenAI first, falls back to Gemini if needed.
        """
        if not self.is_available():
            return self._fallback_response("I'm having trouble connecting. Please try again or contact support@getactualprice.com")
        
        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if conversation_history:
            for msg in conversation_history[-20:]:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        messages.append({"role": "user", "content": message})
        
        if topic and topic in TOPIC_CONTEXT:
            messages.append({"role": "system", "content": f"Context: User selected '{topic}' topic. {TOPIC_CONTEXT[topic]}"})
        
        # Try OpenAI first, then Gemini
        provider = "none"
        assistant_message = None
        
        if self.openai_client:
            try:
                assistant_message = await self._call_openai(messages)
                provider = "openai"
            except Exception as e:
                logger.warning(f"OpenAI failed, trying Gemini: {e}")
        
        if assistant_message is None and self.gemini_client:
            try:
                assistant_message = await self._call_gemini(messages)
                provider = "gemini"
            except Exception as e:
                logger.error(f"Gemini also failed: {e}")
                return self._fallback_response("I apologize, but I'm having trouble right now. Please try again.")
        
        if assistant_message is None:
            return self._fallback_response("I apologize, but I'm having trouble right now. Please try again.")
        
        # Detect topic and get suggested actions
        topic_detected = self._detect_topic(message + " " + (assistant_message or ""))
        suggested_actions = TOPIC_ACTIONS.get(topic_detected, TOPIC_ACTIONS["general"])
        
        return {
            "message": assistant_message,
            "topic_detected": topic_detected,
            "suggested_actions": suggested_actions,
            "ai_provider": provider
        }
    
    def _detect_topic(self, text: str) -> str:
        """Detect topic from message content."""
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
        """Return fallback response when AI is unavailable."""
        return {
            "message": message,
            "topic_detected": "general",
            "suggested_actions": ["Try again", "Contact support"],
            "ai_provider": "none"
        }
    
    def get_topics(self) -> Dict:
        """Get available support topics."""
        return {
            "topics": TOPIC_SUGGESTIONS,
            "default_greeting": DEFAULT_GREETING,
            "suggested_questions": SUGGESTED_QUESTIONS
        }
    
    def get_health(self) -> Dict:
        """Check service health status."""
        return {
            "status": "healthy" if self.is_available() else "degraded",
            "service": "ai_support",
            "openai_configured": self.openai_client is not None,
            "gemini_configured": self.gemini_client is not None,
            "active_provider": self._get_provider(),
            "model": self.model,
            "features": [
                "contextual_responses",
                "conversation_history",
                "topic_detection",
                "suggested_actions",
                "gemini_fallback"
            ]
        }


# Singleton instance
ai_support_service = AISupportService()

