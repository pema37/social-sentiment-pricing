# backend/api/v1/routes/alerts/crisis_detection.py
"""AI-powered crisis detection endpoint."""

from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import BaseModel

from db.session import get_session
from core.deps import get_current_user
from models.user import User
from models.sentiment import Sentiment
from models.product import Product

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class CrisisAlert(BaseModel):
    """AI-detected sentiment crisis."""
    product_id: UUID
    product_name: str
    severity: str  # "critical", "warning", "watch"
    sentiment_drop: float  # percentage drop
    current_sentiment: float
    previous_sentiment: float
    period_hours: int
    negative_mentions: int
    sample_texts: List[str]
    ai_summary: str
    recommended_actions: List[str]
    ai_powered: bool = True


class CrisisDetectionResponse(BaseModel):
    """Response from crisis detection."""
    crises_detected: int
    alerts: List[CrisisAlert]
    scan_period_hours: int
    ai_powered: bool


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_basic_crisis_summary(name: str, severity: str, drop: float, count: int) -> tuple:
    """Generate basic crisis summary without AI."""
    if severity == "critical":
        summary = f"Critical sentiment crisis detected for {name}. Sentiment dropped {drop*100:.0f}% with {count} negative mentions."
        actions = [
            "Immediately review negative feedback",
            "Prepare customer communication",
            "Consider pausing marketing campaigns",
            "Alert customer support team",
        ]
    elif severity == "warning":
        summary = f"Warning: {name} is experiencing negative sentiment trend. {count} negative mentions detected."
        actions = [
            "Monitor situation closely",
            "Review recent customer feedback",
            "Prepare response templates",
        ]
    else:
        summary = f"Watch alert for {name}. Minor sentiment decline detected."
        actions = [
            "Continue monitoring",
            "Review recent reviews and mentions",
        ]
    return summary, actions


async def _generate_crisis_summary(ai_generator, name: str, severity: str, drop: float, texts: list) -> dict:
    """Generate AI-powered crisis summary."""
    import json
    
    prompt = f"""Analyze this potential PR/sentiment crisis:

Product: {name}
Severity: {severity}
Sentiment Drop: {drop*100:.1f}%
Sample negative feedback:
{chr(10).join(f'- "{t}"' for t in texts[:5])}

Provide:
1. A 2-3 sentence summary of what's happening
2. 3-4 specific recommended actions

Return JSON: {{"summary": "...", "actions": ["...", "..."]}}"""

    response = await ai_generator.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a PR crisis management expert. Be specific and actionable."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=400
    )
    
    result_text = response.choices[0].message.content.strip()
    if result_text.startswith("```"):
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]
    
    return json.loads(result_text)


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/crisis-detection", response_model=CrisisDetectionResponse)
async def detect_sentiment_crises(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Period to analyze"),
    threshold: float = Query(0.2, ge=0.1, le=0.5, description="Sentiment drop threshold"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    AI-powered sentiment crisis detection.
    
    Scans all products for significant sentiment drops and provides
    AI-generated analysis of potential PR crises.
    """
    from services.ai_generator import ai_generator
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    previous_cutoff = cutoff - timedelta(hours=hours)
    
    # Get all user's products
    products_result = await session.execute(
        select(Product).where(Product.user_id == current_user.id)
    )
    products = products_result.scalars().all()
    
    crises = []
    
    for product in products:
        # Get recent sentiment
        recent_result = await session.execute(
            select(Sentiment)
            .where(Sentiment.product_id == product.id)
            .where(Sentiment.analyzed_at >= cutoff)
            .order_by(Sentiment.analyzed_at.desc())
        )
        recent_sentiments = recent_result.scalars().all()
        
        # Get previous period sentiment
        previous_result = await session.execute(
            select(Sentiment)
            .where(Sentiment.product_id == product.id)
            .where(Sentiment.analyzed_at >= previous_cutoff)
            .where(Sentiment.analyzed_at < cutoff)
        )
        previous_sentiments = previous_result.scalars().all()
        
        if not recent_sentiments:
            continue
        
        # Calculate averages
        current_avg = sum(float(s.compound_score) for s in recent_sentiments) / len(recent_sentiments)
        
        if previous_sentiments:
            previous_avg = sum(float(s.compound_score) for s in previous_sentiments) / len(previous_sentiments)
        else:
            previous_avg = 0.0
        
        # Check for significant drop
        sentiment_drop = previous_avg - current_avg
        
        if sentiment_drop >= threshold or current_avg < -0.3:
            # Gather negative mentions
            negative_mentions = [s for s in recent_sentiments if float(s.compound_score) < -0.1]
            sample_texts = [s.text[:200] for s in negative_mentions[:5] if s.text]
            
            # Determine severity
            if sentiment_drop >= 0.4 or current_avg < -0.5:
                severity = "critical"
            elif sentiment_drop >= 0.25 or current_avg < -0.3:
                severity = "warning"
            else:
                severity = "watch"
            
            # Generate AI summary if available
            if ai_generator.is_available() and sample_texts:
                try:
                    ai_result = await _generate_crisis_summary(
                        ai_generator,
                        product.name,
                        severity,
                        sentiment_drop,
                        sample_texts,
                    )
                    summary = ai_result["summary"]
                    actions = ai_result["actions"]
                    is_ai = True
                except Exception:
                    summary, actions = _generate_basic_crisis_summary(
                        product.name, severity, sentiment_drop, len(negative_mentions)
                    )
                    is_ai = False
            else:
                summary, actions = _generate_basic_crisis_summary(
                    product.name, severity, sentiment_drop, len(negative_mentions)
                )
                is_ai = False
            
            crises.append(CrisisAlert(
                product_id=product.id,
                product_name=product.name,
                severity=severity,
                sentiment_drop=round(sentiment_drop * 100, 1),
                current_sentiment=round(current_avg, 3),
                previous_sentiment=round(previous_avg, 3),
                period_hours=hours,
                negative_mentions=len(negative_mentions),
                sample_texts=sample_texts,
                ai_summary=summary,
                recommended_actions=actions,
                ai_powered=is_ai,
            ))
    
    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "watch": 2}
    crises.sort(key=lambda x: (severity_order.get(x.severity, 3), -x.sentiment_drop))
    
    return CrisisDetectionResponse(
        crises_detected=len(crises),
        alerts=crises,
        scan_period_hours=hours,
        ai_powered=ai_generator.is_available(),
    )

