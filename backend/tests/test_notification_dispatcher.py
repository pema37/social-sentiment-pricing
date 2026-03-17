"""
Tests for services/notification/notification_dispatcher.py

NotificationDispatcher — orchestrates multi-channel dispatch.
DispatchResult dataclass, dispatch routing, send_quick_alert convenience.
"""

import sys
from enum import Enum
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED = [
    "services.notification.email_service",
    "services.notification.slack_service",
    "services.notification.webhook_service",
    "models.alert",
    "core.config",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# email_service
_email_mod = MagicMock()
_email_mod.EmailService = MagicMock
_email_mod.EmailResult = type(
    "EmailResult",
    (),
    {
        "__init__": lambda self, success=False, message_id=None, error=None: (
            setattr(self, "success", success)
            or setattr(self, "message_id", message_id)
            or setattr(self, "error", error)
        )
    },
)
sys.modules["services.notification.email_service"] = _email_mod

# slack_service
_slack_mod = MagicMock()
_slack_mod.SlackService = MagicMock
_slack_mod.SlackResult = type(
    "SlackResult",
    (),
    {
        "__init__": lambda self, success=False, error=None: (
            setattr(self, "success", success) or setattr(self, "error", error)
        )
    },
)
sys.modules["services.notification.slack_service"] = _slack_mod

# webhook_service
_wh_mod = MagicMock()
_wh_mod.WebhookService = MagicMock
_wh_mod.WebhookResult = type(
    "WebhookResult",
    (),
    {
        "__init__": lambda self, success=False, status_code=None, error=None: (
            setattr(self, "success", success)
            or setattr(self, "status_code", status_code)
            or setattr(self, "error", error)
        )
    },
)
sys.modules["services.notification.webhook_service"] = _wh_mod


# models.alert
class AlertChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


_alert_mod = MagicMock()
_alert_mod.AlertChannel = AlertChannel
sys.modules["models.alert"] = _alert_mod

# core.config (needed by sub-services)
_config_mod = MagicMock()
_config_mod.settings = MagicMock()
sys.modules["core.config"] = _config_mod

from services.notification.notification_dispatcher import (
    DispatchResult,
    NotificationDispatcher,
    send_quick_alert,
)

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

SVC_MOD = "services.notification.notification_dispatcher"


# ── Helpers ───────────────────────────────────────────────────────


def _make_email_result(success=True, error=None):
    r = MagicMock()
    r.success = success
    r.error = error
    r.message_id = "msg-1" if success else None
    return r


def _make_slack_result(success=True, error=None):
    r = MagicMock()
    r.success = success
    r.error = error
    return r


def _make_webhook_result(success=True, error=None):
    r = MagicMock()
    r.success = success
    r.error = error
    r.status_code = 200 if success else 500
    return r


def _make_dispatcher(email_ok=True, slack_ok=True, webhook_ok=True):
    d = NotificationDispatcher()
    d.email_service = MagicMock()
    d.email_service.send_alert_email = AsyncMock(
        return_value=_make_email_result(email_ok, None if email_ok else "email err")
    )
    d.slack_service = MagicMock()
    d.slack_service.send_alert = AsyncMock(return_value=_make_slack_result(slack_ok, None if slack_ok else "slack err"))
    d.webhook_service = MagicMock()
    d.webhook_service.send_alert = AsyncMock(
        return_value=_make_webhook_result(webhook_ok, None if webhook_ok else "webhook err")
    )
    return d


# ──────────────────────────────────────────────
# DispatchResult
# ──────────────────────────────────────────────
class TestDispatchResult:
    def test_defaults(self):
        r = DispatchResult()
        assert r.channels_sent == []
        assert r.channels_failed == []
        assert r.errors == {}

    def test_success_true_when_sent(self):
        r = DispatchResult(channels_sent=["email"])
        assert r.success is True

    def test_success_false_when_none_sent(self):
        r = DispatchResult(channels_failed=["email"])
        assert r.success is False

    def test_success_false_empty(self):
        r = DispatchResult()
        assert r.success is False

    def test_partial_true(self):
        r = DispatchResult(channels_sent=["email"], channels_failed=["slack"])
        assert r.partial is True

    def test_partial_false_all_sent(self):
        r = DispatchResult(channels_sent=["email", "slack"])
        assert r.partial is False

    def test_partial_false_all_failed(self):
        r = DispatchResult(channels_failed=["email", "slack"])
        assert r.partial is False

    def test_partial_false_empty(self):
        r = DispatchResult()
        assert r.partial is False

    def test_errors_dict(self):
        r = DispatchResult(errors={"email": "timeout"})
        assert r.errors["email"] == "timeout"


# ──────────────────────────────────────────────
# NotificationDispatcher — init
# ──────────────────────────────────────────────
class TestDispatcherInit:
    def test_creates_services(self):
        d = NotificationDispatcher()
        assert d.email_service is not None
        assert d.slack_service is not None
        assert d.webhook_service is not None


# ──────────────────────────────────────────────
# dispatch — routing
# ──────────────────────────────────────────────
class TestDispatchRouting:
    @pytest.mark.asyncio
    async def test_email_channel(self):
        d = _make_dispatcher()
        result = await d.dispatch(
            channels=[AlertChannel.EMAIL],
            alert_title="T",
            alert_message="M",
            recipient_email="user@test.com",
        )
        assert "email" in result.channels_sent
        d.email_service.send_alert_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_slack_channel(self):
        d = _make_dispatcher()
        result = await d.dispatch(
            channels=[AlertChannel.SLACK],
            alert_title="T",
            alert_message="M",
            slack_webhook_url="https://hooks.slack.com/test",
        )
        assert "slack" in result.channels_sent
        d.slack_service.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_channel(self):
        d = _make_dispatcher()
        result = await d.dispatch(
            channels=[AlertChannel.WEBHOOK],
            alert_title="T",
            alert_message="M",
            webhook_url="https://test.com/hook",
        )
        assert "webhook" in result.channels_sent
        d.webhook_service.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_in_app_channel(self):
        d = _make_dispatcher()
        result = await d.dispatch(
            channels=[AlertChannel.IN_APP],
            alert_title="T",
            alert_message="M",
        )
        assert "in_app" in result.channels_sent

    @pytest.mark.asyncio
    async def test_all_channels(self):
        d = _make_dispatcher()
        result = await d.dispatch(
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.WEBHOOK, AlertChannel.IN_APP],
            alert_title="T",
            alert_message="M",
            recipient_email="u@t.com",
            slack_webhook_url="https://slack.com",
            webhook_url="https://wh.com",
        )
        assert set(result.channels_sent) == {"email", "slack", "webhook", "in_app"}

    @pytest.mark.asyncio
    async def test_empty_channels(self):
        d = _make_dispatcher()
        result = await d.dispatch(
            channels=[],
            alert_title="T",
            alert_message="M",
        )
        assert result.channels_sent == []
        assert result.channels_failed == []

    @pytest.mark.asyncio
    async def test_returns_dispatch_result(self):
        d = _make_dispatcher()
        result = await d.dispatch(
            channels=[AlertChannel.IN_APP],
            alert_title="T",
            alert_message="M",
        )
        assert isinstance(result, DispatchResult)


# ──────────────────────────────────────────────
# _send_email
# ──────────────────────────────────────────────
class TestSendEmail:
    @pytest.mark.asyncio
    async def test_no_recipient_fails(self):
        d = _make_dispatcher()
        result = DispatchResult()
        await d._send_email(
            result=result,
            recipient_email=None,
            subject="S",
            alert_title="T",
            alert_message="M",
            severity="medium",
            alert_data=None,
        )
        assert "email" in result.channels_failed
        assert "No recipient" in result.errors["email"]

    @pytest.mark.asyncio
    async def test_success(self):
        d = _make_dispatcher(email_ok=True)
        result = DispatchResult()
        await d._send_email(
            result=result,
            recipient_email="u@t.com",
            subject="S",
            alert_title="T",
            alert_message="M",
            severity="medium",
            alert_data=None,
        )
        assert "email" in result.channels_sent

    @pytest.mark.asyncio
    async def test_failure(self):
        d = _make_dispatcher(email_ok=False)
        result = DispatchResult()
        await d._send_email(
            result=result,
            recipient_email="u@t.com",
            subject="S",
            alert_title="T",
            alert_message="M",
            severity="medium",
            alert_data=None,
        )
        assert "email" in result.channels_failed
        assert "email" in result.errors

    @pytest.mark.asyncio
    async def test_passes_params(self):
        d = _make_dispatcher()
        result = DispatchResult()
        data = {"key": "val"}
        await d._send_email(
            result=result,
            recipient_email="user@test.com",
            subject="My Subject",
            alert_title="My Title",
            alert_message="Body",
            severity="high",
            alert_data=data,
        )
        d.email_service.send_alert_email.assert_called_once_with(
            to_email="user@test.com",
            subject="My Subject",
            alert_title="My Title",
            alert_message="Body",
            alert_data=data,
            severity="high",
        )


# ──────────────────────────────────────────────
# _send_slack
# ──────────────────────────────────────────────
class TestSendSlack:
    @pytest.mark.asyncio
    async def test_success(self):
        d = _make_dispatcher(slack_ok=True)
        result = DispatchResult()
        await d._send_slack(
            result=result,
            webhook_url="https://slack.com",
            alert_title="T",
            alert_message="M",
            severity="medium",
            alert_data=None,
        )
        assert "slack" in result.channels_sent

    @pytest.mark.asyncio
    async def test_failure(self):
        d = _make_dispatcher(slack_ok=False)
        result = DispatchResult()
        await d._send_slack(
            result=result,
            webhook_url=None,
            alert_title="T",
            alert_message="M",
            severity="medium",
            alert_data=None,
        )
        assert "slack" in result.channels_failed

    @pytest.mark.asyncio
    async def test_passes_params(self):
        d = _make_dispatcher()
        result = DispatchResult()
        await d._send_slack(
            result=result,
            webhook_url="https://my-hook.com",
            alert_title="Title",
            alert_message="Msg",
            severity="critical",
            alert_data={"a": 1},
        )
        d.slack_service.send_alert.assert_called_once_with(
            webhook_url="https://my-hook.com",
            alert_title="Title",
            alert_message="Msg",
            severity="critical",
            alert_data={"a": 1},
        )


# ──────────────────────────────────────────────
# _send_webhook
# ──────────────────────────────────────────────
class TestSendWebhook:
    @pytest.mark.asyncio
    async def test_no_url_fails(self):
        d = _make_dispatcher()
        result = DispatchResult()
        await d._send_webhook(
            result=result,
            webhook_url=None,
            webhook_secret=None,
            alert_id=None,
            alert_title="T",
            alert_message="M",
            alert_type=None,
            severity="medium",
            alert_data=None,
        )
        assert "webhook" in result.channels_failed
        assert "No webhook URL" in result.errors["webhook"]

    @pytest.mark.asyncio
    async def test_success(self):
        d = _make_dispatcher(webhook_ok=True)
        result = DispatchResult()
        await d._send_webhook(
            result=result,
            webhook_url="https://wh.com",
            webhook_secret="s",
            alert_id="a-1",
            alert_title="T",
            alert_message="M",
            alert_type="type",
            severity="medium",
            alert_data=None,
        )
        assert "webhook" in result.channels_sent

    @pytest.mark.asyncio
    async def test_failure(self):
        d = _make_dispatcher(webhook_ok=False)
        result = DispatchResult()
        await d._send_webhook(
            result=result,
            webhook_url="https://wh.com",
            webhook_secret=None,
            alert_id=None,
            alert_title="T",
            alert_message="M",
            alert_type=None,
            severity="medium",
            alert_data=None,
        )
        assert "webhook" in result.channels_failed

    @pytest.mark.asyncio
    async def test_passes_params(self):
        d = _make_dispatcher()
        result = DispatchResult()
        await d._send_webhook(
            result=result,
            webhook_url="https://wh.com/x",
            webhook_secret="sec",
            alert_id="a-1",
            alert_title="Title",
            alert_message="Msg",
            alert_type="sentiment",
            severity="high",
            alert_data={"b": 2},
        )
        d.webhook_service.send_alert.assert_called_once_with(
            webhook_url="https://wh.com/x",
            webhook_secret="sec",
            alert_id="a-1",
            alert_title="Title",
            alert_message="Msg",
            alert_type="sentiment",
            severity="high",
            alert_data={"b": 2},
        )


# ──────────────────────────────────────────────
# dispatch — mixed results
# ──────────────────────────────────────────────
class TestDispatchMixed:
    @pytest.mark.asyncio
    async def test_partial_failure(self):
        d = _make_dispatcher(email_ok=True, slack_ok=False)
        result = await d.dispatch(
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            alert_title="T",
            alert_message="M",
            recipient_email="u@t.com",
        )
        assert result.success is True
        assert result.partial is True
        assert "email" in result.channels_sent
        assert "slack" in result.channels_failed

    @pytest.mark.asyncio
    async def test_all_fail(self):
        d = _make_dispatcher(email_ok=False, slack_ok=False, webhook_ok=False)
        result = await d.dispatch(
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.WEBHOOK],
            alert_title="T",
            alert_message="M",
            recipient_email="u@t.com",
            webhook_url="https://wh.com",
        )
        assert result.success is False
        assert len(result.channels_failed) == 3

    @pytest.mark.asyncio
    async def test_default_email_subject(self):
        d = _make_dispatcher()
        await d.dispatch(
            channels=[AlertChannel.EMAIL],
            alert_title="My Alert",
            alert_message="M",
            recipient_email="u@t.com",
        )
        call_kw = d.email_service.send_alert_email.call_args[1]
        assert call_kw["subject"] == "[SSP Alert] My Alert"

    @pytest.mark.asyncio
    async def test_custom_email_subject(self):
        d = _make_dispatcher()
        await d.dispatch(
            channels=[AlertChannel.EMAIL],
            alert_title="T",
            alert_message="M",
            recipient_email="u@t.com",
            email_subject="Custom Subject",
        )
        call_kw = d.email_service.send_alert_email.call_args[1]
        assert call_kw["subject"] == "Custom Subject"

    @pytest.mark.asyncio
    async def test_error_none_becomes_unknown(self):
        d = _make_dispatcher()
        # Make email return success=False with error=None
        d.email_service.send_alert_email = AsyncMock(return_value=MagicMock(success=False, error=None))
        result = await d.dispatch(
            channels=[AlertChannel.EMAIL],
            alert_title="T",
            alert_message="M",
            recipient_email="u@t.com",
        )
        assert result.errors["email"] == "Unknown error"


# ──────────────────────────────────────────────
# send_quick_alert
# ──────────────────────────────────────────────
class TestSendQuickAlert:
    @pytest.mark.asyncio
    async def test_always_includes_in_app(self):
        with patch(f"{SVC_MOD}.NotificationDispatcher") as MockDisp:
            mock_d = MagicMock()
            mock_d.dispatch = AsyncMock(return_value=DispatchResult(channels_sent=["in_app"]))
            MockDisp.return_value = mock_d

            await send_quick_alert(title="T", message="M")

            call_kw = mock_d.dispatch.call_args[1]
            assert AlertChannel.IN_APP in call_kw["channels"]

    @pytest.mark.asyncio
    async def test_adds_email_channel(self):
        with patch(f"{SVC_MOD}.NotificationDispatcher") as MockDisp:
            mock_d = MagicMock()
            mock_d.dispatch = AsyncMock(return_value=DispatchResult(channels_sent=["in_app"]))
            MockDisp.return_value = mock_d

            await send_quick_alert(title="T", message="M", email="u@t.com")

            call_kw = mock_d.dispatch.call_args[1]
            assert AlertChannel.EMAIL in call_kw["channels"]
            assert call_kw["recipient_email"] == "u@t.com"

    @pytest.mark.asyncio
    async def test_adds_slack_channel(self):
        with patch(f"{SVC_MOD}.NotificationDispatcher") as MockDisp:
            mock_d = MagicMock()
            mock_d.dispatch = AsyncMock(return_value=DispatchResult(channels_sent=["in_app"]))
            MockDisp.return_value = mock_d

            await send_quick_alert(title="T", message="M", slack_webhook="https://slack.com")

            call_kw = mock_d.dispatch.call_args[1]
            assert AlertChannel.SLACK in call_kw["channels"]

    @pytest.mark.asyncio
    async def test_adds_webhook_channel(self):
        with patch(f"{SVC_MOD}.NotificationDispatcher") as MockDisp:
            mock_d = MagicMock()
            mock_d.dispatch = AsyncMock(return_value=DispatchResult(channels_sent=["in_app"]))
            MockDisp.return_value = mock_d

            await send_quick_alert(
                title="T",
                message="M",
                webhook_url="https://wh.com",
                webhook_secret="sec",
            )

            call_kw = mock_d.dispatch.call_args[1]
            assert AlertChannel.WEBHOOK in call_kw["channels"]
            assert call_kw["webhook_url"] == "https://wh.com"
            assert call_kw["webhook_secret"] == "sec"

    @pytest.mark.asyncio
    async def test_no_optional_channels(self):
        with patch(f"{SVC_MOD}.NotificationDispatcher") as MockDisp:
            mock_d = MagicMock()
            mock_d.dispatch = AsyncMock(return_value=DispatchResult(channels_sent=["in_app"]))
            MockDisp.return_value = mock_d

            await send_quick_alert(title="T", message="M")

            call_kw = mock_d.dispatch.call_args[1]
            assert call_kw["channels"] == [AlertChannel.IN_APP]

    @pytest.mark.asyncio
    async def test_passes_all_params(self):
        with patch(f"{SVC_MOD}.NotificationDispatcher") as MockDisp:
            mock_d = MagicMock()
            mock_d.dispatch = AsyncMock(return_value=DispatchResult(channels_sent=["in_app"]))
            MockDisp.return_value = mock_d

            await send_quick_alert(
                title="Alert",
                message="Body",
                severity="critical",
                alert_type="sentiment_drop",
                data={"k": "v"},
            )

            call_kw = mock_d.dispatch.call_args[1]
            assert call_kw["alert_title"] == "Alert"
            assert call_kw["alert_message"] == "Body"
            assert call_kw["severity"] == "critical"
            assert call_kw["alert_type"] == "sentiment_drop"
            assert call_kw["alert_data"] == {"k": "v"}

    @pytest.mark.asyncio
    async def test_returns_dispatch_result(self):
        with patch(f"{SVC_MOD}.NotificationDispatcher") as MockDisp:
            expected = DispatchResult(channels_sent=["in_app"])
            mock_d = MagicMock()
            mock_d.dispatch = AsyncMock(return_value=expected)
            MockDisp.return_value = mock_d

            result = await send_quick_alert(title="T", message="M")
            assert result is expected
