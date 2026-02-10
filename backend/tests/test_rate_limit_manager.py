"""
Tests for services/rate_limit_manager.py

CircuitState enum, CircuitBreaker dataclass, RateLimitManager singleton,
module-level convenience functions.
"""

import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED = ["core.logging"]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

_log_mod = MagicMock()
_log_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["core.logging"] = _log_mod

from services.rate_limit_manager import (
    CircuitState,
    CircuitBreaker,
    RateLimitManager,
    get_rate_limit_manager,
    is_api_available,
    record_api_success,
    record_api_rate_limit,
    record_api_failure,
)

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

SVC_MOD = "services.rate_limit_manager"


# ──────────────────────────────────────────────
# CircuitState enum
# ──────────────────────────────────────────────
class TestCircuitState:

    def test_closed(self):
        assert CircuitState.CLOSED.value == "closed"

    def test_open(self):
        assert CircuitState.OPEN.value == "open"

    def test_half_open(self):
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_count(self):
        assert len(CircuitState) == 3


# ──────────────────────────────────────────────
# CircuitBreaker — init defaults
# ──────────────────────────────────────────────
class TestCircuitBreakerDefaults:

    def test_name(self):
        cb = CircuitBreaker(name="openai")
        assert cb.name == "openai"

    def test_default_state_closed(self):
        cb = CircuitBreaker(name="x")
        assert cb.state == CircuitState.CLOSED

    def test_default_opened_at_none(self):
        cb = CircuitBreaker(name="x")
        assert cb.opened_at is None

    def test_default_cooldown(self):
        cb = CircuitBreaker(name="x")
        assert cb.cooldown_seconds == 60

    def test_default_failure_count(self):
        cb = CircuitBreaker(name="x")
        assert cb.failure_count == 0

    def test_default_failure_threshold(self):
        cb = CircuitBreaker(name="x")
        assert cb.failure_threshold == 2

    def test_default_last_failure_message(self):
        cb = CircuitBreaker(name="x")
        assert cb.last_failure_message == ""


# ──────────────────────────────────────────────
# CircuitBreaker.is_available
# ──────────────────────────────────────────────
class TestIsAvailable:

    def test_closed_is_available(self):
        cb = CircuitBreaker(name="x")
        assert cb.is_available() is True

    def test_open_not_available(self):
        cb = CircuitBreaker(name="x")
        cb.state = CircuitState.OPEN
        cb.opened_at = datetime.now(timezone.utc)
        assert cb.is_available() is False

    def test_open_becomes_half_open_after_cooldown(self):
        cb = CircuitBreaker(name="x", cooldown_seconds=30)
        cb.state = CircuitState.OPEN
        cb.opened_at = datetime.now(timezone.utc) - timedelta(seconds=31)
        assert cb.is_available() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_open_stays_open_before_cooldown(self):
        cb = CircuitBreaker(name="x", cooldown_seconds=60)
        cb.state = CircuitState.OPEN
        cb.opened_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        assert cb.is_available() is False
        assert cb.state == CircuitState.OPEN

    def test_half_open_is_available(self):
        cb = CircuitBreaker(name="x")
        cb.state = CircuitState.HALF_OPEN
        assert cb.is_available() is True

    def test_open_no_opened_at_not_available(self):
        cb = CircuitBreaker(name="x")
        cb.state = CircuitState.OPEN
        cb.opened_at = None
        assert cb.is_available() is False


# ──────────────────────────────────────────────
# CircuitBreaker.record_success
# ──────────────────────────────────────────────
class TestRecordSuccess:

    def test_resets_to_closed(self):
        cb = CircuitBreaker(name="x")
        cb.state = CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_resets_failure_count(self):
        cb = CircuitBreaker(name="x")
        cb.failure_count = 5
        cb.record_success()
        assert cb.failure_count == 0

    def test_clears_opened_at(self):
        cb = CircuitBreaker(name="x")
        cb.opened_at = datetime.now(timezone.utc)
        cb.record_success()
        assert cb.opened_at is None

    def test_clears_last_failure_message(self):
        cb = CircuitBreaker(name="x")
        cb.last_failure_message = "error"
        cb.record_success()
        assert cb.last_failure_message == ""

    def test_from_closed_stays_closed(self):
        cb = CircuitBreaker(name="x")
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


# ──────────────────────────────────────────────
# CircuitBreaker.record_failure
# ──────────────────────────────────────────────
class TestRecordFailure:

    def test_increments_failure_count(self):
        cb = CircuitBreaker(name="x")
        cb.record_failure("err1")
        assert cb.failure_count == 1

    def test_stores_error_message(self):
        cb = CircuitBreaker(name="x")
        cb.record_failure("connection timeout")
        assert cb.last_failure_message == "connection timeout"

    def test_rate_limit_immediately_opens(self):
        cb = CircuitBreaker(name="x")
        cb.record_failure("429", is_rate_limit=True)
        assert cb.state == CircuitState.OPEN

    def test_rate_limit_sets_opened_at(self):
        cb = CircuitBreaker(name="x")
        cb.record_failure("429", is_rate_limit=True)
        assert cb.opened_at is not None

    def test_threshold_opens_circuit(self):
        cb = CircuitBreaker(name="x", failure_threshold=2)
        cb.record_failure("err1")
        assert cb.state == CircuitState.CLOSED
        cb.record_failure("err2")
        assert cb.state == CircuitState.OPEN

    def test_below_threshold_stays_closed(self):
        cb = CircuitBreaker(name="x", failure_threshold=3)
        cb.record_failure("err1")
        assert cb.state == CircuitState.CLOSED

    def test_default_message_empty(self):
        cb = CircuitBreaker(name="x")
        cb.record_failure()
        assert cb.last_failure_message == ""


# ──────────────────────────────────────────────
# CircuitBreaker.get_status
# ──────────────────────────────────────────────
class TestGetStatus:

    def test_returns_dict(self):
        cb = CircuitBreaker(name="openai")
        status = cb.get_status()
        assert isinstance(status, dict)

    def test_has_name(self):
        cb = CircuitBreaker(name="gemini")
        assert cb.get_status()["name"] == "gemini"

    def test_state_is_string(self):
        cb = CircuitBreaker(name="x")
        assert cb.get_status()["state"] == "closed"

    def test_cooldown_remaining_zero_when_closed(self):
        cb = CircuitBreaker(name="x")
        assert cb.get_status()["cooldown_remaining"] == 0

    def test_cooldown_remaining_when_open(self):
        cb = CircuitBreaker(name="x", cooldown_seconds=60)
        cb.state = CircuitState.OPEN
        cb.opened_at = datetime.now(timezone.utc) - timedelta(seconds=20)
        remaining = cb.get_status()["cooldown_remaining"]
        assert 35 <= remaining <= 41  # ~40s remaining

    def test_cooldown_remaining_never_negative(self):
        cb = CircuitBreaker(name="x", cooldown_seconds=10)
        cb.state = CircuitState.OPEN
        cb.opened_at = datetime.now(timezone.utc) - timedelta(seconds=100)
        assert cb.get_status()["cooldown_remaining"] == 0

    def test_failure_count(self):
        cb = CircuitBreaker(name="x")
        cb.failure_count = 3
        assert cb.get_status()["failure_count"] == 3


# ──────────────────────────────────────────────
# RateLimitManager
# ──────────────────────────────────────────────
class TestRateLimitManager:

    def setup_method(self):
        # Reset singleton
        RateLimitManager._instance = None

    def test_singleton(self):
        m1 = RateLimitManager.get_instance()
        m2 = RateLimitManager.get_instance()
        assert m1 is m2

    def test_init_empty_circuits(self):
        mgr = RateLimitManager()
        assert mgr.circuits == {}

    def test_has_default_configs(self):
        mgr = RateLimitManager()
        assert "openai" in mgr._configs
        assert "gemini" in mgr._configs

    def test_get_circuit_creates(self):
        mgr = RateLimitManager()
        cb = mgr.get_circuit("openai")
        assert isinstance(cb, CircuitBreaker)
        assert cb.name == "openai"

    def test_get_circuit_caches(self):
        mgr = RateLimitManager()
        cb1 = mgr.get_circuit("openai")
        cb2 = mgr.get_circuit("openai")
        assert cb1 is cb2

    def test_get_circuit_uses_config(self):
        mgr = RateLimitManager()
        cb = mgr.get_circuit("openai")
        assert cb.cooldown_seconds == 60
        assert cb.failure_threshold == 2

    def test_get_circuit_unknown_uses_defaults(self):
        mgr = RateLimitManager()
        cb = mgr.get_circuit("some_api")
        assert cb.cooldown_seconds == 60
        assert cb.failure_threshold == 2

    def test_is_available(self):
        mgr = RateLimitManager()
        assert mgr.is_available("openai") is True

    def test_record_success(self):
        mgr = RateLimitManager()
        mgr.record_rate_limit("openai")
        mgr.record_success("openai")
        assert mgr.get_circuit("openai").state == CircuitState.CLOSED

    def test_record_rate_limit(self):
        mgr = RateLimitManager()
        mgr.record_rate_limit("openai")
        assert mgr.get_circuit("openai").state == CircuitState.OPEN

    def test_record_rate_limit_with_retry_after(self):
        mgr = RateLimitManager()
        mgr.record_rate_limit("openai", retry_after=120)
        assert mgr.get_circuit("openai").cooldown_seconds >= 120

    def test_record_rate_limit_retry_after_uses_max(self):
        mgr = RateLimitManager()
        # Default cooldown is 60, retry_after=30 should keep 60
        mgr.record_rate_limit("openai", retry_after=30)
        assert mgr.get_circuit("openai").cooldown_seconds == 60

    def test_record_failure(self):
        mgr = RateLimitManager()
        mgr.record_failure("openai", "timeout")
        cb = mgr.get_circuit("openai")
        assert cb.failure_count == 1
        assert cb.last_failure_message == "timeout"

    def test_get_all_status(self):
        mgr = RateLimitManager()
        mgr.get_circuit("openai")
        mgr.get_circuit("gemini")
        status = mgr.get_all_status()
        assert "openai" in status
        assert "gemini" in status
        assert isinstance(status["openai"], dict)

    def test_get_all_status_empty(self):
        mgr = RateLimitManager()
        assert mgr.get_all_status() == {}


# ──────────────────────────────────────────────
# Module-level convenience functions
# ──────────────────────────────────────────────
class TestConvenienceFunctions:

    def setup_method(self):
        # Reset global state
        RateLimitManager._instance = None
        import services.rate_limit_manager as mod
        mod._manager = None

    def test_get_rate_limit_manager_returns_instance(self):
        mgr = get_rate_limit_manager()
        assert isinstance(mgr, RateLimitManager)

    def test_get_rate_limit_manager_singleton(self):
        m1 = get_rate_limit_manager()
        m2 = get_rate_limit_manager()
        assert m1 is m2

    def test_is_api_available(self):
        assert is_api_available("openai") is True

    def test_record_api_success(self):
        record_api_rate_limit("openai")
        record_api_success("openai")
        assert is_api_available("openai") is True

    def test_record_api_rate_limit(self):
        record_api_rate_limit("openai")
        mgr = get_rate_limit_manager()
        assert mgr.get_circuit("openai").state == CircuitState.OPEN

    def test_record_api_rate_limit_with_retry_after(self):
        record_api_rate_limit("gemini", retry_after=200)
        mgr = get_rate_limit_manager()
        assert mgr.get_circuit("gemini").cooldown_seconds >= 200

    def test_record_api_failure(self):
        record_api_failure("openai", "network error")
        mgr = get_rate_limit_manager()
        assert mgr.get_circuit("openai").failure_count == 1


# ──────────────────────────────────────────────
# Integration — full lifecycle
# ──────────────────────────────────────────────
class TestIntegrationLifecycle:

    def test_full_cycle(self):
        """CLOSED → failures → OPEN → cooldown → HALF_OPEN → success → CLOSED."""
        cb = CircuitBreaker(name="api", cooldown_seconds=1, failure_threshold=2)

        # Starts closed
        assert cb.is_available() is True
        assert cb.state == CircuitState.CLOSED

        # One failure — still closed
        cb.record_failure("err1")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available() is True

        # Second failure — opens
        cb.record_failure("err2")
        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

        # Simulate cooldown elapsed
        cb.opened_at = datetime.now(timezone.utc) - timedelta(seconds=2)
        assert cb.is_available() is True
        assert cb.state == CircuitState.HALF_OPEN

        # Success — closes
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_rate_limit_immediate_open(self):
        """Rate limit opens circuit immediately regardless of threshold."""
        cb = CircuitBreaker(name="api", failure_threshold=10)
        cb.record_failure("429", is_rate_limit=True)
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 1

    def test_half_open_failure_reopens(self):
        """Failure during HALF_OPEN reopens circuit."""
        cb = CircuitBreaker(name="api", cooldown_seconds=1, failure_threshold=1)

        # Open it
        cb.record_failure("err", is_rate_limit=True)
        assert cb.state == CircuitState.OPEN

        # Transition to HALF_OPEN
        cb.opened_at = datetime.now(timezone.utc) - timedelta(seconds=2)
        cb.is_available()
        assert cb.state == CircuitState.HALF_OPEN

        # Failure in HALF_OPEN — back to OPEN
        cb.record_failure("still failing", is_rate_limit=True)
        assert cb.state == CircuitState.OPEN



        