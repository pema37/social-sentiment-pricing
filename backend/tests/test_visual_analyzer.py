"""
Tests for Visual Pricing Analyzer — Recommendation Parsing & Price Calculations

Tests the JSON parsing logic and price change math in the visual pricing pipeline.
No Gemini API dependency.
"""

import pytest
import json
import re
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional


# ── Local replicas of data classes ──

@dataclass
class ProductInfo:
    name: str
    price: Decimal
    currency: str = "USD"
    features: list = field(default_factory=list)


@dataclass
class PricingRecommendation:
    recommended_price: Decimal
    confidence: float
    reasoning: str
    price_change_percent: float
    strategy: str
    risk_level: str
    key_factors: list = field(default_factory=list)


# ── Helper method extracted from VisualPricingAnalyzer ──

def _parse_recommendation(response: str, your_product: ProductInfo) -> PricingRecommendation:
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        else:
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
            key_factors=data.get("key_factors", []),
        )

    except Exception:
        return PricingRecommendation(
            recommended_price=your_product.price,
            confidence=0.3,
            reasoning=response,
            price_change_percent=0,
            strategy="maintain",
            risk_level="medium",
            key_factors=["Unable to parse AI recommendation"],
        )


# ═════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture
def product_29():
    return ProductInfo(name="Wireless Earbuds", price=Decimal("29.99"))


@pytest.fixture
def product_100():
    return ProductInfo(name="Premium Headphones", price=Decimal("100.00"))


@pytest.fixture
def product_zero():
    return ProductInfo(name="Free Tier", price=Decimal("0"))


# ═════════════════════════════════════════════════════════════════════════
# RECOMMENDATION PARSING TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestParseRecommendation:

    def test_valid_json_block(self, product_29):
        response = '''Based on my analysis:

```json
{
  "recommended_price": 24.99,
  "confidence": 0.85,
  "strategy": "decrease",
  "risk_level": "low",
  "key_factors": ["Competitor priced at $22.99", "Strong brand loyalty"]
}
```

This should increase conversion rates.'''

        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("24.99")
        assert result.confidence == 0.85
        assert result.strategy == "decrease"
        assert result.risk_level == "low"
        assert len(result.key_factors) == 2
        assert result.price_change_percent < 0  # Decrease

    def test_price_increase(self, product_29):
        response = '''```json
{
  "recommended_price": 34.99,
  "confidence": 0.7,
  "strategy": "increase",
  "risk_level": "medium"
}
```'''
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("34.99")
        assert result.price_change_percent > 0  # Increase
        assert result.strategy == "increase"

    def test_maintain_price(self, product_29):
        response = '''```json
{
  "recommended_price": 29.99,
  "confidence": 0.9,
  "strategy": "maintain",
  "risk_level": "low"
}
```'''
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("29.99")
        assert abs(result.price_change_percent) < 0.01  # No change

    def test_json_without_language_tag(self, product_29):
        response = '''```
{"recommended_price": 27.99, "confidence": 0.6}
```'''
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("27.99")

    def test_raw_json_in_response(self, product_29):
        """Test regex fallback for JSON without code fences."""
        response = 'I recommend {"recommended_price": 25.00, "confidence": 0.75} for this product.'
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("25.00")
        assert result.confidence == 0.75

    def test_no_json_returns_safe_default(self, product_29):
        response = "I think you should lower the price but I cannot provide structured data."
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == product_29.price  # Keeps current
        assert result.confidence == 0.3
        assert result.strategy == "maintain"
        assert "Unable to parse" in result.key_factors[0]

    def test_malformed_json_returns_safe_default(self, product_29):
        response = '```json\n{broken json\n```'
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == product_29.price
        assert result.confidence == 0.3

    def test_empty_response_returns_safe_default(self, product_29):
        result = _parse_recommendation("", product_29)
        assert result.recommended_price == product_29.price
        assert result.strategy == "maintain"

    def test_missing_fields_use_defaults(self, product_29):
        response = '```json\n{"recommended_price": 22.00}\n```'
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("22.00")
        assert result.confidence == 0.5  # Default
        assert result.strategy == "maintain"  # Default
        assert result.risk_level == "medium"  # Default
        assert result.key_factors == []  # Default


# ═════════════════════════════════════════════════════════════════════════
# PRICE CHANGE CALCULATION TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestPriceChangeCalculation:

    def test_10_percent_decrease(self, product_100):
        response = '```json\n{"recommended_price": 90.00}\n```'
        result = _parse_recommendation(response, product_100)
        assert result.price_change_percent == pytest.approx(-10.0)

    def test_50_percent_increase(self, product_100):
        response = '```json\n{"recommended_price": 150.00}\n```'
        result = _parse_recommendation(response, product_100)
        assert result.price_change_percent == pytest.approx(50.0)

    def test_zero_change(self, product_100):
        response = '```json\n{"recommended_price": 100.00}\n```'
        result = _parse_recommendation(response, product_100)
        assert result.price_change_percent == pytest.approx(0.0)

    def test_zero_price_product(self, product_zero):
        """Division by zero should be handled gracefully."""
        response = '```json\n{"recommended_price": 9.99}\n```'
        result = _parse_recommendation(response, product_zero)
        assert result.recommended_price == Decimal("9.99")
        assert result.price_change_percent == 0  # Can't calculate % from 0

    def test_large_price_change(self, product_29):
        response = '```json\n{"recommended_price": 299.99}\n```'
        result = _parse_recommendation(response, product_29)
        assert result.price_change_percent > 900  # ~900% increase

    def test_penny_difference(self, product_100):
        response = '```json\n{"recommended_price": 100.01}\n```'
        result = _parse_recommendation(response, product_100)
        assert result.price_change_percent == pytest.approx(0.01)

    def test_reasoning_preserved(self, product_29):
        response = '''Here is my detailed analysis of the market.

```json
{"recommended_price": 24.99}
```

The competitor is undercutting you significantly.'''
        result = _parse_recommendation(response, product_29)
        assert "detailed analysis" in result.reasoning
        assert "undercutting" in result.reasoning


# ═════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═════════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_multiple_json_blocks_takes_first(self, product_29):
        """When multiple JSON blocks exist, first one wins."""
        response = '''```json
{"recommended_price": 19.99}
```

Actually on second thought:

```json
{"recommended_price": 39.99}
```'''
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("19.99")

    def test_negative_price_still_parses(self, product_29):
        """Negative price is technically valid JSON — we parse it."""
        response = '```json\n{"recommended_price": -5.00}\n```'
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("-5.00")

    def test_very_long_response(self, product_29):
        """Large response should still find the JSON block."""
        padding = "Analysis data point. " * 1000
        response = f'''{padding}

```json
{{"recommended_price": 27.50, "confidence": 0.95}}
```

{padding}'''
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("27.50")
        assert result.confidence == 0.95

    def test_unicode_in_response(self, product_29):
        response = '''Análisis del precio: está muy alto 🏷️

```json
{"recommended_price": 22.99, "key_factors": ["Precio competitivo"]}
```'''
        result = _parse_recommendation(response, product_29)
        assert result.recommended_price == Decimal("22.99")
        assert "Precio competitivo" in result.key_factors
