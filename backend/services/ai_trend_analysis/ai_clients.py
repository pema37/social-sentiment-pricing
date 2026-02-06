"""
AI Client wrappers for OpenAI and Gemini.

Supports:
- OpenAI GPT-4o-mini (existing)
- Gemini 1.5 Flash (existing, deprecated SDK)
- Gemini 3 Flash/Pro (NEW - multimodal, streaming, thought signatures, thinking levels)
"""

import json
import base64
from typing import Optional, AsyncGenerator, Literal
from dataclasses import dataclass
from enum import Enum

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Gemini 3 model constants
# ---------------------------------------------------------------------------
GEMINI3_FLASH = "gemini-3-flash-preview"
GEMINI3_PRO = "gemini-3-pro-preview"
DEFAULT_MODEL = GEMINI3_FLASH  # Fast streaming for demos


class ThoughtType(str, Enum):
    """Types of AI reasoning steps (thought signatures)."""
    OBSERVATION = "observation"
    ANALYSIS = "analysis"
    HYPOTHESIS = "hypothesis"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"


@dataclass
class StreamChunk:
    """A chunk of streamed AI response."""
    text: str
    thought_type: Optional[ThoughtType] = None
    is_final: bool = False
    is_thought: bool = False  # True if this came from Gemini 3 thinking


@dataclass
class ImageAnalysisResult:
    """Result from analyzing a product screenshot."""
    product_name: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    features: list[str] = None
    reviews_summary: Optional[str] = None
    promo_signals: list[str] = None
    confidence: float = 0.0
    raw_text: str = ""

    def __post_init__(self):
        if self.features is None:
            self.features = []
        if self.promo_signals is None:
            self.promo_signals = []


class AIClients:
    """Manages AI client connections for OpenAI and Gemini."""

    def __init__(self):
        self._openai_client = None
        self._gemini_client = None    # Old SDK (deprecated)
        self._gemini3_client = None   # New SDK

    # ------------------------------------------------------------------
    # Client properties (lazy-loaded)
    # ------------------------------------------------------------------

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
        """Lazy-load Gemini client (old SDK - for backward compatibility)."""
        if self._gemini_client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self._gemini_client = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("Gemini client initialized (legacy SDK)")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
        return self._gemini_client

    @property
    def gemini3_client(self):
        """Lazy-load Gemini 3 client (new SDK with streaming + multimodal)."""
        if self._gemini3_client is None:
            try:
                from google import genai
                self._gemini3_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Gemini 3 client initialized (new SDK)")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini 3 client: {e}")
        return self._gemini3_client

    # ------------------------------------------------------------------
    # Thinking-level config builder (Gemini 3 feature)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_thinking_config(
        thinking_level: str = "low",
    ) -> dict:
        """
        Build Gemini 3 GenerateContentConfig with thinking level.

        Levels:
          - "minimal" : fastest, almost no internal reasoning
          - "low"     : light reasoning, ideal for streaming demos
          - "high"    : deep reasoning (default for Pro), best quality
        """
        try:
            from google.genai import types
            return types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_level=thinking_level,
                ),
            )
        except ImportError:
            logger.warning("google.genai.types not available; skipping thinking config")
            return {}

    # ------------------------------------------------------------------
    # EXISTING METHODS (unchanged for backward compatibility)
    # ------------------------------------------------------------------

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
        """Call Gemini API and return parsed JSON response (legacy method)."""
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self.gemini_client.generate_content(full_prompt)

            text = response.text
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
        use_model: str = "openai",
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

    # ------------------------------------------------------------------
    # THOUGHT SIGNATURE DETECTION
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_thought_from_chunk(chunk) -> Optional[bool]:
        """
        Try to extract native Gemini 3 thought indicator from a chunk.

        Gemini 3 responses can include thought parts where
        ``part.thought == True``. Returns True/False/None.
        """
        try:
            for candidate in getattr(chunk, "candidates", []):
                for part in getattr(candidate.content, "parts", []):
                    if getattr(part, "thought", False):
                        return True
            return False
        except Exception:
            return None

    @staticmethod
    def _detect_thought_type(text: str) -> Optional[ThoughtType]:
        """
        Keyword-based fallback for thought type detection.

        Used when native thought signatures aren't available or to
        classify the *kind* of thought (observation vs. analysis, etc.)
        which Gemini 3's boolean ``thought`` flag doesn't distinguish.
        """
        text_lower = text.lower()

        if any(w in text_lower for w in ["i see", "looking at", "observing", "notice", "scanning"]):
            return ThoughtType.OBSERVATION
        elif any(w in text_lower for w in ["analyzing", "comparing", "examining", "this means", "evaluating"]):
            return ThoughtType.ANALYSIS
        elif any(w in text_lower for w in ["could be", "might", "possibly", "hypothesis", "if we"]):
            return ThoughtType.HYPOTHESIS
        elif any(w in text_lower for w in ["therefore", "conclude", "decision", "determined", "verdict"]):
            return ThoughtType.DECISION
        elif any(w in text_lower for w in ["recommend", "suggest", "should", "optimal", "strategy"]):
            return ThoughtType.RECOMMENDATION

        return None

    # ------------------------------------------------------------------
    # GEMINI 3 STREAMING
    # ------------------------------------------------------------------

    async def stream_gemini3(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        thinking_level: str = "low",
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream response from Gemini 3 with thought signatures.

        Args:
            prompt: The prompt to send
            model: Gemini 3 model string
            thinking_level: "minimal" | "low" | "high"

        Yields:
            StreamChunk objects with text and optional thought type
        """
        try:
            if not self.gemini3_client:
                yield StreamChunk(text="Gemini 3 client not available", is_final=True)
                return

            config = self._build_thinking_config(thinking_level)

            response = self.gemini3_client.models.generate_content_stream(
                model=model,
                contents=prompt,
                config=config,
            )

            buffer = ""
            for chunk in response:
                if chunk.text:
                    buffer += chunk.text

                    # Check for native Gemini 3 thought signature
                    is_thought = self._extract_thought_from_chunk(chunk)

                    # Classify the thought type (keyword-based)
                    thought_type = self._detect_thought_type(buffer)

                    yield StreamChunk(
                        text=chunk.text,
                        thought_type=thought_type,
                        is_final=False,
                        is_thought=bool(is_thought),
                    )

            yield StreamChunk(text="", is_final=True)

        except Exception as e:
            logger.error(f"Gemini 3 streaming failed: {e}")
            yield StreamChunk(text=f"Error: {str(e)}", is_final=True)

    # ------------------------------------------------------------------
    # GEMINI 3 IMAGE ANALYSIS (streaming)
    # ------------------------------------------------------------------

    async def analyze_image_stream(
        self,
        image_data: bytes,
        image_type: Literal["png", "jpeg", "webp", "gif"] = "png",
        analysis_prompt: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        thinking_level: str = "low",
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Analyze a product screenshot with streaming response.

        Args:
            image_data: Raw image bytes
            image_type: Image MIME type
            analysis_prompt: Custom prompt (uses default if not provided)
            model: Gemini 3 model to use
            thinking_level: Controls reasoning depth

        Yields:
            StreamChunk objects with analysis text and thought signatures
        """
        try:
            if not self.gemini3_client:
                yield StreamChunk(text="Gemini 3 client not available", is_final=True)
                return

            if analysis_prompt is None:
                analysis_prompt = """Analyze this product screenshot and extract:

1. OBSERVATION: What do you see? (product name, brand, visual elements)
2. ANALYSIS: Extract specific details:
   - Product name
   - Price (include currency)
   - Key features listed
   - Any promotional signals (discounts, badges, limited time offers)
   - Customer reviews summary if visible
3. HYPOTHESIS: What market positioning does this suggest?
4. RECOMMENDATION: How should a competitor respond to this pricing?

Be specific and structured in your analysis. Start each section with the thought type."""

            image_base64 = base64.b64encode(image_data).decode("utf-8")

            contents = [
                {
                    "parts": [
                        {"text": analysis_prompt},
                        {
                            "inline_data": {
                                "mime_type": f"image/{image_type}",
                                "data": image_base64,
                            }
                        },
                    ]
                }
            ]

            config = self._build_thinking_config(thinking_level)

            response = self.gemini3_client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )

            buffer = ""
            for chunk in response:
                if chunk.text:
                    buffer += chunk.text
                    is_thought = self._extract_thought_from_chunk(chunk)
                    thought_type = self._detect_thought_type(chunk.text)

                    yield StreamChunk(
                        text=chunk.text,
                        thought_type=thought_type,
                        is_final=False,
                        is_thought=bool(is_thought),
                    )

            yield StreamChunk(text="", is_final=True)

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            yield StreamChunk(text=f"Error analyzing image: {str(e)}", is_final=True)

    # ------------------------------------------------------------------
    # GEMINI 3 IMAGE ANALYSIS (structured, non-streaming)
    # ------------------------------------------------------------------

    async def analyze_image(
        self,
        image_data: bytes,
        image_type: Literal["png", "jpeg", "webp", "gif"] = "png",
        model: str = DEFAULT_MODEL,
        thinking_level: str = "low",
    ) -> ImageAnalysisResult:
        """
        Analyze a product screenshot and return structured result.

        Args:
            image_data: Raw image bytes
            image_type: Image MIME type
            model: Gemini 3 model to use
            thinking_level: Controls reasoning depth

        Returns:
            ImageAnalysisResult with extracted product information
        """
        try:
            if not self.gemini3_client:
                return ImageAnalysisResult(raw_text="Gemini 3 client not available")

            image_base64 = base64.b64encode(image_data).decode("utf-8")

            extraction_prompt = """Analyze this product screenshot and respond with ONLY a JSON object:

{
  "product_name": "exact product name visible",
  "price": "price as shown (e.g., '$29.99' or '29.99')",
  "currency": "USD/EUR/GBP/etc",
  "features": ["feature 1", "feature 2"],
  "reviews_summary": "brief summary of reviews if visible, null otherwise",
  "promo_signals": ["any discount badges", "limited time offers", "sale indicators"],
  "confidence": 0.0 to 1.0 based on image clarity
}

Respond with ONLY the JSON, no other text."""

            contents = [
                {
                    "parts": [
                        {"text": extraction_prompt},
                        {
                            "inline_data": {
                                "mime_type": f"image/{image_type}",
                                "data": image_base64,
                            }
                        },
                    ]
                }
            ]

            config = self._build_thinking_config(thinking_level)

            response = self.gemini3_client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            text = response.text

            # Parse JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text.strip())

            return ImageAnalysisResult(
                product_name=data.get("product_name"),
                price=data.get("price"),
                currency=data.get("currency"),
                features=data.get("features", []),
                reviews_summary=data.get("reviews_summary"),
                promo_signals=data.get("promo_signals", []),
                confidence=data.get("confidence", 0.5),
                raw_text=response.text,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse image analysis JSON: {e}")
            return ImageAnalysisResult(
                raw_text=response.text if "response" in dir() else str(e),
                confidence=0.0,
            )
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return ImageAnalysisResult(raw_text=str(e), confidence=0.0)


# Singleton instance
ai_clients = AIClients()



