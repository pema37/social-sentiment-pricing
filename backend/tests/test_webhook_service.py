"""
Tests for services/notification/webhook_service.py

WebhookService — WebhookResult dataclass, send_alert with retries,
HMAC-SHA256 signing, payload/header builders, URL masking.
"""

import hashlib
import hmac
import json
import time
from dataclasses import fields
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.notification.webhook_service import WebhookResult, WebhookService

SVC_MOD = "services.notification.webhook_service"


# ──────────────────────────────────────────────
# WebhookResult dataclass
# ──────────────────────────────────────────────
class TestWebhookResult:
    def test_success(self):
        r = WebhookResult(success=True, status_code=200)
        assert r.success is True
        assert r.status_code == 200
        assert r.error is None

    def test_failure(self):
        r = WebhookResult(success=False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"

    def test_defaults(self):
        r = WebhookResult(success=True)
        assert r.status_code is None
        assert r.error is None

    def test_field_count(self):
        assert len(fields(WebhookResult)) == 3

    def test_all_fields(self):
        r = WebhookResult(success=False, status_code=500, error="Server error")
        assert r.success is False
        assert r.status_code == 500
        assert r.error == "Server error"


# ──────────────────────────────────────────────
# WebhookService — init
# ──────────────────────────────────────────────
class TestWebhookServiceInit:
    def test_timeout_default(self):
        svc = WebhookService()
        assert svc.timeout == 10.0

    def test_max_retries_default(self):
        svc = WebhookService()
        assert svc.max_retries == 2


# ──────────────────────────────────────────────
# WebhookService — _build_payload
# ──────────────────────────────────────────────
class TestBuildPayload:
    def test_returns_dict(self):
        svc = WebhookService()
        result = svc._build_payload(
            alert_id="a-1",
            alert_title="T",
            alert_message="M",
            alert_type="sentiment_drop",
            severity="high",
            alert_data=None,
        )
        assert isinstance(result, dict)

    def test_event_field(self):
        svc = WebhookService()
        result = svc._build_payload(
            alert_id=None,
            alert_title="T",
            alert_message="M",
            alert_type=None,
            severity="medium",
            alert_data=None,
        )
        assert result["event"] == "alert"

    def test_source_field(self):
        svc = WebhookService()
        result = svc._build_payload(
            alert_id=None,
            alert_title="T",
            alert_message="M",
            alert_type=None,
            severity="medium",
            alert_data=None,
        )
        assert result["source"] == "social-sentiment-pricing"

    def test_timestamp_is_int(self):
        svc = WebhookService()
        result = svc._build_payload(
            alert_id=None,
            alert_title="T",
            alert_message="M",
            alert_type=None,
            severity="medium",
            alert_data=None,
        )
        assert isinstance(result["timestamp"], int)

    def test_alert_fields(self):
        svc = WebhookService()
        result = svc._build_payload(
            alert_id="a-1",
            alert_title="My Alert",
            alert_message="Something happened",
            alert_type="price_change",
            severity="critical",
            alert_data=None,
        )
        alert = result["alert"]
        assert alert["id"] == "a-1"
        assert alert["title"] == "My Alert"
        assert alert["message"] == "Something happened"
        assert alert["type"] == "price_change"
        assert alert["severity"] == "critical"

    def test_none_alert_id(self):
        svc = WebhookService()
        result = svc._build_payload(
            alert_id=None,
            alert_title="T",
            alert_message="M",
            alert_type=None,
            severity="medium",
            alert_data=None,
        )
        assert result["alert"]["id"] is None

    def test_with_alert_data(self):
        svc = WebhookService()
        data = {"product_id": "123", "score": -0.45}
        result = svc._build_payload(
            alert_id=None,
            alert_title="T",
            alert_message="M",
            alert_type=None,
            severity="medium",
            alert_data=data,
        )
        assert result["alert"]["data"] == data

    def test_without_alert_data(self):
        svc = WebhookService()
        result = svc._build_payload(
            alert_id=None,
            alert_title="T",
            alert_message="M",
            alert_type=None,
            severity="medium",
            alert_data=None,
        )
        assert "data" not in result["alert"]

    def test_empty_alert_data(self):
        svc = WebhookService()
        result = svc._build_payload(
            alert_id=None,
            alert_title="T",
            alert_message="M",
            alert_type=None,
            severity="medium",
            alert_data={},
        )
        # Empty dict is falsy, so data should not be added
        assert "data" not in result["alert"]


# ──────────────────────────────────────────────
# WebhookService — _build_headers
# ──────────────────────────────────────────────
class TestBuildHeaders:
    def test_content_type(self):
        svc = WebhookService()
        headers = svc._build_headers({"key": "val"}, None)
        assert headers["Content-Type"] == "application/json"

    def test_user_agent(self):
        svc = WebhookService()
        headers = svc._build_headers({"key": "val"}, None)
        assert headers["User-Agent"] == "SSP-Webhook/1.0"

    def test_no_signature_without_secret(self):
        svc = WebhookService()
        headers = svc._build_headers({"key": "val"}, None)
        assert "X-SSP-Signature" not in headers
        assert "X-SSP-Timestamp" not in headers

    def test_signature_with_secret(self):
        svc = WebhookService()
        payload = {"key": "val"}
        headers = svc._build_headers(payload, "my-secret")
        assert "X-SSP-Signature" in headers
        assert headers["X-SSP-Signature"].startswith("sha256=")

    def test_timestamp_with_secret(self):
        svc = WebhookService()
        headers = svc._build_headers({"k": "v"}, "secret")
        assert "X-SSP-Timestamp" in headers
        ts = int(headers["X-SSP-Timestamp"])
        assert abs(ts - int(time.time())) <= 2

    def test_signature_is_valid_hmac(self):
        svc = WebhookService()
        payload = {"hello": "world", "num": 42}
        secret = "test-secret"
        headers = svc._build_headers(payload, secret)

        # Reproduce the HMAC
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        expected = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        actual = headers["X-SSP-Signature"].replace("sha256=", "")
        assert actual == expected

    def test_empty_secret_no_signature(self):
        svc = WebhookService()
        headers = svc._build_headers({"k": "v"}, "")
        # Empty string is falsy
        assert "X-SSP-Signature" not in headers

    def test_always_has_base_headers(self):
        svc = WebhookService()
        headers = svc._build_headers({}, "secret")
        assert "Content-Type" in headers
        assert "User-Agent" in headers


# ──────────────────────────────────────────────
# WebhookService — _mask_url
# ──────────────────────────────────────────────
class TestMaskUrl:
    def test_short_url_unchanged(self):
        svc = WebhookService()
        assert svc._mask_url("https://short.com") == "https://short.com"

    def test_long_url_masked(self):
        svc = WebhookService()
        url = "https://myserver.com/very/long/webhook/path/secret123"
        masked = svc._mask_url(url)
        assert "..." in masked
        assert len(masked) < len(url)

    def test_exactly_30_chars_not_masked(self):
        svc = WebhookService()
        url = "a" * 30
        assert svc._mask_url(url) == url

    def test_31_chars_masked(self):
        svc = WebhookService()
        url = "a" * 31
        masked = svc._mask_url(url)
        assert "..." in masked

    def test_mask_preserves_start_and_end(self):
        svc = WebhookService()
        url = "https://example.com/webhooks/secret-token-12345"
        masked = svc._mask_url(url)
        # url[:20] + "..." + url[-10:]
        assert masked.startswith(url[:20])
        assert masked.endswith(url[-10:])


# ──────────────────────────────────────────────
# WebhookService — _sleep
# ──────────────────────────────────────────────
class TestSleep:
    @pytest.mark.asyncio
    async def test_calls_asyncio_sleep(self):
        svc = WebhookService()
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await svc._sleep(5.0)
            mock_sleep.assert_called_once_with(5.0)


# ──────────────────────────────────────────────
# WebhookService — send_alert
# ──────────────────────────────────────────────
class TestSendAlert:
    @pytest.mark.asyncio
    async def test_no_url_returns_failure(self):
        svc = WebhookService()
        result = await svc.send_alert(
            webhook_url="",
            alert_title="T",
            alert_message="M",
        )
        assert result.success is False
        assert "No webhook URL" in result.error

    @pytest.mark.asyncio
    async def test_none_url_returns_failure(self):
        svc = WebhookService()
        result = await svc.send_alert(
            webhook_url=None,
            alert_title="T",
            alert_message="M",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_success_200(self):
        svc = WebhookService()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc.send_alert(
                webhook_url="https://test.com/hook",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is True
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_success_202(self):
        svc = WebhookService()
        mock_response = MagicMock()
        mock_response.status_code = 202

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc.send_alert(
                webhook_url="https://test.com",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is True
        assert result.status_code == 202

    @pytest.mark.asyncio
    async def test_success_204(self):
        svc = WebhookService()
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc.send_alert(
                webhook_url="https://test.com",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_non_success_status_retries_and_fails(self):
        svc = WebhookService()
        svc.max_retries = 1

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with patch.object(svc, "_sleep", new_callable=AsyncMock):
                result = await svc.send_alert(
                    webhook_url="https://test.com",
                    alert_title="T",
                    alert_message="M",
                )

        assert result.success is False
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_timeout_retries_and_fails(self):
        svc = WebhookService()
        svc.max_retries = 1

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with patch.object(svc, "_sleep", new_callable=AsyncMock):
                result = await svc.send_alert(
                    webhook_url="https://test.com",
                    alert_title="T",
                    alert_message="M",
                )

        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_connect_error_retries(self):
        svc = WebhookService()
        svc.max_retries = 1

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with patch.object(svc, "_sleep", new_callable=AsyncMock):
                result = await svc.send_alert(
                    webhook_url="https://test.com",
                    alert_title="T",
                    alert_message="M",
                )

        assert result.success is False
        assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_generic_exception_retries(self):
        svc = WebhookService()
        svc.max_retries = 0

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("unexpected")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc.send_alert(
                webhook_url="https://test.com",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is False
        assert "unexpected" in result.error

    @pytest.mark.asyncio
    async def test_retries_correct_count(self):
        svc = WebhookService()
        svc.max_retries = 2

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "error"

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with patch.object(svc, "_sleep", new_callable=AsyncMock) as mock_sleep:
                await svc.send_alert(
                    webhook_url="https://test.com",
                    alert_title="T",
                    alert_message="M",
                )

            # 3 attempts total (initial + 2 retries), 2 sleeps
            assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        svc = WebhookService()
        svc.max_retries = 2

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "error"

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with patch.object(svc, "_sleep", new_callable=AsyncMock) as mock_sleep:
                await svc.send_alert(
                    webhook_url="https://test.com",
                    alert_title="T",
                    alert_message="M",
                )

            delays = [c[0][0] for c in mock_sleep.call_args_list]
            assert delays == [1, 2]  # 2^0=1, 2^1=2

    @pytest.mark.asyncio
    async def test_success_on_retry(self):
        svc = WebhookService()
        svc.max_retries = 2

        fail_response = MagicMock()
        fail_response.status_code = 500
        fail_response.text = "error"

        ok_response = MagicMock()
        ok_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [fail_response, ok_response]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with patch.object(svc, "_sleep", new_callable=AsyncMock):
                result = await svc.send_alert(
                    webhook_url="https://test.com",
                    alert_title="T",
                    alert_message="M",
                )

        assert result.success is True
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_sends_json_payload(self):
        svc = WebhookService()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await svc.send_alert(
                webhook_url="https://test.com",
                alert_title="T",
                alert_message="M",
            )

            call_kwargs = mock_client.post.call_args[1]
            assert "json" in call_kwargs
            assert call_kwargs["json"]["event"] == "alert"

    @pytest.mark.asyncio
    async def test_sends_headers(self):
        svc = WebhookService()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await svc.send_alert(
                webhook_url="https://test.com",
                alert_title="T",
                alert_message="M",
                webhook_secret="my-secret",
            )

            call_kwargs = mock_client.post.call_args[1]
            headers = call_kwargs["headers"]
            assert "X-SSP-Signature" in headers

    @pytest.mark.asyncio
    async def test_zero_retries(self):
        svc = WebhookService()
        svc.max_retries = 0

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "fail"

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc.send_alert(
                webhook_url="https://test.com",
                alert_title="T",
                alert_message="M",
            )

        assert result.success is False
        # Only 1 attempt with 0 retries
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_default_severity(self):
        svc = WebhookService()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(f"{SVC_MOD}.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await svc.send_alert(
                webhook_url="https://test.com",
                alert_title="T",
                alert_message="M",
            )

            payload = mock_client.post.call_args[1]["json"]
            assert payload["alert"]["severity"] == "medium"
