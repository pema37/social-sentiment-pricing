"""
Market Trends Visual Analyzer - Multi-Agent Trend Analysis System

Agents:
1. Observer Agent - Scans market data and visual charts for patterns
2. Analyst Agent - Interprets correlations, drivers, and risks
3. Forecaster Agent - Predicts trends and recommends pricing actions

Uses Gemini 3 streaming with multimodal support for chart/graph analysis.
"""

import json
import base64
from typing import AsyncGenerator, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from core.logging import get_logger
from services.ai_trend_analysis.ai_clients import ai_clients, ThoughtType

logger = get_logger(__name__)


class TrendAgent(str, Enum):
    """The three agents in our trend analysis system."""
    OBSERVER = "observer"
    ANALYST = "analyst"
    FORECASTER = "forecaster"


class TrendDirection(str, Enum):
    """Trend direction classifications."""
    STRONG_UP = "strong_up"
    UP = "up"
    STABLE = "stable"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


class TrendTimeframe(str, Enum):
    """Timeframes for trend analysis."""
    IMMEDIATE = "immediate"  # 24-48 hours
    SHORT_TERM = "short_term"  # 1-2 weeks
    MEDIUM_TERM = "medium_term"  # 1-3 months
    LONG_TERM = "long_term"  # 3+ months


@dataclass
class TrendMessage:
    """A message from an agent during trend analysis."""
    agent: TrendAgent
    thought_type: Optional[ThoughtType]
    content: str
    is_final: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class MarketDataPoint:
    """Market data for trend analysis."""
    sentiment_score: float = 0.0  # -1.0 to 1.0
    sentiment_trend: str = "stable"  # up, down, stable
    volume_24h: int = 0
    volume_trend: str = "stable"
    price_change_7d: float = 0.0
    price_change_30d: float = 0.0
    social_mentions: int = 0
    social_trend: str = "stable"
    competitor_activity: str = "normal"
    market_position: str = "mid"
    seasonality: str = "normal"


@dataclass
class TrendForecast:
    """Final trend forecast from the system."""
    direction: TrendDirection
    confidence: float
    timeframe: TrendTimeframe
    recommended_action: str
    price_adjustment: Optional[float] = None
    key_drivers: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    monitoring_points: List[str] = field(default_factory=list)


class MarketTrendsAnalyzer:
    """
    Orchestrates multi-agent market trend analysis.
    
    Flow:
    1. Observer Agent scans market data and visual charts
    2. Analyst Agent interprets patterns and identifies drivers
    3. Forecaster Agent predicts trends and recommends actions
    
    Supports multimodal analysis with chart/graph images.
    """
    
    def __init__(self):
        self.model = "gemini-2.0-flash"
        
        # Analysis thresholds
        self.significant_sentiment_change = 0.2  # 20% change is significant
        self.high_volume_multiplier = 1.5  # 1.5x normal volume
        self.min_confidence = 0.4  # Minimum forecast confidence
    
    # =========================================================================
    # OBSERVER AGENT - Scan market data and visual patterns
    # =========================================================================
    
    async def run_observer_agent(
        self,
        product: str,
        category: str,
        market_data: dict,
        image_analysis: Optional[str] = None
    ) -> AsyncGenerator[TrendMessage, None]:
        """
        Observer Agent: Scans market data and identifies patterns.
        
        Yields TrendMessage objects with real-time observations.
        """
        yield TrendMessage(
            agent=TrendAgent.OBSERVER,
            thought_type=ThoughtType.OBSERVATION,
            content=f"🔍 Observer Agent activated. Scanning market data for {product}..."
        )
        
        # Prepare formatted data summary
        data_summary = self._format_market_data(market_data)
        visual_context = f"\n\nVISUAL CHART ANALYSIS:\n{image_analysis}" if image_analysis else ""
        
        observer_prompt = f"""You are a Market Observer agent analyzing trends for {product} in the {category} category.

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

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(observer_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                # Determine thought type from content
                thought_type = self._classify_observer_thought(chunk.text)
                yield TrendMessage(
                    agent=TrendAgent.OBSERVER,
                    thought_type=thought_type,
                    content=chunk.text
                )
        
        # Extract key observations
        observations = self._extract_observations(full_response, market_data)
        
        yield TrendMessage(
            agent=TrendAgent.OBSERVER,
            thought_type=ThoughtType.DECISION,
            content=f"\n\n✅ Observation complete. Key signals: {len(observations.get('signals', []))} identified.",
            is_final=True,
            metadata={
                "observations": observations,
                "full_analysis": full_response
            }
        )
    
    # =========================================================================
    # ANALYST AGENT - Interpret trends and correlations
    # =========================================================================
    
    async def run_analyst_agent(
        self,
        product: str,
        category: str,
        market_data: dict,
        observations: dict
    ) -> AsyncGenerator[TrendMessage, None]:
        """
        Analyst Agent: Interprets patterns and identifies drivers, risks, opportunities.
        """
        yield TrendMessage(
            agent=TrendAgent.ANALYST,
            thought_type=ThoughtType.OBSERVATION,
            content="📊 Analyst Agent activated. Analyzing correlations and trend drivers..."
        )
        
        analyst_prompt = f"""You are a Market Analyst interpreting trends for {product} in {category}.

OBSERVER FINDINGS:
{observations.get('full_analysis', 'No observations available')}

CURRENT METRICS:
- Sentiment: {market_data.get('sentiment_score', 'N/A')} (trend: {market_data.get('sentiment_trend', 'stable')})
- 7-day price change: {market_data.get('price_change_7d', 0)}%
- 30-day price change: {market_data.get('price_change_30d', 0)}%
- Volume trend: {market_data.get('volume_trend', 'stable')}
- Social mentions: {market_data.get('social_mentions', 0)} (trend: {market_data.get('social_trend', 'stable')})
- Competitor activity: {market_data.get('competitor_activity', 'normal')}
- Market position: {market_data.get('market_position', 'mid')}

Your task is to provide deep analysis:

1. INSIGHT: What key insights emerge from correlating the data?
   - Sentiment vs price correlation
   - Volume vs social mention correlation
   - Leading vs lagging indicators

2. DRIVER: What is driving the current trend?
   - Primary driver (most influential factor)
   - Secondary drivers
   - External factors (market, competitors, seasonal)

3. ANALYSIS: How strong is the current trend?
   - Trend strength (weak/moderate/strong)
   - Trend maturity (early/mid/late stage)
   - Reversal probability

4. RISK: What risks do you identify?
   - Downside risks to current position
   - Volatility risks
   - Competitive risks
   - External/market risks

5. OPPORTUNITY: What opportunities exist?
   - Pricing opportunities
   - Market positioning opportunities
   - Timing opportunities

6. ANALYSIS: What would need to change to reverse this trend?
   - Key reversal triggers
   - Warning signs to monitor

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

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(analyst_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                thought_type = self._classify_analyst_thought(chunk.text)
                yield TrendMessage(
                    agent=TrendAgent.ANALYST,
                    thought_type=thought_type,
                    content=chunk.text
                )
        
        # Parse analysis results
        analysis = self._parse_analyst_json(full_response)
        
        yield TrendMessage(
            agent=TrendAgent.ANALYST,
            thought_type=ThoughtType.DECISION,
            content=f"\n\n✅ Analysis complete. Trend: {analysis.get('trend_strength', 'moderate').upper()} | Stage: {analysis.get('trend_stage', 'mid')}",
            is_final=True,
            metadata={
                "analysis": analysis,
                "full_analysis": full_response
            }
        )
    
    # =========================================================================
    # FORECASTER AGENT - Predict trends and recommend actions
    # =========================================================================
    
    async def run_forecaster_agent(
        self,
        product: str,
        category: str,
        market_data: dict,
        observations: dict,
        analysis: dict
    ) -> AsyncGenerator[TrendMessage, None]:
        """
        Forecaster Agent: Predicts trends and recommends pricing actions.
        """
        yield TrendMessage(
            agent=TrendAgent.FORECASTER,
            thought_type=ThoughtType.OBSERVATION,
            content="🎯 Forecaster Agent activated. Generating forecasts and recommendations..."
        )
        
        forecaster_prompt = f"""You are a Market Forecaster for {product} in {category}.

ANALYST FINDINGS:
- Trend strength: {analysis.get('trend_strength', 'moderate')}
- Trend stage: {analysis.get('trend_stage', 'mid')}
- Primary driver: {analysis.get('primary_driver', 'unknown')}
- Reversal probability: {analysis.get('reversal_probability', 50)}%
- Analysis confidence: {analysis.get('confidence', 50)}%

CURRENT STATE:
- Sentiment: {market_data.get('sentiment_score', 0)} (trend: {market_data.get('sentiment_trend', 'stable')})
- 7-day price change: {market_data.get('price_change_7d', 0)}%
- Volume trend: {market_data.get('volume_trend', 'stable')}
- Competitor pressure: {market_data.get('competitor_activity', 'normal')}

KEY RISKS: {', '.join(analysis.get('key_risks', ['none identified']))}
KEY OPPORTUNITIES: {', '.join(analysis.get('key_opportunities', ['none identified']))}

Your task is to forecast and recommend:

1. FORECAST: Short-term prediction (1-2 weeks)
   - Direction (strong_up/up/stable/down/strong_down)
   - Magnitude (percentage change expected)
   - Confidence level

2. OUTLOOK: Medium-term outlook (1-3 months)
   - Expected trajectory
   - Key milestones or inflection points
   - Scenario analysis (bull/bear/base case)

3. RECOMMENDATION: Pricing action
   - Specific pricing recommendation
   - Percentage adjustment if any
   - Rationale for recommendation

4. TIMING: When to act
   - Optimal timing for action
   - Triggers that should prompt action
   - Conditions to wait for

5. RECOMMENDATION: Risk mitigation
   - How to protect against downside
   - Hedging strategies if applicable

6. MONITORING: What to watch
   - Key metrics to monitor
   - Alert thresholds
   - Review frequency

End with a comprehensive JSON forecast:
```json
{{
  "direction": "strong_up/up/stable/down/strong_down",
  "confidence": 0-100,
  "short_term_change": -10 to +10 (percentage),
  "medium_term_outlook": "bullish/neutral/bearish",
  "recommended_action": "specific action description",
  "price_adjustment_percent": -20 to +20 or null,
  "timing": "immediate/this_week/next_2_weeks/wait_and_monitor",
  "key_triggers": ["trigger1", "trigger2"],
  "monitoring_metrics": ["metric1", "metric2"],
  "risk_mitigation": "strategy description",
  "review_in_days": 7,
  "alternative_scenarios": {{
    "bull_case": "description",
    "bear_case": "description"
  }}
}}
```

Be decisive and specific. Provide actionable recommendations."""

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(forecaster_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                thought_type = self._classify_forecaster_thought(chunk.text)
                yield TrendMessage(
                    agent=TrendAgent.FORECASTER,
                    thought_type=thought_type,
                    content=chunk.text
                )
        
        # Parse forecast
        forecast = self._parse_forecaster_json(full_response)
        
        direction = forecast.get('direction', 'stable').upper()
        confidence = forecast.get('confidence', 50)
        action = forecast.get('recommended_action', 'monitor')
        
        yield TrendMessage(
            agent=TrendAgent.FORECASTER,
            thought_type=ThoughtType.RECOMMENDATION,
            content=f"\n\n✅ Forecast complete. Direction: {direction} | Confidence: {confidence}% | Action: {action}",
            is_final=True,
            metadata={
                "forecast": forecast,
                "full_analysis": full_response
            }
        )
    
    # =========================================================================
    # IMAGE ANALYSIS
    # =========================================================================
    
    async def analyze_image(
        self,
        image_bytes: bytes,
        image_type: str,
        product: str,
        category: str
    ) -> str:
        """
        Analyze a market trend chart/graph image.
        
        Returns text description of visual analysis.
        """
        image_prompt = f"""Analyze this market trend chart/graph for {product} in the {category} category.

Extract the following information:

1. CHART TYPE: What kind of chart is this? (line, bar, candlestick, etc.)

2. TIME RANGE: What time period does the chart cover?

3. TREND DIRECTION: 
   - Overall direction (up, down, sideways)
   - Strength of trend
   - Any acceleration or deceleration

4. KEY INFLECTION POINTS:
   - Significant peaks and troughs
   - Dates/times of major changes
   - Reversal patterns

5. VOLUME/ACTIVITY PATTERNS:
   - If volume is shown, describe the pattern
   - Correlation between volume and price
   - Any divergences

6. SUPPORT/RESISTANCE LEVELS:
   - Key price levels where trend paused
   - Potential future support/resistance

7. PATTERNS:
   - Technical patterns (head & shoulders, double top/bottom, etc.)
   - Trend channels or ranges
   - Breakout or breakdown signals

8. ANOMALIES:
   - Any unusual spikes or drops
   - Gaps in the data
   - Outliers

9. COMPARISON:
   - If multiple lines, what do they represent?
   - Which is outperforming?

Be specific about values, percentages, and dates where visible."""

        try:
            response = ""
            async for chunk in ai_clients.analyze_image_stream(
                image_bytes, image_type, image_prompt, model=self.model
            ):
                if chunk.text:
                    response += chunk.text
            return response
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return f"Image analysis failed: {str(e)}"
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _format_market_data(self, data: dict) -> str:
        """Format market data for prompt."""
        lines = [
            f"📈 SENTIMENT",
            f"   Score: {data.get('sentiment_score', 'N/A')} (-1 to +1 scale)",
            f"   Trend: {data.get('sentiment_trend', 'stable')}",
            f"",
            f"📊 VOLUME",
            f"   24h Volume: {data.get('volume_24h', 'N/A')}",
            f"   Trend: {data.get('volume_trend', 'stable')}",
            f"",
            f"💰 PRICE",
            f"   7-day change: {data.get('price_change_7d', 0)}%",
            f"   30-day change: {data.get('price_change_30d', 0)}%",
            f"",
            f"📱 SOCIAL",
            f"   Mentions: {data.get('social_mentions', 0)}",
            f"   Trend: {data.get('social_trend', 'stable')}",
            f"",
            f"🏢 COMPETITIVE",
            f"   Competitor activity: {data.get('competitor_activity', 'normal')}",
            f"   Market position: {data.get('market_position', 'mid')}",
            f"",
            f"📅 SEASONAL",
            f"   Seasonality: {data.get('seasonality', 'normal')}"
        ]
        return "\n".join(lines)
    
    def _classify_observer_thought(self, text: str) -> ThoughtType:
        """Classify observer thought type from content.
        
        All observer outputs map to OBSERVATION since patterns/signals
        are types of observations.
        """
        # All observer thoughts are observations
        return ThoughtType.OBSERVATION
    
    def _classify_analyst_thought(self, text: str) -> ThoughtType:
        """Classify analyst thought type from content.
        
        Maps to valid ThoughtType values:
        - Insights, correlations, drivers, risks, opportunities → ANALYSIS
        - Hypotheses about causes → HYPOTHESIS
        """
        text_lower = text.lower()
        # Hypothesis when speculating about causation
        if "because" in text_lower or "likely due to" in text_lower or "hypothesis" in text_lower:
            return ThoughtType.HYPOTHESIS
        # Everything else is analysis
        return ThoughtType.ANALYSIS
    
    def _classify_forecaster_thought(self, text: str) -> ThoughtType:
        """Classify forecaster thought type from content.
        
        Maps to valid ThoughtType values:
        - Recommendations, actions, timing → RECOMMENDATION
        - Outlooks, forecasts, predictions → HYPOTHESIS
        - Final decisions → DECISION
        """
        text_lower = text.lower()
        if "recommend" in text_lower or "should" in text_lower or "action" in text_lower:
            return ThoughtType.RECOMMENDATION
        elif "decide" in text_lower or "conclusion" in text_lower or "final" in text_lower:
            return ThoughtType.DECISION
        # Outlooks, forecasts, predictions are hypotheses about future
        return ThoughtType.HYPOTHESIS
    
    def _extract_observations(self, response: str, market_data: dict) -> dict:
        """Extract structured observations from response."""
        signals = []
        
        # Check for significant changes that should be flagged
        sentiment = market_data.get('sentiment_score', 0)
        if abs(sentiment) > 0.5:
            signals.append(f"Strong sentiment: {sentiment}")
        
        price_change = market_data.get('price_change_7d', 0)
        if abs(price_change) > 10:
            signals.append(f"Significant price movement: {price_change}%")
        
        volume_trend = market_data.get('volume_trend', 'stable')
        if volume_trend in ['up', 'strong_up']:
            signals.append(f"Rising volume trend")
        
        return {
            "signals": signals,
            "full_analysis": response
        }
    
    def _parse_analyst_json(self, response: str) -> dict:
        """Parse analyst JSON output."""
        default = {
            "trend_strength": "moderate",
            "trend_stage": "mid",
            "primary_driver": "market conditions",
            "key_risks": [],
            "key_opportunities": [],
            "reversal_probability": 50,
            "confidence": 50
        }
        
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                # Try to find raw JSON
                start = response.rfind("{")
                end = response.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response[start:end]
                else:
                    return default
            
            parsed = json.loads(json_str.strip())
            return {**default, **parsed}
            
        except Exception as e:
            logger.warning(f"Failed to parse analyst JSON: {e}")
            return default
    
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
            "review_in_days": 7
        }
        
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
            logger.warning(f"Failed to parse forecaster JSON: {e}")
            return default
    
    # =========================================================================
    # FULL ORCHESTRATION
    # =========================================================================
    
    async def analyze_stream(
        self,
        product: str,
        category: str,
        market_data: dict,
        image_bytes: Optional[bytes] = None,
        image_type: str = "png"
    ) -> AsyncGenerator[TrendMessage, None]:
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
                thought_type=ThoughtType.OBSERVATION,
                content="📸 Analyzing visual chart data..."
            )
            image_analysis = await self.analyze_image(
                image_bytes, image_type, product, category
            )
            yield TrendMessage(
                agent=TrendAgent.OBSERVER,
                thought_type=ThoughtType.OBSERVATION,
                content=f"Visual analysis complete. Identified chart patterns and trends."
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
        async for msg in self.run_forecaster_agent(
            product, category, market_data, observations, analysis
        ):
            yield msg


# Singleton instance
market_trends_analyzer = MarketTrendsAnalyzer()



