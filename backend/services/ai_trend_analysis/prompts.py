"""
AI Trend Analysis - Prompt Templates

These prompts are used with OpenAI/Gemini to generate insights.
"""

SYSTEM_PROMPT = """You are an expert e-commerce pricing analyst specializing in social sentiment analysis and market trends. Your role is to analyze data about products, their social media mentions, sentiment scores, and competitor prices to provide actionable pricing insights.

You must:
1. Be data-driven - base all conclusions on the provided metrics
2. Be specific - give concrete numbers and percentages
3. Be actionable - every insight should have a clear next step
4. Consider risk - always mention potential downsides
5. Use business language - speak to merchants, not data scientists

Output format: Always respond in valid JSON matching the requested schema."""


TREND_ANALYSIS_PROMPT = """Analyze the following e-commerce data and provide a comprehensive trend analysis.

## Product Data
{product_data}

## Sentiment History (Last {days} Days)
{sentiment_history}

## Social Mentions Summary
{mentions_summary}

## Competitor Data
{competitor_data}

## Current Market Signals
- Average sentiment score: {avg_sentiment}
- Sentiment trend: {sentiment_trend}
- Mention volume change: {volume_change}%
- Competitor price changes: {competitor_changes}

## Analysis Required

Provide a JSON response with the following structure:
{{
    "market_sentiment": "rising|falling|stable|volatile",
    "market_sentiment_score": <number from -100 to 100>,
    "predictions": [
        {{
            "direction": "rising|falling|stable|volatile",
            "category": "viral_positive|viral_negative|competitor_launch|seasonal|news_event|market_shift|organic_growth|organic_decline",
            "confidence": "low|medium|high|very_high",
            "confidence_score": <0-100>,
            "predicted_change": <percentage>,
            "timeframe_days": <1-30>,
            "reasoning": "<2-3 sentences explaining the prediction>"
        }}
    ],
    "opportunities": [
        {{
            "opportunity_type": "price_increase|price_decrease|hold|promotional|premium_positioning",
            "product_id": "<from input>",
            "product_name": "<from input>",
            "current_price": "<decimal>",
            "suggested_price": "<decimal>",
            "expected_impact": "<e.g., '+12% revenue'>",
            "confidence": "low|medium|high|very_high",
            "confidence_score": <0-100>,
            "reasoning": "<why this opportunity exists>",
            "triggers": ["<what signals triggered this>"]
        }}
    ],
    "risks": [
        {{
            "risk_level": "low|medium|high|critical",
            "risk_type": "<type of risk>",
            "title": "<short title>",
            "description": "<description of the risk>",
            "affected_products": ["<product names>"],
            "recommended_actions": ["<specific action items>"]
        }}
    ],
    "executive_summary": "<3-4 sentence summary of the overall analysis>",
    "recommended_actions": ["<top 3-5 prioritized actions to take>"],
    "key_insights": ["<3-5 key data-driven insights>"]
}}

Focus on identifying:
1. Trending products (positive or negative)
2. Pricing opportunities based on sentiment and competitor positions
3. Risks from negative sentiment or competitor actions
4. Seasonal or event-driven patterns
5. Actionable recommendations with expected impact"""


OPPORTUNITY_ANALYSIS_PROMPT = """Based on the following product and market data, identify specific pricing opportunities.

## Product: {product_name}
- Current Price: ${current_price}
- Min Price: ${min_price}
- Max Price: ${max_price}
- Cost: ${cost} (if available)

## Sentiment Data
- Current Score: {sentiment_score} (scale: -1 to +1)
- 7-day average: {sentiment_7d}
- 30-day average: {sentiment_30d}
- Trend: {sentiment_trend}

## Volume Data
- Current daily mentions: {current_volume}
- Average daily mentions: {avg_volume}
- Volume change: {volume_change}%

## Competitor Prices
{competitor_prices}

## Recent Mentions (Sample)
{recent_mentions}

Analyze this data and respond with a JSON object:
{{
    "recommendation": "increase|decrease|hold",
    "suggested_price": <decimal>,
    "confidence_score": <0-100>,
    "expected_revenue_impact": "<percentage>",
    "reasoning": {{
        "sentiment_factor": "<how sentiment affects this>",
        "volume_factor": "<how volume affects this>",
        "competitor_factor": "<how competitors affect this>",
        "overall": "<1-2 sentence summary>"
    }},
    "timing": {{
        "act_now": <boolean>,
        "optimal_window_days": <number>,
        "urgency_reason": "<why>"
    }},
    "risks": ["<potential downsides>"]
}}"""


RISK_DETECTION_PROMPT = """Analyze the following data for potential risks to the merchant's pricing and reputation.

## Products Being Monitored
{products}

## Recent Negative Mentions
{negative_mentions}

## Sentiment Drops (Last 7 Days)
{sentiment_drops}

## Competitor Activities
{competitor_activities}

## Current Alerts
{current_alerts}

Identify any risks and respond with a JSON array:
{{
    "risks": [
        {{
            "risk_level": "low|medium|high|critical",
            "risk_type": "reputation|competitor|market|operational",
            "title": "<short, descriptive title>",
            "description": "<detailed description>",
            "affected_products": ["<product names>"],
            "indicators": ["<what data points indicate this>"],
            "recommended_actions": ["<specific steps to mitigate>"],
            "urgency_hours": <how quickly to act>
        }}
    ],
    "overall_risk_assessment": "low|medium|high|critical",
    "summary": "<1-2 sentences summarizing risk landscape>"
}}"""


INSIGHT_GENERATION_PROMPT = """Generate a market insight based on the following analysis data.

## Time Period: Last {days} Days

## Key Metrics
- Total mentions analyzed: {total_mentions}
- Average sentiment: {avg_sentiment}
- Sentiment volatility: {sentiment_volatility}
- Top performing product: {top_product}
- Worst performing product: {worst_product}

## Trends Detected
{trends}

## Notable Events
{events}

Generate an insightful analysis in JSON format:
{{
    "title": "<catchy, informative title>",
    "summary": "<2-3 sentence executive summary>",
    "detailed_analysis": "<4-6 paragraph deep dive>",
    "key_factors": ["<3-5 key factors driving the market>"],
    "actionable_takeaways": ["<3-5 specific actions>"],
    "outlook": {{
        "short_term": "<1-7 days outlook>",
        "medium_term": "<7-30 days outlook>",
        "confidence": "low|medium|high"
    }}
}}"""


def build_trend_analysis_prompt(
    product_data: str,
    sentiment_history: str,
    mentions_summary: str,
    competitor_data: str,
    avg_sentiment: float,
    sentiment_trend: str,
    volume_change: float,
    competitor_changes: str,
    days: int = 30,
) -> str:
    """Build the complete trend analysis prompt."""
    return TREND_ANALYSIS_PROMPT.format(
        product_data=product_data,
        sentiment_history=sentiment_history,
        mentions_summary=mentions_summary,
        competitor_data=competitor_data,
        avg_sentiment=avg_sentiment,
        sentiment_trend=sentiment_trend,
        volume_change=volume_change,
        competitor_changes=competitor_changes,
        days=days,
    )


def build_opportunity_prompt(
    product_name: str,
    current_price: str,
    min_price: str,
    max_price: str,
    cost: str,
    sentiment_score: float,
    sentiment_7d: float,
    sentiment_30d: float,
    sentiment_trend: str,
    current_volume: int,
    avg_volume: float,
    volume_change: float,
    competitor_prices: str,
    recent_mentions: str,
) -> str:
    """Build the opportunity analysis prompt."""
    return OPPORTUNITY_ANALYSIS_PROMPT.format(
        product_name=product_name,
        current_price=current_price,
        min_price=min_price,
        max_price=max_price,
        cost=cost or "N/A",
        sentiment_score=sentiment_score,
        sentiment_7d=sentiment_7d,
        sentiment_30d=sentiment_30d,
        sentiment_trend=sentiment_trend,
        current_volume=current_volume,
        avg_volume=avg_volume,
        volume_change=volume_change,
        competitor_prices=competitor_prices,
        recent_mentions=recent_mentions,
    )


def build_risk_prompt(
    products: str,
    negative_mentions: str,
    sentiment_drops: str,
    competitor_activities: str,
    current_alerts: str,
) -> str:
    """Build the risk detection prompt."""
    return RISK_DETECTION_PROMPT.format(
        products=products,
        negative_mentions=negative_mentions,
        sentiment_drops=sentiment_drops,
        competitor_activities=competitor_activities,
        current_alerts=current_alerts,
    )


def build_insight_prompt(
    days: int,
    total_mentions: int,
    avg_sentiment: float,
    sentiment_volatility: float,
    top_product: str,
    worst_product: str,
    trends: str,
    events: str,
) -> str:
    """Build the insight generation prompt."""
    return INSIGHT_GENERATION_PROMPT.format(
        days=days,
        total_mentions=total_mentions,
        avg_sentiment=avg_sentiment,
        sentiment_volatility=sentiment_volatility,
        top_product=top_product,
        worst_product=worst_product,
        trends=trends,
        events=events,
    )
