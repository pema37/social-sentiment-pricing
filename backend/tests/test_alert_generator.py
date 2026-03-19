"""
Tests for services/notification/alert_generator.py

AlertGenerator — generates alerts from system events, persists to DB,
dispatches via Celery or sync fallback. Tests cover severity thresholds,
message formatting, config matching, cooldown/limits, dispatch paths.
"""

import sys
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED = [
    "sqlmodel",
    "models.alert",
    "services.notification.notification_dispatcher",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# sqlmodel
_sqlmodel = MagicMock()
sys.modules["sqlmodel"] = _sqlmodel
_sqlmodel.Session = MagicMock
_sqlmodel.select = MagicMock()
_sqlmodel.func = MagicMock()


# models.alert — real-ish enums
class AlertType(StrEnum):
    SENTIMENT_DROP = "sentiment_drop"
    SENTIMENT_SPIKE = "sentiment_spike"
    PRICE_RECOMMENDATION = "price_recommendation"
    PRICE_APPLIED = "price_applied"
    COMPETITOR_PRICE_CHANGE = "competitor_price_change"
    VOLUME_SURGE = "volume_surge"


class AlertSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class AlertChannel(StrEnum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"


_alert_mod = MagicMock()
_alert_mod.Alert = MagicMock()
_alert_mod.AlertConfiguration = MagicMock()
_alert_mod.AlertType = AlertType
_alert_mod.AlertSeverity = AlertSeverity
_alert_mod.AlertStatus = AlertStatus
_alert_mod.AlertChannel = AlertChannel
sys.modules["models.alert"] = _alert_mod

# notification_dispatcher
_disp_mod = MagicMock()


class _FakeDispatchResult:
    def __init__(self, success=True, channels_sent=None, channels_failed=None):
        self.success = success
        self.channels_sent = channels_sent or []
        self.channels_failed = channels_failed or []


_disp_mod.DispatchResult = _FakeDispatchResult
_disp_mod.NotificationDispatcher = MagicMock
sys.modules["services.notification.notification_dispatcher"] = _disp_mod

from services.notification.alert_generator import AlertGenerator

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

SVC_MOD = "services.notification.alert_generator"


class _ColumnMock:
    def __lt__(self, other):
        return MagicMock()

    def __le__(self, other):
        return MagicMock()

    def __gt__(self, other):
        return MagicMock()

    def __ge__(self, other):
        return MagicMock()

    def __eq__(self, other):
        return MagicMock()

    def __ne__(self, other):
        return MagicMock()

    def __hash__(self):
        return id(self)


class _FakeAlert:
    id = _ColumnMock()
    configuration_id = _ColumnMock()
    created_at = _ColumnMock()
    user_id = _ColumnMock()
    alert_type = _ColumnMock()
    severity = _ColumnMock()
    status = _ColumnMock()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


# ── Helpers ───────────────────────────────────────────────────────


def _make_generator(use_celery=False):
    """Create AlertGenerator with mocked session and dispatcher."""
    session = MagicMock()
    gen = AlertGenerator(session=session, use_celery=use_celery)
    gen.dispatcher = MagicMock()
    gen.dispatcher.dispatch = AsyncMock(
        return_value=_FakeDispatchResult(
            success=True,
            channels_sent=["email"],
            channels_failed=[],
        )
    )
    return gen


def _stub_create_and_dispatch(gen, return_alert=None):
    """Stub _create_and_dispatch to return a fake alert."""
    fake_alert = return_alert or MagicMock(id=uuid4())
    gen._create_and_dispatch = AsyncMock(return_value=fake_alert)
    return fake_alert


# ──────────────────────────────────────────────
# __init__
# ──────────────────────────────────────────────
class TestInit:
    def test_stores_session(self):
        session = MagicMock()
        gen = AlertGenerator(session=session)
        assert gen.session is session

    def test_creates_dispatcher(self):
        gen = AlertGenerator(session=MagicMock())
        assert gen.dispatcher is not None

    def test_use_celery_default_true(self):
        gen = AlertGenerator(session=MagicMock())
        assert gen.use_celery is True

    def test_use_celery_false(self):
        gen = AlertGenerator(session=MagicMock(), use_celery=False)
        assert gen.use_celery is False


# ──────────────────────────────────────────────
# generate_sentiment_alert — severity thresholds
# ──────────────────────────────────────────────
class TestSentimentSeverity:
    @pytest.mark.asyncio
    async def test_critical_at_0_5_drop(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_sentiment_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="Widget",
            sentiment_score=-0.3,
            previous_score=0.2,
            mention_count=100,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_high_at_0_3_change(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_sentiment_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            sentiment_score=0.0,
            previous_score=0.35,
            mention_count=50,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_medium_at_0_15_change(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_sentiment_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            sentiment_score=0.0,
            previous_score=0.2,
            mention_count=50,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_low_under_0_15(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_sentiment_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            sentiment_score=0.1,
            previous_score=0.2,
            mention_count=50,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.LOW


class TestSentimentAlertContent:
    @pytest.mark.asyncio
    async def test_drop_type(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_sentiment_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="Widget",
            sentiment_score=-0.1,
            previous_score=0.5,
            mention_count=100,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["alert_type"] == AlertType.SENTIMENT_DROP

    @pytest.mark.asyncio
    async def test_spike_type(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_sentiment_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="Widget",
            sentiment_score=0.8,
            previous_score=0.1,
            mention_count=100,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["alert_type"] == AlertType.SENTIMENT_SPIKE

    @pytest.mark.asyncio
    async def test_title_contains_product_name(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_sentiment_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="SuperWidget",
            sentiment_score=-0.5,
            previous_score=0.1,
            mention_count=10,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "SuperWidget" in call_kw["title"]

    @pytest.mark.asyncio
    async def test_message_contains_scores(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_sentiment_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            sentiment_score=-0.45,
            previous_score=0.12,
            mention_count=847,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "-0.45" in call_kw["message"]
        assert "0.12" in call_kw["message"]
        assert "847" in call_kw["message"]

    @pytest.mark.asyncio
    async def test_alert_data_fields(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_sentiment_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            sentiment_score=0.5,
            previous_score=0.3,
            mention_count=10,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        data = call_kw["alert_data"]
        assert "current_score" in data
        assert "previous_score" in data
        assert "change" in data
        assert "mention_count" in data


# ──────────────────────────────────────────────
# generate_price_recommendation_alert
# ──────────────────────────────────────────────
class TestPriceRecommendationAlert:
    @pytest.mark.asyncio
    async def test_high_confidence_large_change(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_recommendation_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_price=100,
            recommended_price=115,
            confidence=0.85,
            recommendation_id=uuid4(),
            reasoning="test",
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_medium_confidence(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_recommendation_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_price=100,
            recommended_price=105,
            confidence=0.65,
            recommendation_id=uuid4(),
            reasoning="test",
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_low_confidence(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_recommendation_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_price=100,
            recommended_price=105,
            confidence=0.4,
            recommendation_id=uuid4(),
            reasoning="test",
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.LOW

    @pytest.mark.asyncio
    async def test_increase_direction(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_recommendation_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_price=100,
            recommended_price=120,
            confidence=0.9,
            recommendation_id=uuid4(),
            reasoning="r",
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "Increase" in call_kw["title"]

    @pytest.mark.asyncio
    async def test_decrease_direction(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_recommendation_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_price=100,
            recommended_price=85,
            confidence=0.9,
            recommendation_id=uuid4(),
            reasoning="r",
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "Decrease" in call_kw["title"]

    @pytest.mark.asyncio
    async def test_alert_type(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_recommendation_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_price=100,
            recommended_price=110,
            confidence=0.7,
            recommendation_id=uuid4(),
            reasoning="r",
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["alert_type"] == AlertType.PRICE_RECOMMENDATION


# ──────────────────────────────────────────────
# generate_price_applied_alert
# ──────────────────────────────────────────────
class TestPriceAppliedAlert:
    @pytest.mark.asyncio
    async def test_auto_applied_medium_severity(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_applied_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=110,
            auto_applied=True,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_manual_applied_low_severity(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_applied_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=110,
            auto_applied=False,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.LOW

    @pytest.mark.asyncio
    async def test_increase_title(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_applied_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=120,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "Increased" in call_kw["title"]

    @pytest.mark.asyncio
    async def test_decrease_title(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_applied_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=80,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "Decreased" in call_kw["title"]

    @pytest.mark.asyncio
    async def test_alert_type(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_applied_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=110,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["alert_type"] == AlertType.PRICE_APPLIED

    @pytest.mark.asyncio
    async def test_message_contains_auto(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_applied_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=110,
            auto_applied=True,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "automatically" in call_kw["message"]

    @pytest.mark.asyncio
    async def test_message_contains_manual(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_price_applied_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=110,
            auto_applied=False,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "manually" in call_kw["message"]


# ──────────────────────────────────────────────
# generate_competitor_alert
# ──────────────────────────────────────────────
class TestCompetitorAlert:
    @pytest.mark.asyncio
    async def test_large_change_high(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_competitor_alert(
            user_id=uuid4(),
            competitor_id=uuid4(),
            competitor_name="Rival",
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=125,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_medium_change(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_competitor_alert(
            user_id=uuid4(),
            competitor_id=uuid4(),
            competitor_name="Rival",
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=112,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_small_change_low(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_competitor_alert(
            user_id=uuid4(),
            competitor_id=uuid4(),
            competitor_name="Rival",
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=105,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.LOW

    @pytest.mark.asyncio
    async def test_title_contains_competitor(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_competitor_alert(
            user_id=uuid4(),
            competitor_id=uuid4(),
            competitor_name="BigCorp",
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=80,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "BigCorp" in call_kw["title"]

    @pytest.mark.asyncio
    async def test_alert_type(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_competitor_alert(
            user_id=uuid4(),
            competitor_id=uuid4(),
            competitor_name="R",
            product_id=uuid4(),
            product_name="W",
            old_price=100,
            new_price=80,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["alert_type"] == AlertType.COMPETITOR_PRICE_CHANGE


# ──────────────────────────────────────────────
# generate_volume_surge_alert
# ──────────────────────────────────────────────
class TestVolumeSurgeAlert:
    @pytest.mark.asyncio
    async def test_high_surge(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_volume_surge_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_volume=500,
            average_volume=100,
            surge_multiplier=5.0,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_medium_surge(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_volume_surge_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_volume=300,
            average_volume=100,
            surge_multiplier=3.0,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_low_surge(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_volume_surge_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_volume=200,
            average_volume=100,
            surge_multiplier=2.0,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.LOW

    @pytest.mark.asyncio
    async def test_alert_type(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_volume_surge_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_volume=500,
            average_volume=100,
            surge_multiplier=5.0,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["alert_type"] == AlertType.VOLUME_SURGE

    @pytest.mark.asyncio
    async def test_message_contains_volumes(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_volume_surge_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            current_volume=500,
            average_volume=100,
            surge_multiplier=5.0,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "500" in call_kw["message"]
        assert "100" in call_kw["message"]


# ──────────────────────────────────────────────
# generate_trend_alert
# ──────────────────────────────────────────────
class TestTrendAlert:
    @pytest.mark.asyncio
    async def test_high_impact(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_trend_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            trend_type="viral_content",
            description="desc",
            impact_score=0.8,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_medium_impact(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_trend_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            trend_type="seasonal",
            description="desc",
            impact_score=0.5,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_low_impact(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_trend_alert(
            user_id=uuid4(),
            product_id=uuid4(),
            product_name="W",
            trend_type="minor",
            description="desc",
            impact_score=0.2,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert call_kw["severity"] == AlertSeverity.LOW

    @pytest.mark.asyncio
    async def test_title_formats_trend_type(self):
        gen = _make_generator()
        _stub_create_and_dispatch(gen)

        await gen.generate_trend_alert(
            user_id=uuid4(),
            product_id=None,
            product_name="W",
            trend_type="viral_content",
            description="d",
            impact_score=0.5,
        )

        call_kw = gen._create_and_dispatch.call_args[1]
        assert "Viral Content" in call_kw["title"]


# ──────────────────────────────────────────────
# _create_and_dispatch
# ──────────────────────────────────────────────
class TestCreateAndDispatch:
    @pytest.mark.asyncio
    async def test_creates_alert_in_db(self):
        gen = _make_generator()
        gen._find_matching_config = AsyncMock(return_value=None)

        with patch(f"{SVC_MOD}.Alert") as MockAlert:
            mock_alert = MagicMock(id=uuid4())
            MockAlert.return_value = mock_alert

            await gen._create_and_dispatch(
                user_id=uuid4(),
                alert_type=AlertType.VOLUME_SURGE,
                severity=AlertSeverity.HIGH,
                title="T",
                message="M",
                alert_data={},
            )

        gen.session.add.assert_called()
        gen.session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_returns_alert(self):
        gen = _make_generator()
        gen._find_matching_config = AsyncMock(return_value=None)

        with patch(f"{SVC_MOD}.Alert") as MockAlert:
            mock_alert = MagicMock(id=uuid4())
            MockAlert.return_value = mock_alert

            result = await gen._create_and_dispatch(
                user_id=uuid4(),
                alert_type=AlertType.VOLUME_SURGE,
                severity=AlertSeverity.HIGH,
                title="T",
                message="M",
                alert_data={},
            )

        assert result is mock_alert

    @pytest.mark.asyncio
    async def test_suppressed_by_limits_returns_none(self):
        gen = _make_generator()

        config = MagicMock()
        config.id = uuid4()
        config.channels = [AlertChannel.EMAIL]
        gen._find_matching_config = AsyncMock(return_value=config)
        gen._check_limits = AsyncMock(return_value=False)

        result = await gen._create_and_dispatch(
            user_id=uuid4(),
            alert_type=AlertType.VOLUME_SURGE,
            severity=AlertSeverity.HIGH,
            title="T",
            message="M",
            alert_data={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_dispatches_when_config_has_channels(self):
        gen = _make_generator()

        config = MagicMock()
        config.id = uuid4()
        config.channels = [AlertChannel.EMAIL]
        gen._find_matching_config = AsyncMock(return_value=config)
        gen._check_limits = AsyncMock(return_value=True)
        gen._dispatch_alert = AsyncMock()

        with patch(f"{SVC_MOD}.Alert") as MockAlert:
            mock_alert = MagicMock(id=uuid4())
            MockAlert.return_value = mock_alert

            await gen._create_and_dispatch(
                user_id=uuid4(),
                alert_type=AlertType.VOLUME_SURGE,
                severity=AlertSeverity.HIGH,
                title="T",
                message="M",
                alert_data={},
            )

        gen._dispatch_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_dispatch_without_channels(self):
        gen = _make_generator()

        config = MagicMock()
        config.id = uuid4()
        config.channels = []
        gen._find_matching_config = AsyncMock(return_value=config)
        gen._check_limits = AsyncMock(return_value=True)
        gen._dispatch_alert = AsyncMock()

        with patch(f"{SVC_MOD}.Alert") as MockAlert:
            MockAlert.return_value = MagicMock(id=uuid4())

            await gen._create_and_dispatch(
                user_id=uuid4(),
                alert_type=AlertType.VOLUME_SURGE,
                severity=AlertSeverity.HIGH,
                title="T",
                message="M",
                alert_data={},
            )

        gen._dispatch_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_config_no_dispatch(self):
        gen = _make_generator()
        gen._find_matching_config = AsyncMock(return_value=None)
        gen._dispatch_alert = AsyncMock()

        with patch(f"{SVC_MOD}.Alert") as MockAlert:
            MockAlert.return_value = MagicMock(id=uuid4())

            await gen._create_and_dispatch(
                user_id=uuid4(),
                alert_type=AlertType.VOLUME_SURGE,
                severity=AlertSeverity.HIGH,
                title="T",
                message="M",
                alert_data={},
            )

        gen._dispatch_alert.assert_not_called()


# ──────────────────────────────────────────────
# _check_limits
# ──────────────────────────────────────────────
@patch(f"{SVC_MOD}.Alert", _FakeAlert)
@patch(f"{SVC_MOD}.select", MagicMock())
@patch(f"{SVC_MOD}.func", MagicMock())
class TestCheckLimits:
    @pytest.mark.asyncio
    async def test_no_cooldown_passes(self):
        gen = _make_generator()
        config = MagicMock()
        config.last_triggered_at = None
        config.cooldown_minutes = 30
        config.max_per_day = 100
        config.id = uuid4()

        gen.session.exec.return_value.one.return_value = 0

        result = await gen._check_limits(config)
        assert result is True

    @pytest.mark.asyncio
    async def test_in_cooldown_fails(self):
        gen = _make_generator()
        config = MagicMock()
        config.last_triggered_at = datetime.now(UTC) - timedelta(minutes=5)
        config.cooldown_minutes = 30
        config.max_per_day = 100
        config.id = uuid4()

        result = await gen._check_limits(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_past_cooldown_passes(self):
        gen = _make_generator()
        config = MagicMock()
        config.last_triggered_at = datetime.now(UTC) - timedelta(minutes=60)
        config.cooldown_minutes = 30
        config.max_per_day = 100
        config.id = uuid4()

        gen.session.exec.return_value.one.return_value = 0

        result = await gen._check_limits(config)
        assert result is True

    @pytest.mark.asyncio
    async def test_daily_limit_reached(self):
        gen = _make_generator()
        config = MagicMock()
        config.last_triggered_at = None
        config.cooldown_minutes = 0
        config.max_per_day = 5
        config.id = uuid4()

        gen.session.exec.return_value.one.return_value = 5

        result = await gen._check_limits(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_under_daily_limit_passes(self):
        gen = _make_generator()
        config = MagicMock()
        config.last_triggered_at = None
        config.cooldown_minutes = 0
        config.max_per_day = 10
        config.id = uuid4()

        gen.session.exec.return_value.one.return_value = 3

        result = await gen._check_limits(config)
        assert result is True


# ──────────────────────────────────────────────
# _dispatch_alert — celery vs sync
# ──────────────────────────────────────────────
class TestDispatchAlert:
    @pytest.mark.asyncio
    async def test_celery_path(self):
        gen = _make_generator(use_celery=True)
        gen.use_celery = True

        alert = MagicMock(id=uuid4())
        config = MagicMock()
        config.last_triggered_at = None

        with patch(f"{SVC_MOD}.dispatch_alert_task", create=True) as mock_task:
            # Simulate import inside method
            with patch.dict(
                "sys.modules", {"workers.tasks.notification_tasks": MagicMock(dispatch_alert_task=mock_task)}
            ):
                await gen._dispatch_alert(alert, config)

                mock_task.delay.assert_called_once_with(str(alert.id))

    @pytest.mark.asyncio
    async def test_celery_failure_falls_back_to_sync(self):
        gen = _make_generator(use_celery=True)
        gen.use_celery = True
        gen._dispatch_alert_sync = AsyncMock()

        alert = MagicMock(id=uuid4())
        config = MagicMock()

        with patch.dict("sys.modules", {"workers.tasks.notification_tasks": None}):
            await gen._dispatch_alert(alert, config)

        gen._dispatch_alert_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_path_when_celery_disabled(self):
        gen = _make_generator(use_celery=False)
        gen._dispatch_alert_sync = AsyncMock()

        alert = MagicMock(id=uuid4())
        config = MagicMock()

        await gen._dispatch_alert(alert, config)

        gen._dispatch_alert_sync.assert_called_once_with(alert, config)
