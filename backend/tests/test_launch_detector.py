"""
Tests for Launch Detector — Confidence Scoring, JSON Parsing & Signal Processing

Tests all pure helper methods in the launch detection pipeline.
No Gemini API dependency.
"""

import pytest
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List


# ── Local replica of data classes ──

@dataclass
class LaunchSignal:
    source: str
    content: str
    url: Optional[str] = None
    timestamp: Optional[datetime] = None
    engagement: int = 0
    author: Optional[str] = None
    image_data: Optional[bytes] = None
    image_type: str = "png"


# ── Helper methods extracted from LaunchDetector ──

LAUNCH_KEYWORDS = [
    "new product", "launching", "announcing", "introducing",
    "released", "unveiled", "debuting", "available now",
    "coming soon", "pre-order", "just dropped", "brand new"
]
MIN_CONFIDENCE = 0.3


def _analyze_scanner_response(response, signals):
    response_lower = response.lower()

    keyword_matches = sum(1 for kw in LAUNCH_KEYWORDS if kw in response_lower)
    signal_matches = sum(
        1 for sig in signals
        if any(kw in sig.content.lower() for kw in LAUNCH_KEYWORDS)
    )

    base_confidence = 0.0

    if keyword_matches >= 3:
        base_confidence += 0.4
    elif keyword_matches >= 1:
        base_confidence += 0.2

    if signal_matches >= 2:
        base_confidence += 0.4
    elif signal_matches >= 1:
        base_confidence += 0.2

    strong_indicators = ["announcing", "introducing", "launching today", "now available"]
    if any(ind in response_lower for ind in strong_indicators):
        base_confidence += 0.2

    confidence = min(base_confidence, 1.0)
    launch_detected = confidence >= MIN_CONFIDENCE

    return launch_detected, confidence


def _parse_validator_json(response):
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
    except Exception:
        return default


def _parse_assessor_json(response):
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
    except Exception:
        return default


def _prepare_signal_summary(signals):
    if not signals:
        return "No signals available"
    lines = []
    for i, sig in enumerate(signals[:20], 1):
        timestamp = sig.timestamp.strftime("%Y-%m-%d %H:%M") if sig.timestamp else "Unknown time"
        engagement = f" | Engagement: {sig.engagement}" if sig.engagement > 0 else ""
        author = f" | @{sig.author}" if sig.author else ""
        lines.append(f"[Signal {i}] [{sig.source.upper()}] {timestamp}{author}{engagement}")
        lines.append(f"Content: {sig.content[:300]}{'...' if len(sig.content) > 300 else ''}")
        if sig.url:
            lines.append(f"URL: {sig.url}")
        lines.append("")
    return "\n".join(lines)


def _get_signal_sources(signals):
    return list(set(sig.source for sig in signals))


def _get_detailed_signals(signals, limit=5):
    sorted_signals = sorted(signals, key=lambda x: x.engagement, reverse=True)
    lines = []
    for sig in sorted_signals[:limit]:
        lines.append(f"=== [{sig.source.upper()}] ===")
        lines.append(sig.content)
        lines.append("")
    return "\n".join(lines) if lines else "No detailed signals available"


# ═════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════

@pytest.fixture
def launch_signals():
    """Signals clearly indicating a product launch."""
    base = datetime(2026, 2, 1, 10, 0)
    return [
        LaunchSignal(
            source="twitter", content="Apple is announcing a brand new iPhone model today!",
            timestamp=base, engagement=5000, author="techcrunch"
        ),
        LaunchSignal(
            source="reddit", content="Just dropped: Apple's new product is now available for pre-order",
            timestamp=base + timedelta(hours=1), engagement=3000, author="apple_insider"
        ),
        LaunchSignal(
            source="news", content="Apple introducing revolutionary pricing for new iPhone",
            timestamp=base + timedelta(hours=2), engagement=8000, author="verge"
        ),
    ]


@pytest.fixture
def boring_signals():
    """Signals with no launch indicators."""
    base = datetime(2026, 2, 1, 10, 0)
    return [
        LaunchSignal(
            source="twitter", content="I like using my current phone",
            timestamp=base, engagement=10, author="user1"
        ),
        LaunchSignal(
            source="reddit", content="What's your favorite app this week?",
            timestamp=base + timedelta(hours=1), engagement=5, author="user2"
        ),
    ]


@pytest.fixture
def single_signal():
    return [
        LaunchSignal(
            source="twitter", content="They are launching something new",
            timestamp=datetime(2026, 2, 1), engagement=100
        )
    ]


# ═════════════════════════════════════════════════════════════════════════
# SCANNER RESPONSE ANALYSIS TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestAnalyzeScannerResponse:

    def test_strong_launch_high_confidence(self, launch_signals):
        response = "The signals clearly show Apple is announcing and introducing a new product. It is now available for pre-order."
        detected, confidence = _analyze_scanner_response(response, launch_signals)
        assert detected is True
        assert confidence >= 0.6

    def test_no_launch_keywords_low_confidence(self, boring_signals):
        response = "Nothing interesting happening in the market today."
        detected, confidence = _analyze_scanner_response(response, boring_signals)
        assert detected is False
        assert confidence < MIN_CONFIDENCE

    def test_response_keywords_only(self, boring_signals):
        """Keywords in response but not in signals — needs strong indicator to cross threshold."""
        response = "They are announcing a brand new product launching today."
        detected, confidence = _analyze_scanner_response(response, boring_signals)
        assert detected is True  # Multiple keywords + strong indicator
        assert confidence >= MIN_CONFIDENCE

    def test_signal_keywords_only(self, launch_signals):
        """Keywords in signals but not in response."""
        response = "Based on the data I reviewed above."
        detected, confidence = _analyze_scanner_response(response, launch_signals)
        assert detected is True  # Signal matches contribute to confidence
        assert confidence >= 0.4

    def test_strong_indicators_boost(self):
        """Strong indicators like 'announcing' add 0.2 boost."""
        signals = [LaunchSignal(source="twitter", content="regular content")]
        response = "They are officially announcing a new product line."
        detected, confidence = _analyze_scanner_response(response, signals)
        # "announcing" is both a keyword (+0.2) and strong indicator (+0.2)
        assert confidence >= 0.4

    def test_confidence_capped_at_1(self, launch_signals):
        """Confidence should never exceed 1.0."""
        response = "announcing introducing launching new product released unveiled brand new available now"
        _, confidence = _analyze_scanner_response(response, launch_signals)
        assert confidence <= 1.0

    def test_empty_response_empty_signals(self):
        detected, confidence = _analyze_scanner_response("", [])
        assert detected is False
        assert confidence == 0.0

    def test_case_insensitive(self, boring_signals):
        response = "They are ANNOUNCING a NEW PRODUCT"
        detected, _ = _analyze_scanner_response(response, boring_signals)
        assert detected is True

    def test_minimum_confidence_boundary(self):
        """Confidence exactly at threshold should detect launch."""
        signals = [LaunchSignal(source="twitter", content="nothing special")]
        # One keyword match = 0.2, one strong indicator = 0.2 = 0.4 >= 0.3
        response = "They are announcing something"
        detected, confidence = _analyze_scanner_response(response, signals)
        assert detected is True
        assert confidence >= MIN_CONFIDENCE


# ═════════════════════════════════════════════════════════════════════════
# VALIDATOR JSON PARSING TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestParseValidatorJson:

    def test_valid_complete_json(self):
        response = '''After thorough analysis:

```json
{
  "is_confirmed_launch": true,
  "launch_type": "new_product",
  "confidence": 85,
  "product_name": "iPhone 17 Pro",
  "key_features": ["AI camera", "Titanium body", "USB-C"],
  "target_market": "Premium smartphone users",
  "estimated_price": "$1199",
  "launch_date": "March 2026"
}
```

This is a high-confidence detection.'''
        result = _parse_validator_json(response)
        assert result["is_confirmed_launch"] is True
        assert result["product_name"] == "iPhone 17 Pro"
        assert result["confidence"] == 85
        assert len(result["key_features"]) == 3
        assert result["launch_date"] == "March 2026"

    def test_partial_json_uses_defaults(self):
        response = '''```json
{
  "is_confirmed_launch": true,
  "product_name": "New Widget"
}
```'''
        result = _parse_validator_json(response)
        assert result["is_confirmed_launch"] is True
        assert result["product_name"] == "New Widget"
        # Defaults filled in
        assert result["launch_type"] == "unknown"
        assert result["key_features"] == []
        assert result["launch_date"] == "TBD"

    def test_no_json_returns_defaults(self):
        response = "I analyzed the signals but found no JSON to extract."
        result = _parse_validator_json(response)
        assert result["is_confirmed_launch"] is False
        assert result["product_name"] == "Unknown"

    def test_malformed_json_returns_defaults(self):
        response = '```json\n{invalid}\n```'
        result = _parse_validator_json(response)
        assert result["is_confirmed_launch"] is False
        assert result["confidence"] == 0

    def test_json_without_language_tag(self):
        response = '''```
{"is_confirmed_launch": true, "product_name": "Test Product"}
```'''
        result = _parse_validator_json(response)
        assert result["is_confirmed_launch"] is True

    def test_empty_response(self):
        result = _parse_validator_json("")
        assert result["product_name"] == "Unknown"


# ═════════════════════════════════════════════════════════════════════════
# ASSESSOR JSON PARSING TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestParseAssessorJson:

    def test_valid_assessment(self):
        response = '''```json
{
  "threat_level": "high",
  "threat_score": 78,
  "urgency": "immediate",
  "impact_areas": ["pricing", "market share"],
  "immediate_actions": ["Adjust pricing", "Brief sales team"],
  "strategic_actions": ["Accelerate roadmap"]
}
```'''
        result = _parse_assessor_json(response)
        assert result["threat_level"] == "high"
        assert result["threat_score"] == 78
        assert result["urgency"] == "immediate"
        assert len(result["immediate_actions"]) == 2

    def test_defaults_for_missing_fields(self):
        response = '```json\n{"threat_level": "low"}\n```'
        result = _parse_assessor_json(response)
        assert result["threat_level"] == "low"
        assert result["threat_score"] == 50  # default
        assert result["urgency"] == "monitor"  # default
        assert result["impact_areas"] == []  # default

    def test_no_json_returns_defaults(self):
        result = _parse_assessor_json("No structured data here.")
        assert result["threat_level"] == "medium"
        assert result["threat_score"] == 50

    def test_malformed_returns_defaults(self):
        result = _parse_assessor_json('```json\n{broken\n```')
        assert result["threat_level"] == "medium"


# ═════════════════════════════════════════════════════════════════════════
# SIGNAL PROCESSING TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestPrepareSignalSummary:

    def test_empty_signals(self):
        assert _prepare_signal_summary([]) == "No signals available"

    def test_formats_signal_correctly(self):
        signals = [LaunchSignal(
            source="twitter",
            content="Big announcement coming",
            timestamp=datetime(2026, 2, 1, 14, 30),
            engagement=500,
            author="techguru"
        )]
        result = _prepare_signal_summary(signals)
        assert "[TWITTER]" in result
        assert "2026-02-01 14:30" in result
        assert "@techguru" in result
        assert "Engagement: 500" in result
        assert "Big announcement coming" in result

    def test_no_engagement_omits_field(self):
        signals = [LaunchSignal(source="reddit", content="Test", timestamp=datetime(2026, 2, 1))]
        result = _prepare_signal_summary(signals)
        assert "Engagement:" not in result

    def test_no_author_omits_field(self):
        signals = [LaunchSignal(source="reddit", content="Test", timestamp=datetime(2026, 2, 1))]
        result = _prepare_signal_summary(signals)
        assert "@" not in result

    def test_no_timestamp_shows_unknown(self):
        signals = [LaunchSignal(source="news", content="Breaking news")]
        result = _prepare_signal_summary(signals)
        assert "Unknown time" in result

    def test_truncates_long_content(self):
        signals = [LaunchSignal(source="reddit", content="A" * 500, timestamp=datetime(2026, 2, 1))]
        result = _prepare_signal_summary(signals)
        assert "..." in result

    def test_limits_to_20_signals(self):
        signals = [
            LaunchSignal(source="twitter", content=f"Signal {i}", timestamp=datetime(2026, 2, 1))
            for i in range(30)
        ]
        result = _prepare_signal_summary(signals)
        assert "[Signal 20]" in result
        assert "[Signal 21]" not in result

    def test_includes_url(self):
        signals = [LaunchSignal(
            source="news", content="Article", url="https://example.com/article",
            timestamp=datetime(2026, 2, 1)
        )]
        result = _prepare_signal_summary(signals)
        assert "https://example.com/article" in result


class TestGetSignalSources:

    def test_unique_sources(self, launch_signals):
        sources = _get_signal_sources(launch_signals)
        assert set(sources) == {"twitter", "reddit", "news"}

    def test_empty_signals(self):
        assert _get_signal_sources([]) == []

    def test_duplicate_sources(self):
        signals = [
            LaunchSignal(source="twitter", content="a"),
            LaunchSignal(source="twitter", content="b"),
        ]
        sources = _get_signal_sources(signals)
        assert sources == ["twitter"]


class TestGetDetailedSignals:

    def test_sorts_by_engagement(self, launch_signals):
        result = _get_detailed_signals(launch_signals)
        # Highest engagement (8000) should come first
        lines = result.split("\n")
        first_source_line = [l for l in lines if l.startswith("===")][0]
        assert "[NEWS]" in first_source_line

    def test_limits_results(self, launch_signals):
        result = _get_detailed_signals(launch_signals, limit=1)
        source_lines = [l for l in result.split("\n") if l.startswith("===")]
        assert len(source_lines) == 1

    def test_empty_signals(self):
        assert _get_detailed_signals([]) == "No detailed signals available"
