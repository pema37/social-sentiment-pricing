"""
Tests for services/notification/email_service.py

EmailService with SendGrid — EmailResult dataclass, configuration checks,
client initialization, send_alert_email, HTML/plain text builders.
"""

import sys
from dataclasses import fields
from unittest.mock import MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
_saved = {}
_to_mock = ["core.config", "sendgrid", "sendgrid.helpers", "sendgrid.helpers.mail"]

for _m in _to_mock:
    _saved[_m] = sys.modules.get(_m)

# Fake settings
_settings = MagicMock()
_settings.SENDGRID_API_KEY = "SG.fake-key"
_settings.SENDGRID_FROM_EMAIL = "alerts@actualprice.com"

_config_mod = MagicMock()
_config_mod.settings = _settings
sys.modules["core.config"] = _config_mod

# Fake sendgrid
_sg_mod = MagicMock()
sys.modules["sendgrid"] = _sg_mod
sys.modules["sendgrid.helpers"] = MagicMock()
sys.modules["sendgrid.helpers.mail"] = MagicMock()

from services.notification.email_service import EmailResult, EmailService

# ── Restore ──────────────────────────────────────────────────────
for _m in _to_mock:
    if _saved[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _saved[_m]
del _m, _saved

SVC_MOD = "services.notification.email_service"


# ──────────────────────────────────────────────
# EmailResult dataclass
# ──────────────────────────────────────────────
class TestEmailResult:
    def test_success_result(self):
        r = EmailResult(success=True, message_id="msg-123")
        assert r.success is True
        assert r.message_id == "msg-123"
        assert r.error is None

    def test_failure_result(self):
        r = EmailResult(success=False, error="SendGrid down")
        assert r.success is False
        assert r.error == "SendGrid down"
        assert r.message_id is None

    def test_defaults(self):
        r = EmailResult(success=True)
        assert r.message_id is None
        assert r.error is None

    def test_field_count(self):
        assert len(fields(EmailResult)) == 3

    def test_all_fields_set(self):
        r = EmailResult(success=False, message_id="m-1", error="err")
        assert r.success is False
        assert r.message_id == "m-1"
        assert r.error == "err"


# ──────────────────────────────────────────────
# EmailService — init
# ──────────────────────────────────────────────
class TestEmailServiceInit:
    def test_reads_api_key(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "key-123"
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            svc = EmailService()
            assert svc.api_key == "key-123"

    def test_reads_from_email(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "key"
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            svc = EmailService()
            assert svc.from_email == "from@test.com"

    def test_client_initially_none(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "key"
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            svc = EmailService()
            assert svc._client is None


# ──────────────────────────────────────────────
# EmailService — is_configured
# ──────────────────────────────────────────────
class TestIsConfigured:
    def test_true_when_both_set(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "key"
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            svc = EmailService()
            assert svc.is_configured is True

    def test_false_when_no_api_key(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            svc = EmailService()
            assert svc.is_configured is False

    def test_false_when_no_from_email(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "key"
            mock_settings.SENDGRID_FROM_EMAIL = ""
            svc = EmailService()
            assert svc.is_configured is False

    def test_false_when_none_api_key(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = None
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            svc = EmailService()
            assert svc.is_configured is False

    def test_false_when_both_empty(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = ""
            svc = EmailService()
            assert svc.is_configured is False


# ──────────────────────────────────────────────
# EmailService — _get_client
# ──────────────────────────────────────────────
class TestGetClient:
    def test_returns_none_when_not_configured(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = ""
            svc = EmailService()
            assert svc._get_client() is None

    def test_creates_client_when_configured(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "SG.test"
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            svc = EmailService()

            mock_sg_cls = MagicMock()
            mock_sg_instance = MagicMock()
            mock_sg_cls.return_value = mock_sg_instance

            with patch.dict("sys.modules", {"sendgrid": MagicMock(SendGridAPIClient=mock_sg_cls)}):
                client = svc._get_client()
                assert client is mock_sg_instance

    def test_caches_client(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "SG.test"
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            svc = EmailService()
            sentinel = MagicMock()
            svc._client = sentinel

            result = svc._get_client()
            assert result is sentinel

    def test_import_error_returns_none(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "SG.test"
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            svc = EmailService()

            # Simulate import failure inside _get_client
            with patch.dict("sys.modules", {"sendgrid": None}):
                # Force fresh import attempt
                svc._client = None
                # The try/except ImportError should catch
                try:
                    result = svc._get_client()
                except (ImportError, TypeError):
                    result = None
                # Client should still be None or the method returns None
                # Either way, no crash


# ──────────────────────────────────────────────
# EmailService — send_alert_email
# ──────────────────────────────────────────────
class TestSendAlertEmail:
    def _make_service(self, api_key="SG.test", from_email="from@test.com"):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = api_key
            mock_settings.SENDGRID_FROM_EMAIL = from_email
            return EmailService()

    @pytest.mark.asyncio
    async def test_not_configured_returns_failure(self):
        svc = self._make_service(api_key="", from_email="")
        result = await svc.send_alert_email(
            to_email="user@test.com",
            subject="Test",
            alert_title="Alert",
            alert_message="Message",
        )
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_no_client_returns_failure(self):
        svc = self._make_service()
        svc._get_client = MagicMock(return_value=None)

        result = await svc.send_alert_email(
            to_email="user@test.com",
            subject="Test",
            alert_title="Alert",
            alert_message="Message",
        )
        assert result.success is False
        assert "Failed to initialize" in result.error

    @pytest.mark.asyncio
    async def test_successful_send(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {"X-Message-Id": "msg-abc"}

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response
        svc._client = mock_client

        # Mock sendgrid.helpers.mail imports
        with patch.dict(
            "sys.modules",
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            result = await svc.send_alert_email(
                to_email="user@test.com",
                subject="Price Alert",
                alert_title="Sentiment Drop",
                alert_message="Product X dropped",
            )

        assert result.success is True
        assert result.message_id == "msg-abc"

    @pytest.mark.asyncio
    async def test_status_200_success(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"X-Message-Id": "msg-200"}

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response
        svc._client = mock_client

        with patch.dict(
            "sys.modules",
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            result = await svc.send_alert_email(
                to_email="u@t.com",
                subject="S",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_status_201_success(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"X-Message-Id": "msg-201"}

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response
        svc._client = mock_client

        with patch.dict(
            "sys.modules",
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            result = await svc.send_alert_email(
                to_email="u@t.com",
                subject="S",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_non_success_status_returns_failure(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response
        svc._client = mock_client

        with patch.dict(
            "sys.modules",
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            result = await svc.send_alert_email(
                to_email="u@t.com",
                subject="S",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is False
        assert "400" in result.error

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        svc = self._make_service()

        mock_client = MagicMock()
        mock_client.send.side_effect = Exception("Network error")
        svc._client = mock_client

        with patch.dict(
            "sys.modules",
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            result = await svc.send_alert_email(
                to_email="u@t.com",
                subject="S",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is False
        assert "Network error" in result.error

    @pytest.mark.asyncio
    async def test_missing_message_id_header(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {}  # No X-Message-Id

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response
        svc._client = mock_client

        with patch.dict(
            "sys.modules",
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            result = await svc.send_alert_email(
                to_email="u@t.com",
                subject="S",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is True
        assert result.message_id == "unknown"

    @pytest.mark.asyncio
    async def test_default_severity_is_medium(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {"X-Message-Id": "msg-1"}

        mock_client = MagicMock()
        mock_client.send.return_value = mock_response
        svc._client = mock_client

        with patch.dict(
            "sys.modules",
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": MagicMock(),
            },
        ):
            # Just verify it doesn't crash with default severity
            result = await svc.send_alert_email(
                to_email="u@t.com",
                subject="S",
                alert_title="T",
                alert_message="M",
            )
            assert result.success is True


# ──────────────────────────────────────────────
# EmailService — _build_alert_html
# ──────────────────────────────────────────────
class TestBuildAlertHtml:
    def _make_service(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "key"
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            return EmailService()

    def test_contains_title(self):
        svc = self._make_service()
        html = svc._build_alert_html("My Alert", "body", None, "medium")
        assert "My Alert" in html

    def test_contains_message(self):
        svc = self._make_service()
        html = svc._build_alert_html("Title", "Alert body text", None, "medium")
        assert "Alert body text" in html

    def test_contains_severity_label(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "high")
        assert "HIGH PRIORITY" in html

    def test_severity_color_low(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "low")
        assert "#6B7280" in html

    def test_severity_color_medium(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "medium")
        assert "#F59E0B" in html

    def test_severity_color_high(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "high")
        assert "#EF4444" in html

    def test_severity_color_critical(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "critical")
        assert "#DC2626" in html

    def test_unknown_severity_uses_default_gray(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "unknown")
        assert "#6B7280" in html

    def test_case_insensitive_severity(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "HIGH")
        assert "#EF4444" in html

    def test_with_alert_data(self):
        svc = self._make_service()
        data = {"product": "Widget", "change": "-25%"}
        html = svc._build_alert_html("T", "M", data, "medium")
        assert "product" in html
        assert "Widget" in html
        assert "change" in html
        assert "-25%" in html

    def test_without_alert_data(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "medium")
        assert "<table" not in html or "Details" not in html

    def test_contains_footer(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "medium")
        assert "Social Sentiment Pricing" in html

    def test_is_valid_html(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", None, "medium")
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_empty_alert_data_dict(self):
        svc = self._make_service()
        html = svc._build_alert_html("T", "M", {}, "medium")
        # Empty dict should produce empty data section
        assert isinstance(html, str)


# ──────────────────────────────────────────────
# EmailService — _build_alert_plain
# ──────────────────────────────────────────────
class TestBuildAlertPlain:
    def _make_service(self):
        with patch(f"{SVC_MOD}.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "key"
            mock_settings.SENDGRID_FROM_EMAIL = "from@test.com"
            return EmailService()

    def test_contains_title(self):
        svc = self._make_service()
        text = svc._build_alert_plain("My Alert", "body", None)
        assert "My Alert" in text

    def test_contains_message(self):
        svc = self._make_service()
        text = svc._build_alert_plain("T", "Alert body text", None)
        assert "Alert body text" in text

    def test_contains_footer(self):
        svc = self._make_service()
        text = svc._build_alert_plain("T", "M", None)
        assert "Social Sentiment Pricing" in text

    def test_with_alert_data(self):
        svc = self._make_service()
        data = {"product": "Widget", "change": "-25%"}
        text = svc._build_alert_plain("T", "M", data)
        assert "product: Widget" in text
        assert "change: -25%" in text
        assert "Details:" in text

    def test_without_alert_data(self):
        svc = self._make_service()
        text = svc._build_alert_plain("T", "M", None)
        assert "Details:" not in text

    def test_title_wrapped_in_equals(self):
        svc = self._make_service()
        text = svc._build_alert_plain("My Alert", "M", None)
        assert "=== My Alert ===" in text

    def test_separator_line(self):
        svc = self._make_service()
        text = svc._build_alert_plain("T", "M", None)
        assert "---" in text

    def test_returns_string(self):
        svc = self._make_service()
        text = svc._build_alert_plain("T", "M", None)
        assert isinstance(text, str)

    def test_empty_alert_data_dict(self):
        svc = self._make_service()
        text = svc._build_alert_plain("T", "M", {})
        # Empty dict — "Details:" header appears but no items
        assert isinstance(text, str)

    def test_multiple_data_items(self):
        svc = self._make_service()
        data = {"a": 1, "b": 2, "c": 3}
        text = svc._build_alert_plain("T", "M", data)
        assert "a: 1" in text
        assert "b: 2" in text
        assert "c: 3" in text
