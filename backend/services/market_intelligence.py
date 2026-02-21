"""
Market Intelligence Pipeline for ActualPrice.

Multi-agent system: Scout → Analyst → Strategist
- Scout: Gathers live competitor data via You.com APIs (parallel searches)
- Analyst: Synthesizes market position using Gemini streaming
- Strategist: Recommends optimal price with confidence score

DeveloperWeek 2026 Hackathon - You.com Challenge Track
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Optional

from core.config import settings
from core.logging import get_logger
from services.youcom_client import YouComClient, Freshness, SearchResponse

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums & Data Models (matches existing AgentMessage shape)
# ---------------------------------------------------------------------------

class AgentRole(str, Enum):
    """Agent roles in the pipeline."""
    SCOUT = "scout"
    ANALYST = "analyst"
    STRATEGIST = "strategist"


class ThoughtType(str, Enum):
    """Types of agent thoughts (matches visual-pricing pattern)."""
    OBSERVATION = "observation"
    ANALYSIS = "analysis"
    HYPOTHESIS = "hypothesis"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"


@dataclass
class AgentEvent:
    """
    Single event from an agent in the pipeline.

    Matches the AgentMessage shape used by visual-pricing, crisis-detection,
    and other demo routes so the frontend can reuse the same components.
    """
    agent: AgentRole
    thought_type: Optional[ThoughtType]
    content: str
    is_final: bool = False
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "agent": self.agent.value,
            "thought_type": self.thought_type.value if self.thought_type else None,
            "content": self.content,
            "is_final": self.is_final,
            "metadata": self.metadata,
        }

    def to_sse(self) -> str:
        """Format as Server-Sent Event data line."""
        return f"data: {json.dumps(self.to_dict())}\n\n"


@dataclass
class IntelligenceRequest:
    """Input for the market intelligence pipeline."""
    product_name: str
    current_price: Optional[float] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    features: Optional[list[str]] = None


@dataclass
class PriceRecommendation:
    """Structured output from the Strategist agent."""
    recommended_price: float
    confidence: float
    price_range_low: float
    price_range_high: float
    risk_level: str  # low, medium, high
    strategy: str
    reasoning: str
    key_factors: list[str] = field(default_factory=list)
    price_change_percent: float = 0.0
    sources_used: int = 0


# ---------------------------------------------------------------------------
# Scout Agent
# ---------------------------------------------------------------------------

class ScoutAgent:
    """
    Gathers live market data via You.com parallel searches.

    Runs 2-3 searches simultaneously:
    1. Competitor prices
    2. Market sentiment / reviews
    3. Category trends (if category provided)
    """

    def __init__(self, client: YouComClient):
        self._client = client

    async def gather(
        self, request: IntelligenceRequest
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run parallel searches and yield events as results arrive."""
        yield AgentEvent(
            agent=AgentRole.SCOUT,
            thought_type=ThoughtType.OBSERVATION,
            content=f"Starting live web search for \"{request.product_name}\"...",
        )

        # Build parallel search tasks
        tasks: dict[str, asyncio.Task] = {}

        tasks["prices"] = asyncio.create_task(
            self._client.search_competitor_prices(
                product_name=request.product_name,
                category=request.category,
                brand=request.brand,
            )
        )

        tasks["sentiment"] = asyncio.create_task(
            self._client.search_market_sentiment(
                product_name=request.product_name,
                brand=request.brand,
            )
        )

        if request.category:
            tasks["trends"] = asyncio.create_task(
                self._client.search_market_trends(
                    category=request.category,
                    freshness=Freshness.WEEK,
                )
            )

        # Collect results as they complete
        results: dict[str, SearchResponse] = {}
        total_sources = 0

        for name, task in tasks.items():
            try:
                response: SearchResponse = await task
                results[name] = response
                count = response.total_results
                total_sources += count

                label = {
                    "prices": "competitor pricing",
                    "sentiment": "reviews & sentiment",
                    "trends": "market trends",
                }[name]

                yield AgentEvent(
                    agent=AgentRole.SCOUT,
                    thought_type=ThoughtType.OBSERVATION,
                    content=f"Found {count} {label} sources ({response.latency_ms:.0f}ms)",
                )

            except Exception as exc:
                logger.warning("Scout search '%s' failed: %s", name, exc)
                yield AgentEvent(
                    agent=AgentRole.SCOUT,
                    thought_type=ThoughtType.OBSERVATION,
                    content=f"⚠ {name} search unavailable — continuing with other sources",
                )

        # Build combined context block for downstream agents
        context_parts = []
        source_urls = []

        for name, response in results.items():
            context_parts.append(response.to_context_block())
            for r in response.web_results:
                if r.url:
                    source_urls.append({"title": r.title, "url": r.url})
            for n in response.news_results:
                if n.url:
                    source_urls.append({"title": n.title, "url": n.url})

        combined_context = "\n\n---\n\n".join(context_parts) if context_parts else ""

        yield AgentEvent(
            agent=AgentRole.SCOUT,
            thought_type=ThoughtType.OBSERVATION,
            content=f"✓ Gathered {total_sources} sources from live web data",
            is_final=True,
            metadata={
                "scout_context": combined_context,
                "sources": source_urls[:20],  # Cap at 20 for UI
                "total_sources": total_sources,
            },
        )


# ---------------------------------------------------------------------------
# Analyst Agent
# ---------------------------------------------------------------------------

class AnalystAgent:
    """
    Synthesizes Scout data into a market analysis using Gemini streaming.

    Produces: competitor price range, market sentiment, positioning insights.
    """

    SYSTEM_PROMPT = (
        "You are a market analyst AI for ActualPrice, an e-commerce pricing platform. "
        "Analyze the live web data provided by the Scout agent. "
        "Extract: (1) competitor price range (min, max, average), "
        "(2) overall market sentiment, (3) key positioning factors. "
        "Be specific — cite actual prices and sources when available. "
        "Keep your analysis concise (3-5 bullet points max)."
    )

    async def analyze(
        self, scout_context: str, request: IntelligenceRequest
    ) -> AsyncGenerator[AgentEvent, None]:
        """Analyze scout data via Gemini and yield streaming events."""
        yield AgentEvent(
            agent=AgentRole.ANALYST,
            thought_type=ThoughtType.ANALYSIS,
            content="Synthesizing market data from Scout findings...",
        )

        if not scout_context.strip():
            yield AgentEvent(
                agent=AgentRole.ANALYST,
                thought_type=ThoughtType.ANALYSIS,
                content="Limited data available — providing general analysis.",
                is_final=True,
                metadata={"analyst_summary": "Insufficient data for detailed analysis."},
            )
            return

        user_prompt = self._build_prompt(scout_context, request)

        # Try Gemini streaming
        if settings.GEMINI_API_KEY:
            full_text = ""
            try:
                from google import genai

                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                gemini_model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")

                response = client.models.generate_content_stream(
                    model=gemini_model,
                    contents=user_prompt,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_PROMPT,
                        temperature=0.3,
                        max_output_tokens=1024,
                    ),
                )

                for chunk in response:
                    text = chunk.text if hasattr(chunk, "text") and chunk.text else ""
                    if text:
                        full_text += text
                        yield AgentEvent(
                            agent=AgentRole.ANALYST,
                            thought_type=ThoughtType.ANALYSIS,
                            content=text,
                        )

            except Exception as exc:
                logger.error("Analyst Gemini error: %s", exc)
                full_text = f"Analysis could not be completed via AI: {exc}"
                yield AgentEvent(
                    agent=AgentRole.ANALYST,
                    thought_type=ThoughtType.ANALYSIS,
                    content=full_text,
                )
        else:
            full_text = (
                "Gemini not configured. Based on the Scout data, "
                "a manual review of competitor prices is recommended."
            )
            yield AgentEvent(
                agent=AgentRole.ANALYST,
                thought_type=ThoughtType.ANALYSIS,
                content=full_text,
            )

        yield AgentEvent(
            agent=AgentRole.ANALYST,
            thought_type=ThoughtType.ANALYSIS,
            content="✓ Market analysis complete",
            is_final=True,
            metadata={"analyst_summary": full_text},
        )

    def _build_prompt(self, scout_context: str, request: IntelligenceRequest) -> str:
        parts = [f"## Product Under Analysis\n- Name: {request.product_name}"]
        if request.current_price:
            parts.append(f"- Current Price: ${request.current_price:.2f}")
        if request.brand:
            parts.append(f"- Brand: {request.brand}")
        if request.category:
            parts.append(f"- Category: {request.category}")
        if request.features:
            parts.append(f"- Features: {', '.join(request.features)}")

        parts.append(f"\n## Live Web Data (from You.com)\n{scout_context}")
        parts.append(
            "\n## Your Task\n"
            "Analyze the data above. Extract competitor price range, "
            "market sentiment, and positioning insights. Be specific."
        )
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Strategist Agent
# ---------------------------------------------------------------------------

class StrategistAgent:
    """
    Produces final pricing recommendation with confidence score.

    Uses Gemini to generate structured JSON output.
    """

    SYSTEM_PROMPT = (
        "You are a pricing strategist AI for ActualPrice. "
        "Based on the Analyst's market summary and the Scout's raw data, "
        "recommend an optimal price. "
        "Respond ONLY with a JSON object — no markdown fences, no preamble. "
        "JSON schema:\n"
        "{\n"
        '  "recommended_price": <float>,\n'
        '  "confidence": <float 0-1>,\n'
        '  "price_range_low": <float>,\n'
        '  "price_range_high": <float>,\n'
        '  "risk_level": "<low|medium|high>",\n'
        '  "strategy": "<short strategy label>",\n'
        '  "reasoning": "<2-3 sentence explanation>",\n'
        '  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],\n'
        '  "price_change_percent": <float>\n'
        "}"
    )

    async def recommend(
        self,
        scout_context: str,
        analyst_summary: str,
        request: IntelligenceRequest,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Generate pricing recommendation and yield events."""
        yield AgentEvent(
            agent=AgentRole.STRATEGIST,
            thought_type=ThoughtType.DECISION,
            content="Calculating optimal pricing strategy...",
        )

        user_prompt = self._build_prompt(scout_context, analyst_summary, request)
        recommendation: Optional[PriceRecommendation] = None

        if settings.GEMINI_API_KEY:
            try:
                from google import genai

                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                gemini_model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")

                response = client.models.generate_content(
                    model=gemini_model,
                    contents=user_prompt,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_PROMPT,
                        temperature=0.2,
                        max_output_tokens=512,
                    ),
                )

                raw = response.text.strip()
                # Strip markdown fences if present
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw.rsplit("```", 1)[0]
                raw = raw.strip()

                data = json.loads(raw)
                recommendation = PriceRecommendation(
                    recommended_price=float(data["recommended_price"]),
                    confidence=float(data["confidence"]),
                    price_range_low=float(data["price_range_low"]),
                    price_range_high=float(data["price_range_high"]),
                    risk_level=data.get("risk_level", "medium"),
                    strategy=data.get("strategy", "Market-aligned pricing"),
                    reasoning=data.get("reasoning", "Based on market analysis."),
                    key_factors=data.get("key_factors", []),
                    price_change_percent=float(data.get("price_change_percent", 0)),
                )

                yield AgentEvent(
                    agent=AgentRole.STRATEGIST,
                    thought_type=ThoughtType.RECOMMENDATION,
                    content=(
                        f"Recommended price: ${recommendation.recommended_price:.2f} "
                        f"(confidence: {recommendation.confidence:.0%})"
                    ),
                )

            except json.JSONDecodeError as exc:
                logger.error("Strategist JSON parse error: %s | raw: %s", exc, raw[:200])
                yield AgentEvent(
                    agent=AgentRole.STRATEGIST,
                    thought_type=ThoughtType.DECISION,
                    content="⚠ Could not parse structured recommendation — using fallback.",
                )
                recommendation = self._fallback_recommendation(request)

            except Exception as exc:
                logger.error("Strategist Gemini error: %s", exc)
                yield AgentEvent(
                    agent=AgentRole.STRATEGIST,
                    thought_type=ThoughtType.DECISION,
                    content=f"⚠ AI recommendation unavailable: {exc}",
                )
                recommendation = self._fallback_recommendation(request)
        else:
            yield AgentEvent(
                agent=AgentRole.STRATEGIST,
                thought_type=ThoughtType.DECISION,
                content="Gemini not configured — generating heuristic recommendation.",
            )
            recommendation = self._fallback_recommendation(request)

        # Final event with recommendation payload
        rec_dict = {
            "recommended_price": recommendation.recommended_price,
            "confidence": recommendation.confidence,
            "price_range_low": recommendation.price_range_low,
            "price_range_high": recommendation.price_range_high,
            "risk_level": recommendation.risk_level,
            "strategy": recommendation.strategy,
            "reasoning": recommendation.reasoning,
            "key_factors": recommendation.key_factors,
            "price_change_percent": recommendation.price_change_percent,
            "sources_used": recommendation.sources_used,
        }

        yield AgentEvent(
            agent=AgentRole.STRATEGIST,
            thought_type=ThoughtType.RECOMMENDATION,
            content="✓ Pricing recommendation ready",
            is_final=True,
            metadata={"recommendation": rec_dict},
        )

    def _build_prompt(
        self,
        scout_context: str,
        analyst_summary: str,
        request: IntelligenceRequest,
    ) -> str:
        parts = [f"## Product\n- Name: {request.product_name}"]
        if request.current_price:
            parts.append(f"- Current Price: ${request.current_price:.2f}")
        if request.brand:
            parts.append(f"- Brand: {request.brand}")
        if request.category:
            parts.append(f"- Category: {request.category}")
        if request.features:
            parts.append(f"- Features: {', '.join(request.features)}")

        parts.append(f"\n## Analyst Summary\n{analyst_summary}")
        parts.append(f"\n## Raw Market Data\n{scout_context[:3000]}")
        parts.append(
            "\n## Your Task\n"
            "Based on the above, recommend an optimal price. "
            "Respond ONLY with the JSON object."
        )
        return "\n".join(parts)

    def _fallback_recommendation(self, request: IntelligenceRequest) -> PriceRecommendation:
        """Heuristic fallback when Gemini is unavailable."""
        base = request.current_price or 50.0
        return PriceRecommendation(
            recommended_price=round(base * 0.95, 2),
            confidence=0.35,
            price_range_low=round(base * 0.80, 2),
            price_range_high=round(base * 1.10, 2),
            risk_level="medium",
            strategy="Conservative market-aligned",
            reasoning=(
                "Heuristic recommendation based on a 5% competitive discount. "
                "Enable Gemini API for AI-powered analysis."
            ),
            key_factors=["No AI analysis available", "Using price heuristic"],
            price_change_percent=-5.0,
        )


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------

class MarketIntelligencePipeline:
    """
    Orchestrates Scout → Analyst → Strategist pipeline.

    Each agent yields AgentEvent objects that are streamed to the
    frontend as SSE events.
    """

    def __init__(self, youcom_api_key: Optional[str] = None):
        api_key = youcom_api_key or getattr(settings, "YOUCOM_API_KEY", None)
        if not api_key:
            raise ValueError(
                "You.com API key required. Set YOUCOM_API_KEY in your .env"
            )
        self._client = YouComClient(api_key=api_key)
        self._scout = ScoutAgent(self._client)
        self._analyst = AnalystAgent()
        self._strategist = StrategistAgent()

    async def run(
        self, request: IntelligenceRequest
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Execute full pipeline and yield events for SSE streaming.

        Events flow: Scout findings → Analyst synthesis → Strategist recommendation
        """
        start = time.time()
        scout_context = ""
        sources: list[dict] = []
        analyst_summary = ""

        # --- Phase 1: Scout ---
        try:
            async for event in self._scout.gather(request):
                yield event
                if event.is_final and event.metadata:
                    scout_context = event.metadata.get("scout_context", "")
                    sources = event.metadata.get("sources", [])
        except Exception as exc:
            logger.error("Scout phase failed: %s", exc)
            yield AgentEvent(
                agent=AgentRole.SCOUT,
                thought_type=ThoughtType.OBSERVATION,
                content=f"⚠ Scout phase encountered an error: {exc}",
                is_final=True,
                metadata={"scout_context": "", "sources": []},
            )

        # --- Phase 2: Analyst ---
        try:
            async for event in self._analyst.analyze(scout_context, request):
                yield event
                if event.is_final and event.metadata:
                    analyst_summary = event.metadata.get("analyst_summary", "")
        except Exception as exc:
            logger.error("Analyst phase failed: %s", exc)
            yield AgentEvent(
                agent=AgentRole.ANALYST,
                thought_type=ThoughtType.ANALYSIS,
                content=f"⚠ Analyst phase encountered an error: {exc}",
                is_final=True,
                metadata={"analyst_summary": "Analysis unavailable."},
            )
            analyst_summary = "Analysis unavailable due to error."

        # --- Phase 3: Strategist ---
        try:
            async for event in self._strategist.recommend(
                scout_context, analyst_summary, request
            ):
                # Inject sources into the final strategist event
                if event.is_final and event.metadata:
                    event.metadata["sources"] = sources
                    rec = event.metadata.get("recommendation", {})
                    if isinstance(rec, dict):
                        rec["sources_used"] = len(sources)
                yield event
        except Exception as exc:
            logger.error("Strategist phase failed: %s", exc)
            yield AgentEvent(
                agent=AgentRole.STRATEGIST,
                thought_type=ThoughtType.RECOMMENDATION,
                content=f"⚠ Strategist phase encountered an error: {exc}",
                is_final=True,
                metadata={"recommendation": None, "sources": sources},
            )

        elapsed = time.time() - start
        logger.info(
            "Pipeline complete for %r in %.1fs (%d sources)",
            request.product_name,
            elapsed,
            len(sources),
        )

    async def close(self) -> None:
        """Clean up the You.com HTTP client."""
        await self._client.close()


        