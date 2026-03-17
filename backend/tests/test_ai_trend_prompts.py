"""
Tests for services/ai_trend_analysis/prompts.py

Covers:
- Prompt template constants exist and contain key content
- build_trend_analysis_prompt (all params + default days)
- build_opportunity_prompt (all params + cost=None → "N/A")
- build_risk_prompt (all params)
- build_insight_prompt (all params)
"""

import sys
from unittest.mock import MagicMock

# ── Import isolation ──────────────────────────────────────────────
for mod in ["db.session"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from services.ai_trend_analysis.prompts import (
    INSIGHT_GENERATION_PROMPT,
    OPPORTUNITY_ANALYSIS_PROMPT,
    RISK_DETECTION_PROMPT,
    SYSTEM_PROMPT,
    TREND_ANALYSIS_PROMPT,
    build_insight_prompt,
    build_opportunity_prompt,
    build_risk_prompt,
    build_trend_analysis_prompt,
)

# ==================================================================
# Prompt Constants
# ==================================================================


class TestPromptConstants:
    """Verify prompt templates exist and contain expected structure."""

    def test_system_prompt_exists(self):
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 50

    def test_system_prompt_contains_role(self):
        assert "e-commerce" in SYSTEM_PROMPT.lower()
        assert "pricing" in SYSTEM_PROMPT.lower()

    def test_system_prompt_requires_json(self):
        assert "JSON" in SYSTEM_PROMPT

    def test_trend_analysis_prompt_has_placeholders(self):
        assert "{product_data}" in TREND_ANALYSIS_PROMPT
        assert "{sentiment_history}" in TREND_ANALYSIS_PROMPT
        assert "{mentions_summary}" in TREND_ANALYSIS_PROMPT
        assert "{competitor_data}" in TREND_ANALYSIS_PROMPT
        assert "{avg_sentiment}" in TREND_ANALYSIS_PROMPT
        assert "{sentiment_trend}" in TREND_ANALYSIS_PROMPT
        assert "{volume_change}" in TREND_ANALYSIS_PROMPT
        assert "{competitor_changes}" in TREND_ANALYSIS_PROMPT
        assert "{days}" in TREND_ANALYSIS_PROMPT

    def test_trend_analysis_prompt_has_json_schema(self):
        assert "market_sentiment" in TREND_ANALYSIS_PROMPT
        assert "predictions" in TREND_ANALYSIS_PROMPT
        assert "opportunities" in TREND_ANALYSIS_PROMPT
        assert "risks" in TREND_ANALYSIS_PROMPT
        assert "executive_summary" in TREND_ANALYSIS_PROMPT

    def test_opportunity_prompt_has_placeholders(self):
        assert "{product_name}" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "{current_price}" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "{min_price}" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "{max_price}" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "{cost}" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "{sentiment_score}" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "{sentiment_7d}" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "{sentiment_30d}" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "{competitor_prices}" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "{recent_mentions}" in OPPORTUNITY_ANALYSIS_PROMPT

    def test_opportunity_prompt_has_json_schema(self):
        assert "recommendation" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "suggested_price" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "confidence_score" in OPPORTUNITY_ANALYSIS_PROMPT
        assert "timing" in OPPORTUNITY_ANALYSIS_PROMPT

    def test_risk_prompt_has_placeholders(self):
        assert "{products}" in RISK_DETECTION_PROMPT
        assert "{negative_mentions}" in RISK_DETECTION_PROMPT
        assert "{sentiment_drops}" in RISK_DETECTION_PROMPT
        assert "{competitor_activities}" in RISK_DETECTION_PROMPT
        assert "{current_alerts}" in RISK_DETECTION_PROMPT

    def test_risk_prompt_has_json_schema(self):
        assert "risk_level" in RISK_DETECTION_PROMPT
        assert "risk_type" in RISK_DETECTION_PROMPT
        assert "overall_risk_assessment" in RISK_DETECTION_PROMPT

    def test_insight_prompt_has_placeholders(self):
        assert "{days}" in INSIGHT_GENERATION_PROMPT
        assert "{total_mentions}" in INSIGHT_GENERATION_PROMPT
        assert "{avg_sentiment}" in INSIGHT_GENERATION_PROMPT
        assert "{sentiment_volatility}" in INSIGHT_GENERATION_PROMPT
        assert "{top_product}" in INSIGHT_GENERATION_PROMPT
        assert "{worst_product}" in INSIGHT_GENERATION_PROMPT
        assert "{trends}" in INSIGHT_GENERATION_PROMPT
        assert "{events}" in INSIGHT_GENERATION_PROMPT

    def test_insight_prompt_has_json_schema(self):
        assert "title" in INSIGHT_GENERATION_PROMPT
        assert "detailed_analysis" in INSIGHT_GENERATION_PROMPT
        assert "actionable_takeaways" in INSIGHT_GENERATION_PROMPT
        assert "outlook" in INSIGHT_GENERATION_PROMPT


# ==================================================================
# build_trend_analysis_prompt
# ==================================================================


class TestBuildTrendAnalysisPrompt:
    def _call(self, **overrides):
        defaults = {
            "product_data": "- Widget: $29.99",
            "sentiment_history": "- 2026-02-01: 0.75 (n=10)",
            "mentions_summary": "Total mentions: 50",
            "competitor_data": "- Amazon: $24.99",
            "avg_sentiment": 0.72,
            "sentiment_trend": "rising",
            "volume_change": 15.5,
            "competitor_changes": "Amazon dropped 10%",
        }
        defaults.update(overrides)
        return build_trend_analysis_prompt(**defaults)

    def test_returns_string(self):
        result = self._call()
        assert isinstance(result, str)

    def test_contains_product_data(self):
        result = self._call(product_data="- Premium Widget: $99.99")
        assert "Premium Widget: $99.99" in result

    def test_contains_sentiment_history(self):
        result = self._call(sentiment_history="- 2026-02-05: 0.85 (n=20)")
        assert "2026-02-05: 0.85 (n=20)" in result

    def test_contains_mentions_summary(self):
        result = self._call(mentions_summary="Total mentions: 150")
        assert "Total mentions: 150" in result

    def test_contains_competitor_data(self):
        result = self._call(competitor_data="- BestBuy: $19.99")
        assert "BestBuy: $19.99" in result

    def test_contains_avg_sentiment(self):
        result = self._call(avg_sentiment=0.42)
        assert "0.42" in result

    def test_contains_sentiment_trend(self):
        result = self._call(sentiment_trend="falling")
        assert "falling" in result

    def test_contains_volume_change(self):
        result = self._call(volume_change=-25.3)
        assert "-25.3" in result

    def test_contains_competitor_changes(self):
        result = self._call(competitor_changes="Target raised 5%")
        assert "Target raised 5%" in result

    def test_default_days_is_30(self):
        result = self._call()
        assert "Last 30 Days" in result

    def test_custom_days(self):
        result = build_trend_analysis_prompt(
            product_data="x",
            sentiment_history="x",
            mentions_summary="x",
            competitor_data="x",
            avg_sentiment=0.5,
            sentiment_trend="stable",
            volume_change=0.0,
            competitor_changes="none",
            days=7,
        )
        assert "Last 7 Days" in result

    def test_no_unformatted_placeholders(self):
        result = self._call()
        # Should have no remaining {placeholder} patterns
        # (escaped {{ }} in JSON schema are fine)
        import re

        # Find single-brace placeholders, not double-brace
        singles = re.findall(r"(?<!\{)\{[a-z_]+\}(?!\})", result)
        assert singles == [], f"Unformatted placeholders found: {singles}"

    def test_contains_json_schema(self):
        result = self._call()
        assert "market_sentiment" in result
        assert "predictions" in result


# ==================================================================
# build_opportunity_prompt
# ==================================================================


class TestBuildOpportunityPrompt:
    def _call(self, **overrides):
        defaults = {
            "product_name": "Wireless Headphones",
            "current_price": "79.99",
            "min_price": "49.99",
            "max_price": "129.99",
            "cost": "35.00",
            "sentiment_score": 0.72,
            "sentiment_7d": 0.68,
            "sentiment_30d": 0.55,
            "sentiment_trend": "rising",
            "current_volume": 45,
            "avg_volume": 30.0,
            "volume_change": 50.0,
            "competitor_prices": "- Amazon: $69.99",
            "recent_mentions": "- [0.85] Great product...",
        }
        defaults.update(overrides)
        return build_opportunity_prompt(**defaults)

    def test_returns_string(self):
        result = self._call()
        assert isinstance(result, str)

    def test_contains_product_name(self):
        result = self._call(product_name="Super Widget Pro")
        assert "Super Widget Pro" in result

    def test_contains_prices(self):
        result = self._call(
            current_price="99.99",
            min_price="59.99",
            max_price="149.99",
        )
        assert "$99.99" in result
        assert "$59.99" in result
        assert "$149.99" in result

    def test_contains_cost(self):
        result = self._call(cost="45.00")
        assert "$45.00" in result

    def test_cost_none_shows_na(self):
        result = self._call(cost=None)
        assert "N/A" in result

    def test_cost_empty_string_shows_na(self):
        result = self._call(cost="")
        assert "N/A" in result

    def test_contains_sentiment_scores(self):
        result = self._call(
            sentiment_score=0.85,
            sentiment_7d=0.78,
            sentiment_30d=0.60,
        )
        assert "0.85" in result
        assert "0.78" in result
        assert "0.6" in result

    def test_contains_sentiment_trend(self):
        result = self._call(sentiment_trend="volatile")
        assert "volatile" in result

    def test_contains_volume_data(self):
        result = self._call(
            current_volume=100,
            avg_volume=50.0,
            volume_change=100.0,
        )
        assert "100" in result
        assert "50.0" in result

    def test_contains_competitor_prices(self):
        result = self._call(competitor_prices="- BestBuy: $59.99\n- Target: $64.99")
        assert "BestBuy: $59.99" in result
        assert "Target: $64.99" in result

    def test_contains_recent_mentions(self):
        result = self._call(recent_mentions="- [0.90] Amazing quality...")
        assert "Amazing quality" in result

    def test_no_unformatted_placeholders(self):
        result = self._call()
        import re

        singles = re.findall(r"(?<!\{)\{[a-z_]+\}(?!\})", result)
        assert singles == [], f"Unformatted placeholders found: {singles}"

    def test_contains_json_schema(self):
        result = self._call()
        assert "recommendation" in result
        assert "suggested_price" in result


# ==================================================================
# build_risk_prompt
# ==================================================================


class TestBuildRiskPrompt:
    def _call(self, **overrides):
        defaults = {
            "products": "- Widget: $29.99",
            "negative_mentions": "- [-0.9] Terrible quality",
            "sentiment_drops": "- Score dropped 40% on 2026-02-01",
            "competitor_activities": "- Amazon dropped price 20%",
            "current_alerts": "- price_drop: Competitor undercut by 15%",
        }
        defaults.update(overrides)
        return build_risk_prompt(**defaults)

    def test_returns_string(self):
        result = self._call()
        assert isinstance(result, str)

    def test_contains_products(self):
        result = self._call(products="- Premium Widget: $99.99")
        assert "Premium Widget: $99.99" in result

    def test_contains_negative_mentions(self):
        result = self._call(negative_mentions="- [-0.95] Product broke after 1 day")
        assert "Product broke after 1 day" in result

    def test_contains_sentiment_drops(self):
        result = self._call(sentiment_drops="- Major drop on Feb 3")
        assert "Major drop on Feb 3" in result

    def test_contains_competitor_activities(self):
        result = self._call(competitor_activities="- Target launched competing product")
        assert "Target launched competing product" in result

    def test_contains_current_alerts(self):
        result = self._call(current_alerts="- crisis: PR incident detected")
        assert "crisis: PR incident detected" in result

    def test_no_unformatted_placeholders(self):
        result = self._call()
        import re

        singles = re.findall(r"(?<!\{)\{[a-z_]+\}(?!\})", result)
        assert singles == [], f"Unformatted placeholders found: {singles}"

    def test_contains_json_schema(self):
        result = self._call()
        assert "risk_level" in result
        assert "overall_risk_assessment" in result


# ==================================================================
# build_insight_prompt
# ==================================================================


class TestBuildInsightPrompt:
    def _call(self, **overrides):
        defaults = {
            "days": 30,
            "total_mentions": 500,
            "avg_sentiment": 0.65,
            "sentiment_volatility": 0.15,
            "top_product": "Wireless Headphones",
            "worst_product": "Budget Earbuds",
            "trends": "- Rising demand for wireless audio",
            "events": "- CES 2026 product announcements",
        }
        defaults.update(overrides)
        return build_insight_prompt(**defaults)

    def test_returns_string(self):
        result = self._call()
        assert isinstance(result, str)

    def test_contains_days(self):
        result = self._call(days=7)
        assert "Last 7 Days" in result

    def test_contains_total_mentions(self):
        result = self._call(total_mentions=1234)
        assert "1234" in result

    def test_contains_avg_sentiment(self):
        result = self._call(avg_sentiment=0.82)
        assert "0.82" in result

    def test_contains_sentiment_volatility(self):
        result = self._call(sentiment_volatility=0.35)
        assert "0.35" in result

    def test_contains_top_product(self):
        result = self._call(top_product="Super Widget")
        assert "Super Widget" in result

    def test_contains_worst_product(self):
        result = self._call(worst_product="Bad Widget")
        assert "Bad Widget" in result

    def test_contains_trends(self):
        result = self._call(trends="- Strong uptrend in electronics")
        assert "Strong uptrend in electronics" in result

    def test_contains_events(self):
        result = self._call(events="- Prime Day announced")
        assert "Prime Day announced" in result

    def test_no_unformatted_placeholders(self):
        result = self._call()
        import re

        singles = re.findall(r"(?<!\{)\{[a-z_]+\}(?!\})", result)
        assert singles == [], f"Unformatted placeholders found: {singles}"

    def test_contains_json_schema(self):
        result = self._call()
        assert "title" in result
        assert "detailed_analysis" in result
        assert "outlook" in result

    def test_negative_sentiment(self):
        result = self._call(avg_sentiment=-0.45)
        assert "-0.45" in result

    def test_zero_mentions(self):
        result = self._call(total_mentions=0)
        assert "0" in result
