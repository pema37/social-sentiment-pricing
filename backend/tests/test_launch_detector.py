"""
Tests for services/ai_trend_analysis/launch_detector.py

Covers:
- Enums: LaunchAgent, ThreatLevel, LaunchType
- Dataclasses: LaunchMessage, LaunchSignal, LaunchAlert
- LaunchDetector helper methods:
  - _prepare_signal_summary
  - _get_detailed_signals
  - _get_signal_sources
  - _analyze_scanner_response
  - _parse_validator_json
  - _parse_assessor_json
- LaunchDetector.analyze orchestration (insufficient data, no launch, full pipeline)
"""

import sys
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
for mod in ["db.session", "core.logging", "google.genai"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
sys.modules["core.logging"].get_logger = MagicMock(return_value=MagicMock())

from services.ai_trend_analysis.launch_detector import (
    LaunchAgent,
    ThreatLevel,
    LaunchType,
    LaunchMessage,
    LaunchSignal,
    LaunchAlert,
    LaunchDetector,
)


# ── Helpers ───────────────────────────────────────────────────────

def _make_signal(
    source="twitter",
    content="Check out our new product!",
    url=None,
    timestamp=None,
    engagement=0,
    author=None,
    image_data=None,
):
    return LaunchSignal(
        source=source,
        content=content,
        url=url,
        timestamp=timestamp or datetime(2026, 2, 8, 12, 0, tzinfo=timezone.utc),
        engagement=engagement,
        author=author,
        image_data=image_data,
    )


# ==================================================================
# Enums
# ==================================================================

class TestLaunchAgent:
    def test_scanner(self):
        assert LaunchAgent.SCANNER == "scanner"

    def test_validator(self):
        assert LaunchAgent.VALIDATOR == "validator"

    def test_assessor(self):
        assert LaunchAgent.ASSESSOR == "assessor"

    def test_is_str_enum(self):
        assert isinstance(LaunchAgent.SCANNER, str)


class TestThreatLevel:
    def test_none(self):
        assert ThreatLevel.NONE == "none"

    def test_low(self):
        assert ThreatLevel.LOW == "low"

    def test_medium(self):
        assert ThreatLevel.MEDIUM == "medium"

    def test_high(self):
        assert ThreatLevel.HIGH == "high"

    def test_critical(self):
        assert ThreatLevel.CRITICAL == "critical"

    def test_is_str_enum(self):
        assert isinstance(ThreatLevel.CRITICAL, str)


class TestLaunchType:
    def test_new_product(self):
        assert LaunchType.NEW_PRODUCT == "new_product"

    def test_major_update(self):
        assert LaunchType.MAJOR_UPDATE == "major_update"

    def test_rebrand(self):
        assert LaunchType.REBRAND == "rebrand"

    def test_expansion(self):
        assert LaunchType.EXPANSION == "expansion"

    def test_pricing_change(self):
        assert LaunchType.PRICING_CHANGE == "pricing_change"

    def test_unknown(self):
        assert LaunchType.UNKNOWN == "unknown"

    def test_is_str_enum(self):
        assert isinstance(LaunchType.NEW_PRODUCT, str)


# ==================================================================
# Dataclasses
# ==================================================================

class TestLaunchMessage:
    def test_basic_creation(self):
        msg = LaunchMessage(
            agent=LaunchAgent.SCANNER,
            thought_type=None,
            content="Scanning...",
        )
        assert msg.agent == LaunchAgent.SCANNER
        assert msg.content == "Scanning..."
        assert msg.is_final is False
        assert msg.metadata == {}

    def test_with_all_fields(self):
        msg = LaunchMessage(
            agent=LaunchAgent.ASSESSOR,
            thought_type=MagicMock(),
            content="Done",
            is_final=True,
            metadata={"threat": "high"},
        )
        assert msg.is_final is True
        assert msg.metadata["threat"] == "high"

    def test_default_metadata_separate_instances(self):
        m1 = LaunchMessage(agent=LaunchAgent.SCANNER, thought_type=None, content="A")
        m2 = LaunchMessage(agent=LaunchAgent.SCANNER, thought_type=None, content="B")
        assert m1.metadata is not m2.metadata


class TestLaunchSignal:
    def test_basic_creation(self):
        sig = _make_signal()
        assert sig.source == "twitter"
        assert sig.content == "Check out our new product!"

    def test_defaults(self):
        sig = LaunchSignal(source="reddit", content="text")
        assert sig.url is None
        assert sig.timestamp is None
        assert sig.engagement == 0
        assert sig.author is None
        assert sig.image_data is None
        assert sig.image_type == "png"

    def test_with_all_fields(self):
        sig = LaunchSignal(
            source="news",
            content="Big launch",
            url="https://example.com",
            timestamp=datetime(2026, 2, 8, tzinfo=timezone.utc),
            engagement=500,
            author="journalist",
            image_data=b"fake_image",
            image_type="jpeg",
        )
        assert sig.url == "https://example.com"
        assert sig.engagement == 500
        assert sig.image_data == b"fake_image"
        assert sig.image_type == "jpeg"


class TestLaunchAlert:
    def test_basic_creation(self):
        alert = LaunchAlert(
            is_launch=True,
            launch_type=LaunchType.NEW_PRODUCT,
            threat_level=ThreatLevel.HIGH,
            confidence=0.85,
            product_name="CompetitorX Pro",
            competitor_name="CompetitorX",
            summary="New product launched",
        )
        assert alert.is_launch is True
        assert alert.launch_type == LaunchType.NEW_PRODUCT
        assert alert.threat_level == ThreatLevel.HIGH

    def test_defaults(self):
        alert = LaunchAlert(
            is_launch=False,
            launch_type=LaunchType.UNKNOWN,
            threat_level=ThreatLevel.NONE,
            confidence=0.0,
            product_name="",
            competitor_name="",
            summary="",
        )
        assert alert.key_features == []
        assert alert.target_market == "unknown"
        assert alert.estimated_price is None
        assert alert.launch_date is None
        assert alert.recommended_actions == []
        assert alert.urgency == "monitor"
        assert alert.sources == []

    def test_separate_default_lists(self):
        a1 = LaunchAlert(is_launch=False, launch_type=LaunchType.UNKNOWN, threat_level=ThreatLevel.NONE, confidence=0, product_name="", competitor_name="", summary="")
        a2 = LaunchAlert(is_launch=False, launch_type=LaunchType.UNKNOWN, threat_level=ThreatLevel.NONE, confidence=0, product_name="", competitor_name="", summary="")
        assert a1.key_features is not a2.key_features
        assert a1.recommended_actions is not a2.recommended_actions
        assert a1.sources is not a2.sources


# ==================================================================
# LaunchDetector.__init__
# ==================================================================

class TestLaunchDetectorInit:
    def test_default_thresholds(self):
        d = LaunchDetector()
        assert d.min_confidence == 0.3
        assert d.min_signals == 1

    def test_launch_keywords_populated(self):
        d = LaunchDetector()
        assert len(d.launch_keywords) > 0
        assert "launching" in d.launch_keywords
        assert "introducing" in d.launch_keywords


# ==================================================================
# _prepare_signal_summary
# ==================================================================

class TestPrepareSignalSummary:
    def test_empty_signals(self):
        d = LaunchDetector()
        assert d._prepare_signal_summary([]) == "No signals available"

    def test_single_signal_basic(self):
        d = LaunchDetector()
        sig = _make_signal(source="twitter", content="New product!")
        result = d._prepare_signal_summary([sig])
        assert "TWITTER" in result
        assert "New product!" in result
        assert "Signal 1" in result

    def test_timestamp_formatted(self):
        d = LaunchDetector()
        sig = _make_signal(timestamp=datetime(2026, 2, 8, 14, 30, tzinfo=timezone.utc))
        result = d._prepare_signal_summary([sig])
        assert "2026-02-08 14:30" in result

    def test_no_timestamp_shows_unknown(self):
        d = LaunchDetector()
        sig = LaunchSignal(source="reddit", content="text", timestamp=None)
        result = d._prepare_signal_summary([sig])
        assert "Unknown time" in result

    def test_engagement_shown_when_positive(self):
        d = LaunchDetector()
        sig = _make_signal(engagement=150)
        result = d._prepare_signal_summary([sig])
        assert "Engagement: 150" in result

    def test_engagement_hidden_when_zero(self):
        d = LaunchDetector()
        sig = _make_signal(engagement=0)
        result = d._prepare_signal_summary([sig])
        assert "Engagement" not in result

    def test_author_shown(self):
        d = LaunchDetector()
        sig = _make_signal(author="techreporter")
        result = d._prepare_signal_summary([sig])
        assert "@techreporter" in result

    def test_author_hidden_when_none(self):
        d = LaunchDetector()
        sig = _make_signal(author=None)
        result = d._prepare_signal_summary([sig])
        assert "@" not in result

    def test_url_shown(self):
        d = LaunchDetector()
        sig = _make_signal(url="https://example.com/launch")
        result = d._prepare_signal_summary([sig])
        assert "URL: https://example.com/launch" in result

    def test_content_truncated_at_300(self):
        d = LaunchDetector()
        sig = _make_signal(content="A" * 500)
        result = d._prepare_signal_summary([sig])
        assert "A" * 300 + "..." in result

    def test_content_not_truncated_at_300(self):
        d = LaunchDetector()
        sig = _make_signal(content="A" * 300)
        result = d._prepare_signal_summary([sig])
        assert "..." not in result.split("Content: ")[1].split("\n")[0]

    def test_limits_to_20_signals(self):
        d = LaunchDetector()
        signals = [_make_signal(content=f"Signal {i}") for i in range(30)]
        result = d._prepare_signal_summary(signals)
        assert "Signal 20" in result
        assert "Signal 21" not in result


# ==================================================================
# _get_detailed_signals
# ==================================================================

class TestGetDetailedSignals:
    def test_empty_signals(self):
        d = LaunchDetector()
        result = d._get_detailed_signals([])
        assert result == "No detailed signals available"

    def test_returns_signal_content(self):
        d = LaunchDetector()
        sig = _make_signal(source="news", content="Major product launch announced")
        result = d._get_detailed_signals([sig])
        assert "NEWS" in result
        assert "Major product launch announced" in result

    def test_sorted_by_engagement_descending(self):
        d = LaunchDetector()
        signals = [
            _make_signal(content="Low engagement", engagement=5),
            _make_signal(content="High engagement", engagement=500),
        ]
        result = d._get_detailed_signals(signals)
        # High engagement should appear first
        high_pos = result.index("High engagement")
        low_pos = result.index("Low engagement")
        assert high_pos < low_pos

    def test_limits_to_specified_count(self):
        d = LaunchDetector()
        signals = [_make_signal(content=f"Sig {i}", engagement=i) for i in range(10)]
        result = d._get_detailed_signals(signals, limit=3)
        assert "Sig 9" in result  # Highest engagement
        assert "Sig 0" not in result  # Lowest engagement, beyond limit

    def test_default_limit_is_5(self):
        d = LaunchDetector()
        signals = [_make_signal(content=f"Sig {i}", engagement=i) for i in range(10)]
        result = d._get_detailed_signals(signals)
        # Should have exactly 5 source headers
        assert result.count("===") == 10  # 5 signals * 2 "===" per line


# ==================================================================
# _get_signal_sources
# ==================================================================

class TestGetSignalSources:
    def test_empty_signals(self):
        d = LaunchDetector()
        result = d._get_signal_sources([])
        assert result == []

    def test_unique_sources(self):
        d = LaunchDetector()
        signals = [
            _make_signal(source="twitter"),
            _make_signal(source="twitter"),
            _make_signal(source="reddit"),
        ]
        result = d._get_signal_sources(signals)
        assert set(result) == {"twitter", "reddit"}

    def test_single_source(self):
        d = LaunchDetector()
        signals = [_make_signal(source="news")]
        result = d._get_signal_sources(signals)
        assert result == ["news"]


# ==================================================================
# _analyze_scanner_response
# ==================================================================

class TestAnalyzeScannerResponse:
    def test_no_keywords_no_signals(self):
        d = LaunchDetector()
        detected, confidence = d._analyze_scanner_response(
            "Nothing interesting here", []
        )
        assert detected is False
        assert confidence == 0.0

    def test_one_keyword_in_response(self):
        d = LaunchDetector()
        detected, confidence = d._analyze_scanner_response(
            "They are launching something", []
        )
        assert confidence >= 0.2

    def test_three_plus_keywords_in_response(self):
        d = LaunchDetector()
        detected, confidence = d._analyze_scanner_response(
            "They are launching and introducing a new product that is available now", []
        )
        assert confidence >= 0.4

    def test_signal_content_keyword_matches(self):
        d = LaunchDetector()
        signals = [
            _make_signal(content="We are launching our new product"),
            _make_signal(content="Introducing the next generation"),
        ]
        detected, confidence = d._analyze_scanner_response("Nothing", signals)
        assert confidence >= 0.4

    def test_single_signal_match(self):
        d = LaunchDetector()
        signals = [_make_signal(content="We are launching today")]
        detected, confidence = d._analyze_scanner_response("Nothing", signals)
        assert confidence >= 0.2

    def test_strong_indicator_boost(self):
        d = LaunchDetector()
        detected, confidence = d._analyze_scanner_response(
            "They are announcing and introducing something now available", []
        )
        # "introducing" is a strong indicator
        assert confidence >= 0.3

    def test_confidence_capped_at_1(self):
        d = LaunchDetector()
        signals = [
            _make_signal(content="launching new product introducing"),
            _make_signal(content="announcing available now brand new"),
            _make_signal(content="just dropped pre-order coming soon"),
        ]
        detected, confidence = d._analyze_scanner_response(
            "launching introducing announcing available now brand new just dropped",
            signals,
        )
        assert confidence <= 1.0

    def test_launch_detected_when_above_min_confidence(self):
        d = LaunchDetector()
        detected, confidence = d._analyze_scanner_response(
            "They are launching and introducing a new product", []
        )
        assert detected is True
        assert confidence >= d.min_confidence

    def test_no_launch_when_below_min_confidence(self):
        d = LaunchDetector()
        detected, confidence = d._analyze_scanner_response("No keywords", [])
        assert detected is False
        assert confidence < d.min_confidence


# ==================================================================
# _parse_validator_json
# ==================================================================

class TestParseValidatorJson:
    def test_valid_json_block(self):
        d = LaunchDetector()
        data = {
            "is_confirmed_launch": True,
            "launch_type": "new_product",
            "confidence": 85,
            "product_name": "SuperWidget",
        }
        response = f'Text\n```json\n{json.dumps(data)}\n```\nEnd'
        result = d._parse_validator_json(response)
        assert result["is_confirmed_launch"] is True
        assert result["product_name"] == "SuperWidget"
        assert result["confidence"] == 85

    def test_generic_code_block(self):
        d = LaunchDetector()
        data = {"product_name": "Gadget"}
        response = f'Text\n```\n{json.dumps(data)}\n```'
        result = d._parse_validator_json(response)
        assert result["product_name"] == "Gadget"

    def test_no_json_returns_default(self):
        d = LaunchDetector()
        result = d._parse_validator_json("Plain text no JSON")
        assert result["is_confirmed_launch"] is False
        assert result["product_name"] == "Unknown"
        assert result["launch_type"] == "unknown"
        assert result["confidence"] == 0

    def test_invalid_json_returns_default(self):
        d = LaunchDetector()
        result = d._parse_validator_json('```json\n{broken}\n```')
        assert result["is_confirmed_launch"] is False

    def test_partial_json_merged_with_defaults(self):
        d = LaunchDetector()
        data = {"product_name": "Widget", "confidence": 70}
        response = f'```json\n{json.dumps(data)}\n```'
        result = d._parse_validator_json(response)
        assert result["product_name"] == "Widget"
        assert result["confidence"] == 70
        # Defaults filled in
        assert result["is_confirmed_launch"] is False
        assert result["key_features"] == []
        assert result["launch_date"] == "TBD"

    def test_empty_string_returns_default(self):
        d = LaunchDetector()
        result = d._parse_validator_json("")
        assert result["product_name"] == "Unknown"


# ==================================================================
# _parse_assessor_json
# ==================================================================

class TestParseAssessorJson:
    def test_valid_json_block(self):
        d = LaunchDetector()
        data = {
            "threat_level": "high",
            "threat_score": 80,
            "urgency": "immediate",
            "immediate_actions": ["Brief sales team"],
        }
        response = f'Analysis\n```json\n{json.dumps(data)}\n```'
        result = d._parse_assessor_json(response)
        assert result["threat_level"] == "high"
        assert result["threat_score"] == 80
        assert result["urgency"] == "immediate"

    def test_no_json_returns_default(self):
        d = LaunchDetector()
        result = d._parse_assessor_json("No JSON here")
        assert result["threat_level"] == "medium"
        assert result["threat_score"] == 50
        assert result["urgency"] == "monitor"
        assert result["immediate_actions"] == []

    def test_invalid_json_returns_default(self):
        d = LaunchDetector()
        result = d._parse_assessor_json('```json\n{bad}\n```')
        assert result["threat_level"] == "medium"

    def test_partial_json_merged_with_defaults(self):
        d = LaunchDetector()
        data = {"threat_level": "critical", "urgency": "immediate"}
        response = f'```json\n{json.dumps(data)}\n```'
        result = d._parse_assessor_json(response)
        assert result["threat_level"] == "critical"
        assert result["urgency"] == "immediate"
        # Defaults
        assert result["threat_score"] == 50
        assert result["monitoring_priorities"] == []

    def test_empty_string_returns_default(self):
        d = LaunchDetector()
        result = d._parse_assessor_json("")
        assert result["threat_level"] == "medium"


# ==================================================================
# analyze — orchestration
# ==================================================================

class TestAnalyze:
    @pytest.mark.asyncio
    async def test_insufficient_signals_no_image(self):
        d = LaunchDetector()
        messages = []
        async for msg in d.analyze([], "Competitor", "MyProduct"):
            messages.append(msg)
        assert len(messages) == 1
        assert "Insufficient data" in messages[0].content
        assert messages[0].is_final is True
        assert messages[0].metadata.get("error") == "insufficient_data"

    @pytest.mark.asyncio
    async def test_image_bypasses_signal_check(self):
        """With image_data, even 0 signals should proceed."""
        d = LaunchDetector()

        async def mock_stream(*args, **kwargs):
            chunk = MagicMock()
            chunk.text = "No launch in image"
            chunk.is_final = False
            chunk.thought_type = None
            yield chunk

        async def mock_image_stream(*args, **kwargs):
            chunk = MagicMock()
            chunk.text = "Just a regular product page"
            chunk.is_final = False
            chunk.thought_type = None
            yield chunk

        with patch("services.ai_trend_analysis.launch_detector.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream
            mock_ai.analyze_image_stream = mock_image_stream
            messages = []
            async for msg in d.analyze(
                [], "Competitor", "MyProduct",
                image_data=b"fake_image", image_type="png"
            ):
                messages.append(msg)

        # Should NOT have insufficient data error
        assert not any("Insufficient data" in m.content for m in messages)

    @pytest.mark.asyncio
    async def test_no_launch_detected_stops_after_scanner(self):
        d = LaunchDetector()
        signals = [_make_signal(content="Nothing special happening")]

        async def mock_stream(*args, **kwargs):
            chunk = MagicMock()
            chunk.text = "Everything looks normal, no launches"
            chunk.is_final = False
            chunk.thought_type = None
            yield chunk

        with patch("services.ai_trend_analysis.launch_detector.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream
            messages = []
            async for msg in d.analyze(signals, "Competitor", "MyProduct"):
                messages.append(msg)

        agents_seen = {m.agent for m in messages}
        assert LaunchAgent.SCANNER in agents_seen
        assert LaunchAgent.VALIDATOR not in agents_seen
        assert LaunchAgent.ASSESSOR not in agents_seen

    @pytest.mark.asyncio
    async def test_exactly_min_signals_proceeds(self):
        """Exactly 1 signal should not trigger insufficient data."""
        d = LaunchDetector()
        signals = [_make_signal(content="Regular update")]

        async def mock_stream(*args, **kwargs):
            chunk = MagicMock()
            chunk.text = "Analyzing the signal"
            chunk.is_final = False
            chunk.thought_type = None
            yield chunk

        with patch("services.ai_trend_analysis.launch_detector.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream
            messages = []
            async for msg in d.analyze(signals, "Competitor", "MyProduct"):
                messages.append(msg)

        assert not any("Insufficient data" in m.content for m in messages)

        