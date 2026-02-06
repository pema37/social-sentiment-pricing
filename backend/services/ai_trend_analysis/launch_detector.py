"""
Launch Detector - Multi-Agent Product Launch Detection System

Agents:
1. Scanner Agent - Scans social signals and images for launch indicators
2. Validator Agent - Validates and extracts detailed launch information
3. Assessor Agent - Assesses competitive threat and recommends response

Uses Gemini 3 streaming with multimodal support for image analysis.
"""

import json
from typing import Optional, AsyncGenerator, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from core.logging import get_logger
from services.ai_trend_analysis.ai_clients import (
    ai_clients,
    DEFAULT_MODEL,
    StreamChunk,
    ThoughtType,
)

logger = get_logger(__name__)


class LaunchAgent(str, Enum):
    """The three agents in our launch detection system."""
    SCANNER = "scanner"
    VALIDATOR = "validator"
    ASSESSOR = "assessor"


class ThreatLevel(str, Enum):
    """Threat levels for competitive launches."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LaunchType(str, Enum):
    """Types of product launches detected."""
    NEW_PRODUCT = "new_product"
    MAJOR_UPDATE = "major_update"
    REBRAND = "rebrand"
    EXPANSION = "expansion"
    PRICING_CHANGE = "pricing_change"
    UNKNOWN = "unknown"


@dataclass
class LaunchMessage:
    """A message from an agent during launch analysis."""
    agent: LaunchAgent
    thought_type: Optional[ThoughtType]
    content: str
    is_final: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class LaunchSignal:
    """A signal indicating potential product launch."""
    source: str  # twitter, reddit, screenshot, news, press_release
    content: str  # text content or image description
    url: Optional[str] = None
    timestamp: Optional[datetime] = None
    engagement: int = 0  # likes, shares, comments
    author: Optional[str] = None
    image_data: Optional[bytes] = None
    image_type: str = "png"


@dataclass
class LaunchAlert:
    """Final launch alert from the system."""
    is_launch: bool
    launch_type: LaunchType
    threat_level: ThreatLevel
    confidence: float
    product_name: str
    competitor_name: str
    summary: str
    key_features: List[str] = field(default_factory=list)
    target_market: str = "unknown"
    estimated_price: Optional[str] = None
    launch_date: Optional[str] = None
    recommended_actions: List[str] = field(default_factory=list)
    urgency: str = "monitor"
    sources: List[str] = field(default_factory=list)


class LaunchDetector:
    """
    Orchestrates multi-agent product launch detection and analysis.
    
    Flow:
    1. Scanner Agent analyzes signals (text/images) for launch indicators
    2. Validator Agent confirms launch and extracts detailed information
    3. Assessor Agent evaluates competitive threat and recommends response
    
    All agents stream their "thinking" in real-time.
    """
    
    def __init__(self):
        self.model = DEFAULT_MODEL
        
        # Detection thresholds
        self.min_confidence = 0.3  # Minimum confidence to proceed to validation
        self.min_signals = 1  # Minimum signals needed for analysis
        
        # Launch indicator keywords
        self.launch_keywords = [
            "new product", "launching", "announcing", "introducing",
            "released", "unveiled", "debuting", "available now",
            "coming soon", "pre-order", "just dropped", "brand new"
        ]
    
    # =========================================================================
    # SCANNER AGENT - Detect launch signals from images/text
    # =========================================================================
    
    async def run_scanner_agent(
        self,
        signals: List[LaunchSignal],
        competitor_name: str,
        image_data: Optional[bytes] = None,
        image_type: str = "png"
    ) -> AsyncGenerator[LaunchMessage, None]:
        """
        Scanner Agent: Analyzes signals for product launch indicators.
        
        Handles both text signals and image analysis (multimodal).
        """
        yield LaunchMessage(
            agent=LaunchAgent.SCANNER,
            thought_type=ThoughtType.OBSERVATION,
            content=f"🔍 Scanner Agent activated. Analyzing {len(signals)} signals for {competitor_name}..."
        )
        
        # If we have an image, prioritize multimodal analysis
        if image_data:
            async for msg in self._analyze_image(image_data, image_type, competitor_name):
                yield msg
            return
        
        # Prepare signal summary for Gemini
        signal_summary = self._prepare_signal_summary(signals)
        
        scanner_prompt = f"""You are a competitive intelligence scanner detecting product launches.

COMPETITOR: {competitor_name}
TOTAL SIGNALS: {len(signals)}

SIGNALS TO ANALYZE:
{signal_summary}

Your task is to identify product launch indicators:

1. OBSERVATION: What do these signals tell us about {competitor_name}'s activities?
2. ANALYSIS: Are there any explicit launch announcements?
3. ANALYSIS: What implicit signals suggest a new product (increased buzz, teaser content, etc.)?
4. ANALYSIS: Which platforms show the strongest launch signals?
5. HYPOTHESIS: If there is a launch, what type of product might it be?
6. DECISION: Is there sufficient evidence of a product launch? Rate confidence 0-100%.

Look for:
- Direct announcements ("We're launching...", "Introducing...")
- Teaser campaigns or countdowns
- Unusual engagement spikes
- Press release language
- Product comparisons or competitive mentions

Be specific about which signals support your conclusions."""

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(scanner_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield LaunchMessage(
                    agent=LaunchAgent.SCANNER,
                    thought_type=chunk.thought_type or ThoughtType.OBSERVATION,
                    content=chunk.text
                )
        
        # Analyze response for launch detection
        launch_detected, confidence = self._analyze_scanner_response(full_response, signals)
        
        status = "🚨 LAUNCH SIGNALS DETECTED" if launch_detected else "✅ No launch indicators"
        
        yield LaunchMessage(
            agent=LaunchAgent.SCANNER,
            thought_type=ThoughtType.DECISION,
            content=f"\n\n{status}. Confidence: {confidence:.0%}",
            is_final=True,
            metadata={
                "scan_result": {
                    "launch_detected": launch_detected,
                    "confidence": confidence,
                    "signals_analyzed": len(signals),
                    "sources": self._get_signal_sources(signals),
                    "analysis": full_response
                }
            }
        )
    
    async def _analyze_image(
        self,
        image_data: bytes,
        image_type: str,
        competitor_name: str
    ) -> AsyncGenerator[LaunchMessage, None]:
        """
        Analyze product screenshot/image for launch signals.
        
        Uses Gemini's multimodal capabilities for image understanding.
        """
        yield LaunchMessage(
            agent=LaunchAgent.SCANNER,
            thought_type=ThoughtType.OBSERVATION,
            content=f"📸 Analyzing product image for {competitor_name}..."
        )
        
        image_prompt = f"""You are analyzing a product image/screenshot for competitive intelligence.

COMPETITOR: {competitor_name}

Analyze this image thoroughly:

1. OBSERVATION: What product or announcement do you see?
   - Product name (if visible)
   - Visual design and branding
   - Key features highlighted
   - Pricing (if shown)
   - Release date (if shown)

2. ANALYSIS: Is this a NEW product or existing?
   - What visual cues indicate newness? ("New", "Introducing", launch graphics)
   - Product version numbers
   - "Coming soon" or availability indicators

3. ANALYSIS: Extract all visible product details:
   - Product specifications
   - Target audience signals
   - Competitive positioning statements
   - Call-to-action text

4. HYPOTHESIS: What market segment is this targeting?

5. DECISION: Is this evidence of a new product launch?
   - Confidence level (0-100%)
   - Launch type (new product, update, rebrand)

Be thorough - extract every piece of text and visual information relevant to competitive analysis."""

        full_response = ""
        async for chunk in ai_clients.analyze_image_stream(
            image_data, image_type, image_prompt, model=self.model
        ):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield LaunchMessage(
                    agent=LaunchAgent.SCANNER,
                    thought_type=chunk.thought_type or ThoughtType.OBSERVATION,
                    content=chunk.text
                )
        
        # Check for launch indicators in image analysis
        launch_detected = any(
            kw in full_response.lower() 
            for kw in ["new product", "launch", "introducing", "announcing", "just released", "now available"]
        )
        confidence = 0.8 if launch_detected else 0.2
        
        status = "🚨 LAUNCH DETECTED IN IMAGE" if launch_detected else "✅ No launch indicators in image"
        
        yield LaunchMessage(
            agent=LaunchAgent.SCANNER,
            thought_type=ThoughtType.DECISION,
            content=f"\n\n{status}. Confidence: {confidence:.0%}",
            is_final=True,
            metadata={
                "scan_result": {
                    "launch_detected": launch_detected,
                    "confidence": confidence,
                    "analysis_type": "image",
                    "analysis": full_response
                }
            }
        )
    
    # =========================================================================
    # VALIDATOR AGENT - Confirm launch and extract details
    # =========================================================================
    
    async def run_validator_agent(
        self,
        scan_result: dict,
        competitor_name: str,
        signals: List[LaunchSignal]
    ) -> AsyncGenerator[LaunchMessage, None]:
        """
        Validator Agent: Confirms launch and extracts detailed product information.
        """
        yield LaunchMessage(
            agent=LaunchAgent.VALIDATOR,
            thought_type=ThoughtType.OBSERVATION,
            content="🔎 Validator Agent activated. Confirming launch details..."
        )
        
        # Get most relevant signal content for validation
        signal_details = self._get_detailed_signals(signals, limit=5)
        
        validator_prompt = f"""You are a competitive intelligence validator confirming a potential product launch.

COMPETITOR: {competitor_name}
INITIAL SCAN CONFIDENCE: {scan_result.get('confidence', 0):.0%}

SCANNER ANALYSIS:
{scan_result.get('analysis', 'No analysis available')}

DETAILED SIGNAL CONTENT:
{signal_details}

Your task is to validate and extract launch details:

1. OBSERVATION: Review the scanner's findings. What evidence is strongest?

2. ANALYSIS: Determine launch type:
   - Is this a genuinely NEW product (never existed before)?
   - Is this a MAJOR UPDATE to existing product?
   - Is this a REBRAND or repositioning?
   - Is this MARKET EXPANSION (existing product, new region)?

3. ANALYSIS: Extract confirmed details:
   - Product name (exact, if mentioned)
   - Key features (list specific capabilities)
   - Target market/audience
   - Pricing (if any indication)
   - Launch date or availability

4. ANALYSIS: Assess information quality:
   - Is this from official sources or rumors?
   - How many independent sources confirm this?
   - Any contradictory information?

5. HYPOTHESIS: What competitive advantage is this product claiming?

6. DECISION: Final validation verdict with confidence adjustment.

End with a structured JSON block:
```json
{{
  "is_confirmed_launch": true/false,
  "launch_type": "new_product/major_update/rebrand/expansion/unknown",
  "confidence": 0-100,
  "product_name": "extracted name or 'Unknown'",
  "key_features": ["feature1", "feature2", "feature3"],
  "target_market": "description of target audience",
  "estimated_price": "price or price range if mentioned, else null",
  "launch_date": "date if mentioned, else 'TBD'",
  "official_source": true/false,
  "source_quality": "high/medium/low"
}}
```"""

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(validator_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield LaunchMessage(
                    agent=LaunchAgent.VALIDATOR,
                    thought_type=chunk.thought_type or ThoughtType.ANALYSIS,
                    content=chunk.text
                )
        
        # Parse validation results
        validated = self._parse_validator_json(full_response)
        
        confidence = validated.get('confidence', 0)
        product_name = validated.get('product_name', 'Unknown Product')
        
        yield LaunchMessage(
            agent=LaunchAgent.VALIDATOR,
            thought_type=ThoughtType.DECISION,
            content=f"\n\n✅ Validation complete. Product: {product_name} | Confidence: {confidence}%",
            is_final=True,
            metadata={
                "validated": validated,
                "full_analysis": full_response
            }
        )
    
    # =========================================================================
    # ASSESSOR AGENT - Assess threat and recommend response
    # =========================================================================
    
    async def run_assessor_agent(
        self,
        scan_result: dict,
        validated: dict,
        competitor_name: str,
        your_product: str
    ) -> AsyncGenerator[LaunchMessage, None]:
        """
        Assessor Agent: Evaluates competitive threat and recommends response strategy.
        """
        yield LaunchMessage(
            agent=LaunchAgent.ASSESSOR,
            thought_type=ThoughtType.OBSERVATION,
            content="🎯 Assessor Agent activated. Evaluating competitive threat..."
        )
        
        assessor_prompt = f"""You are a competitive strategy assessor evaluating a competitor's product launch.

COMPETITOR: {competitor_name}
YOUR PRODUCT: {your_product}

VALIDATED LAUNCH DETAILS:
- Product: {validated.get('product_name', 'Unknown')}
- Launch Type: {validated.get('launch_type', 'unknown')}
- Confidence: {validated.get('confidence', 0)}%
- Key Features: {', '.join(validated.get('key_features', ['Unknown']))}
- Target Market: {validated.get('target_market', 'Unknown')}
- Price: {validated.get('estimated_price', 'Unknown')}
- Launch Date: {validated.get('launch_date', 'TBD')}

Your task is to assess the competitive threat:

1. OBSERVATION: How does this launch relate to your product space?

2. ANALYSIS: Direct Competition Assessment
   - Feature overlap with {your_product}
   - Price positioning comparison
   - Target audience overlap
   - Unique advantages of competitor's product

3. ANALYSIS: Market Impact Prediction
   - Which customer segments are most at risk?
   - Potential market share impact
   - Timeline of impact (immediate vs gradual)

4. HYPOTHESIS: How might customers react?
   - Likely switching behavior
   - Comparison shopping increase
   - Perception changes

5. RECOMMENDATION: Immediate Actions (within 24-48 hours)
   - Communication adjustments
   - Sales team briefing needs
   - Monitoring to set up

6. RECOMMENDATION: Strategic Response (within 1-4 weeks)
   - Product positioning adjustments
   - Pricing considerations
   - Feature roadmap implications
   - Marketing response options

7. RECOMMENDATION: Long-term Considerations
   - Product development priorities
   - Partnership opportunities
   - Market differentiation strategies

Rate overall threat level based on:
- CRITICAL: Direct competitor to your core product, strong features, aggressive pricing
- HIGH: Significant feature overlap, targets your key segments
- MEDIUM: Some overlap, different positioning or target market
- LOW: Minimal overlap, different market segment
- NONE: No competitive threat identified

End with a structured JSON block:
```json
{{
  "threat_level": "none/low/medium/high/critical",
  "threat_score": 0-100,
  "urgency": "immediate/soon/monitor/none",
  "impact_areas": ["area1", "area2"],
  "at_risk_segments": ["segment1", "segment2"],
  "immediate_actions": ["action1", "action2", "action3"],
  "strategic_actions": ["action1", "action2"],
  "monitoring_priorities": ["what to watch1", "what to watch2"],
  "competitive_advantages_to_emphasize": ["your advantage1", "your advantage2"],
  "estimated_response_budget": "low/medium/high",
  "recommended_timeline": "description of response timeline"
}}
```"""

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(assessor_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield LaunchMessage(
                    agent=LaunchAgent.ASSESSOR,
                    thought_type=chunk.thought_type or ThoughtType.ANALYSIS,
                    content=chunk.text
                )
        
        # Parse assessment results
        assessment = self._parse_assessor_json(full_response)
        threat_level = assessment.get('threat_level', 'medium').upper()
        urgency = assessment.get('urgency', 'monitor')
        
        yield LaunchMessage(
            agent=LaunchAgent.ASSESSOR,
            thought_type=ThoughtType.RECOMMENDATION,
            content=f"\n\n✅ Assessment complete. Threat Level: {threat_level} | Urgency: {urgency.upper()}",
            is_final=True,
            metadata={
                "assessment": assessment,
                "full_analysis": full_response
            }
        )
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _prepare_signal_summary(self, signals: List[LaunchSignal]) -> str:
        """Prepare signals as formatted text for Gemini."""
        if not signals:
            return "No signals available"
        
        lines = []
        for i, sig in enumerate(signals[:20], 1):  # Limit to 20 signals
            timestamp = sig.timestamp.strftime("%Y-%m-%d %H:%M") if sig.timestamp else "Unknown time"
            engagement = f" | Engagement: {sig.engagement}" if sig.engagement > 0 else ""
            author = f" | @{sig.author}" if sig.author else ""
            
            lines.append(f"[Signal {i}] [{sig.source.upper()}] {timestamp}{author}{engagement}")
            lines.append(f"Content: {sig.content[:300]}{'...' if len(sig.content) > 300 else ''}")
            if sig.url:
                lines.append(f"URL: {sig.url}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _get_detailed_signals(self, signals: List[LaunchSignal], limit: int = 5) -> str:
        """Get detailed content from top signals for validation."""
        # Sort by engagement if available
        sorted_signals = sorted(signals, key=lambda x: x.engagement, reverse=True)
        
        lines = []
        for sig in sorted_signals[:limit]:
            lines.append(f"=== [{sig.source.upper()}] ===")
            lines.append(sig.content)
            lines.append("")
        
        return "\n".join(lines) if lines else "No detailed signals available"
    
    def _get_signal_sources(self, signals: List[LaunchSignal]) -> List[str]:
        """Get unique sources from signals."""
        return list(set(sig.source for sig in signals))
    
    def _analyze_scanner_response(
        self, 
        response: str, 
        signals: List[LaunchSignal]
    ) -> tuple[bool, float]:
        """Analyze scanner response to determine launch detection."""
        response_lower = response.lower()
        
        # Count keyword matches
        keyword_matches = sum(
            1 for kw in self.launch_keywords 
            if kw in response_lower
        )
        
        # Check signal content for launch keywords
        signal_matches = sum(
            1 for sig in signals
            if any(kw in sig.content.lower() for kw in self.launch_keywords)
        )
        
        # Calculate confidence
        base_confidence = 0.0
        
        if keyword_matches >= 3:
            base_confidence += 0.4
        elif keyword_matches >= 1:
            base_confidence += 0.2
        
        if signal_matches >= 2:
            base_confidence += 0.4
        elif signal_matches >= 1:
            base_confidence += 0.2
        
        # Boost for strong indicators
        strong_indicators = ["announcing", "introducing", "launching today", "now available"]
        if any(ind in response_lower for ind in strong_indicators):
            base_confidence += 0.2
        
        confidence = min(base_confidence, 1.0)
        launch_detected = confidence >= self.min_confidence
        
        return launch_detected, confidence
    
    def _parse_validator_json(self, response: str) -> dict:
        """Parse the JSON validation result."""
        default = {
            "is_confirmed_launch": False,
            "launch_type": "unknown",
            "confidence": 0,
            "product_name": "Unknown",
            "key_features": [],
            "target_market": "Unknown",
            "estimated_price": None,
            "launch_date": "TBD"
        }
        
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                return default
            
            parsed = json.loads(json_str.strip())
            return {**default, **parsed}
            
        except Exception as e:
            logger.warning(f"Failed to parse validator JSON: {e}")
            return default
    
    def _parse_assessor_json(self, response: str) -> dict:
        """Parse the JSON assessment result."""
        default = {
            "threat_level": "medium",
            "threat_score": 50,
            "urgency": "monitor",
            "impact_areas": [],
            "at_risk_segments": [],
            "immediate_actions": [],
            "strategic_actions": [],
            "monitoring_priorities": []
        }
        
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                return default
            
            parsed = json.loads(json_str.strip())
            return {**default, **parsed}
            
        except Exception as e:
            logger.warning(f"Failed to parse assessor JSON: {e}")
            return default
    
    # =========================================================================
    # FULL ORCHESTRATION
    # =========================================================================
    
    async def analyze(
        self,
        signals: List[LaunchSignal],
        competitor_name: str,
        your_product: str,
        image_data: Optional[bytes] = None,
        image_type: str = "png"
    ) -> AsyncGenerator[LaunchMessage, None]:
        """
        Run the full launch detection pipeline.
        
        Args:
            signals: List of social/news signals to analyze
            competitor_name: Name of competitor being monitored
            your_product: Name of your product (for threat assessment)
            image_data: Optional product screenshot for multimodal analysis
            image_type: Image MIME subtype (png, jpeg, etc.)
            
        Yields:
            LaunchMessage objects from each agent in sequence
        """
        if len(signals) < self.min_signals and not image_data:
            yield LaunchMessage(
                agent=LaunchAgent.SCANNER,
                thought_type=ThoughtType.DECISION,
                content=f"⚠️ Insufficient data: {len(signals)} signals (minimum: {self.min_signals})",
                is_final=True,
                metadata={"error": "insufficient_data"}
            )
            return
        
        # Phase 1: Scanner Agent
        scan_result = {}
        async for msg in self.run_scanner_agent(signals, competitor_name, image_data, image_type):
            yield msg
            if msg.is_final and msg.metadata.get("scan_result"):
                scan_result = msg.metadata["scan_result"]
        
        # If no launch detected, stop here (early exit)
        if not scan_result.get("launch_detected", False):
            yield LaunchMessage(
                agent=LaunchAgent.SCANNER,
                thought_type=ThoughtType.DECISION,
                content="✅ No product launch detected. Monitoring complete.",
                is_final=True,
                metadata={"status": "no_launch", "scan_result": scan_result}
            )
            return
        
        # Phase 2: Validator Agent
        validated = {}
        async for msg in self.run_validator_agent(scan_result, competitor_name, signals):
            yield msg
            if msg.is_final and msg.metadata.get("validated"):
                validated = msg.metadata["validated"]
        
        # If validation failed or low confidence, note it but continue
        if not validated.get("is_confirmed_launch", False) and validated.get("confidence", 0) < 30:
            yield LaunchMessage(
                agent=LaunchAgent.VALIDATOR,
                thought_type=ThoughtType.DECISION,
                content="⚠️ Launch could not be confirmed with high confidence. Proceeding with assessment anyway.",
                is_final=False
            )
        
        # Phase 3: Assessor Agent
        async for msg in self.run_assessor_agent(scan_result, validated, competitor_name, your_product):
            yield msg


# Singleton instance
launch_detector = LaunchDetector()



