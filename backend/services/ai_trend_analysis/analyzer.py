"""
AI Trend Analysis Service - Main Orchestrator

This service coordinates data collection, AI calls, and response parsing
to generate actionable pricing insights and predictions.

FIX (2026-01-17): Updated to await async data collector methods.
All self.collector.get_*() calls now use await.
"""

from typing import Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

from .ai_clients import ai_clients
from .data_collector import DataCollector
from .formatters import DataFormatter
from .calculators import TrendCalculators
from .parsers import ResponseParser
from .prompts import (
    SYSTEM_PROMPT,
    build_trend_analysis_prompt,
    build_opportunity_prompt,
    build_risk_prompt,
    build_insight_prompt,
)
from .models import (
    TrendAnalysisResult,
    PricingOpportunity,
    RiskAlert,
    AIInsight,
)

logger = get_logger(__name__)


class AITrendAnalyzer:
    """
    AI-powered trend analysis service.
    
    Coordinates data collection, AI model calls, and response parsing
    to generate predictions, opportunities, and risk alerts.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.collector = DataCollector(db)
        self.formatter = DataFormatter()
        self.calculator = TrendCalculators()
        self.parser = ResponseParser()
    
    async def analyze(
        self,
        user_id: str,
        days: int = 30,
        product_ids: Optional[list[str]] = None,
        use_model: str = "openai",
    ) -> TrendAnalysisResult:
        """
        Perform comprehensive AI trend analysis.
        
        Args:
            user_id: The user requesting analysis
            days: Number of days to analyze (default 30)
            product_ids: Optional list of specific product IDs (None = all)
            use_model: Which AI model to use ('openai' or 'gemini')
            
        Returns:
            TrendAnalysisResult with predictions, opportunities, and insights
        """
        logger.info(f"Starting AI trend analysis for user {user_id}, {days} days")
        
        # 1. Collect data (ASYNC - use await)
        products = await self.collector.get_products(user_id, product_ids)
        sentiment_data = await self.collector.get_sentiment_history(user_id, days, product_ids)
        mentions_data = await self.collector.get_mentions_summary(user_id, days, product_ids)
        competitor_data = await self.collector.get_competitor_data(user_id, product_ids)
        
        # Handle case where no products exist
        if not products:
            logger.warning(f"No products found for user {user_id}")
            # Return empty result instead of failing
            return self.parser.parse_analysis_response(
                user_id=user_id,
                ai_response={
                    "market_sentiment": "stable",
                    "market_sentiment_score": 0,
                    "predictions": [],
                    "opportunities": [],
                    "risks": [],
                    "executive_summary": "No products found. Add products to enable trend analysis.",
                    "recommended_actions": ["Add products to your catalog"],
                    "key_insights": ["No data available for analysis"],
                },
                products=[],
                model_used=use_model,
                days=days,
                mentions_count=0,
            )
        
        # 2. Calculate metrics
        avg_sentiment = self.calculator.calculate_avg_sentiment(sentiment_data)
        sentiment_trend = self.calculator.calculate_sentiment_trend(sentiment_data)
        volume_change = self.calculator.calculate_volume_change(mentions_data, days)
        competitor_changes = self.calculator.summarize_competitor_changes(competitor_data)
        
        # 3. Build prompt
        prompt = build_trend_analysis_prompt(
            product_data=self.formatter.format_products(products),
            sentiment_history=self.formatter.format_sentiment_history(sentiment_data),
            mentions_summary=self.formatter.format_mentions_summary(mentions_data),
            competitor_data=self.formatter.format_competitor_data(competitor_data),
            avg_sentiment=avg_sentiment,
            sentiment_trend=sentiment_trend,
            volume_change=volume_change,
            competitor_changes=competitor_changes,
            days=days,
        )
        
        # 4. Call AI
        try:
            ai_response, model_used = await ai_clients.call(SYSTEM_PROMPT, prompt, use_model)
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            # Return fallback response
            ai_response = {
                "market_sentiment": "stable",
                "market_sentiment_score": 0,
                "predictions": [],
                "opportunities": [],
                "risks": [],
                "executive_summary": "AI analysis temporarily unavailable. Please try again later.",
                "recommended_actions": ["Check AI API configuration", "Try again in a few minutes"],
                "key_insights": ["Analysis could not be completed"],
            }
            model_used = "fallback"
        
        # 5. Parse response
        result = self.parser.parse_analysis_response(
            user_id=user_id,
            ai_response=ai_response,
            products=products,
            model_used=model_used,
            days=days,
            mentions_count=len(mentions_data),
        )
        
        logger.info(
            f"AI trend analysis complete: {len(result.predictions)} predictions, "
            f"{len(result.opportunities)} opportunities, {len(result.risks)} risks"
        )
        
        return result
    
    async def get_product_opportunity(
        self,
        user_id: str,
        product_id: str,
        use_model: str = "openai",
    ) -> PricingOpportunity:
        """
        Analyze a specific product for pricing opportunities.
        
        Args:
            user_id: The user requesting analysis
            product_id: The product to analyze
            use_model: Which AI model to use
            
        Returns:
            PricingOpportunity for the product
        """
        # Get product (ASYNC)
        products = await self.collector.get_products(user_id, [product_id])
        if not products:
            raise ValueError(f"Product {product_id} not found")
        product = products[0]
        
        # Collect product-specific data (ASYNC)
        sentiment_data = await self.collector.get_product_sentiment(product_id, days=30)
        mentions = await self.collector.get_product_mentions(product_id, days=7)
        competitors = await self.collector.get_product_competitors(product_id)
        
        # Build prompt
        prompt = build_opportunity_prompt(
            product_name=product.name,
            current_price=str(product.base_price) if hasattr(product, 'base_price') else str(product.current_price),
            min_price=str(product.min_price) if product.min_price else "N/A",
            max_price=str(product.max_price) if product.max_price else "N/A",
            cost=str(product.cost) if hasattr(product, 'cost') and product.cost else "N/A",
            sentiment_score=sentiment_data.get("current", 0),
            sentiment_7d=sentiment_data.get("avg_7d", 0),
            sentiment_30d=sentiment_data.get("avg_30d", 0),
            sentiment_trend=sentiment_data.get("trend", "stable"),
            current_volume=len(mentions),
            avg_volume=sentiment_data.get("avg_volume", 0),
            volume_change=sentiment_data.get("volume_change", 0),
            competitor_prices=self.formatter.format_competitor_prices(competitors),
            recent_mentions=self.formatter.format_recent_mentions(mentions[:10]),
        )
        
        # Call AI
        ai_response, _ = await ai_clients.call(SYSTEM_PROMPT, prompt, use_model)
        
        # Parse response
        return self.parser.parse_opportunity_response(product, ai_response)
    
    async def detect_risks(
        self,
        user_id: str,
        use_model: str = "openai",
    ) -> list[RiskAlert]:
        """
        Detect potential risks across all products.
        
        Args:
            user_id: The user to analyze
            use_model: Which AI model to use
            
        Returns:
            List of RiskAlert objects
        """
        # Collect data (ASYNC)
        products = await self.collector.get_products(user_id)
        negative_mentions = await self.collector.get_negative_mentions(user_id, days=7)
        sentiment_drops = await self.collector.get_sentiment_drops(user_id, days=7)
        competitor_activities = await self.collector.get_recent_competitor_activities(user_id)
        current_alerts = await self.collector.get_current_alerts(user_id)
        
        if not products:
            logger.warning(f"No products found for risk detection, user {user_id}")
            return []
        
        # Build prompt
        prompt = build_risk_prompt(
            products=self.formatter.format_products(products),
            negative_mentions=self.formatter.format_negative_mentions(negative_mentions),
            sentiment_drops=self.formatter.format_sentiment_drops(sentiment_drops),
            competitor_activities=self.formatter.format_competitor_activities(competitor_activities),
            current_alerts=self.formatter.format_current_alerts(current_alerts),
        )
        
        # Call AI
        try:
            ai_response, _ = await ai_clients.call(SYSTEM_PROMPT, prompt, use_model)
        except Exception as e:
            logger.error(f"AI call failed for risk detection: {e}")
            return []
        
        # Parse response
        return self.parser.parse_risk_response(ai_response)
    
    async def generate_insight(
        self,
        user_id: str,
        days: int = 30,
        use_model: str = "openai",
    ) -> AIInsight:
        """
        Generate a market insight report.
        
        Args:
            user_id: The user to analyze
            days: Number of days to analyze
            use_model: Which AI model to use
            
        Returns:
            AIInsight object with detailed analysis
        """
        # Collect data (ASYNC)
        products = await self.collector.get_products(user_id)
        sentiment_data = await self.collector.get_sentiment_history(user_id, days)
        mentions_data = await self.collector.get_mentions_summary(user_id, days)
        
        if not products:
            logger.warning(f"No products found for insight generation, user {user_id}")
            # Return placeholder insight
            return self.parser.parse_insight_response(
                ai_response={
                    "title": "No Data Available",
                    "summary": "Add products to enable market insights.",
                    "detailed_analysis": "",
                    "key_factors": [],
                },
                model_used=use_model,
                mentions_count=0,
            )
        
        # Calculate metrics
        avg_sentiment = self.calculator.calculate_avg_sentiment(sentiment_data)
        volatility = self.calculator.calculate_sentiment_volatility(sentiment_data)
        top_product = self.calculator.get_top_performing_product(products, sentiment_data)
        worst_product = self.calculator.get_worst_performing_product(products, sentiment_data)
        trends = self.calculator.detect_basic_trends(sentiment_data)
        events = self.calculator.detect_notable_events(sentiment_data, mentions_data)
        
        # Build prompt
        prompt = build_insight_prompt(
            days=days,
            total_mentions=len(mentions_data),
            avg_sentiment=avg_sentiment,
            sentiment_volatility=volatility,
            top_product=top_product,
            worst_product=worst_product,
            trends=self.formatter.format_trends(trends),
            events=self.formatter.format_events(events),
        )
        
        # Call AI
        try:
            ai_response, model_used = await ai_clients.call(SYSTEM_PROMPT, prompt, use_model)
        except Exception as e:
            logger.error(f"AI call failed for insight generation: {e}")
            return self.parser.parse_insight_response(
                ai_response={
                    "title": "Analysis Unavailable",
                    "summary": "AI service temporarily unavailable. Please try again.",
                    "detailed_analysis": "",
                    "key_factors": [],
                },
                model_used="fallback",
                mentions_count=len(mentions_data),
            )
        
        # Parse response
        return self.parser.parse_insight_response(ai_response, model_used, len(mentions_data))
    


    