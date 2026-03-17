"""
Trend Analysis API Routes

Endpoints for AI-powered trend analysis, pricing opportunities,
risk detection, and market insights.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from db.session import get_session
from schemas.trend_analysis import (
    AIInsightResponse,
    PricingOpportunityResponse,
    QuickStatsResponse,
    RiskAlertResponse,
    RiskDetectionResponse,
    RiskLevel,
    TrendAnalysisRequest,
    TrendAnalysisResponse,
    TrendDirection,
)
from services.ai_trend_analysis import AITrendAnalyzer

router = APIRouter(prefix="/trend-analysis", tags=["Trend Analysis"])


# ============================================
# MAIN ANALYSIS ENDPOINT
# ============================================


@router.post("/analyze", response_model=TrendAnalysisResponse)
async def run_trend_analysis(
    request: TrendAnalysisRequest,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """
    Run comprehensive AI trend analysis.

    Analyzes sentiment data, social mentions, and competitor prices
    to generate predictions, opportunities, and risk alerts.

    - **days**: Number of days to analyze (7-90, default 30)
    - **product_ids**: Optional list of specific products (None = all)
    - **use_model**: AI model to use ('openai' or 'gemini')
    """
    try:
        analyzer = AITrendAnalyzer(db)
        result = await analyzer.analyze(
            user_id=str(current_user.id),
            days=request.days,
            product_ids=request.product_ids,
            use_model=request.use_model,
        )

        return TrendAnalysisResponse(**result.to_dict())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e!s}")


# ============================================
# PRODUCT OPPORTUNITY ENDPOINT
# ============================================


@router.post("/opportunity/{product_id}", response_model=PricingOpportunityResponse)
async def analyze_product_opportunity(
    product_id: str,
    use_model: str = Query(default="openai", pattern="^(openai|gemini)$"),
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """
    Analyze a specific product for pricing opportunities.

    Returns AI-generated pricing recommendation with confidence score,
    expected impact, and reasoning.

    - **product_id**: The product to analyze
    - **use_model**: AI model to use ('openai' or 'gemini')
    """
    try:
        analyzer = AITrendAnalyzer(db)
        result = await analyzer.get_product_opportunity(
            user_id=str(current_user.id),
            product_id=product_id,
            use_model=use_model,
        )

        return PricingOpportunityResponse(
            opportunity_type=result.opportunity_type,
            product_id=result.product_id,
            product_name=result.product_name,
            current_price=str(result.current_price),
            suggested_price=str(result.suggested_price),
            expected_impact=result.expected_impact,
            confidence=result.confidence,
            confidence_score=result.confidence_score,
            reasoning=result.reasoning,
            valid_until=result.valid_until,
            triggers=result.triggers,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e!s}")


# ============================================
# RISK DETECTION ENDPOINT
# ============================================


@router.post("/risks", response_model=RiskDetectionResponse)
async def detect_risks(
    use_model: str = Query(default="openai", pattern="^(openai|gemini)$"),
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """
    Detect potential risks across all products.

    Analyzes negative mentions, sentiment drops, and competitor activities
    to identify risks that require attention.

    - **use_model**: AI model to use ('openai' or 'gemini')
    """
    try:
        analyzer = AITrendAnalyzer(db)
        risks = await analyzer.detect_risks(
            user_id=str(current_user.id),
            use_model=use_model,
        )

        # Determine overall risk level
        if not risks:
            overall_level = RiskLevel.LOW
            summary = "No significant risks detected."
        else:
            risk_levels = [r.risk_level for r in risks]
            if RiskLevel.CRITICAL in risk_levels:
                overall_level = RiskLevel.CRITICAL
            elif RiskLevel.HIGH in risk_levels:
                overall_level = RiskLevel.HIGH
            elif RiskLevel.MEDIUM in risk_levels:
                overall_level = RiskLevel.MEDIUM
            else:
                overall_level = RiskLevel.LOW
            summary = f"Found {len(risks)} risk(s) requiring attention."

        return RiskDetectionResponse(
            risks=[
                RiskAlertResponse(
                    risk_level=r.risk_level,
                    risk_type=r.risk_type,
                    title=r.title,
                    description=r.description,
                    affected_products=r.affected_products,
                    recommended_actions=r.recommended_actions,
                    detected_at=r.detected_at,
                    expires_at=r.expires_at,
                )
                for r in risks
            ],
            overall_risk_level=overall_level,
            summary=summary,
            generated_at=datetime.now(UTC),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk detection failed: {e!s}")


# ============================================
# INSIGHT GENERATION ENDPOINT
# ============================================


@router.post("/insight", response_model=AIInsightResponse)
async def generate_insight(
    days: int = Query(default=30, ge=7, le=90),
    use_model: str = Query(default="openai", pattern="^(openai|gemini)$"),
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """
    Generate a market insight report.

    Creates an AI-generated narrative analysis of market conditions,
    trends, and actionable takeaways.

    - **days**: Number of days to analyze (7-90)
    - **use_model**: AI model to use ('openai' or 'gemini')
    """
    try:
        analyzer = AITrendAnalyzer(db)
        result = await analyzer.generate_insight(
            user_id=str(current_user.id),
            days=days,
            use_model=use_model,
        )

        return AIInsightResponse(
            title=result.title,
            summary=result.summary,
            detailed_analysis=result.detailed_analysis,
            key_factors=result.key_factors,
            data_points_analyzed=result.data_points_analyzed,
            generated_at=result.generated_at,
            model_used=result.model_used,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {e!s}")


# ============================================
# QUICK STATS ENDPOINT (No AI call)
# ============================================


@router.get("/quick-stats", response_model=QuickStatsResponse)
async def get_quick_stats(
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """
    Get quick stats for the trends dashboard.

    Returns real-time metrics without making AI calls.
    Fast endpoint for dashboard loading.
    """
    from sqlmodel import select

    from models.product import Product
    from models.sentiment import Sentiment
    from models.social_mention import SocialMention

    user_id = str(current_user.id)
    now = datetime.now(UTC)

    try:
        # Get products
        result = await db.execute(select(Product).where(Product.user_id == user_id))
        products = result.scalars().all()
        product_ids = [p.id for p in products]

        if not product_ids:
            return QuickStatsResponse(
                current_sentiment=0,
                sentiment_trend=TrendDirection.STABLE,
                sentiment_change_7d=0,
                mentions_today=0,
                mentions_7d=0,
                volume_change_percent=0,
                active_opportunities=0,
                potential_revenue_impact="$0",
                active_risks=0,
                highest_risk_level=RiskLevel.LOW,
                trending_up=[],
                trending_down=[],
                last_updated=now,
            )

        # Get recent sentiments
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(Sentiment).where(Sentiment.product_id.in_(product_ids)).where(Sentiment.created_at >= week_ago)
        )
        recent_sentiments = result.scalars().all()

        result = await db.execute(
            select(Sentiment)
            .where(Sentiment.product_id.in_(product_ids))
            .where(Sentiment.created_at >= two_weeks_ago)
            .where(Sentiment.created_at < week_ago)
        )
        older_sentiments = result.scalars().all()

        # Calculate sentiment metrics
        if recent_sentiments:
            recent_scores = [float(s.score) if s.score else 0 for s in recent_sentiments]
            current_sentiment = sum(recent_scores) / len(recent_scores)
        else:
            recent_scores = []
            current_sentiment = 0

        if older_sentiments:
            older_scores = [float(s.score) if s.score else 0 for s in older_sentiments]
            older_avg = sum(older_scores) / len(older_scores)
        else:
            older_avg = current_sentiment

        sentiment_change = current_sentiment - older_avg

        # Determine trend
        if sentiment_change > 0.1:
            sentiment_trend = TrendDirection.RISING
        elif sentiment_change < -0.1:
            sentiment_trend = TrendDirection.FALLING
        else:
            sentiment_trend = TrendDirection.STABLE

        # Get mention counts
        result = await db.execute(
            select(SocialMention)
            .where(SocialMention.product_id.in_(product_ids))
            .where(SocialMention.created_at >= today_start)
        )
        mentions_today = result.scalars().all()

        result = await db.execute(
            select(SocialMention)
            .where(SocialMention.product_id.in_(product_ids))
            .where(SocialMention.created_at >= week_ago)
        )
        mentions_7d = result.scalars().all()

        result = await db.execute(
            select(SocialMention)
            .where(SocialMention.product_id.in_(product_ids))
            .where(SocialMention.created_at >= two_weeks_ago)
            .where(SocialMention.created_at < week_ago)
        )
        mentions_prev_7d = result.scalars().all()

        # Calculate volume change
        if mentions_prev_7d:
            volume_change = ((len(mentions_7d) - len(mentions_prev_7d)) / len(mentions_prev_7d)) * 100
        else:
            volume_change = 0

        # Find trending products
        product_sentiments = {}
        for s in recent_sentiments:
            pid = str(s.product_id)
            if pid not in product_sentiments:
                product_sentiments[pid] = []
            product_sentiments[pid].append(float(s.score) if s.score else 0)

        trending_up = []
        trending_down = []

        for product in products:
            pid = str(product.id)
            if pid in product_sentiments:
                avg = sum(product_sentiments[pid]) / len(product_sentiments[pid])
                if avg > 0.3:
                    trending_up.append(product.name)
                elif avg < -0.3:
                    trending_down.append(product.name)

        return QuickStatsResponse(
            current_sentiment=round(current_sentiment, 2),
            sentiment_trend=sentiment_trend,
            sentiment_change_7d=round(sentiment_change, 2),
            mentions_today=len(mentions_today),
            mentions_7d=len(mentions_7d),
            volume_change_percent=round(volume_change, 1),
            active_opportunities=0,
            potential_revenue_impact="$0",
            active_risks=0,
            highest_risk_level=RiskLevel.LOW,
            trending_up=trending_up[:5],
            trending_down=trending_down[:5],
            last_updated=now,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e!s}")
