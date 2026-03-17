"""
Tests for services/notification/slack_service.py

SlackService with webhook — SlackResult dataclass, send_alert, payload builder.
"""

import sys
from dataclasses import fields
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
_saved = {}
_to_mock = ["core.config"]
for _m in _to_mock:
    _saved[_m] = sys.modules.get(_m)

_settings = MagicMock()
_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/T00/B00/xxx"
_config_mod = MagicMock()
_config_mod.settings = _settings
sys.modules["core.config"] = _config_mod

from services.notification.slack_service import SlackResult, SlackService

for _m in _to_mock:
    if _saved[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _saved[_m]
del _m, _saved

SVC_MOD = "services.notification.slack_service"


# ──────────────────────────────────────────────
# SlackResult dataclass
# ──────────────────────────────────────────────
class TestSlackResult:
    def test_success(self):
        r = SlackResult(success=True)
        assert r.success is True
        assert r.error is None

    def test_failure(self):
        r = SlackResult(success=False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"

    def test_defaults(self):
        r = SlackResult(success=True)
        assert r.error is None

    def test_field_count(self):
        assert len(fields(SlackResult)) == 2


# ──────────────────────────────────────────────
# SlackService — init
# ──────────────────────────────────────────────
class TestSlackServiceInit:
    def test_reads_default_webhook_url(self):
        with patch(f"{SVC_MOD}.settings") as mock_s:
            mock_s.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"
            svc = SlackService()
            assert svc.default_webhook_url == "https://hooks.slack.com/test"

    def test_timeout_default(self):
        with patch(f"{SVC_MOD}.settings") as mock_s:
            mock_s.SLACK_WEBHOOK_URL = ""
            svc = SlackService()
            assert svc.timeout == 10.0


# ──────────────────────────────────────────────
# SlackService — send_alert
# ──────────────────────────────────────────────
class TestSendAlert:
    def _make_service(self, webhook_url="https://hooks.slack.com/test"):
        with patch(f"{SVC_MOD}.settings") as mock_s:
            mock_s.SLACK_WEBHOOK_URL = webhook_url
            return SlackService()

    @pytest.mark.asyncio
    async def test_no_url_returns_failure(self):
        svc = self._make_service(webhook_url="")
        result = await svc.send_alert(
            alert_title="T",
            alert_message="M",
            webhook_url=None,
        )
        assert result.success is False
        assert "No Slack webhook URL" in result.error

    @pytest.mark.asyncio
    async def test_no_url_both_none_and_empty(self):
        svc = self._make_service(webhook_url=None)
        result = await svc.send_alert(alert_title="T", alert_message="M")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_uses_provided_webhook_url(self):
        svc = self._make_service(webhook_url="https://default.com")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc.send_alert(
                alert_title="T",
                alert_message="M",
                webhook_url="https://custom.com/hook",
            )

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://custom.com/hook"

    @pytest.mark.asyncio
    async def test_falls_back_to_default_url(self):
        svc = self._make_service(webhook_url="https://default.com/hook")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc.send_alert(alert_title="T", alert_message="M")

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://default.com/hook"

    @pytest.mark.asyncio
    async def test_success_200(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await svc.send_alert(alert_title="T", alert_message="M")

        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_non_200_returns_failure(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "invalid_token"

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await svc.send_alert(alert_title="T", alert_message="M")

        assert result.success is False
        assert "403" in result.error
        assert "invalid_token" in result.error

    @pytest.mark.asyncio
    async def test_timeout_returns_failure(self):
        import httpx

        svc = self._make_service()

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await svc.send_alert(alert_title="T", alert_message="M")

        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_generic_exception_returns_failure(self):
        svc = self._make_service()

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("network error")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await svc.send_alert(alert_title="T", alert_message="M")

        assert result.success is False
        assert "network error" in result.error

    @pytest.mark.asyncio
    async def test_posts_json_payload(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc.send_alert(alert_title="T", alert_message="M")

            call_kwargs = mock_client.post.call_args[1]
            assert "json" in call_kwargs
            payload = call_kwargs["json"]
            assert "blocks" in payload
            assert "text" in payload

    @pytest.mark.asyncio
    async def test_passes_alert_data(self):
        svc = self._make_service()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc.send_alert(
                alert_title="T",
                alert_message="M",
                alert_data={"product": "Widget"},
            )

            payload = mock_client.post.call_args[1]["json"]
            # Should have a section with fields
            section_types = [b["type"] for b in payload["blocks"]]
            assert "section" in section_types


# ──────────────────────────────────────────────
# SlackService — _build_payload
# ──────────────────────────────────────────────
class TestBuildPayload:
    def _make_service(self):
        with patch(f"{SVC_MOD}.settings") as mock_s:
            mock_s.SLACK_WEBHOOK_URL = "https://test.com"
            return SlackService()

    def test_returns_dict(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "medium", None)
        assert isinstance(result, dict)

    def test_has_blocks_key(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "medium", None)
        assert "blocks" in result

    def test_has_fallback_text(self):
        svc = self._make_service()
        result = svc._build_payload("My Alert", "Body text", "medium", None)
        assert "text" in result
        assert "My Alert" in result["text"]
        assert "Body text" in result["text"]

    def test_header_block(self):
        svc = self._make_service()
        result = svc._build_payload("My Alert", "M", "medium", None)
        header = result["blocks"][0]
        assert header["type"] == "header"
        assert "My Alert" in header["text"]["text"]

    def test_section_block_with_message(self):
        svc = self._make_service()
        result = svc._build_payload("T", "Alert body", "medium", None)
        section = result["blocks"][1]
        assert section["type"] == "section"
        assert "Alert body" in section["text"]["text"]

    def test_context_block(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "high", None)
        # Context is after header + section (index 2 when no data)
        context = result["blocks"][2]
        assert context["type"] == "context"
        assert "HIGH" in context["elements"][0]["text"]
        assert "Social Sentiment Pricing" in context["elements"][0]["text"]

    def test_divider_at_end(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "medium", None)
        assert result["blocks"][-1]["type"] == "divider"

    def test_severity_emoji_low(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "low", None)
        header_text = result["blocks"][0]["text"]["text"]
        assert "ℹ️" in header_text

    def test_severity_emoji_medium(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "medium", None)
        header_text = result["blocks"][0]["text"]["text"]
        assert "⚠️" in header_text

    def test_severity_emoji_high(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "high", None)
        header_text = result["blocks"][0]["text"]["text"]
        assert "🔴" in header_text

    def test_severity_emoji_critical(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "critical", None)
        header_text = result["blocks"][0]["text"]["text"]
        assert "🚨" in header_text

    def test_severity_emoji_unknown_defaults(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "unknown", None)
        header_text = result["blocks"][0]["text"]["text"]
        assert "⚠️" in header_text

    def test_case_insensitive_severity(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "HIGH", None)
        header_text = result["blocks"][0]["text"]["text"]
        assert "🔴" in header_text

    def test_with_alert_data(self):
        svc = self._make_service()
        data = {"product": "Widget", "change": "-25%"}
        result = svc._build_payload("T", "M", "medium", data)

        # Data section should be inserted at index 2
        data_section = result["blocks"][2]
        assert data_section["type"] == "section"
        assert "fields" in data_section
        assert len(data_section["fields"]) == 2

    def test_alert_data_field_format(self):
        svc = self._make_service()
        data = {"product": "Widget"}
        result = svc._build_payload("T", "M", "medium", data)

        field = result["blocks"][2]["fields"][0]
        assert field["type"] == "mrkdwn"
        assert "*product:*" in field["text"]
        assert "Widget" in field["text"]

    def test_alert_data_max_10_fields(self):
        svc = self._make_service()
        data = {f"key{i}": f"val{i}" for i in range(15)}
        result = svc._build_payload("T", "M", "medium", data)

        data_section = result["blocks"][2]
        assert len(data_section["fields"]) == 10

    def test_without_alert_data_no_fields_section(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "medium", None)

        types = [b["type"] for b in result["blocks"]]
        # Should be: header, section, context, divider
        assert types == ["header", "section", "context", "divider"]

    def test_with_data_block_order(self):
        svc = self._make_service()
        data = {"k": "v"}
        result = svc._build_payload("T", "M", "medium", data)

        types = [b["type"] for b in result["blocks"]]
        # Should be: header, section(msg), section(fields), context, divider
        assert types == ["header", "section", "section", "context", "divider"]

    def test_empty_alert_data(self):
        svc = self._make_service()
        result = svc._build_payload("T", "M", "medium", {})
        # Empty dict is truthy in Python... wait, no it's falsy
        types = [b["type"] for b in result["blocks"]]
        assert types == ["header", "section", "context", "divider"]
