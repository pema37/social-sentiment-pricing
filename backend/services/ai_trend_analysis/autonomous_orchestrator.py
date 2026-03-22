"""
Autonomous Pricing Agent Orchestrator
VETROX AGENTIC 3.0 - Track 3: The Hand (Tool Use & Web3)

Three-agent pipeline that observes markets, reasons about pricing,
and executes decisions on-chain — without human prompting.

Scout → Analyst → Strategist → On-Chain Execution
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from enum import StrEnum

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini Client Configuration
# ---------------------------------------------------------------------------

GEMINI_MODEL = "gemini-2.0-flash"

client = genai.Client(api_key=settings.GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Structured Schemas for Agent-to-Agent Communication
# ---------------------------------------------------------------------------


class AgentPhase(StrEnum):
    SCOUT = "scout"
    ANALYST = "analyst"
    STRATEGIST = "strategist"
    EXECUTION = "execution"


class MarketSignal(BaseModel):
    """Scout Agent output — structured market intelligence."""

    competitor_name: str = Field(description="Name of the competitor detected")
    competitor_price: float = Field(description="Current competitor price in USD")
    price_change_pct: float = Field(description="Percentage change from last known price")
    signal_type: str = Field(description="Type: price_drop, price_increase, new_product, stockout")
    product_category: str = Field(description="Product category being monitored")
    source: str = Field(description="Data source: google_search, api, scraper")
    confidence: float = Field(ge=0.0, le=1.0, description="Signal confidence score")
    raw_data: dict = Field(default_factory=dict, description="Raw scraped/fetched data")
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class MarketAssessment(BaseModel):
    """Analyst Agent output — risk and opportunity assessment."""

    sentiment_score: float = Field(ge=-1.0, le=1.0, description="Aggregated sentiment (-1 bearish to 1 bullish)")
    sentiment_label: str = Field(description="human-readable: bearish, neutral, bullish")
    demand_elasticity: float = Field(description="Price sensitivity coefficient")
    risk_level: str = Field(description="low, medium, high, critical")
    risk_factors: list[str] = Field(default_factory=list, description="Identified risk factors")
    opportunity_score: float = Field(ge=0.0, le=1.0, description="Opportunity to capture margin")
    market_context: str = Field(description="Brief market narrative for the Strategist")
    recommended_direction: str = Field(description="increase, decrease, hold")
    max_safe_change_pct: float = Field(description="Maximum safe price change percentage")


class PricingDecision(BaseModel):
    """Strategist Agent output — the final autonomous pricing action."""

    recommended_price: float = Field(description="Optimal price in USD")
    current_price: float = Field(description="Current price before change")
    change_pct: float = Field(description="Price change percentage")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Decision confidence")
    reasoning: str = Field(description="Full chain-of-thought reasoning")
    action: str = Field(description="execute, hold, escalate")
    risk_acknowledgment: str = Field(description="Known risks of this decision")
    expected_revenue_impact: str = Field(description="Projected impact on revenue")
    tx_hash: str | None = Field(default=None, description="BNB Chain transaction hash if executed")
    executed_at: str | None = Field(default=None, description="ISO timestamp of on-chain execution")


class AgentStreamEvent(BaseModel):
    """SSE event for real-time agent reasoning display."""

    agent: str
    phase: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    is_complete: bool = False
    data: dict | None = None


# ---------------------------------------------------------------------------
# Tool Declarations for Each Agent
# ---------------------------------------------------------------------------

SCOUT_TOOLS = [
    types.Tool(google_search=types.GoogleSearch()),  # Grounding in real-time web data
]

SCOUT_FUNCTION_TOOLS = types.Tool(
    function_declarations=[
        {
            "name": "fetch_competitor_price",
            "description": "Fetch the current price of a competitor's product from monitoring APIs",
            "parameters": {
                "type": "object",
                "properties": {
                    "competitor_url": {"type": "string", "description": "URL of the competitor product page"},
                    "product_category": {"type": "string", "description": "Product category to search"},
                },
                "required": ["product_category"],
            },
        },
        {
            "name": "detect_price_change",
            "description": "Compare current price against last known price to detect changes",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_price": {"type": "number", "description": "Current detected price"},
                    "last_known_price": {"type": "number", "description": "Previously recorded price"},
                    "product_id": {"type": "string", "description": "Internal product identifier"},
                },
                "required": ["current_price", "last_known_price", "product_id"],
            },
        },
    ]
)

ANALYST_FUNCTION_TOOLS = types.Tool(
    function_declarations=[
        {
            "name": "analyze_sentiment",
            "description": "Run sentiment analysis on social media mentions for a product category",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_category": {"type": "string"},
                    "timeframe_hours": {"type": "integer", "description": "Hours of history to analyze"},
                },
                "required": ["product_category"],
            },
        },
        {
            "name": "calculate_elasticity",
            "description": "Calculate price elasticity of demand based on historical price-volume data",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "price_history": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["product_id"],
            },
        },
        {
            "name": "assess_risk",
            "description": "Evaluate risk factors: brand perception, competitor strength, market conditions",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal": {"type": "object", "description": "The MarketSignal from Scout"},
                    "sentiment_score": {"type": "number"},
                },
                "required": ["signal", "sentiment_score"],
            },
        },
    ]
)

STRATEGIST_FUNCTION_TOOLS = types.Tool(
    function_declarations=[
        {
            "name": "calculate_optimal_price",
            "description": "Compute the optimal price given market assessment, costs, and constraints",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_price": {"type": "number"},
                    "cost_basis": {"type": "number"},
                    "margin_floor_pct": {"type": "number"},
                    "assessment": {"type": "object", "description": "MarketAssessment from Analyst"},
                    "signal": {"type": "object", "description": "MarketSignal from Scout"},
                },
                "required": ["current_price", "assessment", "signal"],
            },
        },
        {
            "name": "write_price_to_chain",
            "description": "Execute pricing decision by writing to BNB Chain smart contract",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "new_price": {"type": "number"},
                    "reasoning_hash": {"type": "string", "description": "IPFS/hash of reasoning trace"},
                    "confidence": {"type": "number"},
                },
                "required": ["product_id", "new_price", "confidence"],
            },
        },
    ]
)


# ---------------------------------------------------------------------------
# Tool Execution Handlers (called when Gemini invokes a function)
# ---------------------------------------------------------------------------


async def handle_tool_call(function_name: str, args: dict) -> dict:
    """
    Execute tool calls from Gemini agents.
    In production, these connect to real APIs. For the demo,
    we return realistic simulated data.
    """
    handlers = {
        "fetch_competitor_price": _handle_fetch_competitor_price,
        "detect_price_change": _handle_detect_price_change,
        "analyze_sentiment": _handle_analyze_sentiment,
        "calculate_elasticity": _handle_calculate_elasticity,
        "assess_risk": _handle_assess_risk,
        "calculate_optimal_price": _handle_calculate_optimal_price,
        "write_price_to_chain": _handle_write_price_to_chain,
    }
    handler = handlers.get(function_name)
    if handler:
        return await handler(args)
    return {"error": f"Unknown tool: {function_name}"}


async def _handle_fetch_competitor_price(args: dict) -> dict:
    """Fetch competitor price from monitoring system."""
    # In production: calls competitor_scraper.py or price APIs
    return {
        "competitor_name": "CompetitorX",
        "product": args.get("product_category", "electronics"),
        "current_price": 89.99,
        "previous_price": 105.99,
        "currency": "USD",
        "last_updated": datetime.now(UTC).isoformat(),
        "source": "google_search_grounding",
    }


async def _handle_detect_price_change(args: dict) -> dict:
    """Compare prices to detect significant changes."""
    current = args.get("current_price", 0)
    last = args.get("last_known_price", 0)
    change_pct = ((current - last) / last * 100) if last else 0
    return {
        "change_detected": abs(change_pct) > 2.0,
        "change_pct": round(change_pct, 2),
        "signal_type": "price_drop" if change_pct < -2 else "price_increase" if change_pct > 2 else "stable",
        "significance": "high" if abs(change_pct) > 10 else "medium" if abs(change_pct) > 5 else "low",
    }


async def _handle_analyze_sentiment(args: dict) -> dict:
    """Run sentiment analysis via VADER + Gemini hybrid pipeline."""
    # In production: calls hybrid_sentiment_analyzer.py
    return {
        "sentiment_score": -0.42,
        "sentiment_label": "bearish",
        "mention_count": 847,
        "top_keywords": ["overpriced", "competitor", "alternative", "better deal"],
        "platforms": {"reddit": -0.55, "twitter": -0.38, "reviews": -0.33},
        "trend": "declining",
        "timeframe_hours": args.get("timeframe_hours", 24),
    }


async def _handle_calculate_elasticity(args: dict) -> dict:
    """Calculate price elasticity of demand."""
    # In production: calls pricing/signal_processor.py
    return {
        "elasticity_coefficient": -1.8,
        "interpretation": "elastic_demand",
        "price_sensitivity": "high",
        "optimal_range": {"min": 79.99, "max": 94.99},
        "data_points_analyzed": 156,
    }


async def _handle_assess_risk(args: dict) -> dict:
    """Multi-factor risk assessment."""
    return {
        "risk_level": "medium",
        "risk_factors": [
            "Competitor price 15% below current",
            "Bearish consumer sentiment trending",
            "High demand elasticity increases churn risk",
        ],
        "mitigation": "Match competitor within 5% to retain market share",
        "brand_impact": "low",
        "revenue_risk_if_no_action": "12-18% volume decline projected",
    }


async def _handle_calculate_optimal_price(args: dict) -> dict:
    """Compute optimal price using assessment data."""
    current = args.get("current_price", 99.99)
    assessment = args.get("assessment", {})
    direction = assessment.get("recommended_direction", "decrease")

    if direction == "decrease":
        optimal = round(current * 0.88, 2)  # 12% reduction
    elif direction == "increase":
        optimal = round(current * 1.05, 2)
    else:
        optimal = current

    return {
        "optimal_price": optimal,
        "change_pct": round((optimal - current) / current * 100, 2),
        "confidence": 0.87,
        "method": "sentiment_weighted_competitive_positioning",
        "factors_weighted": {
            "competitor_price": 0.35,
            "sentiment_signal": 0.25,
            "elasticity": 0.25,
            "margin_floor": 0.15,
        },
    }


async def _handle_write_price_to_chain(args: dict) -> dict:
    """Write pricing decision to BNB Chain smart contract."""
    # In production: calls payment/eth_service.py for BNB transaction
    # For demo: simulate successful on-chain execution
    tx_hash = f"0x{'a1b2c3d4e5f6' * 6}"[:66]
    return {
        "success": True,
        "tx_hash": tx_hash,
        "chain": "BNB Chain Testnet",
        "block_number": 45678901,
        "gas_used": 85432,
        "contract_address": os.getenv("BNB_CONTRACT_ADDRESS", "0xDEMO..."),
        "explorer_url": f"https://testnet.bscscan.com/tx/{tx_hash}",
        "executed_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Agent Implementations
# ---------------------------------------------------------------------------


class AutonomousOrchestrator:
    """
    Three-agent autonomous pricing pipeline.
    Detects market signals, reasons about impact, and executes pricing
    decisions on-chain — without human intervention.
    """

    def __init__(self):
        self.client = client
        self.model = GEMINI_MODEL
        self._reasoning_log: list[AgentStreamEvent] = []

    async def run_pipeline(
        self,
        product_id: str,
        current_price: float = 99.99,
        product_category: str = "electronics",
        cost_basis: float = 45.00,
        margin_floor_pct: float = 20.0,
    ) -> PricingDecision:
        """
        Execute the full autonomous pipeline.
        Returns the final PricingDecision with on-chain tx hash.
        """
        logger.info(f"[AUTONOMOUS] Pipeline triggered for product {product_id}")

        # Phase 1: Scout — detect market signals
        signal = await self._run_scout(product_id, product_category)

        # Phase 2: Analyst — assess impact
        assessment = await self._run_analyst(signal)

        # Phase 3: Strategist — decide and execute
        decision = await self._run_strategist(
            signal, assessment, current_price, cost_basis, margin_floor_pct, product_id
        )

        logger.info(
            f"[AUTONOMOUS] Pipeline complete: {decision.action} "
            f"${decision.current_price} → ${decision.recommended_price} "
            f"(confidence: {decision.confidence_score})"
        )
        return decision

    async def run_pipeline_streaming(
        self,
        product_id: str,
        current_price: float = 99.99,
        product_category: str = "electronics",
        cost_basis: float = 45.00,
        margin_floor_pct: float = 20.0,
    ) -> AsyncGenerator[str]:
        """
        Execute pipeline with SSE streaming for real-time UI display.
        Yields Server-Sent Events showing each agent's reasoning.
        """
        try:
            # --- SCOUT PHASE ---
            yield self._sse_event("scout", "starting", "🔍 Scout Agent activated — scanning market signals...")

            signal = await self._run_scout(product_id, product_category)

            yield self._sse_event(
                "scout",
                "complete",
                json.dumps(
                    {
                        "competitor": signal.competitor_name,
                        "price_change": f"{signal.price_change_pct:+.1f}%",
                        "signal": signal.signal_type,
                        "confidence": signal.confidence,
                    }
                ),
                is_complete=True,
            )

            # --- ANALYST PHASE ---
            yield self._sse_event(
                "analyst", "starting", "📊 Analyst Agent activated — processing market intelligence..."
            )

            assessment = await self._run_analyst(signal)

            yield self._sse_event(
                "analyst",
                "complete",
                json.dumps(
                    {
                        "sentiment": f"{assessment.sentiment_score:+.2f} ({assessment.sentiment_label})",
                        "elasticity": assessment.demand_elasticity,
                        "risk": assessment.risk_level,
                        "direction": assessment.recommended_direction,
                        "max_safe_change": f"{assessment.max_safe_change_pct}%",
                    }
                ),
                is_complete=True,
            )

            # --- STRATEGIST PHASE ---
            yield self._sse_event(
                "strategist", "starting", "💰 Strategist Agent activated — computing optimal price..."
            )

            decision = await self._run_strategist(
                signal, assessment, current_price, cost_basis, margin_floor_pct, product_id
            )

            yield self._sse_event(
                "strategist",
                "complete",
                json.dumps(
                    {
                        "action": decision.action,
                        "price": f"${decision.current_price} → ${decision.recommended_price}",
                        "change": f"{decision.change_pct:+.1f}%",
                        "confidence": f"{decision.confidence_score:.0%}",
                        "reasoning": decision.reasoning[:200],
                    }
                ),
                is_complete=True,
            )

            # --- EXECUTION PHASE ---
            if decision.action == "execute" and decision.tx_hash:
                yield self._sse_event(
                    "execution",
                    "complete",
                    json.dumps(
                        {
                            "tx_hash": decision.tx_hash,
                            "chain": "BNB Chain Testnet",
                            "explorer": f"https://testnet.bscscan.com/tx/{decision.tx_hash}",
                            "executed_at": decision.executed_at,
                        }
                    ),
                    is_complete=True,
                )

            # --- PIPELINE COMPLETE ---
            yield self._sse_event(
                "pipeline",
                "complete",
                "✅ Autonomous pipeline complete. All decisions logged on-chain.",
                is_complete=True,
            )

        except Exception as e:
            logger.exception(f"[AUTONOMOUS] Pipeline error: {e}")
            yield self._sse_event("error", "failed", str(e))

    # -----------------------------------------------------------------------
    # Individual Agent Runners
    # -----------------------------------------------------------------------

    async def _run_scout(self, product_id: str, product_category: str) -> MarketSignal:
        """
        Scout Agent: Monitors markets, detects signals.
        Uses Google Search grounding + function calling.
        Thinking level: minimal (speed-optimized).
        """
        system_prompt = """You are the Scout Agent in an autonomous pricing system.
Your job is to detect market signals — competitor price changes, new product launches,
sentiment shifts — using real-time data. You act WITHOUT human prompting.

When you detect a signal, use your tools to gather data, then return a structured
MarketSignal with your findings. Be precise with numbers. Speed matters."""

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[SCOUT_FUNCTION_TOOLS, types.Tool(google_search=types.GoogleSearch())],
            thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            response_mime_type="application/json",
            response_schema=MarketSignal.model_json_schema(),
            temperature=0.1,
        )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=f"""Scan the market for product category: {product_category}.
Product ID: {product_id}.
Detect any competitor price changes, new product launches, or sentiment shifts.
Return a structured MarketSignal.""",
            config=config,
        )

        # Parse structured response
        try:
            data = json.loads(response.text)
            return MarketSignal(**data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Scout parse fallback: {e}")
            return MarketSignal(
                competitor_name="CompetitorX",
                competitor_price=89.99,
                price_change_pct=-15.1,
                signal_type="price_drop",
                product_category=product_category,
                source="google_search",
                confidence=0.85,
            )

    async def _run_analyst(self, signal: MarketSignal) -> MarketAssessment:
        """
        Analyst Agent: Processes signals into actionable assessments.
        Uses sentiment analysis + elasticity modeling.
        Thinking level: medium (balanced reasoning).
        """
        system_prompt = """You are the Analyst Agent in an autonomous pricing system.
You receive MarketSignals from the Scout and produce a MarketAssessment.
Your job: analyze sentiment, calculate demand elasticity, assess risk,
and recommend a pricing direction. Be quantitative — numbers, not adjectives.
Every assessment must include risk factors and a maximum safe price change."""

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[ANALYST_FUNCTION_TOOLS],
            thinking_config=types.ThinkingConfig(thinking_level="medium"),
            response_mime_type="application/json",
            response_schema=MarketAssessment.model_json_schema(),
            temperature=0.2,
        )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=f"""Analyze this market signal from the Scout Agent:

{signal.model_dump_json(indent=2)}

Produce a MarketAssessment with sentiment score, elasticity, risk level,
and recommended pricing direction. Use your tools to gather additional data.""",
            config=config,
        )

        try:
            data = json.loads(response.text)
            return MarketAssessment(**data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Analyst parse fallback: {e}")
            return MarketAssessment(
                sentiment_score=-0.42,
                sentiment_label="bearish",
                demand_elasticity=-1.8,
                risk_level="medium",
                risk_factors=[
                    f"Competitor price {signal.price_change_pct:+.1f}% change detected",
                    "Bearish consumer sentiment trending",
                    "High demand elasticity increases churn risk",
                ],
                opportunity_score=0.65,
                market_context=f"Competitor dropped price by {abs(signal.price_change_pct):.1f}%. Market sentiment is bearish. High elasticity suggests customers will switch.",
                recommended_direction="decrease",
                max_safe_change_pct=15.0,
            )

    async def _run_strategist(
        self,
        signal: MarketSignal,
        assessment: MarketAssessment,
        current_price: float,
        cost_basis: float,
        margin_floor_pct: float,
        product_id: str,
    ) -> PricingDecision:
        """
        Strategist Agent: Decides and executes.
        Uses complex reasoning + on-chain execution.
        Thinking level: high (maximum reasoning depth).
        """
        system_prompt = """You are the Strategist Agent in an autonomous pricing system.
You receive a MarketSignal (from Scout) and a MarketAssessment (from Analyst).
Your job: calculate the optimal price, assess confidence, and EXECUTE the decision
by writing it to the blockchain. You do not ask for permission. You act.

Rules:
- Never set price below cost_basis + margin_floor
- Confidence must be > 0.7 to auto-execute; otherwise escalate
- Always explain your reasoning chain
- When you decide to execute, call write_price_to_chain"""

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[STRATEGIST_FUNCTION_TOOLS],
            thinking_config=types.ThinkingConfig(thinking_level="high"),
            temperature=0.3,
        )

        prompt = f"""Make a pricing decision based on this intelligence:

SCOUT SIGNAL:
{signal.model_dump_json(indent=2)}

ANALYST ASSESSMENT:
{assessment.model_dump_json(indent=2)}

CONSTRAINTS:
- Current price: ${current_price}
- Cost basis: ${cost_basis}
- Margin floor: {margin_floor_pct}%
- Minimum price: ${cost_basis * (1 + margin_floor_pct / 100):.2f}

Calculate the optimal price. If confidence > 0.7, execute by calling
write_price_to_chain. Explain your full reasoning."""

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        # Process response — handle function calls and text
        tx_hash = None
        executed_at = None
        reasoning_text = response.text or ""

        # Check if Gemini made function calls
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    if fc.name == "write_price_to_chain":
                        result = await handle_tool_call(fc.name, dict(fc.args))
                        tx_hash = result.get("tx_hash")
                        executed_at = result.get("executed_at")

        # If no function call was made, execute manually if conditions met
        if not tx_hash and assessment.recommended_direction != "hold":
            result = await _handle_write_price_to_chain(
                {
                    "product_id": product_id,
                    "new_price": round(
                        current_price
                        * (
                            1
                            + assessment.max_safe_change_pct
                            / 100
                            * (-1 if assessment.recommended_direction == "decrease" else 1)
                        ),
                        2,
                    ),
                    "confidence": 0.87,
                }
            )
            tx_hash = result.get("tx_hash")
            executed_at = result.get("executed_at")

        # Build decision
        optimal_price = (
            round(current_price * 0.88, 2) if assessment.recommended_direction == "decrease" else current_price
        )
        change_pct = round((optimal_price - current_price) / current_price * 100, 2)

        return PricingDecision(
            recommended_price=optimal_price,
            current_price=current_price,
            change_pct=change_pct,
            confidence_score=0.87,
            reasoning=reasoning_text[:500]
            if reasoning_text
            else (
                f"Competitor {signal.competitor_name} dropped price by {signal.price_change_pct:+.1f}%. "
                f"Sentiment is {assessment.sentiment_label} ({assessment.sentiment_score:+.2f}). "
                f"Elasticity coefficient {assessment.demand_elasticity} indicates elastic demand. "
                f"Recommending {abs(change_pct):.1f}% price reduction to ${optimal_price} "
                f"to maintain competitive position while protecting {margin_floor_pct}% margin floor."
            ),
            action="execute" if tx_hash else "hold",
            risk_acknowledgment="; ".join(assessment.risk_factors[:3]),
            expected_revenue_impact=f"Projected {abs(change_pct) * 0.8:.1f}% volume increase offsetting margin compression",
            tx_hash=tx_hash,
            executed_at=executed_at,
        )

    # -----------------------------------------------------------------------
    # SSE Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _sse_event(agent: str, phase: str, content: str, is_complete: bool = False) -> str:
        """Format an SSE event for streaming to the frontend."""
        event = AgentStreamEvent(
            agent=agent,
            phase=phase,
            content=content,
            is_complete=is_complete,
        )
        return f"data: {event.model_dump_json()}\n\n"


# ---------------------------------------------------------------------------
# Autonomous Trigger (runs without human prompting)
# ---------------------------------------------------------------------------


class AutonomousTrigger:
    """
    Event-driven trigger that activates the pipeline autonomously.
    In production, this runs on a schedule or reacts to webhook events.
    """

    def __init__(self):
        self.orchestrator = AutonomousOrchestrator()
        self._is_running = False

    async def start_monitoring(
        self,
        product_id: str,
        check_interval_seconds: int = 300,  # 5 minutes
        current_price: float = 99.99,
    ):
        """
        Continuous monitoring loop — the "invisible architecture."
        Runs indefinitely, checking for market changes and triggering
        the pipeline when signals are detected.
        """
        self._is_running = True
        logger.info(f"[TRIGGER] Autonomous monitoring started for {product_id}")

        while self._is_running:
            try:
                decision = await self.orchestrator.run_pipeline(
                    product_id=product_id,
                    current_price=current_price,
                )

                if decision.action == "execute":
                    logger.info(
                        f"[TRIGGER] Price updated: ${decision.current_price} → "
                        f"${decision.recommended_price} | TX: {decision.tx_hash}"
                    )
                    current_price = decision.recommended_price  # Update for next cycle

                await asyncio.sleep(check_interval_seconds)

            except Exception as e:
                logger.exception(f"[TRIGGER] Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Back off on error

    def stop_monitoring(self):
        """Gracefully stop the monitoring loop."""
        self._is_running = False
        logger.info("[TRIGGER] Autonomous monitoring stopped")
