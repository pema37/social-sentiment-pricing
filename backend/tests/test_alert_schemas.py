"""
Test Suite: backend/schemas/alert.py
Covers: AlertConfigurationCreate/Update/Read, AlertCreate, AlertRead,
        AlertAcknowledge, AlertResolve, AlertStats, AlertListResponse.

Place this file at: backend/tests/test_alert_schemas.py
Run with: pytest backend/tests/test_alert_schemas.py -v
"""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from models.alert import AlertChannel, AlertSeverity, AlertStatus, AlertType
from schemas.alert import (
    AlertAcknowledge,
    AlertConfigurationCreate,
    AlertConfigurationRead,
    AlertConfigurationUpdate,
    AlertCreate,
    AlertListResponse,
    AlertRead,
    AlertResolve,
    AlertStats,
)

# =====================================================================
# AlertConfigurationCreate
# =====================================================================


class TestAlertConfigurationCreate:
    def test_valid_minimal(self):
        c = AlertConfigurationCreate(
            name="Sentiment Alert",
            alert_type=AlertType.SENTIMENT_DROP,
        )
        assert c.name == "Sentiment Alert"
        assert c.alert_type == AlertType.SENTIMENT_DROP
        assert c.is_active is True
        assert c.product_ids is None
        assert c.conditions == {}
        assert c.channels == [AlertChannel.IN_APP]
        assert c.channel_settings == {}
        assert c.cooldown_minutes == 60
        assert c.max_per_day == 10

    def test_valid_full(self):
        pid = uuid.uuid4()
        c = AlertConfigurationCreate(
            name="Critical Price Change",
            description="Alert when competitor drops price > 10%",
            alert_type=AlertType.COMPETITOR_PRICE_CHANGE,
            is_active=True,
            product_ids=[pid],
            conditions={"threshold": -10, "direction": "below"},
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            channel_settings={"email": "test@example.com"},
            cooldown_minutes=30,
            max_per_day=5,
        )
        assert c.product_ids == [pid]
        assert len(c.channels) == 2
        assert c.cooldown_minutes == 30

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            AlertConfigurationCreate(alert_type=AlertType.SENTIMENT_DROP)

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            AlertConfigurationCreate(
                name="x" * 256,
                alert_type=AlertType.SENTIMENT_DROP,
            )

    def test_missing_alert_type_raises(self):
        with pytest.raises(ValidationError):
            AlertConfigurationCreate(name="Test")

    def test_invalid_alert_type_raises(self):
        with pytest.raises(ValidationError):
            AlertConfigurationCreate(
                name="Test",
                alert_type="not_a_type",
            )

    def test_all_alert_types_accepted(self):
        for at in AlertType:
            c = AlertConfigurationCreate(name=f"Test {at.value}", alert_type=at)
            assert c.alert_type == at

    def test_all_channels_accepted(self):
        for ch in AlertChannel:
            c = AlertConfigurationCreate(
                name="Test",
                alert_type=AlertType.SENTIMENT_DROP,
                channels=[ch],
            )
            assert c.channels == [ch]

    def test_cooldown_minutes_min(self):
        with pytest.raises(ValidationError):
            AlertConfigurationCreate(
                name="Test",
                alert_type=AlertType.SENTIMENT_DROP,
                cooldown_minutes=0,
            )

    def test_max_per_day_min(self):
        with pytest.raises(ValidationError):
            AlertConfigurationCreate(
                name="Test",
                alert_type=AlertType.SENTIMENT_DROP,
                max_per_day=0,
            )


# =====================================================================
# AlertConfigurationUpdate
# =====================================================================


class TestAlertConfigurationUpdate:
    def test_empty_update(self):
        u = AlertConfigurationUpdate()
        assert u.name is None
        assert u.is_active is None
        assert u.channels is None

    def test_partial_update(self):
        u = AlertConfigurationUpdate(
            name="Updated Name",
            is_active=False,
            cooldown_minutes=120,
        )
        assert u.name == "Updated Name"
        assert u.is_active is False
        assert u.cooldown_minutes == 120

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            AlertConfigurationUpdate(name="x" * 256)

    def test_cooldown_min(self):
        with pytest.raises(ValidationError):
            AlertConfigurationUpdate(cooldown_minutes=0)

    def test_max_per_day_min(self):
        with pytest.raises(ValidationError):
            AlertConfigurationUpdate(max_per_day=0)

    def test_update_channels(self):
        u = AlertConfigurationUpdate(
            channels=[AlertChannel.WEBHOOK, AlertChannel.EMAIL],
        )
        assert len(u.channels) == 2


# =====================================================================
# AlertConfigurationRead
# =====================================================================


class TestAlertConfigurationRead:
    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "name": "Sentiment Alert",
            "description": "Triggers on sentiment drop",
            "alert_type": AlertType.SENTIMENT_DROP,
            "is_active": True,
            "product_ids": None,
            "conditions": {"threshold": -0.3},
            "channels": [AlertChannel.IN_APP],
            "channel_settings": {},
            "cooldown_minutes": 60,
            "max_per_day": 10,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "last_triggered_at": None,
        }

    def test_valid(self, valid_data):
        r = AlertConfigurationRead(**valid_data)
        assert r.name == "Sentiment Alert"
        assert r.last_triggered_at is None

    def test_with_last_triggered(self, valid_data):
        valid_data["last_triggered_at"] = datetime.now(UTC)
        r = AlertConfigurationRead(**valid_data)
        assert r.last_triggered_at is not None

    def test_missing_id_raises(self, valid_data):
        del valid_data["id"]
        with pytest.raises(ValidationError):
            AlertConfigurationRead(**valid_data)

    def test_missing_alert_type_raises(self, valid_data):
        del valid_data["alert_type"]
        with pytest.raises(ValidationError):
            AlertConfigurationRead(**valid_data)


# =====================================================================
# AlertCreate
# =====================================================================


class TestAlertCreate:
    def test_valid_minimal(self):
        a = AlertCreate(
            alert_type=AlertType.PRICE_RECOMMENDATION,
            title="New Price Recommendation",
            message="Product X has a new recommendation.",
        )
        assert a.severity == AlertSeverity.MEDIUM
        assert a.product_id is None
        assert a.data == {}

    def test_valid_full(self):
        a = AlertCreate(
            alert_type=AlertType.SENTIMENT_DROP,
            severity=AlertSeverity.CRITICAL,
            title="Sentiment Crash",
            message="Sentiment dropped 60% in 2 hours",
            product_id=uuid.uuid4(),
            competitor_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            configuration_id=uuid.uuid4(),
            data={"score": -0.65, "previous": 0.2},
        )
        assert a.severity == AlertSeverity.CRITICAL
        assert a.product_id is not None

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            AlertCreate(
                alert_type=AlertType.SENTIMENT_DROP,
                message="Missing title",
            )

    def test_missing_message_raises(self):
        with pytest.raises(ValidationError):
            AlertCreate(
                alert_type=AlertType.SENTIMENT_DROP,
                title="Missing message",
            )

    def test_title_max_length(self):
        with pytest.raises(ValidationError):
            AlertCreate(
                alert_type=AlertType.SENTIMENT_DROP,
                title="x" * 256,
                message="test",
            )

    def test_all_severities_accepted(self):
        for sev in AlertSeverity:
            a = AlertCreate(
                alert_type=AlertType.SENTIMENT_DROP,
                severity=sev,
                title="Test",
                message="test",
            )
            assert a.severity == sev


# =====================================================================
# AlertRead
# =====================================================================


class TestAlertRead:
    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "configuration_id": None,
            "alert_type": AlertType.VIRAL_MENTION,
            "severity": AlertSeverity.HIGH,
            "title": "Viral Mention Detected",
            "message": "Product mentioned in viral tweet",
            "product_id": uuid.uuid4(),
            "competitor_id": None,
            "recommendation_id": None,
            "data": {"reach": 50000, "engagement": 3000},
            "status": AlertStatus.SENT,
            "channels_sent": ["email", "in_app"],
            "channels_failed": [],
            "created_at": datetime.now(UTC),
            "sent_at": datetime.now(UTC),
            "acknowledged_at": None,
            "acknowledged_by": None,
            "resolved_at": None,
        }

    def test_valid(self, valid_data):
        r = AlertRead(**valid_data)
        assert r.status == AlertStatus.SENT
        assert len(r.channels_sent) == 2

    def test_all_statuses(self, valid_data):
        for status in AlertStatus:
            valid_data["status"] = status
            r = AlertRead(**valid_data)
            assert r.status == status

    def test_missing_id_raises(self, valid_data):
        del valid_data["id"]
        with pytest.raises(ValidationError):
            AlertRead(**valid_data)

    def test_missing_title_raises(self, valid_data):
        del valid_data["title"]
        with pytest.raises(ValidationError):
            AlertRead(**valid_data)


# =====================================================================
# AlertAcknowledge / AlertResolve
# =====================================================================


class TestAlertAcknowledgeResolve:
    def test_acknowledge_empty(self):
        a = AlertAcknowledge()
        assert a is not None

    def test_resolve_without_note(self):
        r = AlertResolve()
        assert r.resolution_note is None

    def test_resolve_with_note(self):
        r = AlertResolve(resolution_note="Issue was a false positive")
        assert r.resolution_note == "Issue was a false positive"


# =====================================================================
# AlertStats
# =====================================================================


class TestAlertStats:
    def test_valid(self):
        s = AlertStats(
            total_unread=15,
            by_severity={"critical": 2, "high": 5, "medium": 5, "low": 3},
            by_type={"sentiment_drop": 8, "competitor_price_change": 7},
            recent_24h=10,
        )
        assert s.total_unread == 15
        assert s.by_severity["critical"] == 2

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            AlertStats(total_unread=5)


# =====================================================================
# AlertListResponse
# =====================================================================


class TestAlertListResponse:
    def test_valid(self):
        alert_data = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "configuration_id": None,
            "alert_type": AlertType.PRICE_APPLIED,
            "severity": AlertSeverity.LOW,
            "title": "Price Applied",
            "message": "New price applied to product",
            "product_id": None,
            "competitor_id": None,
            "recommendation_id": None,
            "data": {},
            "status": AlertStatus.ACKNOWLEDGED,
            "channels_sent": ["in_app"],
            "channels_failed": [],
            "created_at": datetime.now(UTC),
            "sent_at": datetime.now(UTC),
            "acknowledged_at": datetime.now(UTC),
            "acknowledged_by": uuid.uuid4(),
            "resolved_at": None,
        }
        r = AlertListResponse(
            alerts=[AlertRead(**alert_data)],
            total=1,
            page=1,
            per_page=20,
            has_more=False,
        )
        assert r.total == 1
        assert r.has_more is False

    def test_empty_list(self):
        r = AlertListResponse(
            alerts=[],
            total=0,
            page=1,
            per_page=20,
            has_more=False,
        )
        assert len(r.alerts) == 0
