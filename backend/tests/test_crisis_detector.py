"""
Tests for Crisis Detector — Anomaly Detection, Severity Assessment & JSON Parsing

Tests all pure helper methods in the crisis detection pipeline.
No Gemini API dependency.
"""

import pytest
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


# ── Local replicas of data classes for isolated testing ──

class CrisisSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SentimentDataPoint:
    timestamp: datetime
    score: float
    volume: int
    source: str
    sample_text: Optional[str] = None


# ── Helper methods extracted from CrisisDetector for isolated testing ──

SENTIMENT_DROP_THRESHOLD = -0.2
VOLUME_SPIKE_THRESHOLD = 2.0


def _calculate_anomaly_metrics(data, baseline):
    if not data:
        return False, {
            'sentiment_change': 0,
            'volume_change': 0,
            'current_sentiment': baseline
        }

    sorted_data = sorted(data, key=lambda x: x.timestamp)
    midpoint = len(sorted_data) // 2
    old_data = sorted_data[:midpoint] if midpoint > 0 else sorted_data
    recent_data = sorted_data[midpoint:] if midpoint > 0 else sorted_data

    old_sentiment = sum(d.score for d in old_data) / len(old_data) if old_data else baseline
    recent_sentiment = sum(d.score for d in recent_data) / len(recent_data) if recent_data else baseline

    old_volume = sum(d.volume for d in old_data) / len(old_data) if old_data else 1
    recent_volume = sum(d.volume for d in recent_data) / len(recent_data) if recent_data else 1

    sentiment_change = (recent_sentiment - old_sentiment) / max(abs(old_sentiment), 0.1)
    volume_change = (recent_volume - old_volume) / max(old_volume, 1)

    most_negative = min(data, key=lambda x: x.score)

    anomaly_detected = (
        sentiment_change < SENTIMENT_DROP_THRESHOLD or
        volume_change > VOLUME_SPIKE_THRESHOLD
    )

    return anomaly_detected, {
        'sentiment_change': sentiment_change,
        'volume_change': volume_change,
        'current_sentiment': recent_sentiment,
        'peak_negative_time': most_negative.timestamp.isoformat(),
        'peak_negative_score': most_negative.score
    }


def _assess_severity(monitoring_result):
    sentiment_change = abs(monitoring_result.get('sentiment_change', 0))
    volume_change = monitoring_result.get('volume_change', 0)

    if sentiment_change > 0.6 or volume_change > 5:
        return CrisisSeverity.CRITICAL
    elif sentiment_change > 0.4 or volume_change > 3:
        return CrisisSeverity.HIGH
    elif sentiment_change > 0.2 or volume_change > 1.5:
        return CrisisSeverity.MEDIUM
    elif sentiment_change > 0.1 or volume_change > 0.5:
        return CrisisSeverity.LOW
    else:
        return CrisisSeverity.NONE


def _get_affected_sources(data):
    source_scores = {}
    for d in data:
        if d.source not in source_scores:
            source_scores[d.source] = []
        source_scores[d.source].append(d.score)
    return [
        source for source, scores in source_scores.items()
        if sum(scores) / len(scores) < 0
    ]


def _parse_response_json(response):
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        else:
            return {"crisis_title": "Crisis Response Plan", "immediate_actions": []}
        return json.loads(json_str.strip())
    except Exception:
        return {"crisis_title": "Crisis Response Plan", "immediate_actions": []}


def _prepare_data_summary(data, baseline):
    if not data:
        return "No data available"
    lines = []
    for dp in sorted(data, key=lambda x: x.timestamp)[-50:]:
        time_str = dp.timestamp.strftime("%Y-%m-%d %H:%M")
        diff = dp.score - baseline
        direction = "↑" if diff > 0 else "↓" if diff < 0 else "→"
        lines.append(
            f"[{time_str}] Score: {dp.score:.2f} ({direction}{abs(diff):.2f}) | "
            f"Volume: {dp.volume} mentions | Source: {dp.source}"
        )
        if dp.sample_text:
            lines.append(f'  Sample: "{dp.sample_text[:100]}..."')
    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════

@pytest.fixture
def stable_sentiment():
    """Stable sentiment data — no anomaly."""
    base = datetime(2026, 2, 1, 12, 0)
    return [
        SentimentDataPoint(base + timedelta(hours=i), score=0.5, volume=10, source="twitter")
        for i in range(10)
    ]


@pytest.fixture
def crisis_sentiment():
    """Sentiment data showing a clear crisis — sharp drop + volume spike."""
    base = datetime(2026, 2, 1, 12, 0)
    # First 5: positive, low volume
    old = [
        SentimentDataPoint(base + timedelta(hours=i), score=0.6, volume=10, source="twitter")
        for i in range(5)
    ]
    # Last 5: very negative, high volume
    recent = [
        SentimentDataPoint(base + timedelta(hours=i + 5), score=-0.7, volume=200, source="reddit")
        for i in range(5)
    ]
    return old + recent


@pytest.fixture
def mixed_sources():
    """Data across multiple sources with mixed sentiment."""
    base = datetime(2026, 2, 1, 12, 0)
    return [
        SentimentDataPoint(base, score=-0.5, volume=10, source="twitter"),
        SentimentDataPoint(base + timedelta(hours=1), score=-0.3, volume=5, source="twitter"),
        SentimentDataPoint(base + timedelta(hours=2), score=0.8, volume=20, source="reddit"),
        SentimentDataPoint(base + timedelta(hours=3), score=0.6, volume=15, source="reddit"),
        SentimentDataPoint(base + timedelta(hours=4), score=-0.1, volume=3, source="news"),
    ]


# ═════════════════════════════════════════════════════════════════════════
# ANOMALY DETECTION TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestCalculateAnomalyMetrics:

    def test_empty_data_no_anomaly(self):
        detected, metrics = _calculate_anomaly_metrics([], 0.5)
        assert detected is False
        assert metrics['sentiment_change'] == 0
        assert metrics['current_sentiment'] == 0.5

    def test_stable_data_no_anomaly(self, stable_sentiment):
        detected, metrics = _calculate_anomaly_metrics(stable_sentiment, 0.5)
        assert detected is False
        assert abs(metrics['sentiment_change']) < 0.1

    def test_crisis_data_detects_anomaly(self, crisis_sentiment):
        detected, metrics = _calculate_anomaly_metrics(crisis_sentiment, 0.5)
        assert detected is True
        assert metrics['sentiment_change'] < 0  # Negative = sentiment dropped
        assert metrics['volume_change'] > 0  # Positive = volume spiked

    def test_crisis_data_tracks_peak_negative(self, crisis_sentiment):
        _, metrics = _calculate_anomaly_metrics(crisis_sentiment, 0.5)
        assert metrics['peak_negative_score'] == -0.7

    def test_single_data_point(self):
        data = [SentimentDataPoint(datetime(2026, 2, 1), score=-0.5, volume=100, source="twitter")]
        detected, metrics = _calculate_anomaly_metrics(data, 0.5)
        assert metrics['current_sentiment'] == -0.5

    def test_volume_spike_triggers_anomaly(self):
        """Volume spike alone should trigger anomaly."""
        base = datetime(2026, 2, 1)
        data = [
            SentimentDataPoint(base, score=0.5, volume=5, source="twitter"),
            SentimentDataPoint(base + timedelta(hours=1), score=0.5, volume=5, source="twitter"),
            SentimentDataPoint(base + timedelta(hours=2), score=0.5, volume=500, source="twitter"),
            SentimentDataPoint(base + timedelta(hours=3), score=0.5, volume=500, source="twitter"),
        ]
        detected, metrics = _calculate_anomaly_metrics(data, 0.5)
        assert detected is True
        assert metrics['volume_change'] > VOLUME_SPIKE_THRESHOLD


# ═════════════════════════════════════════════════════════════════════════
# SEVERITY ASSESSMENT TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestAssessSeverity:

    def test_critical_high_sentiment_drop(self):
        assert _assess_severity({'sentiment_change': -0.7, 'volume_change': 0}) == CrisisSeverity.CRITICAL

    def test_critical_high_volume_spike(self):
        assert _assess_severity({'sentiment_change': 0, 'volume_change': 6}) == CrisisSeverity.CRITICAL

    def test_high_severity(self):
        assert _assess_severity({'sentiment_change': -0.5, 'volume_change': 0}) == CrisisSeverity.HIGH

    def test_high_severity_volume(self):
        assert _assess_severity({'sentiment_change': 0, 'volume_change': 4}) == CrisisSeverity.HIGH

    def test_medium_severity(self):
        assert _assess_severity({'sentiment_change': -0.3, 'volume_change': 0}) == CrisisSeverity.MEDIUM

    def test_medium_severity_volume(self):
        assert _assess_severity({'sentiment_change': 0, 'volume_change': 2}) == CrisisSeverity.MEDIUM

    def test_low_severity(self):
        assert _assess_severity({'sentiment_change': -0.15, 'volume_change': 0}) == CrisisSeverity.LOW

    def test_low_severity_volume(self):
        assert _assess_severity({'sentiment_change': 0, 'volume_change': 0.8}) == CrisisSeverity.LOW

    def test_none_severity(self):
        assert _assess_severity({'sentiment_change': 0, 'volume_change': 0}) == CrisisSeverity.NONE

    def test_missing_keys_defaults_to_none(self):
        assert _assess_severity({}) == CrisisSeverity.NONE

    def test_absolute_value_used(self):
        """Negative sentiment_change should use absolute value."""
        assert _assess_severity({'sentiment_change': -0.7, 'volume_change': 0}) == CrisisSeverity.CRITICAL


# ═════════════════════════════════════════════════════════════════════════
# AFFECTED SOURCES TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestGetAffectedSources:

    def test_identifies_negative_sources(self, mixed_sources):
        affected = _get_affected_sources(mixed_sources)
        assert "twitter" in affected
        assert "reddit" not in affected  # Reddit has positive avg

    def test_news_borderline_negative(self, mixed_sources):
        affected = _get_affected_sources(mixed_sources)
        assert "news" in affected  # -0.1 avg is negative

    def test_empty_data(self):
        assert _get_affected_sources([]) == []

    def test_all_positive(self):
        data = [
            SentimentDataPoint(datetime.now(), score=0.5, volume=10, source="twitter"),
            SentimentDataPoint(datetime.now(), score=0.3, volume=10, source="reddit"),
        ]
        assert _get_affected_sources(data) == []

    def test_all_negative(self):
        data = [
            SentimentDataPoint(datetime.now(), score=-0.5, volume=10, source="twitter"),
            SentimentDataPoint(datetime.now(), score=-0.3, volume=10, source="reddit"),
        ]
        affected = _get_affected_sources(data)
        assert "twitter" in affected
        assert "reddit" in affected


# ═════════════════════════════════════════════════════════════════════════
# JSON PARSING TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestParseResponseJson:

    def test_valid_json_block(self):
        response = '''Here is my analysis.

```json
{
  "crisis_title": "Brand Reputation Crisis",
  "severity": "high",
  "immediate_actions": ["Issue public statement", "Pause ad campaigns"]
}
```

That concludes my assessment.'''
        result = _parse_response_json(response)
        assert result["crisis_title"] == "Brand Reputation Crisis"
        assert len(result["immediate_actions"]) == 2

    def test_json_without_language_tag(self):
        response = '''Analysis complete.

```
{
  "crisis_title": "Product Recall",
  "immediate_actions": ["Contact customers"]
}
```'''
        result = _parse_response_json(response)
        assert result["crisis_title"] == "Product Recall"

    def test_no_json_returns_default(self):
        response = "I analyzed the data and found no crisis."
        result = _parse_response_json(response)
        assert result["crisis_title"] == "Crisis Response Plan"
        assert result["immediate_actions"] == []

    def test_malformed_json_returns_default(self):
        response = '''```json
{broken json here}
```'''
        result = _parse_response_json(response)
        assert result["crisis_title"] == "Crisis Response Plan"

    def test_empty_response(self):
        result = _parse_response_json("")
        assert result["crisis_title"] == "Crisis Response Plan"

    def test_nested_json(self):
        response = '''```json
{
  "crisis_title": "Social Media Storm",
  "immediate_actions": ["Respond on Twitter"],
  "long_term": {"strategy": "rebrand", "timeline": "6 months"}
}
```'''
        result = _parse_response_json(response)
        assert result["crisis_title"] == "Social Media Storm"
        assert result["long_term"]["strategy"] == "rebrand"


# ═════════════════════════════════════════════════════════════════════════
# DATA PREPARATION TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestPrepareDataSummary:

    def test_empty_data(self):
        assert _prepare_data_summary([], 0.5) == "No data available"

    def test_formats_data_correctly(self):
        data = [
            SentimentDataPoint(
                datetime(2026, 2, 1, 14, 30), score=0.7, volume=25,
                source="twitter", sample_text="Great product!"
            )
        ]
        result = _prepare_data_summary(data, 0.5)
        assert "2026-02-01 14:30" in result
        assert "Score: 0.70" in result
        assert "↑" in result  # 0.7 > 0.5 baseline
        assert "Volume: 25" in result
        assert "twitter" in result
        assert "Great product!" in result

    def test_downward_arrow_for_negative(self):
        data = [
            SentimentDataPoint(datetime(2026, 2, 1), score=-0.3, volume=10, source="reddit")
        ]
        result = _prepare_data_summary(data, 0.5)
        assert "↓" in result

    def test_neutral_arrow_for_baseline(self):
        data = [
            SentimentDataPoint(datetime(2026, 2, 1), score=0.5, volume=10, source="news")
        ]
        result = _prepare_data_summary(data, 0.5)
        assert "→" in result

    def test_limits_to_50_points(self):
        """Should only include last 50 data points."""
        base = datetime(2026, 2, 1)
        data = [
            SentimentDataPoint(base + timedelta(minutes=i), score=0.1, volume=1, source="twitter")
            for i in range(100)
        ]
        result = _prepare_data_summary(data, 0.0)
        # Count score lines (each data point produces at least one line with "Score:")
        score_lines = [l for l in result.split("\n") if "Score:" in l]
        assert len(score_lines) == 50

    def test_truncates_long_sample_text(self):
        long_text = "A" * 200
        data = [
            SentimentDataPoint(datetime(2026, 2, 1), score=0.1, volume=1, source="twitter", sample_text=long_text)
        ]
        result = _prepare_data_summary(data, 0.0)
        # Sample should be truncated to 100 chars + "..."
        assert 'A"...' in result or "A..." in result
