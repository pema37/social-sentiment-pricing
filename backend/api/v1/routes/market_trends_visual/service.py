"""
Market Trends Visual - Service Layer

Contains the MarketTrendsAnalyzer class with all business logic:
- Observer Agent: Scans market data and visual patterns
- Analyst Agent: Interprets trends and correlations
- Forecaster Agent: Predicts trends and recommends actions

This is the core intelligence of the market trends visual system.
"""

import json
from collections.abc import AsyncGenerator

from core.logging import get_logger
from services.ai_trend_analysis.ai_clients import ThoughtType, ai_clients

from .schemas import TrendAgent, TrendMessage

logger = get_logger(__name__)


class MarketTrendsAnalyzer:
    """
    Orchestrates multi-agent market trend analysis.

    Flow:
    1. Observer Agent scans market data and visual charts
    2. Analyst Agent interprets patterns and identifies drivers
    3. Forecaster Agent predicts trends and recommends actions

    Supports multimodal analysis with chart/graph images.
    """

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model

        # Analysis thresholds
        self.significant_sentiment_change = 0.2  # 20% change is significant
        self.high_volume_multiplier = 1.5  # 1.5x normal volume
        self.min_confidence = 0.4  # Minimum forecast confidence

    # =========================================================================
    # OBSERVER AGENT
    # =========================================================================

    async def run_observer_agent(
        self, product: str, category: str, market_data: dict, image_analysis: str | None = None
    ) -> AsyncGenerator[TrendMessage]:
        """
        Observer Agent: Scans market data and identifies patterns.
        """
        yield TrendMessage(
            agent=TrendAgent.OBSERVER,
            thought_type=ThoughtType.OBSERVATION.value,
            content=f"🔍 Observer Agent activated. Scanning market data for {product}...",
        )

        data_summary = self._format_market_data(market_data)
        visual_context = f"\n\nVISUAL CHART ANALYSIS:\n{image_analysis}" if image_analysis else ""

        observer_prompt = self._build_observer_prompt(product, category, data_summary, visual_context)

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(observer_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                thought_type = self._classify_observer_thought(chunk.text)
                yield TrendMessage(agent=TrendAgent.OBSERVER, thought_type=thought_type, content=chunk.text)

        observations = self._extract_observations(full_response, market_data)

        yield TrendMessage(
            agent=TrendAgent.OBSERVER,
            thought_type=ThoughtType.DECISION.value,
            content=f"\n\n✅ Observation complete. Key signals: {len(observations.get('signals', []))} identified.",
            is_final=True,
            metadata={"observations": observations, "full_analysis": full_response},
        )

    # =========================================================================
    # ANALYST AGENT
    # =========================================================================

    async def run_analyst_agent(
        self, product: str, category: str, market_data: dict, observations: dict
    ) -> AsyncGenerator[TrendMessage]:
        """
        Analyst Agent: Interprets patterns and identifies drivers, risks, opportunities.
        """
        yield TrendMessage(
            agent=TrendAgent.ANALYST,
            thought_type=ThoughtType.OBSERVATION.value,
            content="📊 Analyst Agent activated. Analyzing correlations and trend drivers...",
        )

        analyst_prompt = self._build_analyst_prompt(product, category, market_data, observations)

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(analyst_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                thought_type = self._classify_analyst_thought(chunk.text)
                yield TrendMessage(agent=TrendAgent.ANALYST, thought_type=thought_type, content=chunk.text)

        analysis = self._parse_analyst_json(full_response)

        yield TrendMessage(
            agent=TrendAgent.ANALYST,
            thought_type=ThoughtType.DECISION.value,
            content=f"\n\n✅ Analysis complete. Trend: {analysis.get('trend_strength', 'moderate').upper()} | Stage: {analysis.get('trend_stage', 'mid')}",
            is_final=True,
            metadata={"analysis": analysis, "full_analysis": full_response},
        )

    # =========================================================================
    # FORECASTER AGENT
    # =========================================================================

    async def run_forecaster_agent(
        self, product: str, category: str, market_data: dict, observations: dict, analysis: dict
    ) -> AsyncGenerator[TrendMessage]:
        """
        Forecaster Agent: Predicts trends and recommends pricing actions.
        """
        yield TrendMessage(
            agent=TrendAgent.FORECASTER,
            thought_type=ThoughtType.OBSERVATION.value,
            content="🎯 Forecaster Agent activated. Generating forecasts and recommendations...",
        )

        forecaster_prompt = self._build_forecaster_prompt(product, category, market_data, analysis)

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(forecaster_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                thought_type = self._classify_forecaster_thought(chunk.text)
                yield TrendMessage(agent=TrendAgent.FORECASTER, thought_type=thought_type, content=chunk.text)

        forecast = self._parse_forecaster_json(full_response)

        direction = forecast.get("direction", "stable").upper()
        confidence = forecast.get("confidence", 50)
        action = forecast.get("recommended_action", "monitor")

        yield TrendMessage(
            agent=TrendAgent.FORECASTER,
            thought_type=ThoughtType.RECOMMENDATION.value,
            content=f"\n\n✅ Forecast complete. Direction: {direction} | Confidence: {confidence}% | Action: {action}",
            is_final=True,
            metadata={"forecast": forecast, "full_analysis": full_response},
        )

    # =========================================================================
    # IMAGE ANALYSIS
    # =========================================================================

    async def analyze_image(self, image_bytes: bytes, image_type: str, product: str, category: str) -> str:
        """Analyze a market trend chart/graph image."""
        image_prompt = self._build_image_prompt(product, category)

        try:
            response = ""
            async for chunk in ai_clients.analyze_image_stream(image_bytes, image_type, image_prompt, model=self.model):
                if chunk.text:
                    response += chunk.text
            return response
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return f"Image analysis failed: {e!s}"

    # =========================================================================
    # FULL ORCHESTRATION
    # =========================================================================

    async def analyze_stream(
        self, product: str, category: str, market_data: dict, image_bytes: bytes | None = None, image_type: str = "png"
    ) -> AsyncGenerator[TrendMessage]:
        """
        Run the full trend analysis pipeline.

        Args:
            product: Product name being analyzed
            category: Product category
            market_data: Dictionary of market metrics
            image_bytes: Optional chart/graph image for visual analysis
            image_type: Image MIME subtype (png, jpeg, etc.)

        Yields:
            TrendMessage objects from each agent in sequence
        """
        # Step 0: Analyze image if provided
        image_analysis = None
        if image_bytes:
            yield TrendMessage(
                agent=TrendAgent.OBSERVER,
                thought_type=ThoughtType.OBSERVATION.value,
                content="📸 Analyzing visual chart data...",
            )
            image_analysis = await self.analyze_image(image_bytes, image_type, product, category)
            yield TrendMessage(
                agent=TrendAgent.OBSERVER,
                thought_type=ThoughtType.OBSERVATION.value,
                content="Visual analysis complete. Identified chart patterns and trends.",
            )

        # Phase 1: Observer Agent
        observations = {}
        async for msg in self.run_observer_agent(product, category, market_data, image_analysis):
            yield msg
            if msg.is_final and msg.metadata.get("observations"):
                observations = msg.metadata["observations"]

        # Phase 2: Analyst Agent
        analysis = {}
        async for msg in self.run_analyst_agent(product, category, market_data, observations):
            yield msg
            if msg.is_final and msg.metadata.get("analysis"):
                analysis = msg.metadata["analysis"]

        # Phase 3: Forecaster Agent
        async for msg in self.run_forecaster_agent(product, category, market_data, observations, analysis):
            yield msg

    # =========================================================================
    # PROMPT BUILDERS
    # =========================================================================

    def _build_observer_prompt(self, product: str, category: str, data_summary: str, visual_context: str) -> str:
        return f"""You are a Market Observer agent analyzing trends for {product} in the {category} category.

MARKET DATA SUMMARY:
{data_summary}
{visual_context}

Your task is to scan and identify patterns:

1. OBSERVATION: What is the current state of each metric?
   - Sentiment level and direction
   - Volume patterns and anomalies
   - Price movement characteristics
   - Social media activity levels

2. OBSERVATION: What does the visual chart show (if provided)?
   - Trend direction visible in the chart
   - Key inflection points or reversals
   - Volume/activity correlation with price
   - Any visual anomalies or patterns

3. PATTERN: What recurring patterns do you identify?
   - Cyclical patterns (daily, weekly, seasonal)
   - Correlation between metrics
   - Historical pattern recognition

4. SIGNAL: What notable signals should we track?
   - Early warning signals
   - Breakout or breakdown indicators
   - Divergences between metrics

5. OBSERVATION: How does this compare to typical {category} trends?

Be specific about numbers and percentages.
Flag any metrics that are outside normal ranges."""

    def _build_analyst_prompt(self, product: str, category: str, market_data: dict, observations: dict) -> str:
        return f"""You are a Market Analyst interpreting trends for {product} in {category}.

OBSERVER FINDINGS:
{observations.get("full_analysis", "No observations available")}

CURRENT METRICS:
- Sentiment: {market_data.get("sentiment_score", "N/A")} (trend: {market_data.get("sentiment_trend", "stable")})
- 7-day price change: {market_data.get("price_change_7d", 0)}%
- 30-day price change: {market_data.get("price_change_30d", 0)}%
- Volume trend: {market_data.get("volume_trend", "stable")}
- Social mentions: {market_data.get("social_mentions", 0)} (trend: {market_data.get("social_trend", "stable")})
- Competitor activity: {market_data.get("competitor_activity", "normal")}
- Market position: {market_data.get("market_position", "mid")}

Your task is to provide deep analysis:

1. INSIGHT: What key insights emerge from correlating the data?
2. DRIVER: What is driving the current trend?
3. ANALYSIS: How strong is the current trend?
4. RISK: What risks do you identify?
5. OPPORTUNITY: What opportunities exist?
6. ANALYSIS: What would need to change to reverse this trend?

End with a JSON summary:
```json
{{
  "trend_strength": "weak/moderate/strong",
  "trend_stage": "early/mid/late",
  "primary_driver": "description",
  "key_risks": ["risk1", "risk2"],
  "key_opportunities": ["opp1", "opp2"],
  "reversal_probability": 0-100,
  "confidence": 0-100
}}
```"""

    def _build_forecaster_prompt(self, product: str, category: str, market_data: dict, analysis: dict) -> str:
        return f"""You are a Market Forecaster for {product} in {category}.

ANALYST FINDINGS:
- Trend strength: {analysis.get("trend_strength", "moderate")}
- Trend stage: {analysis.get("trend_stage", "mid")}
- Primary driver: {analysis.get("primary_driver", "unknown")}
- Reversal probability: {analysis.get("reversal_probability", 50)}%
- Analysis confidence: {analysis.get("confidence", 50)}%

CURRENT STATE:
- Sentiment: {market_data.get("sentiment_score", 0)} (trend: {market_data.get("sentiment_trend", "stable")})
- 7-day price change: {market_data.get("price_change_7d", 0)}%
- Volume trend: {market_data.get("volume_trend", "stable")}
- Competitor pressure: {market_data.get("competitor_activity", "normal")}

KEY RISKS: {", ".join(analysis.get("key_risks", ["none identified"]))}
KEY OPPORTUNITIES: {", ".join(analysis.get("key_opportunities", ["none identified"]))}

Your task is to forecast and recommend:

1. FORECAST: Short-term prediction (1-2 weeks)
2. OUTLOOK: Medium-term outlook (1-3 months)
3. RECOMMENDATION: Pricing action
4. TIMING: When to act
5. RECOMMENDATION: Risk mitigation
6. MONITORING: What to watch

End with a comprehensive JSON forecast:
```json
{{
  "direction": "strong_up/up/stable/down/strong_down",
  "confidence": 0-100,
  "short_term_change": -10 to +10,
  "medium_term_outlook": "bullish/neutral/bearish",
  "recommended_action": "specific action description",
  "price_adjustment_percent": -20 to +20 or null,
  "timing": "immediate/this_week/next_2_weeks/wait_and_monitor",
  "key_triggers": ["trigger1", "trigger2"],
  "monitoring_metrics": ["metric1", "metric2"],
  "risk_mitigation": "strategy description",
  "review_in_days": 7
}}
```

Be decisive and specific. Provide actionable recommendations."""

    def _build_image_prompt(self, product: str, category: str) -> str:
        return f"""Analyze this market trend chart/graph for {product} in the {category} category.

Extract:
1. CHART TYPE: What kind of chart? (line, bar, candlestick, etc.)
2. TIME RANGE: What time period?
3. TREND DIRECTION: Overall direction, strength, acceleration
4. KEY INFLECTION POINTS: Peaks, troughs, reversals
5. VOLUME/ACTIVITY PATTERNS: If shown, describe patterns
6. SUPPORT/RESISTANCE LEVELS: Key price levels
7. PATTERNS: Technical patterns (head & shoulders, double top, etc.)
8. ANOMALIES: Unusual spikes, drops, gaps
9. COMPARISON: If multiple lines, what do they represent?

Be specific about values, percentages, and dates where visible."""

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _format_market_data(self, data: dict) -> str:
        """Format market data for prompt."""
        lines = [
            "📈 SENTIMENT",
            f"   Score: {data.get('sentiment_score', 'N/A')} (-1 to +1 scale)",
            f"   Trend: {data.get('sentiment_trend', 'stable')}",
            "",
            "📊 VOLUME",
            f"   24h Volume: {data.get('volume_24h', 'N/A')}",
            f"   Trend: {data.get('volume_trend', 'stable')}",
            "",
            "💰 PRICE",
            f"   7-day change: {data.get('price_change_7d', 0)}%",
            f"   30-day change: {data.get('price_change_30d', 0)}%",
            "",
            "📱 SOCIAL",
            f"   Mentions: {data.get('social_mentions', 0)}",
            f"   Trend: {data.get('social_trend', 'stable')}",
            "",
            "🏢 COMPETITIVE",
            f"   Competitor activity: {data.get('competitor_activity', 'normal')}",
            f"   Market position: {data.get('market_position', 'mid')}",
            "",
            "📅 SEASONAL",
            f"   Seasonality: {data.get('seasonality', 'normal')}",
        ]
        return "\n".join(lines)

    def _classify_observer_thought(self, text: str) -> str:
        """All observer thoughts are observations."""
        return ThoughtType.OBSERVATION.value

    def _classify_analyst_thought(self, text: str) -> str:
        """Classify analyst thought type."""
        text_lower = text.lower()
        if "because" in text_lower or "likely due to" in text_lower or "hypothesis" in text_lower:
            return ThoughtType.HYPOTHESIS.value
        return ThoughtType.ANALYSIS.value

    def _classify_forecaster_thought(self, text: str) -> str:
        """Classify forecaster thought type."""
        text_lower = text.lower()
        if "recommend" in text_lower or "should" in text_lower or "action" in text_lower:
            return ThoughtType.RECOMMENDATION.value
        elif "decide" in text_lower or "conclusion" in text_lower or "final" in text_lower:
            return ThoughtType.DECISION.value
        return ThoughtType.HYPOTHESIS.value

    def _extract_observations(self, response: str, market_data: dict) -> dict:
        """Extract structured observations from response."""
        signals = []

        sentiment = market_data.get("sentiment_score", 0)
        if abs(sentiment) > 0.5:
            signals.append(f"Strong sentiment: {sentiment}")

        price_change = market_data.get("price_change_7d", 0)
        if abs(price_change) > 10:
            signals.append(f"Significant price movement: {price_change}%")

        volume_trend = market_data.get("volume_trend", "stable")
        if volume_trend in ["up", "strong_up"]:
            signals.append("Rising volume trend")

        return {"signals": signals, "full_analysis": response}

    def _parse_analyst_json(self, response: str) -> dict:
        """Parse analyst JSON output."""
        default = {
            "trend_strength": "moderate",
            "trend_stage": "mid",
            "primary_driver": "market conditions",
            "key_risks": [],
            "key_opportunities": [],
            "reversal_probability": 50,
            "confidence": 50,
        }
        return self._extract_json(response, default)

    def _parse_forecaster_json(self, response: str) -> dict:
        """Parse forecaster JSON output."""
        default = {
            "direction": "stable",
            "confidence": 50,
            "short_term_change": 0,
            "medium_term_outlook": "neutral",
            "recommended_action": "continue monitoring",
            "price_adjustment_percent": None,
            "timing": "wait_and_monitor",
            "key_triggers": [],
            "monitoring_metrics": [],
            "review_in_days": 7,
        }
        return self._extract_json(response, default)

    def _extract_json(self, response: str, default: dict) -> dict:
        """Extract JSON from response text."""
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                start = response.rfind("{")
                end = response.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response[start:end]
                else:
                    return default

            parsed = json.loads(json_str.strip())
            return {**default, **parsed}

        except Exception as e:
            logger.warning(f"Failed to parse JSON: {e}")
            return default


# Singleton instance for easy import
market_trends_analyzer = MarketTrendsAnalyzer()
