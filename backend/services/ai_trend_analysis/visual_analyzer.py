"""
Visual Pricing Intelligence - Multi-Agent Analysis System

Agents:
1. Scout Agent - Extracts data from competitor screenshots
2. Analyst Agent - Compares products and market positioning  
3. Strategist Agent - Recommends optimal pricing strategy

Uses Gemini streaming for real-time "thinking" display.
"""

import json
import re
from typing import Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal

from core.logging import get_logger
from services.ai_trend_analysis.ai_clients import (
    ai_clients,
    DEFAULT_MODEL,
    StreamChunk, 
    ThoughtType,
    ImageAnalysisResult
)

logger = get_logger(__name__)


class AgentRole(str, Enum):
    """The three agents in our pricing intelligence system."""
    SCOUT = "scout"
    ANALYST = "analyst"
    STRATEGIST = "strategist"


@dataclass
class AgentMessage:
    """A message from an agent during analysis."""
    agent: AgentRole
    thought_type: Optional[ThoughtType]
    content: str
    is_final: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class ProductInfo:
    """Information about a product (yours or competitor's)."""
    name: str
    price: Decimal
    currency: str = "USD"
    features: list[str] = field(default_factory=list)
    reviews_summary: Optional[str] = None
    promo_signals: list[str] = field(default_factory=list)
    source: str = "manual"  # "manual" or "screenshot"


@dataclass
class PricingRecommendation:
    """Final pricing recommendation from the Strategist."""
    recommended_price: Decimal
    confidence: float
    reasoning: str
    price_change_percent: float
    strategy: str  # "increase", "decrease", "maintain"
    risk_level: str  # "low", "medium", "high"
    key_factors: list[str] = field(default_factory=list)
    alternative_prices: list[dict] = field(default_factory=list)


class VisualPricingAnalyzer:
    """
    Orchestrates multi-agent analysis for visual pricing intelligence.
    
    Flow:
    1. Scout Agent extracts competitor data from screenshot
    2. Analyst Agent compares with your product
    3. Strategist Agent recommends optimal price
    
    All agents stream their "thinking" in real-time.
    """
    
    def __init__(self):
        self.model = DEFAULT_MODEL
    
    # =========================================================================
    # SCOUT AGENT - Extract competitor data from screenshot
    # =========================================================================
    
    async def run_scout_agent(
        self,
        image_data: bytes,
        image_type: str = "png"
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Scout Agent: Extracts product information from competitor screenshot.
        
        Yields AgentMessage objects with real-time thinking.
        """
        yield AgentMessage(
            agent=AgentRole.SCOUT,
            thought_type=ThoughtType.OBSERVATION,
            content="🔍 Scout Agent activated. Analyzing competitor screenshot..."
        )
        
        # Use the streaming image analysis
        full_response = ""
        async for chunk in ai_clients.analyze_image_stream(
            image_data=image_data,
            image_type=image_type,
            model=self.model
        ):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield AgentMessage(
                    agent=AgentRole.SCOUT,
                    thought_type=chunk.thought_type or ThoughtType.OBSERVATION,
                    content=chunk.text
                )
        
        # Also get structured data
        structured_result = await ai_clients.analyze_image(
            image_data=image_data,
            image_type=image_type,
            model=self.model
        )
        
        yield AgentMessage(
            agent=AgentRole.SCOUT,
            thought_type=ThoughtType.DECISION,
            content=f"\n\n✅ Scout Agent complete. Extracted: {structured_result.product_name} at {structured_result.price}",
            is_final=True,
            metadata={
                "extracted_data": {
                    "product_name": structured_result.product_name,
                    "price": structured_result.price,
                    "currency": structured_result.currency,
                    "features": structured_result.features,
                    "promo_signals": structured_result.promo_signals,
                    "confidence": structured_result.confidence
                }
            }
        )
    
    # =========================================================================
    # ANALYST AGENT - Compare products and market positioning
    # =========================================================================
    
    async def run_analyst_agent(
        self,
        your_product: ProductInfo,
        competitor_data: dict
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Analyst Agent: Compares your product with competitor data.
        
        Yields AgentMessage objects with real-time analysis.
        """
        yield AgentMessage(
            agent=AgentRole.ANALYST,
            thought_type=ThoughtType.OBSERVATION,
            content="📊 Analyst Agent activated. Comparing products..."
        )
        
        analysis_prompt = f"""You are a pricing analyst. Compare these two products and provide market positioning analysis.

YOUR PRODUCT:
- Name: {your_product.name}
- Current Price: {your_product.price} {your_product.currency}
- Features: {', '.join(your_product.features) if your_product.features else 'Not specified'}

COMPETITOR PRODUCT (from screenshot):
- Name: {competitor_data.get('product_name', 'Unknown')}
- Price: {competitor_data.get('price', 'Unknown')} {competitor_data.get('currency', 'USD')}
- Features: {', '.join(competitor_data.get('features', [])) if competitor_data.get('features') else 'Not visible'}
- Promotional Signals: {', '.join(competitor_data.get('promo_signals', [])) if competitor_data.get('promo_signals') else 'None detected'}

Analyze step by step:

1. OBSERVATION: What are the key differences I notice?
2. ANALYSIS: How do these products compare on value proposition?
3. ANALYSIS: What is the price differential and what does it mean?
4. HYPOTHESIS: What market segment is each targeting?
5. DECISION: What is your product's competitive position?

Be specific and use the actual numbers provided."""

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(analysis_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield AgentMessage(
                    agent=AgentRole.ANALYST,
                    thought_type=chunk.thought_type or ThoughtType.ANALYSIS,
                    content=chunk.text
                )
        
        # Calculate price differential
        try:
            your_price = float(your_product.price)
            competitor_price_str = competitor_data.get('price', '0')
            # Clean price string (remove currency symbols)
            competitor_price = float(''.join(c for c in competitor_price_str if c.isdigit() or c == '.'))
            
            if competitor_price > 0:
                price_diff_percent = ((your_price - competitor_price) / competitor_price) * 100
                position = "premium" if price_diff_percent > 5 else "discount" if price_diff_percent < -5 else "competitive"
            else:
                price_diff_percent = 0
                position = "unknown"
        except (ValueError, TypeError):
            price_diff_percent = 0
            position = "unknown"
        
        yield AgentMessage(
            agent=AgentRole.ANALYST,
            thought_type=ThoughtType.DECISION,
            content=f"\n\n✅ Analyst Agent complete. Position: {position} ({price_diff_percent:+.1f}% vs competitor)",
            is_final=True,
            metadata={
                "analysis": {
                    "price_differential_percent": price_diff_percent,
                    "market_position": position,
                    "full_analysis": full_response
                }
            }
        )
    
    # =========================================================================
    # STRATEGIST AGENT - Recommend optimal pricing
    # =========================================================================
    
    async def run_strategist_agent(
        self,
        your_product: ProductInfo,
        competitor_data: dict,
        analysis_data: dict
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Strategist Agent: Recommends optimal pricing strategy.
        
        Yields AgentMessage objects with real-time strategic thinking.
        """
        yield AgentMessage(
            agent=AgentRole.STRATEGIST,
            thought_type=ThoughtType.OBSERVATION,
            content="🎯 Strategist Agent activated. Formulating pricing strategy..."
        )
        
        strategy_prompt = f"""You are a pricing strategist. Based on the competitive analysis, recommend an optimal price.

YOUR PRODUCT:
- Name: {your_product.name}
- Current Price: {your_product.price} {your_product.currency}
- Features: {', '.join(your_product.features) if your_product.features else 'Standard features'}

COMPETITOR:
- Name: {competitor_data.get('product_name', 'Competitor')}
- Price: {competitor_data.get('price', 'Unknown')}
- Promos: {', '.join(competitor_data.get('promo_signals', [])) if competitor_data.get('promo_signals') else 'None'}

ANALYSIS:
- Your position: {analysis_data.get('market_position', 'unknown')}
- Price differential: {analysis_data.get('price_differential_percent', 0):+.1f}%

Provide your strategic recommendation:

1. OBSERVATION: What key factors should drive this pricing decision?
2. ANALYSIS: What are the risks and opportunities at different price points?
3. HYPOTHESIS: If we change price, what market response do we expect?
4. RECOMMENDATION: What specific price do you recommend and why?

End with a JSON block containing your final recommendation:
```json
{{
  "recommended_price": <number>,
  "confidence": <0.0-1.0>,
  "strategy": "increase|decrease|maintain",
  "risk_level": "low|medium|high",
  "key_factors": ["factor1", "factor2", "factor3"]
}}
```"""

        full_response = ""
        async for chunk in ai_clients.stream_gemini3(strategy_prompt, model=self.model):
            if chunk.text and not chunk.is_final:
                full_response += chunk.text
                yield AgentMessage(
                    agent=AgentRole.STRATEGIST,
                    thought_type=chunk.thought_type or ThoughtType.RECOMMENDATION,
                    content=chunk.text
                )
        
        # Parse the JSON recommendation from response
        recommendation = self._parse_recommendation(full_response, your_product)
        
        # FIX: Convert Decimal to float for JSON serialization
        yield AgentMessage(
            agent=AgentRole.STRATEGIST,
            thought_type=ThoughtType.RECOMMENDATION,
            content=f"\n\n✅ Strategist Agent complete. Recommended: {recommendation.recommended_price} {your_product.currency} ({recommendation.price_change_percent:+.1f}%)",
            is_final=True,
            metadata={
                "recommendation": {
                    "recommended_price": float(recommendation.recommended_price),
                    "confidence": recommendation.confidence,
                    "strategy": recommendation.strategy,
                    "risk_level": recommendation.risk_level,
                    "price_change_percent": recommendation.price_change_percent,
                    "key_factors": recommendation.key_factors,
                    "reasoning": recommendation.reasoning
                }
            }
        )
    
    def _parse_recommendation(
        self, 
        response: str, 
        your_product: ProductInfo
    ) -> PricingRecommendation:
        """Parse the JSON recommendation from strategist response."""
        try:
            # Find JSON block in response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                # Try to find raw JSON
                match = re.search(r'\{[^{}]*"recommended_price"[^{}]*\}', response)
                if match:
                    json_str = match.group()
                else:
                    raise ValueError("No JSON found in response")
            
            data = json.loads(json_str.strip())
            
            recommended_price = Decimal(str(data.get("recommended_price", your_product.price)))
            current_price = Decimal(str(your_product.price))
            
            if current_price > 0:
                change_percent = float((recommended_price - current_price) / current_price * 100)
            else:
                change_percent = 0
            
            return PricingRecommendation(
                recommended_price=recommended_price,
                confidence=data.get("confidence", 0.5),
                reasoning=response,
                price_change_percent=change_percent,
                strategy=data.get("strategy", "maintain"),
                risk_level=data.get("risk_level", "medium"),
                key_factors=data.get("key_factors", [])
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse recommendation JSON: {e}")
            # Return a safe default
            return PricingRecommendation(
                recommended_price=your_product.price,
                confidence=0.3,
                reasoning=response,
                price_change_percent=0,
                strategy="maintain",
                risk_level="medium",
                key_factors=["Unable to parse AI recommendation"]
            )
    
    # =========================================================================
    # FULL ORCHESTRATION - Run all agents in sequence
    # =========================================================================
    
    async def analyze(
        self,
        image_data: bytes,
        image_type: str,
        your_product_name: str,
        your_product_price: float,
        your_product_currency: str = "USD",
        your_product_features: list[str] = None
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Run the full multi-agent analysis pipeline.
        
        Args:
            image_data: Competitor screenshot bytes
            image_type: Image MIME type (png, jpeg, etc.)
            your_product_name: Your product name
            your_product_price: Your current price
            your_product_currency: Currency code
            your_product_features: List of your product features
            
        Yields:
            AgentMessage objects from each agent in sequence
        """
        your_product = ProductInfo(
            name=your_product_name,
            price=Decimal(str(your_product_price)),
            currency=your_product_currency,
            features=your_product_features or [],
            source="manual"
        )
        
        # Phase 1: Scout Agent
        competitor_data = {}
        async for msg in self.run_scout_agent(image_data, image_type):
            yield msg
            if msg.is_final and msg.metadata.get("extracted_data"):
                competitor_data = msg.metadata["extracted_data"]
        
        if not competitor_data:
            yield AgentMessage(
                agent=AgentRole.SCOUT,
                thought_type=ThoughtType.DECISION,
                content="❌ Scout Agent failed to extract competitor data. Cannot proceed.",
                is_final=True
            )
            return
        
        # Phase 2: Analyst Agent
        analysis_data = {}
        async for msg in self.run_analyst_agent(your_product, competitor_data):
            yield msg
            if msg.is_final and msg.metadata.get("analysis"):
                analysis_data = msg.metadata["analysis"]
        
        # Phase 3: Strategist Agent
        async for msg in self.run_strategist_agent(your_product, competitor_data, analysis_data):
            yield msg


# Singleton instance
visual_analyzer = VisualPricingAnalyzer()



