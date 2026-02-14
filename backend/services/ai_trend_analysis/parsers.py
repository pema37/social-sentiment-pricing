"""
Response parsers for AI outputs.
Converts AI JSON responses into structured data models.
"""

import uuid
from datetime import datetime, timedelta, UTC
from decimal import Decimal

from core.logging import get_logger
from models.product import Product

from .schemas import (
    TrendAnalysisResult,
    TrendPrediction,
    PricingOpportunity,
    RiskAlert,
    AIInsight,
    TrendDirection,
    TrendCategory,
    OpportunityType,
    RiskLevel,
    ConfidenceLevel,
)

logger = get_logger(__name__)


class ResponseParser:
    """Parses AI responses into structured models."""
    
    # ==========================================
    # Main Analysis Parser
    # ==========================================
    
    @staticmethod
    def parse_analysis_response(
        user_id: str,
        ai_response: dict,
        products: list[Product],
        model_used: str,
        days: int,
        mentions_count: int,
    ) -> TrendAnalysisResult:
        """Parse AI response into TrendAnalysisResult."""
        now = datetime.now(UTC)
        
        # Parse market sentiment
        try:
            market_sentiment = TrendDirection(
                ai_response.get("market_sentiment", "stable")
            )
        except ValueError:
            market_sentiment = TrendDirection.STABLE
        
        market_sentiment_score = ai_response.get("market_sentiment_score", 0)
        
        # Parse predictions
        predictions = ResponseParser._parse_predictions(ai_response.get("predictions", []))
        
        # Parse opportunities
        opportunities = ResponseParser._parse_opportunities(
            ai_response.get("opportunities", []),
            products,
            now
        )
        
        # Parse risks
        risks = ResponseParser._parse_risks(ai_response.get("risks", []), now)
        
        # Create insight from key_insights
        insights = []
        key_insights = ai_response.get("key_insights", [])
        if key_insights:
            insights.append(AIInsight(
                title="Market Analysis Summary",
                summary=ai_response.get("executive_summary", ""),
                detailed_analysis="\n".join(key_insights),
                key_factors=key_insights,
                data_points_analyzed=mentions_count,
                generated_at=now,
                model_used=model_used,
            ))
        
        return TrendAnalysisResult(
            user_id=user_id,
            analysis_id=str(uuid.uuid4()),
            generated_at=now,
            market_sentiment=market_sentiment,
            market_sentiment_score=market_sentiment_score,
            predictions=predictions,
            opportunities=opportunities,
            risks=risks,
            insights=insights,
            executive_summary=ai_response.get("executive_summary", ""),
            recommended_actions=ai_response.get("recommended_actions", []),
            products_analyzed=len(products),
            mentions_analyzed=mentions_count,
            time_range_days=days,
        )
    
    # ==========================================
    # Predictions Parser
    # ==========================================
    
    @staticmethod
    def _parse_predictions(predictions_data: list) -> list[TrendPrediction]:
        """Parse predictions from AI response."""
        predictions = []
        
        for p in predictions_data:
            try:
                # Parse direction
                try:
                    direction = TrendDirection(p.get("direction", "stable"))
                except ValueError:
                    direction = TrendDirection.STABLE
                
                # Parse category
                try:
                    category = TrendCategory(p.get("category", "organic_growth"))
                except ValueError:
                    category = TrendCategory.ORGANIC_GROWTH
                
                # Parse confidence
                try:
                    confidence = ConfidenceLevel(p.get("confidence", "medium"))
                except ValueError:
                    confidence = ConfidenceLevel.MEDIUM
                
                predictions.append(TrendPrediction(
                    direction=direction,
                    category=category,
                    confidence=confidence,
                    confidence_score=p.get("confidence_score", 50),
                    predicted_change=p.get("predicted_change", 0),
                    timeframe_days=p.get("timeframe_days", 7),
                    reasoning=p.get("reasoning", ""),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse prediction: {e}")
        
        return predictions
    
    # ==========================================
    # Opportunities Parser
    # ==========================================
    
    @staticmethod
    def _parse_opportunities(
        opportunities_data: list,
        products: list[Product],
        now: datetime
    ) -> list[PricingOpportunity]:
        """Parse opportunities from AI response."""
        opportunities = []
        product_map = {str(p.id): p for p in products}
        
        for o in opportunities_data:
            try:
                product_id = o.get("product_id", "")
                product = product_map.get(product_id)
                
                # Parse opportunity type
                try:
                    opportunity_type = OpportunityType(o.get("opportunity_type", "hold"))
                except ValueError:
                    opportunity_type = OpportunityType.HOLD
                
                # Parse confidence
                try:
                    confidence = ConfidenceLevel(o.get("confidence", "medium"))
                except ValueError:
                    confidence = ConfidenceLevel.MEDIUM
                
                # Get prices
                current_price = o.get("current_price", product.base_price if product else 0)
                suggested_price = o.get("suggested_price", current_price)
                
                opportunities.append(PricingOpportunity(
                    opportunity_type=opportunity_type,
                    product_id=product_id,
                    product_name=o.get("product_name", product.name if product else "Unknown"),
                    current_price=Decimal(str(current_price)),
                    suggested_price=Decimal(str(suggested_price)),
                    expected_impact=o.get("expected_impact", "Unknown"),
                    confidence=confidence,
                    confidence_score=o.get("confidence_score", 50),
                    reasoning=o.get("reasoning", ""),
                    valid_until=now + timedelta(days=7),
                    triggers=o.get("triggers", []),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse opportunity: {e}")
        
        return opportunities
    
    # ==========================================
    # Risks Parser
    # ==========================================
    
    @staticmethod
    def _parse_risks(risks_data: list, now: datetime) -> list[RiskAlert]:
        """Parse risks from AI response."""
        risks = []
        
        for r in risks_data:
            try:
                # Parse risk level
                try:
                    risk_level = RiskLevel(r.get("risk_level", "low"))
                except ValueError:
                    risk_level = RiskLevel.LOW
                
                urgency_hours = r.get("urgency_hours", 24)
                
                risks.append(RiskAlert(
                    risk_level=risk_level,
                    risk_type=r.get("risk_type", "unknown"),
                    title=r.get("title", "Unknown Risk"),
                    description=r.get("description", ""),
                    affected_products=r.get("affected_products", []),
                    recommended_actions=r.get("recommended_actions", []),
                    detected_at=now,
                    expires_at=now + timedelta(hours=urgency_hours),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse risk: {e}")
        
        return risks
    
    @staticmethod
    def parse_risk_response(ai_response: dict) -> list[RiskAlert]:
        """Parse standalone risk detection response."""
        now = datetime.now(UTC)
        return ResponseParser._parse_risks(ai_response.get("risks", []), now)
    
    # ==========================================
    # Opportunity Parser (Single Product)
    # ==========================================
    
    @staticmethod
    def parse_opportunity_response(
        product: Product,
        ai_response: dict,
    ) -> PricingOpportunity:
        """Parse AI response into single PricingOpportunity."""
        recommendation = ai_response.get("recommendation", "hold")
        
        # Map recommendation to opportunity type
        type_map = {
            "increase": OpportunityType.PRICE_INCREASE,
            "decrease": OpportunityType.PRICE_DECREASE,
            "hold": OpportunityType.HOLD,
        }
        opportunity_type = type_map.get(recommendation, OpportunityType.HOLD)
        
        # Determine confidence level from score
        confidence_score = ai_response.get("confidence_score", 50)
        if confidence_score >= 80:
            confidence = ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 60:
            confidence = ConfidenceLevel.HIGH
        elif confidence_score >= 40:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW
        
        # Extract reasoning
        reasoning_parts = ai_response.get("reasoning", {})
        if isinstance(reasoning_parts, dict):
            reasoning = reasoning_parts.get("overall", "")
        else:
            reasoning = str(reasoning_parts)
        
        # Get timing info
        timing = ai_response.get("timing", {})
        optimal_window = timing.get("optimal_window_days", 7) if isinstance(timing, dict) else 7
        
        return PricingOpportunity(
            opportunity_type=opportunity_type,
            product_id=str(product.id),
            product_name=product.name,
            current_price=product.base_price,
            suggested_price=Decimal(str(ai_response.get("suggested_price", product.base_price))),
            expected_impact=ai_response.get("expected_revenue_impact", "Unknown"),
            confidence=confidence,
            confidence_score=confidence_score,
            reasoning=reasoning,
            valid_until=datetime.now(UTC) + timedelta(days=optimal_window),
            triggers=ai_response.get("risks", []),
        )
    
    # ==========================================
    # Insight Parser
    # ==========================================
    
    @staticmethod
    def parse_insight_response(
        ai_response: dict,
        model_used: str,
        data_points: int,
    ) -> AIInsight:
        """Parse AI response into AIInsight."""
        return AIInsight(
            title=ai_response.get("title", "Market Insight"),
            summary=ai_response.get("summary", ""),
            detailed_analysis=ai_response.get("detailed_analysis", ""),
            key_factors=ai_response.get("key_factors", []),
            data_points_analyzed=data_points,
            generated_at=datetime.now(UTC),
            model_used=model_used,
        )
    


    