"""
Tests for services/integration/circuit_breaker.py

Circuit breaker pattern — state machine, async context manager, registry.
Pure async logic, no DB dependencies.
"""

import asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from services.integration.circuit_breaker import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitBreaker,
    CircuitBreakerRegistry,
    circuit_breaker_registry,
)


# ──────────────────────────────────────────────
# CircuitState enum
# ──────────────────────────────────────────────
class TestCircuitState:

    def test_closed_value(self):
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_has_three_members(self):
        assert len(CircuitState) == 3

    def test_members_are_unique(self):
        values = [s.value for s in CircuitState]
        assert len(values) == len(set(values))


# ──────────────────────────────────────────────
# CircuitBreakerConfig
# ──────────────────────────────────────────────
class TestCircuitBreakerConfig:

    def test_defaults(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.success_threshold == 2
        assert cfg.timeout == 30.0
        assert cfg.excluded_exceptions == ()

    def test_custom_values(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=3,
            timeout=60.0,
            excluded_exceptions=(ValueError, TypeError),
        )
        assert cfg.failure_threshold == 10
        assert cfg.success_threshold == 3
        assert cfg.timeout == 60.0
        assert cfg.excluded_exceptions == (ValueError, TypeError)

    def test_partial_override(self):
        cfg = CircuitBreakerConfig(failure_threshold=1)
        assert cfg.failure_threshold == 1
        assert cfg.success_threshold == 2  # default

    def test_zero_threshold(self):
        cfg = CircuitBreakerConfig(failure_threshold=0)
        assert cfg.failure_threshold == 0

    def test_float_timeout(self):
        cfg = CircuitBreakerConfig(timeout=0.5)
        assert cfg.timeout == 0.5


# ──────────────────────────────────────────────
# CircuitOpenError
# ──────────────────────────────────────────────
class TestCircuitOpenError:

    def test_is_exception(self):
        assert issubclass(CircuitOpenError, Exception)

    def test_message(self):
        err = CircuitOpenError("test message")
        assert str(err) == "test message"

    def test_catchable_as_exception(self):
        with pytest.raises(Exception):
            raise CircuitOpenError("fail")

    def test_catchable_specifically(self):
        with pytest.raises(CircuitOpenError):
            raise CircuitOpenError("fail")


# ──────────────────────────────────────────────
# CircuitBreaker — init and properties
# ──────────────────────────────────────────────
class TestCircuitBreakerInit:

    def test_name_stored(self):
        cb = CircuitBreaker("test-store")
        assert cb.name == "test-store"

    def test_default_config(self):
        cb = CircuitBreaker("test")
        assert isinstance(cb.config, CircuitBreakerConfig)
        assert cb.config.failure_threshold == 5

    def test_custom_config(self):
        cfg = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=cfg)
        assert cb.config.failure_threshold == 3

    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_is_closed_true_initially(self):
        cb = CircuitBreaker("test")
        assert cb.is_closed is True

    def test_is_open_false_initially(self):
        cb = CircuitBreaker("test")
        assert cb.is_open is False

    def test_initial_failure_count_zero(self):
        cb = CircuitBreaker("test")
        assert cb._failure_count == 0

    def test_initial_success_count_zero(self):
        cb = CircuitBreaker("test")
        assert cb._success_count == 0

    def test_initial_last_failure_none(self):
        cb = CircuitBreaker("test")
        assert cb._last_failure_time is None

    def test_has_lock(self):
        cb = CircuitBreaker("test")
        assert isinstance(cb._lock, asyncio.Lock)


# ──────────────────────────────────────────────
# CircuitBreaker — state transitions
# ──────────────────────────────────────────────
class TestCircuitBreakerStateTransitions:

    @pytest.mark.asyncio
    async def test_closed_to_open_after_threshold(self):
        cfg = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=cfg)

        for _ in range(3):
            await cb.record_failure()

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_stays_closed_below_threshold(self):
        cfg = CircuitBreakerConfig(failure_threshold=5)
        cb = CircuitBreaker("test", config=cfg)

        for _ in range(4):
            await cb.record_failure()

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self):
        cfg = CircuitBreakerConfig(failure_threshold=1, timeout=0.0)
        cb = CircuitBreaker("test", config=cfg)

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Simulate time passed by backdating last_failure_time
        cb._last_failure_time = datetime.now(UTC) - timedelta(seconds=60)
        await cb._check_state()

        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_open_stays_open_before_timeout(self):
        cfg = CircuitBreakerConfig(failure_threshold=1, timeout=3600.0)
        cb = CircuitBreaker("test", config=cfg)

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await cb._check_state()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed_after_success_threshold(self):
        cfg = CircuitBreakerConfig(success_threshold=2)
        cb = CircuitBreaker("test", config=cfg)
        cb._state = CircuitState.HALF_OPEN

        await cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN  # 1 < 2

        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker("test")
        cb._state = CircuitState.HALF_OPEN

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_resets_success_count(self):
        cfg = CircuitBreakerConfig(failure_threshold=1, timeout=0.0)
        cb = CircuitBreaker("test", config=cfg)

        await cb.record_failure()
        cb._last_failure_time = datetime.now(UTC) - timedelta(seconds=60)
        await cb._check_state()

        assert cb.state == CircuitState.HALF_OPEN
        assert cb._success_count == 0


# ──────────────────────────────────────────────
# CircuitBreaker — record_success
# ──────────────────────────────────────────────
class TestRecordSuccess:

    @pytest.mark.asyncio
    async def test_closed_resets_failure_count(self):
        cb = CircuitBreaker("test")
        cb._failure_count = 3

        await cb.record_success()
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_increments_success(self):
        cb = CircuitBreaker("test")
        cb._state = CircuitState.HALF_OPEN

        await cb.record_success()
        assert cb._success_count == 1

    @pytest.mark.asyncio
    async def test_open_state_no_change(self):
        """Success while OPEN has no effect (shouldn't happen normally)"""
        cb = CircuitBreaker("test")
        cb._state = CircuitState.OPEN
        cb._failure_count = 5

        await cb.record_success()
        assert cb._failure_count == 5
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed_resets_failure_count(self):
        cfg = CircuitBreakerConfig(success_threshold=1)
        cb = CircuitBreaker("test", config=cfg)
        cb._state = CircuitState.HALF_OPEN
        cb._failure_count = 10

        await cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0


# ──────────────────────────────────────────────
# CircuitBreaker — record_failure
# ──────────────────────────────────────────────
class TestRecordFailure:

    @pytest.mark.asyncio
    async def test_increments_failure_count(self):
        cb = CircuitBreaker("test")
        await cb.record_failure()
        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_sets_last_failure_time(self):
        cb = CircuitBreaker("test")
        assert cb._last_failure_time is None

        await cb.record_failure()
        assert cb._last_failure_time is not None
        assert isinstance(cb._last_failure_time, datetime)

    @pytest.mark.asyncio
    async def test_excluded_exception_ignored(self):
        cfg = CircuitBreakerConfig(excluded_exceptions=(ValueError,))
        cb = CircuitBreaker("test", config=cfg)

        await cb.record_failure(exception=ValueError("skip"))
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_non_excluded_exception_counted(self):
        cfg = CircuitBreakerConfig(excluded_exceptions=(ValueError,))
        cb = CircuitBreaker("test", config=cfg)

        await cb.record_failure(exception=TypeError("count this"))
        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_none_exception_counted(self):
        cb = CircuitBreaker("test")
        await cb.record_failure(exception=None)
        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_no_exception_arg_counted(self):
        cb = CircuitBreaker("test")
        await cb.record_failure()
        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_half_open_immediately_opens(self):
        cb = CircuitBreaker("test")
        cb._state = CircuitState.HALF_OPEN

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_closed_opens_at_threshold(self):
        cfg = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test", config=cfg)

        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_excluded_exception_subclass(self):
        """Subclass of excluded exception should also be excluded"""
        cfg = CircuitBreakerConfig(excluded_exceptions=(OSError,))
        cb = CircuitBreaker("test", config=cfg)

        await cb.record_failure(exception=ConnectionError("subclass of OSError"))
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_failure_updates_time_on_each_call(self):
        cb = CircuitBreaker("test")

        await cb.record_failure()
        t1 = cb._last_failure_time

        await cb.record_failure()
        t2 = cb._last_failure_time

        assert t2 >= t1


# ──────────────────────────────────────────────
# CircuitBreaker — async context manager
# ──────────────────────────────────────────────
class TestAsyncContextManager:

    @pytest.mark.asyncio
    async def test_success_path(self):
        cb = CircuitBreaker("test")

        async with cb:
            pass  # success

        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_failure_path(self):
        cfg = CircuitBreakerConfig(failure_threshold=10)
        cb = CircuitBreaker("test", config=cfg)

        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("boom")

        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_raises_circuit_open_error_when_open(self):
        cb = CircuitBreaker("test")
        cb._state = CircuitState.OPEN
        cb._last_failure_time = datetime.now(UTC)  # recent, won't transition

        with pytest.raises(CircuitOpenError) as exc_info:
            async with cb:
                pass

        assert cb.name in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exception_not_swallowed(self):
        """__aexit__ returns False, so exception propagates"""
        cfg = CircuitBreakerConfig(failure_threshold=10)
        cb = CircuitBreaker("test", config=cfg)

        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("propagate me")

    @pytest.mark.asyncio
    async def test_records_success_on_clean_exit(self):
        cb = CircuitBreaker("test")
        cb._failure_count = 3

        async with cb:
            pass

        assert cb._failure_count == 0  # reset by record_success

    @pytest.mark.asyncio
    async def test_transitions_half_open_on_entry(self):
        cfg = CircuitBreakerConfig(failure_threshold=1, timeout=0.0)
        cb = CircuitBreaker("test", config=cfg)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = datetime.now(UTC) - timedelta(seconds=60)

        async with cb:
            assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_full_lifecycle_closed_open_halfopen_closed(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1,
            timeout=0.0,
        )
        cb = CircuitBreaker("test", config=cfg)

        # 1. Start CLOSED
        assert cb.state == CircuitState.CLOSED

        # 2. Fail twice → OPEN
        for _ in range(2):
            with pytest.raises(RuntimeError):
                async with cb:
                    raise RuntimeError("fail")

        assert cb.state == CircuitState.OPEN

        # 3. Backdate to trigger timeout → HALF_OPEN on next entry
        cb._last_failure_time = datetime.now(UTC) - timedelta(seconds=60)

        # 4. Succeed → CLOSED
        async with cb:
            assert cb.state == CircuitState.HALF_OPEN

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_excluded_exception_in_context(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=1,
            excluded_exceptions=(ValueError,),
        )
        cb = CircuitBreaker("test", config=cfg)

        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("excluded")

        # Excluded exception shouldn't count
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED


# ──────────────────────────────────────────────
# CircuitBreaker — _check_state
# ──────────────────────────────────────────────
class TestCheckState:

    @pytest.mark.asyncio
    async def test_closed_no_transition(self):
        cb = CircuitBreaker("test")
        await cb._check_state()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_no_transition(self):
        cb = CircuitBreaker("test")
        cb._state = CircuitState.HALF_OPEN
        await cb._check_state()
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_open_no_last_failure(self):
        cb = CircuitBreaker("test")
        cb._state = CircuitState.OPEN
        cb._last_failure_time = None
        await cb._check_state()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_transitions_after_timeout(self):
        cfg = CircuitBreakerConfig(timeout=1.0)
        cb = CircuitBreaker("test", config=cfg)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = datetime.now(UTC) - timedelta(seconds=5)

        await cb._check_state()
        assert cb.state == CircuitState.HALF_OPEN
        assert cb._success_count == 0

    @pytest.mark.asyncio
    async def test_open_stays_before_timeout(self):
        cfg = CircuitBreakerConfig(timeout=3600.0)
        cb = CircuitBreaker("test", config=cfg)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = datetime.now(UTC)

        await cb._check_state()
        assert cb.state == CircuitState.OPEN


# ──────────────────────────────────────────────
# CircuitBreaker — get_status
# ──────────────────────────────────────────────
class TestGetStatus:

    def test_initial_status(self):
        cb = CircuitBreaker("my-store")
        status = cb.get_status()

        assert status["name"] == "my-store"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["success_count"] == 0
        assert status["last_failure"] is None

    @pytest.mark.asyncio
    async def test_status_after_failures(self):
        cb = CircuitBreaker("store-1")
        await cb.record_failure()
        await cb.record_failure()

        status = cb.get_status()
        assert status["failure_count"] == 2
        assert status["last_failure"] is not None

    @pytest.mark.asyncio
    async def test_status_open_state(self):
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("store-2", config=cfg)
        await cb.record_failure()

        status = cb.get_status()
        assert status["state"] == "open"

    @pytest.mark.asyncio
    async def test_status_half_open_state(self):
        cb = CircuitBreaker("store-3")
        cb._state = CircuitState.HALF_OPEN
        cb._success_count = 1

        status = cb.get_status()
        assert status["state"] == "half_open"
        assert status["success_count"] == 1

    def test_last_failure_isoformat(self):
        cb = CircuitBreaker("test")
        now = datetime(2026, 2, 9, 12, 0, 0)
        cb._last_failure_time = now

        status = cb.get_status()
        assert status["last_failure"] == "2026-02-09T12:00:00"

    def test_status_returns_dict(self):
        cb = CircuitBreaker("test")
        status = cb.get_status()
        assert isinstance(status, dict)
        assert set(status.keys()) == {
            "name", "state", "failure_count", "success_count", "last_failure"
        }


# ──────────────────────────────────────────────
# CircuitBreakerRegistry
# ──────────────────────────────────────────────
class TestCircuitBreakerRegistry:

    @pytest.mark.asyncio
    async def test_get_creates_new_breaker(self):
        reg = CircuitBreakerRegistry()
        cb = await reg.get("store-1.myshopify.com")

        assert isinstance(cb, CircuitBreaker)
        assert cb.name == "store-1.myshopify.com"

    @pytest.mark.asyncio
    async def test_get_returns_same_instance(self):
        reg = CircuitBreakerRegistry()
        cb1 = await reg.get("store-1")
        cb2 = await reg.get("store-1")

        assert cb1 is cb2

    @pytest.mark.asyncio
    async def test_different_stores_different_breakers(self):
        reg = CircuitBreakerRegistry()
        cb1 = await reg.get("store-1")
        cb2 = await reg.get("store-2")

        assert cb1 is not cb2

    @pytest.mark.asyncio
    async def test_uses_default_config(self):
        cfg = CircuitBreakerConfig(failure_threshold=10)
        reg = CircuitBreakerRegistry(default_config=cfg)
        cb = await reg.get("store-1")

        assert cb.config.failure_threshold == 10

    @pytest.mark.asyncio
    async def test_default_config_when_none(self):
        reg = CircuitBreakerRegistry()
        cb = await reg.get("store-1")

        assert cb.config.failure_threshold == 5  # default

    @pytest.mark.asyncio
    async def test_reset_removes_breaker(self):
        reg = CircuitBreakerRegistry()
        cb1 = await reg.get("store-1")
        await reg.reset("store-1")
        cb2 = await reg.get("store-1")

        assert cb1 is not cb2

    @pytest.mark.asyncio
    async def test_reset_nonexistent_no_error(self):
        reg = CircuitBreakerRegistry()
        await reg.reset("nonexistent")  # should not raise

    @pytest.mark.asyncio
    async def test_get_all_status_empty(self):
        reg = CircuitBreakerRegistry()
        result = await reg.get_all_status()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_status_multiple(self):
        reg = CircuitBreakerRegistry()
        await reg.get("store-1")
        await reg.get("store-2")

        result = await reg.get_all_status()
        assert len(result) == 2
        names = {s["name"] for s in result}
        assert names == {"store-1", "store-2"}

    @pytest.mark.asyncio
    async def test_get_all_status_returns_list_of_dicts(self):
        reg = CircuitBreakerRegistry()
        await reg.get("store-1")

        result = await reg.get_all_status()
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    @pytest.mark.asyncio
    async def test_has_lock(self):
        reg = CircuitBreakerRegistry()
        assert isinstance(reg._lock, asyncio.Lock)


# ──────────────────────────────────────────────
# Global instance
# ──────────────────────────────────────────────
class TestGlobalRegistry:

    def test_global_instance_exists(self):
        assert circuit_breaker_registry is not None

    def test_global_is_registry(self):
        assert isinstance(circuit_breaker_registry, CircuitBreakerRegistry)


# ──────────────────────────────────────────────
# Edge cases & concurrency
# ──────────────────────────────────────────────
class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_rapid_failures_exact_threshold(self):
        cfg = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=cfg)

        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_success_between_failures_resets(self):
        cfg = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=cfg)

        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()  # resets count
        await cb.record_failure()
        await cb.record_failure()

        assert cb.state == CircuitState.CLOSED  # never hit 3 consecutive

    @pytest.mark.asyncio
    async def test_half_open_failure_then_retry(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=1,
            timeout=0.0,
        )
        cb = CircuitBreaker("test", config=cfg)

        # CLOSED → OPEN
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # OPEN → HALF_OPEN
        cb._last_failure_time = datetime.now(UTC) - timedelta(seconds=60)
        await cb._check_state()
        assert cb.state == CircuitState.HALF_OPEN

        # HALF_OPEN → OPEN (failure)
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # OPEN → HALF_OPEN again
        cb._last_failure_time = datetime.now(UTC) - timedelta(seconds=60)
        await cb._check_state()
        assert cb.state == CircuitState.HALF_OPEN

        # HALF_OPEN → CLOSED (success)
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_zero_failure_threshold_opens_immediately(self):
        """With failure_threshold=0, first failure should open (0 >= 0 is True on second failure at count=1)"""
        cfg = CircuitBreakerConfig(failure_threshold=0)
        cb = CircuitBreaker("test", config=cfg)

        # failure_count becomes 1, which is >= 0
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_open_error_message_format(self):
        cfg = CircuitBreakerConfig(timeout=45.0)
        cb = CircuitBreaker("my-shop", config=cfg)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = datetime.now(UTC)

        with pytest.raises(CircuitOpenError) as exc_info:
            async with cb:
                pass

        assert "my-shop" in str(exc_info.value)
        assert "OPEN" in str(exc_info.value)
        assert "45.0" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multiple_breakers_independent(self):
        cfg = CircuitBreakerConfig(failure_threshold=2)
        cb1 = CircuitBreaker("store-1", config=cfg)
        cb2 = CircuitBreaker("store-2", config=cfg)

        await cb1.record_failure()
        await cb1.record_failure()

        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_threshold_one(self):
        cfg = CircuitBreakerConfig(success_threshold=1)
        cb = CircuitBreaker("test", config=cfg)
        cb._state = CircuitState.HALF_OPEN

        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_high_failure_threshold(self):
        cfg = CircuitBreakerConfig(failure_threshold=100)
        cb = CircuitBreaker("test", config=cfg)

        for _ in range(99):
            await cb.record_failure()

        assert cb.state == CircuitState.CLOSED

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        