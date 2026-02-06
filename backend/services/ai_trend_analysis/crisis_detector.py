"""
AI Crisis Detector - Multi-Agent Monitoring System

Agents:
1. Monitor Agent - Scans sentiment data for anomalies (sudden drops, volume spikes)
2. Investigator Agent - Deep dives into crisis source (what's causing it)
3. Response Agent - Recommends crisis response actions

Uses Gemini 3 streaming with 1M token context for comprehensive analysis.
"""

import json
from typing import Optional, AsyncGenerator, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from decimal import Decimal

from core.logging import get_logger
from services.ai_trend_analysis.ai_clients import (
    ai_clients,
    DEFAULT_MODEL,
    StreamChunk,
    ThoughtType,
)

logger = get_logger(__name__)


class CrisisAgentRole(str, Enum):
    """The three agents in our crisis detection system."""
    MONITOR = "monitor"
    INVESTIGATOR = "investigator"
    RESPONSE = "response"


class CrisisSeverity(str, Enum):
    """Severity levels for detected crises."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CrisisAgentMessage:
    """A message from an agent during crisis analysis."""
    agent: CrisisAgentRole
    thought_type: Optional[ThoughtType]
    content: str
    is_final: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class SentimentDataPoint:
    """A single sentiment data point for analysis."""
    timestamp: datetime
    score: float  # -1.0 to 1.0
    volume: int  # number of mentions
    source: str  # twitter, reddit, news, etc.
    sample_text: Optional[str] = None


@dataclass
class CrisisAlert:
    """Final crisis alert from the system."""
    is_crisis: bool
    severity: CrisisSeverity
    confidence: float
    title: str
    summary: str
    trigger_event: Optional[str] = None
    affected_products: List[str] = field(default_factory=list)
    sentiment_drop_percent: float = 0.0
    volume_spike_percent: float = 0.0
    recommended_actions: List[str] = field(default_factory=list)
    estimated_impact: str = "unknown"
    sources: List[str] = field(default_factory=list)


class CrisisDetector:
    """
    Orchestrates multi-agent crisis detection and analysis.
    
    Flow:
    1. Monitor Agent scans sentiment for anomalies
    2. Investigator Agent identifies the root cause
    3. Response Agent recommends crisis management actions
    
    All agents stream their "thinking" in real-time.
    """
    
    def __init__(self):
        self.model = DEFAULT_MODEL
        
        # Crisis detection thresholds
        self.sentiment_drop_threshold = -0.3  # 30% drop triggers investigation
        self.volume_spike_threshold = 2.0  # 2x normal volume is suspicious
        self.minimum_mentions = 10  # Need at least 10 mentions to analyze
    
    # =========================================================================
    # MONITOR AGENT - Scan sentiment data for anomalies
    # =========================================================================
    
    async def run_monitor_agent(
        self,
        sentiment_data: List[SentimentDataPoint],
        product_name: str,
        baseline_sentiment: float = 0.0
    ) -> AsyncGenerator[CrisisAgentMessage, None]:
        """
        Monitor Agent: Scans sentiment data for crisis indicators.
        
        Yields CrisisAgentMessage objects with real-time thinking.
        """
        yield CrisisAgentMessage(
            agent=CrisisAgentRole.MONITOR,
            thought_type=ThoughtType.OBSERVATION,
            content=f"🔍 Monitor Agent activated. Scanning {len(sentiment_data)} data points for {product_name}..."
        )
        
        # Prepare data summary for Gemini
        data_summary = self._prepare_data_summary(sentiment_data, baseline_sentiment)
        
        monitor_prompt = f"""You are a crisis monitoring agent for brand sentiment analysis.

PRODUCT: {product_name}
BASELINE SENTIMENT: {baseline_sentiment:.2f} (normal level)

RECENT SENTIMENT DATA (last 24-48 hours):
{data_summary}

Your task is to identify potential crisis indicators:

1. OBSERVATION: What patterns do you see in the sentiment data?
2. ANALYSIS: Are there any sudden drops in sentiment scores?
3. ANALYSIS: Are there unusual volume spikes in mentions?
4. HYPOTHESIS: Could any of these indicate a PR crisis or brand issue?
5. DECISION: Is there a potential crisis that needs investigation?

Be specific about timestamps, score changes, and volume changes.
Flag anything where sentiment dropped more than 30% or volume spiked more than 2x."""

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(monitor_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield CrisisAgentMessage(
                    agent=CrisisAgentRole.MONITOR,
                    thought_type=chunk.thought_type or ThoughtType.OBSERVATION,
                    content=chunk.text
                )
        
        # Calculate actual metrics
        anomaly_detected, metrics = self._calculate_anomaly_metrics(
            sentiment_data, baseline_sentiment
        )
        
        status = "⚠️ ANOMALY DETECTED" if anomaly_detected else "✅ No crisis indicators"
        
        yield CrisisAgentMessage(
            agent=CrisisAgentRole.MONITOR,
            thought_type=ThoughtType.DECISION,
            content=f"\n\n{status}. Sentiment change: {metrics['sentiment_change']:.1%}, Volume change: {metrics['volume_change']:.1%}",
            is_final=True,
            metadata={
                "monitoring_result": {
                    "anomaly_detected": anomaly_detected,
                    "sentiment_change": metrics['sentiment_change'],
                    "volume_change": metrics['volume_change'],
                    "current_sentiment": metrics['current_sentiment'],
                    "peak_negative_time": metrics.get('peak_negative_time'),
                    "analysis": full_response
                }
            }
        )
    
    # =========================================================================
    # INVESTIGATOR AGENT - Deep dive into crisis source
    # =========================================================================
    
    async def run_investigator_agent(
        self,
        sentiment_data: List[SentimentDataPoint],
        product_name: str,
        monitoring_result: dict
    ) -> AsyncGenerator[CrisisAgentMessage, None]:
        """
        Investigator Agent: Identifies the root cause of detected anomalies.
        
        Yields CrisisAgentMessage objects with real-time investigation.
        """
        yield CrisisAgentMessage(
            agent=CrisisAgentRole.INVESTIGATOR,
            thought_type=ThoughtType.OBSERVATION,
            content="🔎 Investigator Agent activated. Analyzing crisis source..."
        )
        
        # Get sample negative mentions for analysis
        negative_samples = self._get_negative_samples(sentiment_data, limit=20)
        
        investigate_prompt = f"""You are a crisis investigator analyzing a potential brand crisis.

PRODUCT: {product_name}
DETECTED ANOMALY:
- Sentiment dropped: {monitoring_result.get('sentiment_change', 0):.1%}
- Volume changed: {monitoring_result.get('volume_change', 0):.1%}
- Current sentiment: {monitoring_result.get('current_sentiment', 0):.2f}

SAMPLE NEGATIVE MENTIONS:
{negative_samples}

Investigate the root cause:

1. OBSERVATION: What common themes appear in the negative mentions?
2. ANALYSIS: Is this a product issue, service issue, PR event, or external factor?
3. ANALYSIS: Which platforms/sources are most affected?
4. HYPOTHESIS: What triggered this sentiment shift?
5. DECISION: What is the likely root cause?

Identify specific:
- Trigger event (if identifiable)
- Affected aspects (product quality, customer service, pricing, etc.)
- Scale of impact (isolated incident vs. widespread)"""

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(investigate_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield CrisisAgentMessage(
                    agent=CrisisAgentRole.INVESTIGATOR,
                    thought_type=chunk.thought_type or ThoughtType.ANALYSIS,
                    content=chunk.text
                )
        
        # Determine severity based on metrics and analysis
        severity = self._assess_severity(monitoring_result)
        
        yield CrisisAgentMessage(
            agent=CrisisAgentRole.INVESTIGATOR,
            thought_type=ThoughtType.DECISION,
            content=f"\n\n✅ Investigation complete. Assessed severity: {severity.value.upper()}",
            is_final=True,
            metadata={
                "investigation_result": {
                    "severity": severity.value,
                    "root_cause_analysis": full_response,
                    "sources_affected": self._get_affected_sources(sentiment_data)
                }
            }
        )
    
    # =========================================================================
    # RESPONSE AGENT - Recommend crisis response actions
    # =========================================================================
    
    async def run_response_agent(
        self,
        product_name: str,
        monitoring_result: dict,
        investigation_result: dict
    ) -> AsyncGenerator[CrisisAgentMessage, None]:
        """
        Response Agent: Recommends crisis response actions.
        
        Yields CrisisAgentMessage objects with real-time strategic thinking.
        """
        yield CrisisAgentMessage(
            agent=CrisisAgentRole.RESPONSE,
            thought_type=ThoughtType.OBSERVATION,
            content="🎯 Response Agent activated. Formulating crisis response strategy..."
        )
        
        severity = investigation_result.get('severity', 'medium')
        
        response_prompt = f"""You are a crisis response strategist for brand management.

PRODUCT: {product_name}
CRISIS SEVERITY: {severity.upper()}
SENTIMENT DROP: {monitoring_result.get('sentiment_change', 0):.1%}
VOLUME SPIKE: {monitoring_result.get('volume_change', 0):.1%}

ROOT CAUSE ANALYSIS:
{investigation_result.get('root_cause_analysis', 'Unknown')}

Recommend a crisis response:

1. OBSERVATION: What are the immediate risks to the brand?
2. ANALYSIS: What stakeholders need to be notified?
3. HYPOTHESIS: How might this evolve if unaddressed?
4. RECOMMENDATION: What immediate actions should be taken?
5. RECOMMENDATION: What medium-term strategy should be employed?

Provide specific, actionable recommendations.

End with a JSON block:
```json
{{
  "crisis_title": "Brief title for this crisis",
  "immediate_actions": ["action1", "action2", "action3"],
  "stakeholders_to_notify": ["stakeholder1", "stakeholder2"],
  "communication_strategy": "brief description",
  "estimated_recovery_time": "hours/days/weeks",
  "risk_if_unaddressed": "low/medium/high/critical"
}}
```"""

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(response_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield CrisisAgentMessage(
                    agent=CrisisAgentRole.RESPONSE,
                    thought_type=chunk.thought_type or ThoughtType.RECOMMENDATION,
                    content=chunk.text
                )
        
        # Parse the JSON response
        response_data = self._parse_response_json(full_response)
        
        yield CrisisAgentMessage(
            agent=CrisisAgentRole.RESPONSE,
            thought_type=ThoughtType.RECOMMENDATION,
            content=f"\n\n✅ Response strategy complete: {response_data.get('crisis_title', 'Crisis Response Plan')}",
            is_final=True,
            metadata={
                "response_plan": response_data,
                "full_analysis": full_response
            }
        )
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _prepare_data_summary(
        self, 
        data: List[SentimentDataPoint],
        baseline: float
    ) -> str:
        """Prepare sentiment data as text summary for Gemini."""
        if not data:
            return "No data available"
        
        lines = []
        for dp in sorted(data, key=lambda x: x.timestamp)[-50:]:  # Last 50 points
            time_str = dp.timestamp.strftime("%Y-%m-%d %H:%M")
            diff = dp.score - baseline
            direction = "↑" if diff > 0 else "↓" if diff < 0 else "→"
            lines.append(
                f"[{time_str}] Score: {dp.score:.2f} ({direction}{abs(diff):.2f}) | "
                f"Volume: {dp.volume} mentions | Source: {dp.source}"
            )
            if dp.sample_text:
                lines.append(f"  Sample: \"{dp.sample_text[:100]}...\"")
        
        return "\n".join(lines)
    
    def _calculate_anomaly_metrics(
        self,
        data: List[SentimentDataPoint],
        baseline: float
    ) -> tuple[bool, dict]:
        """Calculate anomaly metrics from sentiment data."""
        if not data:
            return False, {
                'sentiment_change': 0,
                'volume_change': 0,
                'current_sentiment': baseline
            }
        
        # Sort by time
        sorted_data = sorted(data, key=lambda x: x.timestamp)
        
        # Get recent vs older data (split at midpoint)
        midpoint = len(sorted_data) // 2
        old_data = sorted_data[:midpoint] if midpoint > 0 else sorted_data
        recent_data = sorted_data[midpoint:] if midpoint > 0 else sorted_data
        
        # Calculate averages
        old_sentiment = sum(d.score for d in old_data) / len(old_data) if old_data else baseline
        recent_sentiment = sum(d.score for d in recent_data) / len(recent_data) if recent_data else baseline
        
        old_volume = sum(d.volume for d in old_data) / len(old_data) if old_data else 1
        recent_volume = sum(d.volume for d in recent_data) / len(recent_data) if recent_data else 1
        
        # Calculate changes
        sentiment_change = (recent_sentiment - old_sentiment) / max(abs(old_sentiment), 0.1)
        volume_change = (recent_volume - old_volume) / max(old_volume, 1)
        
        # Find peak negative
        most_negative = min(data, key=lambda x: x.score)
        
        # Detect anomaly
        anomaly_detected = (
            sentiment_change < self.sentiment_drop_threshold or
            volume_change > self.volume_spike_threshold
        )
        
        return anomaly_detected, {
            'sentiment_change': sentiment_change,
            'volume_change': volume_change,
            'current_sentiment': recent_sentiment,
            'peak_negative_time': most_negative.timestamp.isoformat(),
            'peak_negative_score': most_negative.score
        }
    
    def _get_negative_samples(
        self, 
        data: List[SentimentDataPoint], 
        limit: int = 20
    ) -> str:
        """Get sample negative mentions for investigation."""
        negative = [d for d in data if d.score < 0 and d.sample_text]
        negative.sort(key=lambda x: x.score)  # Most negative first
        
        if not negative:
            return "No negative samples available"
        
        samples = []
        for d in negative[:limit]:
            samples.append(
                f"[{d.source}] Score: {d.score:.2f}\n\"{d.sample_text}\""
            )
        
        return "\n\n".join(samples)
    
    def _get_affected_sources(self, data: List[SentimentDataPoint]) -> List[str]:
        """Get list of sources with negative sentiment."""
        source_scores = {}
        for d in data:
            if d.source not in source_scores:
                source_scores[d.source] = []
            source_scores[d.source].append(d.score)
        
        # Return sources with negative average
        return [
            source for source, scores in source_scores.items()
            if sum(scores) / len(scores) < 0
        ]
    
    def _assess_severity(self, monitoring_result: dict) -> CrisisSeverity:
        """Assess crisis severity based on metrics."""
        sentiment_change = abs(monitoring_result.get('sentiment_change', 0))
        volume_change = monitoring_result.get('volume_change', 0)
        
        if sentiment_change > 0.6 or volume_change > 5:
            return CrisisSeverity.CRITICAL
        elif sentiment_change > 0.4 or volume_change > 3:
            return CrisisSeverity.HIGH
        elif sentiment_change > 0.2 or volume_change > 1.5:
            return CrisisSeverity.MEDIUM
        elif sentiment_change > 0.1 or volume_change > 0.5:
            return CrisisSeverity.LOW
        else:
            return CrisisSeverity.NONE
    
    def _parse_response_json(self, response: str) -> dict:
        """Parse the JSON response plan from strategist."""
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                return {"crisis_title": "Crisis Response Plan", "immediate_actions": []}
            
            return json.loads(json_str.strip())
        except Exception as e:
            logger.warning(f"Failed to parse response JSON: {e}")
            return {"crisis_title": "Crisis Response Plan", "immediate_actions": []}
    
    # =========================================================================
    # FULL ORCHESTRATION
    # =========================================================================
    
    async def analyze(
        self,
        sentiment_data: List[SentimentDataPoint],
        product_name: str,
        baseline_sentiment: float = 0.0
    ) -> AsyncGenerator[CrisisAgentMessage, None]:
        """
        Run the full crisis detection pipeline.
        
        Args:
            sentiment_data: List of sentiment data points to analyze
            product_name: Name of the product/brand being monitored
            baseline_sentiment: Normal sentiment level (-1.0 to 1.0)
            
        Yields:
            CrisisAgentMessage objects from each agent in sequence
        """
        if len(sentiment_data) < self.minimum_mentions:
            yield CrisisAgentMessage(
                agent=CrisisAgentRole.MONITOR,
                thought_type=ThoughtType.DECISION,
                content=f"⚠️ Insufficient data: {len(sentiment_data)} data points (minimum: {self.minimum_mentions})",
                is_final=True,
                metadata={"error": "insufficient_data"}
            )
            return
        
        # Phase 1: Monitor Agent
        monitoring_result = {}
        async for msg in self.run_monitor_agent(sentiment_data, product_name, baseline_sentiment):
            yield msg
            if msg.is_final and msg.metadata.get("monitoring_result"):
                monitoring_result = msg.metadata["monitoring_result"]
        
        # If no anomaly detected, stop here (early exit)
        if not monitoring_result.get("anomaly_detected", False):
            yield CrisisAgentMessage(
                agent=CrisisAgentRole.MONITOR,
                thought_type=ThoughtType.DECISION,
                content="✅ No crisis indicators detected. Monitoring complete.",
                is_final=True,
                metadata={"status": "all_clear", "monitoring_result": monitoring_result}
            )
            return
        
        # Phase 2: Investigator Agent
        investigation_result = {}
        async for msg in self.run_investigator_agent(sentiment_data, product_name, monitoring_result):
            yield msg
            if msg.is_final and msg.metadata.get("investigation_result"):
                investigation_result = msg.metadata["investigation_result"]
        
        # Phase 3: Response Agent
        async for msg in self.run_response_agent(product_name, monitoring_result, investigation_result):
            yield msg


# Singleton instance
crisis_detector = CrisisDetector()



