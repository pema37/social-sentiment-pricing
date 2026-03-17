"""
Tests for services/integration/retry.py

Retry logic with exponential backoff — pure functions, decorator, executor.
"""

import os

# Force fresh import — other test files replace parent packages with MagicMock
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _pkg, _subdir in [
    ("services", "services"),
    ("services.integration", "services/integration"),
]:
    _existing = sys.modules.get(_pkg)
    if _existing is None or not hasattr(_existing, "__path__"):
        _mod = ModuleType(_pkg)
        _mod.__path__ = [os.path.join(_backend_dir, _subdir)]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod
sys.modules.pop("services.integration.retry", None)

from services.integration.retry import (
    DEFAULT_RETRY_CONFIG,
    RetryConfig,
    calculate_backoff_delay,
    execute_with_retry,
    should_retry,
    with_retry,
)


# ──────────────────────────────────────────────
# RetryConfig
# ──────────────────────────────────────────────
class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 60.0
        assert cfg.exponential_base == 2.0
        assert cfg.jitter == 0.1

    def test_default_retry_status_codes(self):
        cfg = RetryConfig()
        assert 408 in cfg.retry_status_codes
        assert 429 in cfg.retry_status_codes
        assert 500 in cfg.retry_status_codes
        assert 502 in cfg.retry_status_codes
        assert 503 in cfg.retry_status_codes
        assert 504 in cfg.retry_status_codes
        assert len(cfg.retry_status_codes) == 6

    def test_custom_values(self):
        cfg = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=0.2,
            retry_status_codes=[429, 503],
        )
        assert cfg.max_retries == 5
        assert cfg.base_delay == 2.0
        assert cfg.max_delay == 120.0
        assert cfg.exponential_base == 3.0
        assert cfg.jitter == 0.2
        assert cfg.retry_status_codes == [429, 503]

    def test_partial_override(self):
        cfg = RetryConfig(max_retries=10)
        assert cfg.max_retries == 10
        assert cfg.base_delay == 1.0  # default

    def test_zero_retries(self):
        cfg = RetryConfig(max_retries=0)
        assert cfg.max_retries == 0

    def test_each_instance_gets_own_status_codes(self):
        cfg1 = RetryConfig()
        cfg2 = RetryConfig()
        cfg1.retry_status_codes.append(999)
        assert 999 not in cfg2.retry_status_codes


# ──────────────────────────────────────────────
# DEFAULT_RETRY_CONFIG
# ──────────────────────────────────────────────
class TestDefaultRetryConfig:
    def test_exists(self):
        assert DEFAULT_RETRY_CONFIG is not None

    def test_is_retry_config(self):
        assert isinstance(DEFAULT_RETRY_CONFIG, RetryConfig)

    def test_has_standard_defaults(self):
        assert DEFAULT_RETRY_CONFIG.max_retries == 3


# ──────────────────────────────────────────────
# calculate_backoff_delay
# ──────────────────────────────────────────────
class TestCalculateBackoffDelay:
    def test_first_attempt_base_delay(self):
        cfg = RetryConfig(base_delay=1.0, jitter=0.0)
        delay = calculate_backoff_delay(0, cfg)
        assert delay == 1.0

    def test_exponential_growth(self):
        cfg = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.0)
        assert calculate_backoff_delay(0, cfg) == 1.0
        assert calculate_backoff_delay(1, cfg) == 2.0
        assert calculate_backoff_delay(2, cfg) == 4.0
        assert calculate_backoff_delay(3, cfg) == 8.0

    def test_custom_base(self):
        cfg = RetryConfig(base_delay=0.5, exponential_base=3.0, jitter=0.0)
        assert calculate_backoff_delay(0, cfg) == 0.5
        assert calculate_backoff_delay(1, cfg) == 1.5  # 0.5 * 3
        assert calculate_backoff_delay(2, cfg) == 4.5  # 0.5 * 9

    def test_caps_at_max_delay(self):
        cfg = RetryConfig(base_delay=1.0, max_delay=10.0, jitter=0.0)
        delay = calculate_backoff_delay(20, cfg)  # would be 1 * 2^20 = huge
        assert delay == 10.0

    def test_rate_limited_longer_delay(self):
        cfg = RetryConfig(base_delay=1.0, jitter=0.0, max_delay=1000.0)
        normal = calculate_backoff_delay(0, cfg, is_rate_limited=False)
        limited = calculate_backoff_delay(0, cfg, is_rate_limited=True)
        assert limited > normal

    def test_rate_limited_minimum_5s(self):
        cfg = RetryConfig(base_delay=0.1, jitter=0.0, max_delay=1000.0)
        delay = calculate_backoff_delay(0, cfg, is_rate_limited=True)
        assert delay >= 10.0  # max(0.1, 5.0) * 2 = 10.0

    def test_rate_limited_doubles(self):
        cfg = RetryConfig(base_delay=10.0, jitter=0.0, max_delay=1000.0)
        delay = calculate_backoff_delay(0, cfg, is_rate_limited=True)
        assert delay == 20.0  # max(10, 5) * 2

    def test_jitter_adds_randomness(self):
        cfg = RetryConfig(base_delay=10.0, jitter=0.1)
        delays = set()
        for _ in range(20):
            delays.add(calculate_backoff_delay(0, cfg))
        # With 10% jitter on 10.0, should get values in [9.0, 11.0]
        assert len(delays) > 1  # not all identical

    def test_jitter_range(self):
        cfg = RetryConfig(base_delay=10.0, jitter=0.1, max_delay=100.0)
        for _ in range(50):
            delay = calculate_backoff_delay(0, cfg)
            assert 9.0 <= delay <= 11.0

    def test_zero_jitter(self):
        cfg = RetryConfig(base_delay=1.0, jitter=0.0)
        delay1 = calculate_backoff_delay(0, cfg)
        delay2 = calculate_backoff_delay(0, cfg)
        assert delay1 == delay2 == 1.0

    def test_attempt_zero(self):
        cfg = RetryConfig(base_delay=5.0, jitter=0.0)
        assert calculate_backoff_delay(0, cfg) == 5.0  # 5 * 2^0 = 5

    def test_max_delay_with_rate_limit(self):
        cfg = RetryConfig(base_delay=1.0, max_delay=8.0, jitter=0.0)
        delay = calculate_backoff_delay(5, cfg, is_rate_limited=True)
        assert delay == 8.0  # capped


# ──────────────────────────────────────────────
# should_retry
# ──────────────────────────────────────────────
class TestShouldRetry:
    def test_exceeds_max_retries(self):
        cfg = RetryConfig(max_retries=3)
        assert should_retry(None, 500, 3, cfg) is False

    def test_at_max_retries(self):
        cfg = RetryConfig(max_retries=3)
        assert should_retry(None, 500, 3, cfg) is False

    def test_below_max_retries_with_retryable_code(self):
        cfg = RetryConfig(max_retries=3)
        assert should_retry(None, 500, 2, cfg) is True

    def test_connect_error_retries(self):
        cfg = RetryConfig(max_retries=3)
        exc = httpx.ConnectError("connection failed")
        assert should_retry(exc, None, 0, cfg) is True

    def test_timeout_exception_retries(self):
        cfg = RetryConfig(max_retries=3)
        exc = httpx.ReadTimeout("read timeout")
        assert should_retry(exc, None, 0, cfg) is True

    def test_retryable_status_codes(self):
        cfg = RetryConfig()
        for code in [408, 429, 500, 502, 503, 504]:
            assert should_retry(None, code, 0, cfg) is True, f"Code {code} should retry"

    def test_non_retryable_status_code(self):
        cfg = RetryConfig()
        assert should_retry(None, 400, 0, cfg) is False
        assert should_retry(None, 401, 0, cfg) is False
        assert should_retry(None, 403, 0, cfg) is False
        assert should_retry(None, 404, 0, cfg) is False
        assert should_retry(None, 422, 0, cfg) is False

    def test_no_exception_no_status(self):
        cfg = RetryConfig()
        assert should_retry(None, None, 0, cfg) is False

    def test_non_network_exception(self):
        cfg = RetryConfig()
        assert should_retry(ValueError("nope"), None, 0, cfg) is False

    def test_zero_max_retries(self):
        cfg = RetryConfig(max_retries=0)
        assert should_retry(None, 500, 0, cfg) is False

    def test_custom_retry_codes(self):
        cfg = RetryConfig(retry_status_codes=[418])
        assert should_retry(None, 418, 0, cfg) is True
        assert should_retry(None, 500, 0, cfg) is False

    def test_connect_error_at_max(self):
        cfg = RetryConfig(max_retries=2)
        exc = httpx.ConnectError("fail")
        assert should_retry(exc, None, 2, cfg) is False

    def test_status_code_none_returns_false(self):
        cfg = RetryConfig()
        assert should_retry(None, None, 0, cfg) is False

    def test_attempt_zero_with_retryable(self):
        cfg = RetryConfig(max_retries=1)
        assert should_retry(None, 503, 0, cfg) is True


# ──────────────────────────────────────────────
# execute_with_retry
# ──────────────────────────────────────────────
class TestExecuteWithRetry:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        func = AsyncMock(return_value="ok")
        result = await execute_with_retry(func)
        assert result == "ok"
        func.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self):
        func = AsyncMock(return_value="ok")
        await execute_with_retry(func, "a", "b", key="val")
        func.assert_called_once_with("a", "b", key="val")

    @pytest.mark.asyncio
    async def test_uses_default_config_when_none(self):
        func = AsyncMock(return_value="ok")
        result = await execute_with_retry(func, config=None)
        assert result == "ok"

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_on_retryable_status(self, mock_sleep):
        response = MagicMock()
        response.status_code = 503
        exc = httpx.HTTPStatusError("fail", request=MagicMock(), response=response)

        func = AsyncMock(side_effect=[exc, "ok"])
        cfg = RetryConfig(max_retries=3, jitter=0.0, base_delay=0.01)

        result = await execute_with_retry(func, config=cfg)
        assert result == "ok"
        assert func.call_count == 2
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_on_connect_error(self, mock_sleep):
        exc = httpx.ConnectError("connection failed")
        func = AsyncMock(side_effect=[exc, "ok"])
        cfg = RetryConfig(max_retries=3, jitter=0.0, base_delay=0.01)

        result = await execute_with_retry(func, config=cfg)
        assert result == "ok"
        assert func.call_count == 2

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_on_timeout(self, mock_sleep):
        exc = httpx.ReadTimeout("timeout")
        func = AsyncMock(side_effect=[exc, "ok"])
        cfg = RetryConfig(max_retries=3, jitter=0.0, base_delay=0.01)

        result = await execute_with_retry(func, config=cfg)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_non_retryable_status_raises_immediately(self):
        response = MagicMock()
        response.status_code = 404
        exc = httpx.HTTPStatusError("not found", request=MagicMock(), response=response)

        func = AsyncMock(side_effect=exc)
        cfg = RetryConfig(max_retries=3)

        with pytest.raises(httpx.HTTPStatusError):
            await execute_with_retry(func, config=cfg)

        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_request_error_raises_immediately(self):
        exc = httpx.RequestError("bad request")
        func = AsyncMock(side_effect=exc)
        cfg = RetryConfig(max_retries=3)

        with pytest.raises(httpx.RequestError):
            await execute_with_retry(func, config=cfg)

        assert func.call_count == 1

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_exhausts_retries_then_raises(self, mock_sleep):
        response = MagicMock()
        response.status_code = 500
        exc = httpx.HTTPStatusError("fail", request=MagicMock(), response=response)

        func = AsyncMock(side_effect=exc)
        cfg = RetryConfig(max_retries=2, jitter=0.0, base_delay=0.01)

        with pytest.raises(httpx.HTTPStatusError):
            await execute_with_retry(func, config=cfg)

        assert func.call_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_exhausts_network_retries(self, mock_sleep):
        exc = httpx.ConnectError("down")
        func = AsyncMock(side_effect=exc)
        cfg = RetryConfig(max_retries=1, jitter=0.0, base_delay=0.01)

        with pytest.raises(httpx.ConnectError):
            await execute_with_retry(func, config=cfg)

        assert func.call_count == 2  # initial + 1 retry

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_rate_limited_429_uses_longer_delay(self, mock_sleep):
        response = MagicMock()
        response.status_code = 429
        exc = httpx.HTTPStatusError("rate limited", request=MagicMock(), response=response)

        func = AsyncMock(side_effect=[exc, "ok"])
        cfg = RetryConfig(max_retries=3, jitter=0.0, base_delay=1.0, max_delay=1000.0)

        await execute_with_retry(func, config=cfg)

        # Rate limited delay: max(1.0, 5.0) * 2 = 10.0
        call_args = mock_sleep.call_args[0][0]
        assert call_args == 10.0

    @pytest.mark.asyncio
    async def test_zero_retries_fails_on_first_error(self):
        response = MagicMock()
        response.status_code = 500
        exc = httpx.HTTPStatusError("fail", request=MagicMock(), response=response)

        func = AsyncMock(side_effect=exc)
        cfg = RetryConfig(max_retries=0)

        with pytest.raises(httpx.HTTPStatusError):
            await execute_with_retry(func, config=cfg)

        assert func.call_count == 1

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_operation_name_in_logging(self, mock_sleep):
        response = MagicMock()
        response.status_code = 503
        exc = httpx.HTTPStatusError("fail", request=MagicMock(), response=response)

        func = AsyncMock(side_effect=[exc, "ok"])
        cfg = RetryConfig(max_retries=3, jitter=0.0, base_delay=0.01)

        # Should not raise — just verify it works
        result = await execute_with_retry(func, config=cfg, operation_name="test_op")
        assert result == "ok"

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_multiple_retries_increasing_delay(self, mock_sleep):
        response = MagicMock()
        response.status_code = 500
        exc = httpx.HTTPStatusError("fail", request=MagicMock(), response=response)

        func = AsyncMock(side_effect=[exc, exc, "ok"])
        cfg = RetryConfig(max_retries=3, jitter=0.0, base_delay=1.0)

        result = await execute_with_retry(func, config=cfg)
        assert result == "ok"

        # Check delays are increasing
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(delays) == 2
        assert delays[0] < delays[1]  # exponential growth


# ──────────────────────────────────────────────
# with_retry decorator
# ──────────────────────────────────────────────
class TestWithRetryDecorator:
    @pytest.mark.asyncio
    async def test_wraps_function(self):
        @with_retry()
        async def my_func():
            return "hello"

        result = await my_func()
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        @with_retry()
        async def my_special_func():
            return "hi"

        assert my_special_func.__name__ == "my_special_func"

    @pytest.mark.asyncio
    async def test_passes_config(self):
        cfg = RetryConfig(max_retries=0)

        call_count = 0

        @with_retry(config=cfg)
        async def failing_func():
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 500
            raise httpx.HTTPStatusError("fail", request=MagicMock(), response=response)

        with pytest.raises(httpx.HTTPStatusError):
            await failing_func()

        assert call_count == 1  # no retries with max_retries=0

    @pytest.mark.asyncio
    async def test_passes_args_to_function(self):
        @with_retry()
        async def add(a, b):
            return a + b

        result = await add(3, 4)
        assert result == 7

    @pytest.mark.asyncio
    async def test_custom_operation_name(self):
        @with_retry(operation_name="custom_op")
        async def my_func():
            return "ok"

        result = await my_func()
        assert result == "ok"

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_through_decorator(self, mock_sleep):
        attempts = 0

        @with_retry(config=RetryConfig(max_retries=2, jitter=0.0, base_delay=0.01))
        async def flaky_func():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise httpx.ConnectError("fail")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert attempts == 2

    @pytest.mark.asyncio
    async def test_decorator_with_no_args(self):
        @with_retry()
        async def simple():
            return 42

        assert await simple() == 42

    @pytest.mark.asyncio
    async def test_decorator_with_method(self):
        class MyService:
            @with_retry()
            async def fetch(self, url):
                return f"fetched {url}"

        svc = MyService()
        result = await svc.fetch("http://example.com")
        assert result == "fetched http://example.com"


# ──────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────
class TestEdgeCases:
    def test_backoff_very_high_attempt(self):
        cfg = RetryConfig(jitter=0.0, max_delay=60.0)
        delay = calculate_backoff_delay(100, cfg)
        assert delay == 60.0  # capped

    def test_backoff_attempt_zero_no_rate_limit(self):
        cfg = RetryConfig(base_delay=1.0, jitter=0.0)
        assert calculate_backoff_delay(0, cfg, is_rate_limited=False) == 1.0

    def test_should_retry_httpx_pool_timeout(self):
        """PoolTimeout is a subclass of TimeoutException"""
        cfg = RetryConfig(max_retries=3)
        exc = httpx.PoolTimeout("pool exhausted")
        assert should_retry(exc, None, 0, cfg) is True

    def test_should_retry_write_timeout(self):
        cfg = RetryConfig(max_retries=3)
        exc = httpx.WriteTimeout("write timeout")
        assert should_retry(exc, None, 0, cfg) is True

    @pytest.mark.asyncio
    @patch("services.integration.retry.asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_then_different_exception(self, mock_sleep):
        """First call retryable, second call non-retryable"""
        response_500 = MagicMock()
        response_500.status_code = 500
        exc_500 = httpx.HTTPStatusError("fail", request=MagicMock(), response=response_500)

        response_400 = MagicMock()
        response_400.status_code = 400
        exc_400 = httpx.HTTPStatusError("bad", request=MagicMock(), response=response_400)

        func = AsyncMock(side_effect=[exc_500, exc_400])
        cfg = RetryConfig(max_retries=3, jitter=0.0, base_delay=0.01)

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await execute_with_retry(func, config=cfg)

        assert exc_info.value.response.status_code == 400
        assert func.call_count == 2

    def test_retry_config_independent_lists(self):
        """Each RetryConfig instance should have its own list"""
        cfg1 = RetryConfig()
        cfg2 = RetryConfig()
        cfg1.retry_status_codes.append(418)
        assert 418 not in cfg2.retry_status_codes

    @pytest.mark.asyncio
    async def test_execute_returns_correct_type(self):
        func = AsyncMock(return_value={"key": "value"})
        result = await execute_with_retry(func)
        assert result == {"key": "value"}
