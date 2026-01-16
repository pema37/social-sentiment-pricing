"""
AI Client wrappers for OpenAI and Gemini.
"""

import json
from typing import Optional

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class AIClients:
    """Manages AI client connections for OpenAI and Gemini."""
    
    def __init__(self):
        self._openai_client = None
        self._gemini_client = None
    
    @property
    def openai_client(self):
        """Lazy-load OpenAI client."""
        if self._openai_client is None:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
        return self._openai_client
    
    @property
    def gemini_client(self):
        """Lazy-load Gemini client."""
        if self._gemini_client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self._gemini_client = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("Gemini client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
        return self._gemini_client
    
    async def call_openai(self, system_prompt: str, user_prompt: str) -> dict:
        """Call OpenAI API and return parsed JSON response."""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=4000,
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return self._get_fallback_response()
    
    async def call_gemini(self, system_prompt: str, user_prompt: str) -> dict:
        """Call Gemini API and return parsed JSON response."""
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self.gemini_client.generate_content(full_prompt)
            
            text = response.text
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            return json.loads(text.strip())
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            return self._get_fallback_response()
    
    async def call(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        use_model: str = "openai"
    ) -> tuple[dict, str]:
        """
        Call the specified AI model.
        
        Returns:
            Tuple of (response_dict, model_used)
        """
        if use_model == "gemini" and self.gemini_client:
            return await self.call_gemini(system_prompt, user_prompt), "gemini"
        else:
            return await self.call_openai(system_prompt, user_prompt), "openai"
    
    def _get_fallback_response(self) -> dict:
        """Return a safe fallback response when AI fails."""
        return {
            "market_sentiment": "stable",
            "market_sentiment_score": 0,
            "predictions": [],
            "opportunities": [],
            "risks": [],
            "executive_summary": "Unable to generate AI analysis at this time. Please try again later.",
            "recommended_actions": ["Review your data manually", "Ensure sentiment collection is running"],
            "key_insights": ["AI analysis temporarily unavailable"],
        }


# Singleton instance
ai_clients = AIClients()



