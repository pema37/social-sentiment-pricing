"""
Tests for services/ai_trend_analysis/crisis_detector.py

Covers:
- Enums: CrisisAgentRole, CrisisSeverity
- Dataclasses: CrisisAgentMessage, SentimentDataPoint, CrisisAlert
- CrisisDetector helper methods:
  - _prepare_data_summary
  - _calculate_anomaly_metrics
  - _get_negative_samples
  - _get_affected_sources
  - _assess_severity
  - _parse_response_json
- CrisisDetector.analyze orchestration (insufficient data, no anomaly, full pipeline)
"""

import sys
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
for mod in ["db.session", "core.logging", "google.genai"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
sys.modules["core.logging"].get_logger = MagicMock(return_value=MagicMock())

from services.ai_trend_analysis.crisis_detector import (
    CrisisAgentRole,
    CrisisSeverity,
    CrisisAgentMessage,
    SentimentDataPoint,
    CrisisAlert,
    CrisisDetector,
)


# ── Helpers ───────────────────────────────────────────────────────

def _make_data_point(
    score=0.5,
    volume=10,
    source="reddit",
    sample_text=None,
    hours_ago=0,
):
    return SentimentDataPoint(
        timestamp=datetime(2026, 2, 8, 12, 0, tzinfo=timezone.utc) - timedelta(hours=hours_ago),
        score=score,
        volume=volume,
        source=source,
        sample_text=sample_text,
    )


# ==================================================================
# Enums
# ==================================================================

class TestCrisisAgentRole:
    def test_monitor(self):
        assert CrisisAgentRole.MONITOR == "monitor"

    def test_investigator(self):
        assert CrisisAgentRole.INVESTIGATOR == "investigator"

    def test_response(self):
        assert CrisisAgentRole.RESPONSE == "response"

    def test_is_str_enum(self):
        assert isinstance(CrisisAgentRole.MONITOR, str)


class TestCrisisSeverity:
    def test_none(self):
        assert CrisisSeverity.NONE == "none"

    def test_low(self):
        assert CrisisSeverity.LOW == "low"

    def test_medium(self):
        assert CrisisSeverity.MEDIUM == "medium"

    def test_high(self):
        assert CrisisSeverity.HIGH == "high"

    def test_critical(self):
        assert CrisisSeverity.CRITICAL == "critical"

    def test_is_str_enum(self):
        assert isinstance(CrisisSeverity.CRITICAL, str)


# ==================================================================
# Dataclasses
# ==================================================================

class TestCrisisAgentMessage:
    def test_basic_creation(self):
        msg = CrisisAgentMessage(
            agent=CrisisAgentRole.MONITOR,
            thought_type=None,
            content="Test",
        )
        assert msg.agent == CrisisAgentRole.MONITOR
        assert msg.content == "Test"
        assert msg.is_final is False
        assert msg.metadata == {}

    def test_with_all_fields(self):
        msg = CrisisAgentMessage(
            agent=CrisisAgentRole.INVESTIGATOR,
            thought_type=MagicMock(),
            content="Analysis done",
            is_final=True,
            metadata={"key": "value"},
        )
        assert msg.is_final is True
        assert msg.metadata == {"key": "value"}

    def test_default_metadata_is_empty_dict(self):
        msg1 = CrisisAgentMessage(agent=CrisisAgentRole.MONITOR, thought_type=None, content="A")
        msg2 = CrisisAgentMessage(agent=CrisisAgentRole.MONITOR, thought_type=None, content="B")
        # Default factory creates separate dicts
        assert msg1.metadata is not msg2.metadata


class TestSentimentDataPoint:
    def test_basic_creation(self):
        dp = _make_data_point(score=0.8, volume=25, source="twitter")
        assert dp.score == 0.8
        assert dp.volume == 25
        assert dp.source == "twitter"
        assert dp.sample_text is None

    def test_with_sample_text(self):
        dp = _make_data_point(sample_text="Great product!")
        assert dp.sample_text == "Great product!"


class TestCrisisAlert:
    def test_basic_creation(self):
        alert = CrisisAlert(
            is_crisis=True,
            severity=CrisisSeverity.HIGH,
            confidence=0.85,
            title="PR Crisis",
            summary="Major negative sentiment detected",
        )
        assert alert.is_crisis is True
        assert alert.severity == CrisisSeverity.HIGH
        assert alert.confidence == 0.85

    def test_defaults(self):
        alert = CrisisAlert(
            is_crisis=False,
            severity=CrisisSeverity.NONE,
            confidence=0.0,
            title="No crisis",
            summary="All clear",
        )
        assert alert.trigger_event is None
        assert alert.affected_products == []
        assert alert.sentiment_drop_percent == 0.0
        assert alert.volume_spike_percent == 0.0
        assert alert.recommended_actions == []
        assert alert.estimated_impact == "unknown"
        assert alert.sources == []

    def test_separate_default_lists(self):
        a1 = CrisisAlert(is_crisis=False, severity=CrisisSeverity.NONE, confidence=0, title="", summary="")
        a2 = CrisisAlert(is_crisis=False, severity=CrisisSeverity.NONE, confidence=0, title="", summary="")
        assert a1.affected_products is not a2.affected_products
        assert a1.recommended_actions is not a2.recommended_actions


# ==================================================================
# CrisisDetector.__init__
# ==================================================================

class TestCrisisDetectorInit:
    def test_default_thresholds(self):
        detector = CrisisDetector()
        assert detector.sentiment_drop_threshold == -0.3
        assert detector.volume_spike_threshold == 2.0
        assert detector.minimum_mentions == 10


# ==================================================================
# _prepare_data_summary
# ==================================================================

class TestPrepareDataSummary:
    def test_empty_data(self):
        detector = CrisisDetector()
        result = detector._prepare_data_summary([], baseline=0.0)
        assert result == "No data available"

    def test_single_data_point(self):
        detector = CrisisDetector()
        dp = _make_data_point(score=0.5, volume=10, source="reddit")
        result = detector._prepare_data_summary([dp], baseline=0.0)
        assert "0.50" in result
        assert "10 mentions" in result
        assert "reddit" in result

    def test_positive_diff_shows_up_arrow(self):
        detector = CrisisDetector()
        dp = _make_data_point(score=0.5)
        result = detector._prepare_data_summary([dp], baseline=0.0)
        assert "↑" in result

    def test_negative_diff_shows_down_arrow(self):
        detector = CrisisDetector()
        dp = _make_data_point(score=-0.5)
        result = detector._prepare_data_summary([dp], baseline=0.0)
        assert "↓" in result

    def test_zero_diff_shows_right_arrow(self):
        detector = CrisisDetector()
        dp = _make_data_point(score=0.5)
        result = detector._prepare_data_summary([dp], baseline=0.5)
        assert "→" in result

    def test_sample_text_included(self):
        detector = CrisisDetector()
        dp = _make_data_point(sample_text="Terrible product quality")
        result = detector._prepare_data_summary([dp], baseline=0.0)
        assert "Terrible product quality" in result

    def test_sample_text_truncated_at_100(self):
        detector = CrisisDetector()
        dp = _make_data_point(sample_text="A" * 200)
        result = detector._prepare_data_summary([dp], baseline=0.0)
        assert "A" * 100 + "..." in result

    def test_no_sample_text_not_included(self):
        detector = CrisisDetector()
        dp = _make_data_point(sample_text=None)
        result = detector._prepare_data_summary([dp], baseline=0.0)
        assert "Sample:" not in result

    def test_limits_to_50_points(self):
        detector = CrisisDetector()
        data = [_make_data_point(hours_ago=i) for i in range(100)]
        result = detector._prepare_data_summary(data, baseline=0.0)
        # Count score lines (not sample lines)
        score_lines = [l for l in result.split("\n") if "Score:" in l]
        assert len(score_lines) == 50

    def test_sorted_by_timestamp(self):
        detector = CrisisDetector()
        data = [
            _make_data_point(score=0.1, hours_ago=10),
            _make_data_point(score=0.9, hours_ago=1),
        ]
        result = detector._prepare_data_summary(data, baseline=0.0)
        lines = [l for l in result.split("\n") if "Score:" in l]
        # Earlier timestamp should come first after sorting
        assert "0.10" in lines[0]
        assert "0.90" in lines[1]


# ==================================================================
# _calculate_anomaly_metrics
# ==================================================================

class TestCalculateAnomalyMetrics:
    def test_empty_data(self):
        detector = CrisisDetector()
        detected, metrics = detector._calculate_anomaly_metrics([], baseline=0.5)
        assert detected is False
        assert metrics["sentiment_change"] == 0
        assert metrics["volume_change"] == 0
        assert metrics["current_sentiment"] == 0.5

    def test_no_anomaly_stable_data(self):
        detector = CrisisDetector()
        data = [_make_data_point(score=0.5, volume=10, hours_ago=i) for i in range(20)]
        detected, metrics = detector._calculate_anomaly_metrics(data, baseline=0.5)
        assert detected is False

    def test_anomaly_sentiment_drop(self):
        """Large sentiment drop triggers anomaly."""
        detector = CrisisDetector()
        # Old data: positive, Recent data: very negative
        data = [_make_data_point(score=0.8, volume=10, hours_ago=20 - i) for i in range(10)]
        data += [_make_data_point(score=-0.5, volume=10, hours_ago=10 - i) for i in range(10)]
        detected, metrics = detector._calculate_anomaly_metrics(data, baseline=0.5)
        assert detected is True
        assert metrics["sentiment_change"] < detector.sentiment_drop_threshold

    def test_anomaly_volume_spike(self):
        """Large volume spike triggers anomaly."""
        detector = CrisisDetector()
        data = [_make_data_point(score=0.5, volume=10, hours_ago=20 - i) for i in range(10)]
        data += [_make_data_point(score=0.5, volume=100, hours_ago=10 - i) for i in range(10)]
        detected, metrics = detector._calculate_anomaly_metrics(data, baseline=0.5)
        assert detected is True
        assert metrics["volume_change"] > detector.volume_spike_threshold

    def test_current_sentiment_from_recent_data(self):
        detector = CrisisDetector()
        data = [_make_data_point(score=0.2, hours_ago=10)]
        data += [_make_data_point(score=0.8, hours_ago=1)]
        detected, metrics = detector._calculate_anomaly_metrics(data, baseline=0.5)
        assert metrics["current_sentiment"] == 0.8

    def test_peak_negative_time_returned(self):
        detector = CrisisDetector()
        data = [
            _make_data_point(score=0.5, hours_ago=5),
            _make_data_point(score=-0.9, hours_ago=2),
            _make_data_point(score=0.3, hours_ago=1),
        ]
        detected, metrics = detector._calculate_anomaly_metrics(data, baseline=0.5)
        assert "peak_negative_time" in metrics
        assert metrics["peak_negative_score"] == -0.9

    def test_single_data_point(self):
        """Single data point should not crash."""
        detector = CrisisDetector()
        data = [_make_data_point(score=0.5, volume=10)]
        detected, metrics = detector._calculate_anomaly_metrics(data, baseline=0.5)
        assert isinstance(detected, bool)
        assert "current_sentiment" in metrics

    def test_avoids_division_by_zero_sentiment(self):
        """When old_sentiment is 0, uses max(abs(0), 0.1) = 0.1."""
        detector = CrisisDetector()
        data = [_make_data_point(score=0.0, hours_ago=10)]
        data += [_make_data_point(score=0.0, hours_ago=1)]
        detected, metrics = detector._calculate_anomaly_metrics(data, baseline=0.0)
        # Should not raise ZeroDivisionError
        assert isinstance(metrics["sentiment_change"], float)


# ==================================================================
# _get_negative_samples
# ==================================================================

class TestGetNegativeSamples:
    def test_no_negative_data(self):
        detector = CrisisDetector()
        data = [_make_data_point(score=0.5, sample_text="Great!")]
        result = detector._get_negative_samples(data)
        assert result == "No negative samples available"

    def test_negative_without_sample_text(self):
        detector = CrisisDetector()
        data = [_make_data_point(score=-0.5, sample_text=None)]
        result = detector._get_negative_samples(data)
        assert result == "No negative samples available"

    def test_returns_negative_samples(self):
        detector = CrisisDetector()
        data = [_make_data_point(score=-0.8, source="twitter", sample_text="Terrible")]
        result = detector._get_negative_samples(data)
        assert "twitter" in result
        assert "-0.80" in result
        assert "Terrible" in result

    def test_sorted_most_negative_first(self):
        detector = CrisisDetector()
        data = [
            _make_data_point(score=-0.3, sample_text="Bad"),
            _make_data_point(score=-0.9, sample_text="Worst"),
        ]
        result = detector._get_negative_samples(data)
        lines = result.split("\n\n")
        assert "Worst" in lines[0]

    def test_limits_to_specified_count(self):
        detector = CrisisDetector()
        data = [_make_data_point(score=-0.5, sample_text=f"Bad {i}") for i in range(30)]
        result = detector._get_negative_samples(data, limit=5)
        entries = result.split("\n\n")
        assert len(entries) == 5

    def test_default_limit_is_20(self):
        detector = CrisisDetector()
        data = [_make_data_point(score=-0.5, sample_text=f"Bad {i}") for i in range(30)]
        result = detector._get_negative_samples(data)
        entries = result.split("\n\n")
        assert len(entries) == 20

    def test_empty_data(self):
        detector = CrisisDetector()
        result = detector._get_negative_samples([])
        assert result == "No negative samples available"


# ==================================================================
# _get_affected_sources
# ==================================================================

class TestGetAffectedSources:
    def test_no_negative_sources(self):
        detector = CrisisDetector()
        data = [_make_data_point(score=0.5, source="reddit")]
        result = detector._get_affected_sources(data)
        assert result == []

    def test_all_negative_source(self):
        detector = CrisisDetector()
        data = [
            _make_data_point(score=-0.5, source="twitter"),
            _make_data_point(score=-0.3, source="twitter"),
        ]
        result = detector._get_affected_sources(data)
        assert "twitter" in result

    def test_mixed_sources(self):
        detector = CrisisDetector()
        data = [
            _make_data_point(score=-0.8, source="twitter"),
            _make_data_point(score=0.9, source="reddit"),
        ]
        result = detector._get_affected_sources(data)
        assert "twitter" in result
        assert "reddit" not in result

    def test_source_with_mixed_scores_averaged(self):
        detector = CrisisDetector()
        data = [
            _make_data_point(score=-0.1, source="reddit"),
            _make_data_point(score=0.5, source="reddit"),
        ]
        # Average = 0.2, which is positive → not affected
        result = detector._get_affected_sources(data)
        assert "reddit" not in result

    def test_empty_data(self):
        detector = CrisisDetector()
        result = detector._get_affected_sources([])
        assert result == []


# ==================================================================
# _assess_severity
# ==================================================================

class TestAssessSeverity:
    def test_critical_high_sentiment_change(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": -0.7, "volume_change": 0})
        assert result == CrisisSeverity.CRITICAL

    def test_critical_high_volume(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": 0, "volume_change": 6})
        assert result == CrisisSeverity.CRITICAL

    def test_high_sentiment(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": -0.5, "volume_change": 0})
        assert result == CrisisSeverity.HIGH

    def test_high_volume(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": 0, "volume_change": 4})
        assert result == CrisisSeverity.HIGH

    def test_medium_sentiment(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": -0.25, "volume_change": 0})
        assert result == CrisisSeverity.MEDIUM

    def test_medium_volume(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": 0, "volume_change": 2})
        assert result == CrisisSeverity.MEDIUM

    def test_low_sentiment(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": -0.15, "volume_change": 0})
        assert result == CrisisSeverity.LOW

    def test_low_volume(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": 0, "volume_change": 0.6})
        assert result == CrisisSeverity.LOW

    def test_none_severity(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": 0, "volume_change": 0})
        assert result == CrisisSeverity.NONE

    def test_missing_keys_default_to_zero(self):
        detector = CrisisDetector()
        result = detector._assess_severity({})
        assert result == CrisisSeverity.NONE

    def test_positive_sentiment_change_uses_abs(self):
        """_assess_severity uses abs(), so positive changes also count."""
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": 0.7, "volume_change": 0})
        assert result == CrisisSeverity.CRITICAL

    def test_boundary_critical_at_0_6(self):
        detector = CrisisDetector()
        # Exactly 0.6 is not > 0.6, should be HIGH
        result = detector._assess_severity({"sentiment_change": -0.6, "volume_change": 0})
        assert result == CrisisSeverity.HIGH

    def test_boundary_critical_above_0_6(self):
        detector = CrisisDetector()
        result = detector._assess_severity({"sentiment_change": -0.61, "volume_change": 0})
        assert result == CrisisSeverity.CRITICAL


# ==================================================================
# _parse_response_json
# ==================================================================

class TestParseResponseJson:
    def test_valid_json_block(self):
        detector = CrisisDetector()
        response = 'Some text\n```json\n{"crisis_title": "Test Crisis"}\n```\nMore text'
        result = detector._parse_response_json(response)
        assert result["crisis_title"] == "Test Crisis"

    def test_valid_generic_code_block(self):
        detector = CrisisDetector()
        response = 'Text\n```\n{"crisis_title": "Generic Block"}\n```\nEnd'
        result = detector._parse_response_json(response)
        assert result["crisis_title"] == "Generic Block"

    def test_no_json_block_returns_default(self):
        detector = CrisisDetector()
        response = "Just plain text with no JSON"
        result = detector._parse_response_json(response)
        assert result["crisis_title"] == "Crisis Response Plan"
        assert result["immediate_actions"] == []

    def test_invalid_json_returns_default(self):
        detector = CrisisDetector()
        response = '```json\n{invalid json here}\n```'
        result = detector._parse_response_json(response)
        assert result["crisis_title"] == "Crisis Response Plan"

    def test_complex_json(self):
        detector = CrisisDetector()
        data = {
            "crisis_title": "Product Recall",
            "immediate_actions": ["Stop sales", "Issue statement"],
            "stakeholders_to_notify": ["CEO", "PR team"],
        }
        response = f'Analysis:\n```json\n{json.dumps(data)}\n```'
        result = detector._parse_response_json(response)
        assert result["crisis_title"] == "Product Recall"
        assert len(result["immediate_actions"]) == 2

    def test_empty_string(self):
        detector = CrisisDetector()
        result = detector._parse_response_json("")
        assert result["crisis_title"] == "Crisis Response Plan"


# ==================================================================
# analyze — orchestration
# ==================================================================

class TestAnalyze:
    @pytest.mark.asyncio
    async def test_insufficient_data_yields_error(self):
        detector = CrisisDetector()
        data = [_make_data_point() for _ in range(5)]  # Below minimum of 10
        messages = []
        async for msg in detector.analyze(data, "TestProduct"):
            messages.append(msg)
        assert len(messages) == 1
        assert "Insufficient data" in messages[0].content
        assert messages[0].is_final is True
        assert messages[0].metadata.get("error") == "insufficient_data"

    @pytest.mark.asyncio
    async def test_no_anomaly_stops_after_monitor(self):
        """When monitor detects no anomaly, pipeline stops early."""
        detector = CrisisDetector()
        # All stable data → no anomaly
        data = [_make_data_point(score=0.5, volume=10, hours_ago=i) for i in range(20)]

        # Mock the streaming to avoid hitting real AI
        async def mock_stream(*args, **kwargs):
            chunk = MagicMock()
            chunk.text = "All looks normal"
            chunk.is_final = False
            chunk.thought_type = None
            yield chunk
            final = MagicMock()
            final.text = ""
            final.is_final = True
            final.thought_type = None
            yield final

        with patch("services.ai_trend_analysis.crisis_detector.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream
            messages = []
            async for msg in detector.analyze(data, "TestProduct", baseline_sentiment=0.5):
                messages.append(msg)

        # Should have monitor messages but NOT investigator or response
        agents_seen = {m.agent for m in messages}
        assert CrisisAgentRole.MONITOR in agents_seen
        assert CrisisAgentRole.INVESTIGATOR not in agents_seen
        assert CrisisAgentRole.RESPONSE not in agents_seen

    @pytest.mark.asyncio
    async def test_exactly_minimum_mentions_proceeds(self):
        """Exactly 10 data points should not trigger insufficient data."""
        detector = CrisisDetector()
        data = [_make_data_point(score=0.5, volume=10, hours_ago=i) for i in range(10)]

        async def mock_stream(*args, **kwargs):
            chunk = MagicMock()
            chunk.text = "Analyzing"
            chunk.is_final = False
            chunk.thought_type = None
            yield chunk

        with patch("services.ai_trend_analysis.crisis_detector.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream
            messages = []
            async for msg in detector.analyze(data, "TestProduct"):
                messages.append(msg)

        # Should NOT have insufficient data error
        assert not any("Insufficient data" in m.content for m in messages)


        